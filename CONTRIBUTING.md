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

Use a POSIX environment with Bash, Python 3.9 or later available as `python`,
and Git 2.28 or later. The regression fixtures use executable file modes and
symbolic links. GitHub Actions already supplies this environment; local execution
is optional. Run the commands from the repository root:

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

## Campaign labels in portfolio links

`docs/campaign-attribution.js` preserves reviewed UTM labels from the homepage
through the three diagnostic pages, the six localized service offers and the
existing WordPress enquiry link.
It uses no cookies, browser storage, analytics service or network requests.
Plain visits and invalid/ambiguous campaigns keep the links authored in HTML.

Campaign links require `utm_source` from the source vocabulary in that script.
Optional `utm_medium`, `utm_content` and `utm_term` also use explicit vocabulary.
`utm_campaign` supports `it_services`, `api_diagnostic`, `cicd_diagnostic` or
`ai_diagnostic` followed by `_YYYYMM` (years 2000–2099, months 01–12).
Content can also be `post-01` through `post-31`. Labels are lowercase, at most
64 characters, and must never contain personal information or free search text.
Any duplicate or unsupported UTM value rejects the whole incoming bundle.
Unknown parameters are not copied. Add reviewed campaign labels to the vocabulary
and its tests before using them; do not loosen validation to accept arbitrary data.

Example: `?utm_source=linkedin&utm_medium=social&utm_campaign=it_services_202611&utm_content=api`.
The existing Facebook/Threads campaigns also accept `utm_medium=organic_social`
with `utm_content=order_retry_checklist` or `utm_content=order_retry`.
Run `node --test tests/test-campaign-attribution.cjs` with Node.js 20 or later.
The existing launcher CI job runs these navigation and input-validation tests.
This forwards link labels only: verify WordPress form capture and the common
opportunity register separately before claiming conversion measurement.

## Localized service offers

The six `docs/services-*.html` pages present the same API diagnostic in English,
Romanian, Spanish, Portuguese, French and Simplified Chinese. Each is complete
static HTML with a visible language switcher, reciprocal `hreflang` links and a
self-canonical URL. JavaScript is optional for reading and contacting; it only
preserves the existing reviewed campaign labels.

Keep the commercial scope, gross prices, receipt-of-inputs condition, Romania
remote/B2B context, demonstration limits and marketplace rules consistent across
all six pages. The enquiry form and technical evidence remain in English and are
labelled accordingly. A translated page does not imply spoken-language proficiency,
country eligibility, local-platform publication or a guaranteed repair.

The pages are linked from the homepage and included in `docs/sitemap.xml`.
When adding a language, review its final copy independently, update the explicit
internal-path allowlist and navigation tests, and run the full existing CI.
Do not add automatic country redirects or widen accepted query parameters.
