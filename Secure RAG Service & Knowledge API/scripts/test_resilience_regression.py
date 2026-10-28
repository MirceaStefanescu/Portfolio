"""Exercise the real demo orchestration with synthetic Docker/Qdrant boundaries."""
import copy
from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('rag_resilience',Path(__file__).with_name('resilience-demo.py'))
demo=importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


class SyntheticCluster:
    """Controlled API observations; never invokes Docker or a network endpoint."""
    def __init__(self, mode='normal'):
        self.mode=mode;self.commands=[];self.points=[];self.restored=[];self.outage=False;self.restarted=False
        self.addresses={f'http://127.0.0.1:{6300+i}':f'peer{i}' for i in range(1,4)}
        self.addresses['http://127.0.0.1:6304']='restored'

    def run(self, command):
        self.commands.append(command)
        args=command[command.index('-f')+2:]
        if args[0]=='port':
            number=4 if args[1]=='restored' else int(args[1][-1])
            return f'127.0.0.1:{6300+number}'
        if args[:2]==['stop','peer1']: self.outage=True
        if args[:2]==['start','peer1']: self.outage=False;self.restarted=True
        if args[0]=='down' and self.mode=='cleanup_failure': raise RuntimeError('synthetic cleanup failure')
        return ''

    def request(self, base, path, data=None, method=None):
        if self.mode=='startup_failure': raise RuntimeError('synthetic startup failure')
        peer=self.addresses[base]
        if path=='/cluster': return {'status':'enabled','peers':{'1':{},'2':{},'3':{}}}
        if path=='/collections/demo/cluster':
            return {'local_shards':[{'state':'Dead' if self.mode=='inactive_shard' else 'Active'}]}
        if path=='/collections/demo': return {'status':'green'}
        if path=='/collections/demo/points?wait=true':
            if len(data['points'])==20:
                self.points=copy.deepcopy(data['points'])
                if self.mode=='corrupt_initial_data': self.points[0]['vector']=[999.0,0.0,0.0,0.0]
            elif self.mode!='ignored_outage_write': self.points.extend(copy.deepcopy(data['points']))
            return {'status':'completed'}
        if path=='/collections/demo/points/scroll':
            points=copy.deepcopy(self.restored if peer=='restored' else self.points)
            if self.mode=='unavailable_outage_read' and self.outage and len(points)==20: points=[]
            if self.mode=='stale_survivor' and peer=='peer3' and len(points)==21: points=points[:20]
            if self.mode=='stale_recovered_peer' and peer=='peer1' and self.restarted: points=points[:20]
            return {'points':points}
        if path=='/collections/demo/snapshots': return {'name':'synthetic.snapshot'}
        raise AssertionError(('Unexpected API operation',base,path,data,method))

    def urlopen(self, request, timeout):
        class Response(io.BytesIO):
            status=200
        if isinstance(request,str):
            if self.mode=='snapshot_failure': raise OSError('synthetic snapshot failure')
            return Response(b'synthetic snapshot')
        self.restored=copy.deepcopy(self.points)
        if self.mode=='corrupt_restore': self.restored[0]['payload']={'text':'changed'}
        response=Response(b'{}')
        if self.mode=='upload_rejected': response.status=202
        return response


def exercise(mode):
    with tempfile.TemporaryDirectory(prefix='rag-unit-') as directory:
        root=Path(directory)
        cluster=SyntheticCluster(mode)
        stdout=io.StringIO()
        elapsed=[0]
        def monotonic(): return elapsed[0]
        def sleep(seconds): elapsed[0]+=seconds
        outcome={'mode':mode,'error':None,'report':None,'stdout':''}
        with ExitStack() as stack:
            stack.enter_context(patch.object(demo.shutil,'which',return_value='synthetic-docker'))
            stack.enter_context(patch.object(demo.tempfile,'mkdtemp',return_value=directory))
            stack.enter_context(patch.object(demo,'run',side_effect=cluster.run))
            stack.enter_context(patch.object(demo,'request',side_effect=cluster.request))
            stack.enter_context(patch.object(demo.urllib.request,'urlopen',side_effect=cluster.urlopen))
            stack.enter_context(patch.object(demo.time,'monotonic',side_effect=monotonic))
            stack.enter_context(patch.object(demo.time,'sleep',side_effect=sleep))
            stack.enter_context(redirect_stdout(stdout))
            try: demo.main()
            except Exception as error: outcome['error']={'type':type(error).__name__,'message':str(error)}
        if (root/'result.json').exists(): outcome['report']=json.loads((root/'result.json').read_text())
        outcome['stdout']=stdout.getvalue()
        outcome['commands']=cluster.commands
        outcome['compose']=json.loads((root/'compose.json').read_text())
        outcome['elapsed_virtual']=elapsed[0]
        return outcome


class ResilienceWorkflowTests(unittest.TestCase):
    def test_success_verifies_twenty_one_points_and_scoped_cleanup(self):
        observed=exercise('normal')
        self.assertIsNone(observed['error'])
        self.assertEqual(observed['report']['status'],'PASS')
        self.assertEqual(observed['report']['restoredPointsAndVectors'],21)
        self.assertEqual(json.loads(observed['stdout']),observed['report'])
        self.assertEqual(observed['commands'][-1][-3:],['down','--volumes','--remove-orphans'])
        prefixes={tuple(command[:6]) for command in observed['commands']}
        self.assertEqual(len(prefixes),1)
        services=observed['compose']['services']
        self.assertEqual(set(services),{'peer1','peer2','peer3','restored'})
        self.assertTrue(all(service['ports']==['127.0.0.1::6333'] for service in services.values()))

    def test_ignored_write_during_outage_cannot_report_pass(self):
        observed=exercise('ignored_outage_write')
        self.assertIsNotNone(observed['error'])
        self.assertIsNone(observed['report'])
        self.assertEqual(observed['commands'][-1][-3:],['down','--volumes','--remove-orphans'])

    def test_corrupted_initial_vectors_cannot_report_pass(self):
        observed=exercise('corrupt_initial_data')
        self.assertIsNotNone(observed['error'])
        self.assertIsNone(observed['report'])

    def test_corrupted_restore_cannot_report_pass(self):
        observed=exercise('corrupt_restore')
        self.assertIsNotNone(observed['error'])
        self.assertIsNone(observed['report'])

    def test_startup_error_still_runs_only_own_cleanup(self):
        observed=exercise('startup_failure')
        self.assertEqual(observed['error']['message'],'synthetic startup failure')
        self.assertIsNone(observed['report'])
        self.assertEqual(observed['commands'][-1][-3:],['down','--volumes','--remove-orphans'])

    def test_other_failed_milestones_never_report_pass(self):
        for mode in ('inactive_shard','unavailable_outage_read','stale_survivor',
                     'stale_recovered_peer','snapshot_failure','upload_rejected'):
            with self.subTest(mode=mode):
                observed=exercise(mode)
                self.assertIsNotNone(observed['error'])
                self.assertIsNone(observed['report'])
                self.assertEqual(observed['stdout'],'')
                self.assertEqual(observed['commands'][-1][-3:],['down','--volumes','--remove-orphans'])

    def test_cleanup_failure_cannot_leave_success_report(self):
        observed=exercise('cleanup_failure')
        self.assertEqual(observed['error']['message'],'synthetic cleanup failure')
        self.assertIsNone(observed['report'])
        self.assertEqual(observed['stdout'],'')

    def test_repeat_runs_have_distinct_projects(self):
        first=exercise('normal');second=exercise('normal')
        self.assertIsNone(first['error']);self.assertIsNone(second['error'])
        self.assertNotEqual(first['commands'][0][3],second['commands'][0][3])

    def test_missing_docker_fails_before_creating_resources(self):
        with patch.object(demo.shutil,'which',return_value=None),patch.object(demo.tempfile,'mkdtemp') as create:
            with self.assertRaisesRegex(RuntimeError,'Docker Compose v2 is required'):
                demo.main()
            create.assert_not_called()


class ResilienceHelpersTests(unittest.TestCase):
    def test_json_request_preserves_payload_method_result_and_timeout(self):
        body={'points':[{'id':1,'payload':{'text':'șir sintetic'}}]}
        with patch.object(demo.urllib.request,'urlopen',return_value=io.BytesIO(b'{"result":{"status":"ok"}}')) as call:
            self.assertEqual(demo.request('http://127.0.0.1:1234','/fixture',body,'PUT'),{'status':'ok'})
        request=call.call_args.args[0]
        self.assertEqual(request.full_url,'http://127.0.0.1:1234/fixture')
        self.assertEqual(request.get_method(),'PUT')
        self.assertEqual(json.loads(request.data),body)
        self.assertEqual(request.get_header('Content-type'),'application/json')
        self.assertEqual(call.call_args.kwargs,{'timeout':15})

    def test_request_without_data_uses_get(self):
        with patch.object(demo.urllib.request,'urlopen',return_value=io.BytesIO(b'{"result":[]}')) as call:
            self.assertEqual(demo.request('http://127.0.0.1:1234','/fixture'),[])
        self.assertIsNone(call.call_args.args[0].data)
        self.assertEqual(call.call_args.args[0].get_method(),'GET')

    def test_invalid_or_missing_json_result_fails(self):
        for payload,error in ((b'not-json',ValueError),(b'{}',KeyError)):
            with self.subTest(payload=payload),patch.object(demo.urllib.request,'urlopen',return_value=io.BytesIO(payload)):
                with self.assertRaises(error): demo.request('http://127.0.0.1:1234','/fixture')

    def test_command_timeout_is_propagated(self):
        with patch.object(demo.subprocess,'run',side_effect=subprocess.TimeoutExpired(['fixture'],180)):
            with self.assertRaises(subprocess.TimeoutExpired): demo.run(['fixture'])

    def test_command_success_returns_trimmed_stdout_and_preserves_timeout(self):
        response=subprocess.CompletedProcess(['fixture'],0,stdout='  result\n',stderr='')
        with patch.object(demo.subprocess,'run',return_value=response) as call:
            self.assertEqual(demo.run(['fixture','argument with space']),'result')
            call.assert_called_once_with(['fixture','argument with space'],capture_output=True,text=True,timeout=180)

    def test_command_failure_is_not_success_and_diagnostic_is_bounded(self):
        response=subprocess.CompletedProcess(['fixture'],7,stdout='',stderr='x'*2500)
        with patch.object(demo.subprocess,'run',return_value=response),self.assertRaises(RuntimeError) as result:
            demo.run(['fixture'])
        self.assertEqual(str(result.exception),'x'*2000)

    def test_wait_retries_transient_errors_and_returns_on_recovery(self):
        elapsed=[0]
        def sleep(seconds): elapsed[0]+=seconds
        with patch.object(demo.time,'monotonic',side_effect=lambda:elapsed[0]),patch.object(demo.time,'sleep',side_effect=sleep):
            from unittest.mock import Mock
            check=Mock(side_effect=[OSError('temporary'),ValueError('invalid'),KeyError('missing'),False,True])
            demo.wait(check,'fixture')
            self.assertEqual(check.call_count,5)
            self.assertEqual(elapsed[0],4)

    def test_wait_has_bounded_deadline(self):
        elapsed=[0]
        def sleep(seconds): elapsed[0]+=seconds
        with patch.object(demo.time,'monotonic',side_effect=lambda:elapsed[0]),patch.object(demo.time,'sleep',side_effect=sleep):
            with self.assertRaisesRegex(RuntimeError,'Timed out: fixture'):
                demo.wait(lambda:False,'fixture')
            self.assertEqual(elapsed[0],90)

    def test_wait_does_not_swallow_programming_errors(self):
        def check(): raise TypeError('programming failure')
        with self.assertRaisesRegex(TypeError,'programming failure'):
            demo.wait(check,'fixture')


if __name__=='__main__':
    unittest.main()
