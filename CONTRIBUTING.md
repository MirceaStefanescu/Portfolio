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
