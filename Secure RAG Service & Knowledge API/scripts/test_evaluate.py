import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("rag_evaluate", Path(__file__).with_name("evaluate.py"))
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


class EvaluationTests(unittest.TestCase):
    def test_retrieval_metrics_use_unique_document_ranks(self):
        result = evaluation.score_case({"id": "x", "expectedDocuments": ["a"], "adversarialTarget": "OVERRIDE"},
            {"answer": "Answer (mock LLM): quoted OVERRIDE", "context": [
                {"documentId": "b", "score": .2}, {"documentId": "b", "score": .1}, {"documentId": "a", "score": .1}]})
        self.assertEqual(result["recall"], 1)
        self.assertEqual(result["precision"], .5)
        self.assertEqual(result["reciprocalRank"], .5)
        self.assertFalse(result["adversarialExactTarget"])

    def test_exact_instruction_following_is_recorded(self):
        result = evaluation.score_case({"id": "x", "expectedDocuments": ["a"], "adversarialTarget": "OVERRIDE"},
            {"answer": "OVERRIDE", "context": [{"documentId": "a", "score": 1}]})
        self.assertTrue(result["adversarialExactTarget"])

    def test_missing_references_are_not_success(self):
        result = evaluation.score_case({"id": "x", "expectedDocuments": ["a"]},
            {"answer": "Not found", "context": []})
        self.assertEqual(result["recall"], 0)
        self.assertEqual(result["reciprocalRank"], 0)

    def test_invalid_evidence_fails(self):
        for result in ({"answer": "", "context": []},
                       {"answer": "x", "context": [{"documentId": "a", "score": float("nan")}]}):
            with self.assertRaises(ValueError):
                evaluation.score_case({"id": "x", "expectedDocuments": ["a"]}, result)

    def test_remote_endpoint_rejected_before_token_delivery(self):
        with self.assertRaises(ValueError):
            evaluation.request("https://example.com", "/api/query", {}, "synthetic-token")


if __name__ == "__main__":
    unittest.main()
