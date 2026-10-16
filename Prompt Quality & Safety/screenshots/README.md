# Verified demonstrations — Prompt Quality & Safety

Captured on 16 October 2026 from the local demonstration. No external paid service or real transaction was used.

UI images are direct browser captures. API and CLI images display the actual responses or verification output, with local paths abbreviated and credentials omitted. Reused execution evidence is explicitly dated in its image and was checked against unchanged source hashes. Expected rejection responses demonstrate validation and access control.

The evidence covers the existing demonstrated behavior; it does not certify arbitrary production workloads, provider accounts or external model quality. Original diagrams and earlier captures remain preserved.

| Function / observed behavior | Screenshot | Verification |
| --- | --- | --- |
| Executable checks: test_tools_preserve_types_and_validate_arguments, test_provider_tools_are_sent_and_returned_without_execution[openai], test_provider_tools_are_sent_and_returned_without_execution[anthropic], test_provider_tools_are_sent_and_returned_without_execution[local], test_semantic_grade_uses_provider_embeddings_and_rejects_invalid_data, test_injection_detection, test_harm_detection | [action-prompt-tests-1.png](action-prompt-tests-1.png) | All listed tests passed against the current sources; HTTP and model checks use controlled local fixtures. |
| Executable checks: test_refusal_message, test_exact_match, test_exact_match_reference_contract[None--None], test_exact_match_reference_contract[None-value-None], test_exact_match_reference_contract[--1.0], test_exact_match_reference_contract[-, test_exact_match_reference_contract[-unexpected-0.0] | [action-prompt-tests-2.png](action-prompt-tests-2.png) | All listed tests passed against the current sources; HTTP and model checks use controlled local fixtures. |
| Executable checks: test_exact_match_reference_contract[, test_exact_match_reference_contract[value-other-0.0], test_exact_match_reference_contract[, test_keyword_recall, test_refusal_rate, test_injection_defense, test_provider_contracts_without_external_requests[openai] | [action-prompt-tests-3.png](action-prompt-tests-3.png) | All listed tests passed against the current sources; HTTP and model checks use controlled local fixtures. |
| Executable checks: test_provider_contracts_without_external_requests[anthropic], test_provider_contracts_without_external_requests[local], test_missing_credentials_and_invalid_responses, test_cache_separates_reference_metadata_and_preserves_empty_outputs, test_run_suite | [action-prompt-tests-4.png](action-prompt-tests-4.png) | All listed tests passed against the current sources; HTTP and model checks use controlled local fixtures. |
| Evaluation run and metrics | [action-prompt-summary.png](action-prompt-summary.png) | Current CLI run completed using its explicit mock provider. |
| Persisted cases artifacts | [action-prompt-cases.png](action-prompt-cases.png) | Actual JSONL output produced by this local evaluation run. |
