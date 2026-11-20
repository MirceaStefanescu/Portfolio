# Public portfolio availability

This workflow provides bounded recurring observations of the public portfolio.
Its actual deployment and execution evidence is available in the repository's
Actions history; configuration alone does not establish that a scheduled run occurred.

## Scope

- This is an additional public HTTP observation, independent of ChatGPT Tasks.
- It uses only the existing public `MirceaStefanescu/Portfolio` repository and standard GitHub-hosted Ubuntu runner.
- Seven fixed URLs: landing page and six currently published language offers.
- GET requests only, to fixed public URLs. Redirects are never followed, including same-site redirects.
- It checks HTTP status, expected language, canonical URL, title, contact anchor, and the existing WordPress enquiry link.
- It does not submit the form, prove enquiry delivery, post messages, create issues, invoke AI APIs, read private Sheets, or observe agent liveness.
- GitHub Actions and GitHub Pages share a provider. This is a separate failure domain from ChatGPT Tasks, not fully independent from the site host.

## Run bounds and evidence

- Schedule: `17 * * * *` UTC, plus manual workflow dispatch and `push` to `main` only when the monitor's workflow, script, test, or documentation changes. It is deliberately separate from the large existing Portfolio CI workflow.
- Default-branch, exact-repository and public-visibility guards, `contents: read`, pinned existing checkout version, no persisted credentials. A private repository skips this job.
- Standard `ubuntu-24.04`; no paid/larger runner, dependency installs, caches, or uploaded artifacts.
- Single concurrency group; no simultaneous monitor runs. The job has a three-minute timeout and the script a 150-second wall-clock alarm.
- At most two GET attempts per page; blocking socket operations have an eight-second timeout. This is not a wall-clock limit for one attempt: the 150-second global alarm also bounds a slowly trickling response. Two-second backoff applies only to transient transport failures or observed 5xx responses.
- No retry for 401/403/407/429, challenge pages, redirects, or a hard content failure. Access/rate-limit and redirect responses are classified from their headers without reading their bodies. No quota polling.
- Body reads are limited to 256 KiB plus one byte to detect truncation. An incomplete length-framed response cannot pass using only its valid-looking prefix; malformed HTTP/redirect data remains inconclusive without aborting the remaining pages.
- Results are retained as normal workflow logs and a job summary. No public heartbeat from private work is exported.

## Result contract

| State | Evidence | Exit code |
|---|---|---:|
| `HEALTHY` | All seven pages return HTTP 200 and match the expected page contract. | 0 |
| `OBSERVED_FAILURE` | This probe sees 404/410/5xx without a detected challenge, or a successful page violates its content contract. | 1 |
| `INCONCLUSIVE` | This client is blocked, rate-limited or challenged; transport fails; a redirect is returned; body limit/deadline prevents a complete observation. | 2 |

Any observed failure takes precedence in the overall state, while each individual page retains its own result. An inconclusive run also makes the GitHub job fail, with a warning and an explicit state in its summary. A red job therefore does **not** automatically mean site downtime; Health must read the structured result before classifying it.

Neither `HEALTHY` nor an HTTP failure is evidence of reachability in all countries. No claim of continuous AI execution or successful conversion can be inferred from this monitor.

## Integration and acceptance

1. Review and add the workflow, script, test, and this documentation to Portfolio through the existing GitHub workflow. Do not add an hourly schedule to `portfolio-ci.yml`.
2. Run `python3 tests/test-public-site-monitor.py`; it uses in-memory responses only, starts no local server, and makes no network requests.
3. Run the existing required workflow/YAML validation gate. Validate the new workflow on the actual repository revision.
4. After merge, inspect the first real `push` run and its seven page results. The monitor's offline tests run first as a separate step. Record the actual run ID, event, conclusion, commit SHA, and report state. Do not mark a push or manually dispatched run as a natural scheduled run.
5. Observe the first natural `schedule` run separately. A configured cron or successful manual run is not evidence that the scheduled trigger fired.
6. Have the existing Health owner inspect monitor status/last natural completion through its already authorized GitHub read access. Apply the current `PUBLIC_MONITOR_FRESHNESS_V2` policy: a valid scheduled report with `checked_at` more than 90 minutes old is `MONITOR_STALE`, not `SITE_DOWN`; open or update the existing incident on the first stale observation. Keep any fresh, bounded GET fallback separate: it can establish page availability from that client, but does not close the scheduling incident. Allow provider scheduling delay and do not create repeated recovery runs. The separate 180-minute threshold for other workers is unchanged.
7. Read a failed or inconclusive result before any action. One failed observed page can create one deduplicated owner handoff. Blocked client results should remain inconclusive, with a later scheduled retry. No same-run polling or automatic redeploy.
8. Recheck eligibility if the repository becomes private or runner type changes. Do not auto-change billing or add secrets to preserve monitoring.

## Official GitHub constraints, verified 19 November 2026

- Standard GitHub-hosted runners in public repositories are free: https://docs.github.com/en/actions/concepts/billing-and-usage
- Larger runners are chargeable even for public repositories; artifacts/cache have separate storage treatment: https://docs.github.com/en/billing/concepts/product-billing/github-actions
- Scheduled runs can be delayed or dropped during high load, run from the default branch, and can be disabled after 60 days without repository activity: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows
- If a scheduled workflow is disabled, diagnose that concrete state. Do not fabricate activity or commits solely to keep cron alive.

These constraints prevent a zero-cost guarantee of uninterrupted execution. The defensible claim is bounded recurring monitoring with visible failures and recovery opportunities.
