# Synthetic check failure

Confirm probe_success and probe_http_status_code for the exact target. Inspect the demo API health response and Blackbox exporter logs. An HTTP 200 with the wrong body must still fail the check. Restore the affected service, then verify probe_success=1 and both local paging channels resolve the same incident. Never silence the alert to simulate recovery.

The default target is the local demo API. Paging ends at the local inbox; no Slack workspace or PagerDuty account is contacted.
