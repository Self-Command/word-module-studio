# Core layout acceptance

Version 0.1.0 completes the core layout integration scope. Engine commit
`a8fb33e500512e2f42f9df9e3e8f3c1a7fffe90c` passed all six jobs in
[run 38059546545](https://github.com/Self-Command/word-module-studio/actions/runs/38059546545):
core 39, advanced 20, composition 9, layout 26, rendering 5 and distribution 1,
for 100 regression tests. This is evidence for the listed scenarios, not every Word behavior.

Direct review covered 26 generic proofs and all 49 pages: single/double/triple and unequal
columns, landscape pages, Chinese/Latin/RTL content, effective fonts and theme inheritance,
AutoFit and merged tables, continued captions, six editable chart types, floating pictures,
native frames/drop caps, textboxes/shapes, native notes, source-section merging, readable
fractions/cases, author alignment, long outer continuation lines and refreshed TOC/caption
index/alphabetical index after additions and deletions.

[The acceptance manifest](core-acceptance.json) binds every selected proof and its page
hashes to a 21-item receipt with individual page observations. The release workflow checks
the accepted engine commit, the six successful jobs, source consistency and exact artifact
identities before building the skill ZIP. Intermediate refresh passes and the deliberately
unsupported native-break probe are excluded from accepted print proofs.

[The feature catalogue](core-features.json) separates upstream support, integration,
automatic evidence and scoped visual evidence. [Module coverage](module-coverage.json)
keeps structural-only retention claims distinct from print review. Themes/effective format,
container ownership, CJK/pagination rules, actual font-data embedding, native frames/drop
caps, table policies, field-result transplantation, practical OMML and container proof are
integrated and composable through the current contracts. The original 85-test run remains
historical evidence and is not used as completion of these additions.

All tests, conversion, rendering, validation and distribution checks execute in GitHub
Actions. Local work is source editing, transport, artifact inspection and transcription of
the completed visual review. The original editable DOCX is retained; UNO exports are
diagnostic, and only supported field caches are transplanted into a distinct delivery copy.

LibreOffice 26.8.1 is the qualified compatibility renderer. Microsoft Word native rendering
is not tested. This renderer ignores native OMML operator breaks; outer equation arrays
provide the compatible default. Source author alignment and nested atoms are retained;
formula IDs and minor-adjustment suggestions accompany estimated-width warnings. Severe
clipping, symbol loss or changed structure still fail acceptance. Existing-document font
substitutions are declared by actual PDF family; fontconfig candidates are advisory.
Font embedding is proved from actual package data, not from whether Word uses that face.
Interactive annotation/control presentation and arbitrary unknown-object UI are not
certified by these PDFs; their cloud structural retention checks remain available.

The standalone repository contains only this generic DOCX skill, its engine, contracts,
cloud entry points, generic regression fixtures, verification evidence and documentation.
Application adapters, domain policies, user documents and unrelated project inputs are not
part of the current source tree or installation package. Reused generic mathematical and
content-import helpers retain their original MIT provenance and license.
