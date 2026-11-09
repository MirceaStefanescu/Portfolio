# Contributing

Each top-level project has its own README and development requirements.
Read that project's CONTRIBUTING.md and SECURITY.md before changing it.

1. Create a feature branch and keep the change focused.
2. Run the affected project's documented tests, lint, and build.
3. Update its documentation when behavior changes.
4. Open a pull request and wait for Portfolio status to pass.

The root Portfolio CI calls the shared GitOps, prompt-quality, and LLM evaluation
workflows and runs the Node, Java, Python, and shell suites. Workflow definitions
inside subprojects are standalone project examples, not active monorepo workflows.

Every PR first checks the public presentation, active workflow definitions and
new dependencies (known high/critical vulnerabilities block merging). Only PRs
limited to the five root presentation/policy Markdown files and the allowlisted
GitHub Pages files/assets may omit application suites. Code, CI configuration,
unknown paths, inconclusive change detection, pushes to main and manual runs
always use the full suite. Portfolio status remains mandatory in both cases.

Presentation checks reject missing local files/anchors and repeatable external
404/410 responses. Authentication, throttling and temporary network errors are
reported separately in the workflow summary; they are not proof of broken links.
Tools use standard public GitHub Actions runners, with no paid APIs or AI calls.

Report vulnerabilities through SECURITY.md. Never include credentials, local
environments, private paths, or unrelated files in a pull request.
Licensing is defined by each project's existing LICENSE; contributing does not
replace those terms.

## Running the lightweight checks

From the repository root, with Python and Git available:

```bash
bash tests/test-ci-status.sh
python tests/test-ci-scope.py
python tests/test-presentation.py
python scripts/check-presentation.py
```

Use `python scripts/check-presentation.py --external` to also check the approved
public HTTPS hosts. Network warnings appear separately from broken local links.
Dependency Review uses the repository's short-lived GitHub Actions token in CI;
no local token or AI API key is needed for the commands above.

The fast PR path covers `README.md`, `PROFILE_README.md`, `SERVICES.md`,
`CONTRIBUTING.md`, `SECURITY.md`, the existing Pages entry files and direct image
files under `docs/assets/`. Subproject READMEs and newly introduced file types
take the full path until explicitly reviewed. The scope decision and any
external-link warnings are visible in the workflow's job summary.

For an unexpected status failure, inspect the quality job and the final
Portfolio status job together. Fix the underlying result or classification;
do not remove the required check or accept arbitrary skipped jobs.
