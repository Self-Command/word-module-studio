Word Module Studio 0.1.1 publishes the standalone, general-purpose DOCX skill with JSON,
Python and Codex interfaces. English and Chinese READMEs explain installation, cloud task
setup, editing, template registration, outputs and qualification limits, with eight actual
test-page images and their source fingerprints.

The current source and installation exclude application adapters, domain policies, external
manuscripts and unrelated project data. An explicit publication inventory checks the source
tree and supplies the exact installation files. Regression checks verify that unlisted files
cannot enter the package, even when placed inside otherwise supported directories.

The core layout release adds themes and effective font inheritance, section and container
ownership, CJK and pagination controls, native frames and drop caps, real font embedding,
table AutoFit policies, editable field-cache refresh, and practical reversible OMML layout.
Independent module and combination proofs use generic documents. Cloud test runs and bound
page receipts are included in the acceptance report.

Accepted engine: `2ee18d51df26f8e0fbc175bf4e0f3b7988430b99`; cloud run 38064409279.
All six suites pass 101 tests. Direct review accepts 26 generic proofs and all 49 pages.
The release gate rechecks exact PDF/page identities and source consistency before packaging.

For 0.1.1, every current page SHA-256 and observed PDF font family exactly matches the
original directly reviewed run 38059546545. Receipts retain that inspection provenance and
bind the new run's input and PDF identities; the release gate verifies the current page files.

All conversion, rendering and validation run in GitHub Actions. The skill ZIP contains only
allowlisted implementation resources; users can run document tasks in a private repository.

Proofs use LibreOffice 26.8.1. Microsoft Word native rendering has not been tested.
The pinned renderer ignores native OMML operator breaks, so compatibility uses outer equation
arrays. Author alignment and nested mathematical atoms stay intact; difficult formulas can
require a small manual adjustment recorded by formula ID. Page clipping or severe occlusion
must fail visual acceptance. Font embedding requires redistributable font files.

Application-specific integrations require their own repositories and acceptance.
