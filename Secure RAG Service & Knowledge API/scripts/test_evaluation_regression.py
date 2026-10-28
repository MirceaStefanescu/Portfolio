"""Synthetic evaluation regression cases; no live API or model requests."""
import copy
from contextlib import redirect_stdout
import importlib.util
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import threading
import tempfile
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('rag_evaluate', Path(__file__).with_name('evaluate.py'))
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class MetricsRegressionTests(unittest.TestCase):
    def test_partial_recall_precision_rank_and_unique_references(self):
        case = {'id': 'case', 'expectedDocuments': ['a', 'b', 'b']}
        answer = {'answer': 'Answer', 'context': [
            {'documentId': 'x', 'score': .9}, {'documentId': 'x', 'score': .8},
            {'documentId': 'b', 'score': .2}]}
        before = copy.deepcopy([case, answer])
        actual = evaluation.score_case(case, answer)
        self.assertEqual(actual['retrievedDocuments'], ['x', 'b'])
        for name in ('recall', 'precision', 'reciprocalRank'):
            self.assertEqual(actual[name], .5)
        self.assertEqual([case, answer], before)

    def test_empty_expected_documents_fail(self):
        with self.assertRaisesRegex(ValueError, 'explicit relevant documents'):
            evaluation.score_case({'id':'empty', 'expectedDocuments':[]}, {'answer':'x', 'context':[]})

    def test_all_nonfinite_scores_fail(self):
        for value in [float('nan'), float('inf'), -float('inf'), 'NaN', 'Infinity']:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'Nonfinite'):
                evaluation.score_case({'id':'finite', 'expectedDocuments':['a']},
                    {'answer':'x','context':[{'documentId':'a','score':value}]})

    def test_whitespace_answer_is_not_evidence(self):
        with self.assertRaisesRegex(ValueError,'empty answer'):
            evaluation.score_case({'id':'blank','expectedDocuments':['a']},{'answer':' \t\n','context':[]})

    def test_optional_latency_is_reported_without_changing_metrics(self):
        for supplied in [None,0,12.5]:
            with self.subTest(latency=supplied):
                result=evaluation.score_case({'id':'latency','expectedDocuments':['a']},
                    {'answer':'x','context':[],'retrievalTimeMs':supplied})
                self.assertEqual(result['retrievalTimeMs'],supplied)
                self.assertEqual(result['recall'],0)

    def test_target_match_is_exact_after_trimming_answer(self):
        for answer, expected in [(' OVERRIDE\n', True), ('override', False), ('Quoted OVERRIDE', False)]:
            with self.subTest(answer=answer):
                actual=evaluation.score_case({'id':'target', 'expectedDocuments':['a'],'adversarialTarget':'OVERRIDE'},
                    {'answer':answer,'context':[]})
                self.assertIs(actual['adversarialExactTarget'], expected)


class RequestRegressionTests(unittest.TestCase):
    def test_invalid_destinations_are_rejected_before_transport(self):
        bases=['https://127.0.0.1', 'http://example.invalid', 'ftp://localhost',
               'http://user@localhost', 'http://@localhost', 'http://:@127.0.0.1',
               'http://localhost?redirect=x', 'http://localhost#fragment',
               'http://127.0.0.1:0', 'http://127.0.0.1:65536']
        for base in bases:
            with self.subTest(base=base), patch.object(evaluation.urllib.request, 'build_opener') as transport:
                transport.return_value.open.return_value.__enter__.return_value=io.BytesIO(b'{"answer":"fixture"}')
                with self.assertRaises(ValueError):
                    evaluation.request(base, '/api/query', {}, 'synthetic')
                transport.assert_not_called()

    def test_loopback_hosts_and_path_prefix_preserve_route_and_body(self):
        for base in ['http://127.0.0.1:8090', 'http://localhost:8090/prefix/', 'http://[::1]:8090']:
            with self.subTest(base=base), patch.object(evaluation.urllib.request, 'build_opener') as factory:
                factory.return_value.open.return_value.__enter__.return_value=io.BytesIO(b'{"answer":"fixture"}')
                actual=evaluation.request(base, '/api/query', {'question':'Întrebare'}, 'synthetic')
                self.assertEqual(actual, {'answer':'fixture'})
                req=factory.return_value.open.call_args.args[0]
                self.assertEqual(req.full_url, base.rstrip('/') + '/api/query')
                self.assertEqual(json.loads(req.data), {'question':'Întrebare'})
                self.assertEqual(factory.return_value.open.call_args.kwargs, {'timeout':35})
                self.assertIsInstance(factory.call_args.args[0], evaluation.NoRedirect)

    def test_redirect_handler_refuses_all_supported_redirect_statuses(self):
        for status in [301,302,303,307,308]:
            with self.subTest(status=status), self.assertRaisesRegex(RuntimeError, 'refuses redirects'):
                evaluation.NoRedirect().redirect_request(None,None,status,'redirect',{},'http://example.invalid')

    def test_http_failure_is_not_converted_to_an_answer(self):
        with patch.object(evaluation.urllib.request,'build_opener') as factory:
            failure=evaluation.urllib.error.HTTPError('http://localhost/api/query',503,'unavailable',{},None)
            factory.return_value.open.side_effect=failure
            with self.assertRaises(evaluation.urllib.error.HTTPError) as observed:
                evaluation.request('http://localhost','/api/query',{},'synthetic')
            self.assertIs(observed.exception,failure)


class LoopbackTransportTests(unittest.TestCase):
    def setUp(self):
        self.received=[]
        received=self.received
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append((self.path,body,self.headers.get('Authorization')))
                if self.path=='/api/redirect':
                    self.send_response(307)
                    self.send_header('Location','/must-not-be-followed')
                    self.end_headers()
                    return
                response=json.dumps({'answer':'fixture','question':body['question']}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(response)))
                self.end_headers()
                self.wfile.write(response)
            def log_message(self,*args):
                pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.no_proxy=patch.dict(os.environ,{'no_proxy':'127.0.0.1','NO_PROXY':'127.0.0.1'})
        self.no_proxy.start()

    def tearDown(self):
        self.no_proxy.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.assertFalse(self.thread.is_alive())

    def test_real_loopback_roundtrip_uses_json_and_bearer_header(self):
        result=evaluation.request(self.url,'/api/query',{'question':'Întrebare'},'synthetic')
        self.assertEqual(result,{'answer':'fixture','question':'Întrebare'})
        self.assertEqual(self.received,[('/api/query',{'question':'Întrebare'},'Bearer synthetic')])

    def test_real_redirect_is_not_followed_or_replayed(self):
        with self.assertRaisesRegex(RuntimeError,'refuses redirects'):
            evaluation.request(self.url,'/api/redirect',{'question':'synthetic'},'synthetic')
        self.assertEqual(len(self.received),1)
        self.assertEqual(self.received[0][0],'/api/redirect')


class EvaluationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.dataset={'version':1,'scope':'synthetic','documents':[{'documentId':'a','content':'synthetic'}],
                      'cases':[{'id':'one','question':'q','topK':1,'expectedDocuments':['a']},
                               {'id':'two','question':'q2','topK':1,'expectedDocuments':['a'],'adversarialTarget':'OVERRIDE'}]}

    def response(self, answer='Answer', documents=('a',)):
        return {'answer':answer,'context':[{'documentId':d,'score':.2} for d in documents]}

    def test_pass_means_every_case_succeeds_and_reports_aggregate_metrics(self):
        before=copy.deepcopy(self.dataset)
        with patch.object(evaluation,'request', side_effect=[{},self.response(),self.response()]) as request:
            result=evaluation.evaluate('http://localhost','synthetic-admin','synthetic-user',self.dataset)
        self.assertEqual(result['status'],'PASS')
        self.assertEqual(result['metrics'],{'recall':1.0,'precision':1.0,'reciprocalRank':1.0})
        self.assertEqual(result['adversarialCases'],1)
        self.assertEqual(result['exactTargetFailures'],0)
        self.assertEqual([call.args[1] for call in request.call_args_list],['/api/ingest','/api/query','/api/query'])
        self.assertEqual([call.args[3] for call in request.call_args_list],['synthetic-admin','synthetic-user','synthetic-user'])
        self.assertNotIn('synthetic-admin',json.dumps(result))
        self.assertNotIn('synthetic-user',json.dumps(result))
        self.assertEqual(self.dataset,before)

    def test_one_missed_case_fails_the_whole_evaluation(self):
        with patch.object(evaluation,'request',side_effect=[{},self.response(),self.response(documents=())]):
            result=evaluation.evaluate('http://localhost','synthetic-admin','synthetic-user',self.dataset)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['metrics']['recall'],.5)

    def test_exact_adversarial_target_fails_even_with_full_retrieval(self):
        with patch.object(evaluation,'request',side_effect=[{},self.response(),self.response('OVERRIDE')]):
            result=evaluation.evaluate('http://localhost','synthetic-admin','synthetic-user',self.dataset)
        self.assertEqual(result['status'],'FAIL')
        self.assertEqual(result['exactTargetFailures'],1)

    def test_missing_tokens_cause_no_requests(self):
        for admin,user in [(None,'synthetic'),('synthetic',None),('','')]:
            with self.subTest(admin=admin,user=user),patch.object(evaluation,'request') as request:
                with self.assertRaises(ValueError):
                    evaluation.evaluate('http://localhost',admin,user,self.dataset)
                request.assert_not_called()

    def test_failed_ingestion_stops_before_queries(self):
        with patch.object(evaluation,'request',side_effect=RuntimeError('unavailable')) as request:
            with self.assertRaisesRegex(RuntimeError,'unavailable'):
                evaluation.evaluate('http://localhost','synthetic-admin','synthetic-user',self.dataset)
            self.assertEqual(request.call_count,1)
            self.assertEqual(request.call_args.args[1],'/api/ingest')

    def test_cli_writes_report_and_returns_meaningful_exit_status(self):
        for status,code in [('PASS',0),('FAIL',1)]:
            with self.subTest(status=status),tempfile.TemporaryDirectory() as directory:
                dataset=Path(directory)/'data.json'
                report=Path(directory)/'report.json'
                dataset.write_text(json.dumps(self.dataset),encoding='utf-8')
                stdout=io.StringIO()
                expected={'status':status,'scope':'synthetic'}
                with patch.object(sys,'argv',['evaluate.py','--url','http://localhost','--dataset',str(dataset),'--output',str(report)]), \
                     patch.dict(os.environ,{'RAG_EVAL_ADMIN_TOKEN':'synthetic-admin','RAG_EVAL_USER_TOKEN':'synthetic-user'}), \
                     patch.object(evaluation,'evaluate',return_value=expected) as evaluate,redirect_stdout(stdout):
                    self.assertEqual(evaluation.main(),code)
                evaluate.assert_called_once_with('http://localhost','synthetic-admin','synthetic-user',self.dataset)
                self.assertEqual(json.loads(report.read_text(encoding='utf-8')),expected)
                self.assertEqual(json.loads(stdout.getvalue()),expected)

    def test_empty_case_list_fails_instead_of_vacuous_pass(self):
        self.dataset['cases']=[]
        with patch.object(evaluation,'request',return_value={}):
            with self.assertRaisesRegex(ValueError,'no cases'):
                evaluation.evaluate('http://localhost','synthetic-admin','synthetic-user',self.dataset)


if __name__=='__main__':
    unittest.main()
