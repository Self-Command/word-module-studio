# Module contracts and evidence

Each module uses an input fingerprint and stable object ID. Native reads are `snapshot()`
and batch `get`; native mutations are `add/set/remove` with element contracts under
`third_party/officecli/help/docx`. `capabilities.contract(kind)` expands inherited properties,
aliases, enums and allowed actions. Module/element mismatches and unsupported parameters fail
before dispatch. Extension parameters are checked by the named generic handler.
M17/M19/M20 are document services exposed by task stages and Python functions.

`OperationBatch` is atomic on a copy. Source and previously delivered files are retained;
failed work is saved as `.failed.docx` plus `.failure.json`. Unknown parts remain byte-exact,
or are restored after proving XML equivalence. Broken relationships and undeclared changes fail.
`LayoutContext` resolves owning section, named region, margins, per-column widths and styles.
Locked template operations cannot alter protected physical rules; content import strips source
geometry and checks the registered master/spec/font fingerprints.

| Module | Generic implementation and special operations | Conditions / dependencies |
|---|---|---|
| M01 Document/parts | Package open/copy/save, snapshot, relationship audit | DOCX zip; preserve unmodified unknown parts |
| M02 Text | OfficeCLI characters; `text.apply`: replace/range edits across runs | Preserve styles of untouched runs; native RTL/language/fonts |
| M03 Paragraph/style | OfficeCLI paragraph and character styles, inheritance, tabs, borders, keep rules | Style references must exist; fonts available |
| M04 Numbering | OfficeCLI list styles; `numbering.apply`: multilevel, restart, continue, heading numbering | Native numbering IDs and inherited definitions |
| M05 Page/section | OfficeCLI pages/breaks/columns/line numbers; SDK unequal columns | Positive available width, owning section |
| M06 Headers/footer | OfficeCLI native content; `headers.apply`: variants, section links, page fields/restarts | First/even flags and relationship ownership |
| M07 Fields/references | OfficeCLI bookmarks, links, SEQ/REF/PAGEREF; `captions.apply` | Independent Figure/Table/Equation counters; missing targets fail |
| M08 Contents/index | OfficeCLI TOC and native field types; UNO refresh | Actual page cache; at most three convergence attempts |
| M09 Mathematics | Pandoc OMML, reversible structural wrapping, baseline/centre number layout | Shared font metrics and column budget; no font shrink/raster fallback |
| M10 Tables | OfficeCLI row/column/cell actions; `tables.apply`: merge, format, explicit split or `paginate` with continued captions | Cloud row-position discovery, caption space and at most three checks; crossing vertical merge fails |
| M11 Pictures | OfficeCLI inline/anchor/wrap/crop/alt; resource copier and proportional column cap | Explicit local image resources; missing files fail |
| M12 Charts | OfficeCLI chart/series/axis; SDK synchronises editable workbook data | Native chart XML, formula ranges and externalData relationship |
| M13 Shapes | OfficeCLI shapes/textboxes/connectors/watermarks; `shapes.apply`: group, rotate, text effects | Native editable DrawingML; group members must be shapes |
| M14 Notes | OfficeCLI notes/section numbering; SDK footnote/endnote conversion | Native reference IDs and text preservation |
| M15 Comments/revisions | OfficeCLI ranges/replies/status, native insert/delete/format/move and decisions | Decisions scoped by stable target or author; preserve other content |
| M16 Controls | OfficeCLI text/richtext/picture/date/check/list; `controls.apply`: bind, conditional/repeat/fill | Native custom XML bindings; safe semantic values |
| M17 Merge/extract | `merge` / `extract`; docxcompose adapter imports auxiliary parts | Explicit master/source-region header policy; remap media/styles/bookmarks/notes/comments |
| M18 Metadata/accessibility | OfficeCLI core properties; `accessibility.inspect` | Heading hierarchy, default language, image alt and table header checks |
| M19 Template/fonts | `templates.build`, identity and protection checks | TemplateSpec only; explicit font scheme, immutable master, no consumer-name branch |
| M20 Proof/review | `render`, `geometry`, `receipt`, SDK and semantic differences | PDF+PNG, run and file fingerprints; manual page observations required |

Common failures: `CLOUD_ONLY`, `STALE_INPUT`, `INVALID_TARGET`, `UNSUPPORTED_PROPERTY`,
`MODULE_ELEMENT_MISMATCH`, `FONT_MISSING`, `BROKEN_RELATIONSHIP`, `BROKEN_REFERENCE`,
`UNKNOWN_PART_CHANGED`, `UNDECLARED_RUN_CONTENT_CHANGE`, `FORMULA_CANNOT_FIT`,
`TABLE_CANNOT_FIT`, `TABLE_SPLIT_CROSSES_MERGE`, `TEMPLATE_VERSION_REUSE`,
`FIELD_PAGINATION_NOT_CONVERGED`, and `VISUAL_RECEIPT_*`. The precise error and object
identity are retained with the failed task rather than described as a successful conversion.

The coverage JSON names actual cloud test files and tracks acceptance separately. Native
upstream support is not equivalent to our own regression evidence. The 21-item visual checklist
is in the skill; a completed review with findings keeps delivery acceptance false.

## Composing core layout rules

`TemplateSpec` remains compatible with its original required fields. Optional `theme`,
`typography`, region/style `native`, `table_policy`, `font_embedding`, `frames` and
`equations` rules combine the existing modules. See [generic configuration](../examples/core-layout.json).
Frame attributes use the SDK's native `FrameProperties`; `slot` identifies the paragraph.
Font embedding writes obfuscated font data, relationships and font-table references after
fontTools checks the actual file and embedding permissions. A settings flag alone is not
reported as embedding.

`LayoutContext.resolve` resolves paragraph/character inheritance, direct properties,
explicit false pagination values and theme families. Header/footer references, notes and
textboxes use their owning sections and container widths. Shared stories report their
owners; ambiguous ownership and unsupported containers require review. These are source
geometry and format rules. `container_proof` records the renderer's observed page and column
positions, table rows and frame/shape dimensions for comparison and page review.

`field_cache.refresh(source, output, folder)` requires a distinct output and refreshes only
supported field results. It keeps the source instructions, other content and unrelated parts,
audits references and SDK structure, and checks pagination convergence. The UNO-exported
DOCX remains diagnostic. Simple XE imports with an empty hierarchical child are repaired in
that compatibility document; the source XE instruction is retained in the deliverable.

The default practical formula policy preserves author alignment and nested atoms. Width
estimates guide outer break candidates and produce formula IDs and adjustment suggestions;
actual page review decides acceptance. Native OMML breaks are exposed but the pinned
LibreOffice renderer ignores them, so the compatible default uses outer equation arrays.
The PDF import adapter supplies an empty StarMath operand before a leading relation and
an explicit source font size without changing the delivered OMML. Missing operators,
altered structure or severe clipping fail acceptance. Microsoft Word desktop behavior
requires its own qualification.
