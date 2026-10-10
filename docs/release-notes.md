Word Module Studio provides composable DOCX operations and JSON/Python/Codex interfaces.

The core layout release adds themes and effective font inheritance, section and container
ownership, CJK and pagination controls, native frames and drop caps, real font embedding,
table AutoFit policies, editable field-cache refresh, and practical reversible OMML layout.
Independent module and combination proofs use generic documents. Cloud test runs and bound
page receipts are included in the acceptance report.

All conversion, rendering and validation run in GitHub Actions. The skill ZIP contains only
allowlisted implementation resources; users can run document tasks in a private repository.

Proofs use LibreOffice 26.8.1. Microsoft Word native rendering has not been tested.
The pinned renderer ignores native OMML operator breaks, so compatibility uses outer equation
arrays. Author alignment and nested mathematical atoms stay intact; difficult formulas can
require a small manual adjustment recorded by formula ID. Page clipping or severe occlusion
must fail visual acceptance. Font embedding requires redistributable font files.

Paper template suites remain paused pending their own integration and acceptance.
