# Composition

TemplateSpec defines identity/version, a confirmed font scheme, ordered regions with physical
page/column geometry, named role styles and caption directions. It never embeds a journal name
as an executable layout branch. A newly required behavior belongs in a shared module.

Build the master once, validate it, then record its spec/master/font fingerprints. Filling a
manuscript cannot mutate style definitions, section geometry, headers, footers or the master.
Font changes create another registered identity. Candidate masters cannot be claimed released.

Front/body/end regions may use different layouts. No object can infer a global document width:
math, tables, captions and figures resolve their own LayoutContext. Data tables and equation
number layout tables remain different roles. English abstract placement is composition data.

A template registry does not certify official journal compliance. The consumer supplies and
approves academic sources, section names and publication requirements.
