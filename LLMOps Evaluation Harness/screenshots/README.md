# Verified demonstrations — LLMOps Evaluation Harness

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| Executable checks: test_persistent_cache_preserves_empty_responses_and_separates_namespaces, test_failed_generation_is_not_cached, test_regex_and_structured_tools, test_http_rejects_null_responses_and_keeps_structured_tools, test_semantic_grader_checks_indexed_response, test_new_grader_runs_through_artifact_pipeline, test_exact_match | [action-llmops-tests-1.png](action-llmops-tests-1.png) | All listed tests passed against the current sources; HTTP and model checks use controlled local fixtures. |
| Executable checks: test_token_f1, test_hallucination_rate, test_run_evaluation, test_logger_closes_opened_files_if_initialization_fails, test_logger_closes_all_files_after_error, test_existing_run_is_preserved, test_run_name_cannot_escape_output[..] | [action-llmops-tests-2.png](action-llmops-tests-2.png) | All listed tests passed against the current sources; HTTP and model checks use controlled local fixtures. |
| Executable checks: test_run_name_cannot_escape_output[.], test_run_name_cannot_escape_output[../outside], test_run_name_cannot_escape_output[a/b], test_run_name_cannot_escape_output[a\\\\b], test_run_name_cannot_escape_output[C:outside] | [action-llmops-tests-3.png](action-llmops-tests-3.png) | All listed tests passed against the current sources; HTTP and model checks use controlled local fixtures. |
| Evaluation run and metrics | [action-llmops-summary.png](action-llmops-summary.png) | Current CLI run completed using its explicit mock provider. |
| Persisted requests artifacts | [action-llmops-requests.png](action-llmops-requests.png) | Actual JSONL output produced by this local evaluation run. |
| Persisted responses artifacts | [action-llmops-responses.png](action-llmops-responses.png) | Actual JSONL output produced by this local evaluation run. |
| Persisted scores artifacts | [action-llmops-scores.png](action-llmops-scores.png) | Actual JSONL output produced by this local evaluation run. |
