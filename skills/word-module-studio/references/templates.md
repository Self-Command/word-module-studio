# Composition

TemplateSpec defines identity/version, a confirmed font scheme, ordered regions with physical
page/column geometry, named role styles and caption directions. Application requirements are
configuration data. A newly required reusable behavior belongs in a shared module.

Build the master once, validate it, then record its spec/master/font fingerprints. Filling a
document cannot mutate style definitions, section geometry, headers, footers or the master.
Font changes create another registered identity. Candidate masters cannot be claimed released.

Cloud task order is `template-build` → `template-probe` → bound `visual-receipt` →
`template-register`. Formal `compose` carries the registered manifest and exact master as
explicit input files; relocation changes only the local path, never its expected fingerprint.
The Python composition API accepts candidates for development; that does not register them.

Front/body/end regions may use different layouts. No object can infer a global document width:
math, tables, captions and figures resolve their own LayoutContext. Data tables and equation
number layout tables remain different roles. Front-matter placement is composition data.

A registered template certifies its tested layout and content contract. The calling application
supplies any additional domain requirements and decides whether those requirements are met.

Optional composable configuration: `theme`, document `typography`, per-style `native`
and `based_on`, per-region `native`, `table_policy`, slot `frames`, `font_embedding`,
and `equations` (practical policy, operator position and continuation indentation).
Existing specs remain valid. Native properties are validated against the pinned OfficeCLI
contracts; frames and font parts use the Open XML SDK. See `core/examples/core-layout.json`.
LayoutContext includes owning sections, native cell/textbox content widths, resolved theme
fonts, pagination values and effective-format provenance. Before actual pagination, unequal
columns without a renderer position use the narrowest valid width conservatively. The proof
report records actual renderer column assignment and unresolved cases needing page review.
