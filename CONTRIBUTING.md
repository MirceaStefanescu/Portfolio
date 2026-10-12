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

Report vulnerabilities through SECURITY.md. Never include credentials, local
environments, private paths, or unrelated files in a pull request.
Licensing is defined by each project's existing LICENSE; contributing does not
replace those terms.
