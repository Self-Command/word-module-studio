# Operations

Cloud API: `snapshot(path)`; `execute(batch, input_path, output_path, template=manifest)`.
Snapshot objects have IDs bound to the input fingerprint. Every batch declares schema version,
mode, input hash and uniquely named module operations. Inputs stay untouched; invalid operations
roll back the output transaction. Source-specific positions are translated inside the engine.

Example operation:
```json
{"id":"set-title","module":"M02","action":"set","target":"o_FROM_SNAPSHOT","props":{"text":"Updated title"}}
```

Native actions: add/set/remove/get. Add supplies `kind`; permitted properties come from pinned
OfficeCLI contracts under `core/third_party/officecli/help/docx`. Mathematical additions use M09
extension with `formula`, `mode`, optional `number`; Pandoc owns conversion. Extensions expose
typed operations, never arbitrary XML, shell or scripting supplied by a manuscript.

Core layout extensions: M19 `theme` with `properties`; M19 `embed_fonts` with font
family/file/index/variant and an explicit redistributable declaration; M03 or M13 `frame`
with SDK FrameProperties attributes; M10 `format` with `layout: autofit|fixed`,
`preferred_width_pct` and `allow_row_split`; M08 `refresh_fields` with no other parameters.
M09 accepts `policy: practical|safe_wrap|fail` and `break_strategy: outer_array|native`.
The practical default never recursively breaks nested atoms; estimates are diagnostics.
`field_cache.refresh(source, output, proof_folder)` also exposes independent cache refresh.

Cloud task stages: inspect/edit/compose/template-build/template-probe/template-register/render/
refresh-fields/verify/merge/extract/visual-receipt/package.
Local transport requires GitHub CLI authentication and a task repository with the dispatch
workflow installed. Each file is listed with role and SHA-256. Personal input is excluded from
installation assets. See core/schemas for the authoritative contracts.
