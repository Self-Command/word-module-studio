Word Module Studio 0.1.2 adds local execution to the standalone, general-purpose DOCX skill.
Users can run the JSON task runner or Python API locally, use an optional local Docker
environment, or choose GitHub Actions. Local tasks require no GitHub account, repository,
credentials, Actions variables or pinned Git commit. The client never uploads a document
or changes execution location as a fallback for missing dependencies.

The new `run` command stages only explicitly listed files, preserves originals and records
a local run identity, engine version and source fingerprint. `doctor` reports dependency
availability without installing software. Tool paths are configurable. Local and Actions
execution share the document operations and page-review rules.

English and Chinese READMEs explain all three execution choices, installation, editing,
template registration, outputs and qualification limits, with eight actual test-page images
and their source fingerprints.

The current source and installation exclude application adapters, domain policies, external
manuscripts and unrelated project data. An explicit publication inventory checks the source
tree and supplies the exact installation files. Regression checks verify that unlisted files
cannot enter the package, even when placed inside otherwise supported directories.

The core layout release adds themes and effective font inheritance, section and container
ownership, CJK and pagination controls, native frames and drop caps, real font embedding,
table AutoFit policies, editable field-cache refresh, and practical reversible OMML layout.
Independent module and combination proofs use generic documents. Cloud test runs and bound
page receipts are included in the acceptance report.

Accepted engine: `d12f9056b14cff32944b4692db7afa94e4664747`; cloud run 38069365621.
All six suites pass 104 tests. Direct review accepts 26 generic proofs and all 49 pages.
The release gate rechecks exact PDF/page identities and source consistency before packaging.

For 0.1.2, every current page SHA-256 and observed PDF font family exactly matches the
original directly reviewed run 38059546545. Receipts retain that inspection provenance and
bind the new run's input and PDF identities; the release gate verifies the current page files.

Automated release qualification runs in GitHub Actions. A separate Linux x64 container
verification runs with network access disabled and no GitHub credentials or Actions
environment variables; it completes inspection, editing and actual PDF/PNG generation.
Local qualification run: 38069365595, using the same accepted engine commit.
The qualified local container is optional. Configured native Python environments can run
the same API; other native platforms need their own dependency and rendering qualification.
The skill ZIP contains only allowlisted implementation resources.

Proofs use LibreOffice 26.8.1. Microsoft Word native rendering has not been tested.
The pinned renderer ignores native OMML operator breaks, so compatibility uses outer equation
arrays. Author alignment and nested mathematical atoms stay intact; difficult formulas can
require a small manual adjustment recorded by formula ID. Page clipping or severe occlusion
must fail visual acceptance. Font embedding requires redistributable font files.

Application-specific integrations require their own repositories and acceptance.
