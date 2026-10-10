# Third-party provenance

Original Word Module Studio source: Apache-2.0, Copyright 2026 Self-Command.

- OfficeCLI: Apache-2.0, iOfficeAI contributors. Pinned v1.0.156,
  commit 699cafbc8f0b8a7841c6cca53dafd0c24e982f56. Machine-readable help contracts
  copied unmodified into third_party/officecli/help. Word showcase source/assets
  copied into fixtures/upstream/word for cloud qualification, not installation.
  Original license retained in third_party/officecli/LICENSE.
- reference-paper-studio: MIT, Copyright 2026 Self-Command. Mathematical
  migration code retains its license in third_party/reference-paper-studio/LICENSE.
- Open XML SDK 3.4.1: MIT, installed through NuGet; unmodified dependency.
- python-docx 1.2.0: MIT; unmodified Python dependency.
- Pandoc 3.12.1: GPL-2.0-or-later, separate unmodified executable, never embedded
  into the proprietary or Python application code.
- LibreOffice 26.8.1: MPL-2.0, separate unmodified executable.
- docxtpl legacy adapter: LGPL-2.1, optional unmodified dependency; upstream code
  is not relicensed as MIT/Apache or copied into the core.

Cloud builds emit resolved dependencies and download fingerprints. Upstream
examples deliberately tolerate unsupported properties; their scripts are not
used as acceptance tests. Our own commands fail on unsupported properties.
