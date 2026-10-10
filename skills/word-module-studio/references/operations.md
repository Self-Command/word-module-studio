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

Cloud task stages: inspect/edit/compose/template-build/render/verify/visual-receipt/package.
Local transport requires GitHub CLI authentication and a task repository with the dispatch
workflow installed. Each file is listed with role and SHA-256. Personal input is excluded from
installation assets. See core/schemas for the authoritative contracts.
