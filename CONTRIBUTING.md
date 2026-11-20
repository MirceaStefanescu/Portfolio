# Contributing

Each top-level project has its own README and development requirements.
Read any project-specific contribution and security guidance before changing it.

1. Create a feature branch and keep the change focused.
2. Run the affected project's documented tests, lint and build.
3. Update its documentation when behavior changes.
4. Open a pull request and wait for the required Portfolio status check to pass.

Include a clear description of the change, its verification and any limits.
For visible behavior changes, update the relevant project walkthrough or captures.

<a id="private-maintenance-tools"></a>

## CI and shared tooling

Portfolio CI checks presentation, workflow configuration, dependencies and the
affected application suites. Application and automation changes require the full
suite. The final Portfolio status remains required for every change.

Project source and project documentation are public. Shared repository
maintenance tools are maintained in a private companion repository and prepared
automatically for authorized CI runs. Some shared verification and
Jenkins/infrastructure commands require maintainer access to those tools.

Fork pull requests do not receive private automation access. An owner must review
their changes and place approved changes on an owner-controlled branch before the
required checks can pass. Contributors can still inspect the source, discuss an
issue and submit a focused proposed change.

Workflow definitions inside subprojects are examples for standalone projects;
the root workflow definitions control this monorepo.

## Public presentation changes

Keep service scope, prices, stated demonstration limits and contact information
consistent across the homepage, service catalog and localized offers. A
translation does not imply spoken-language proficiency or a guaranteed outcome.

Preserve accessible navigation and the existing reviewed campaign-label behavior.
Do not put personal information, credentials or free search text in campaign URLs.
Update the relevant presentation or navigation tests when changing those features.

## Security and licensing

Report vulnerabilities through [SECURITY.md](SECURITY.md). Never include
credentials, private environments, workstation paths or unrelated files in a pull
request.

Each project's existing LICENSE defines its licensing terms. Contributing does
not replace those terms.
