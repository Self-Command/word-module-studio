# Execution choice

Use the user's selected location. Local execution needs no GitHub account, authentication,
repository or Actions environment variables. Do not upload documents or install dependencies
as an automatic fallback when a local dependency is missing.

## Local Python

From the installed skill folder:

```text
python core/src/word_module_studio/client.py doctor --profile inspect
python core/src/word_module_studio/client.py run --manifest PATH_TO_TASK/task.json --output PATH_TO_OUTPUT/inspection
```

Use `doctor` without `--profile inspect` for full editing, conversion and proof dependencies.
The local task runner reads the same task manifest as Actions. It fills omitted file hashes,
stages only listed inputs into `.inputs`, preserves source files and requires a new or empty
output directory for each run. Reports include `execution: local`, a `local-...` run ID,
the engine version and a source fingerprint. Local tasks need no pinned Git commit.

The Python dependencies and native tool setup are documented in `core/README.md` and
`core/README.zh-CN.md`. The fully qualified native setup is Linux x64; other native setups
need their own dependency and render checks. Tool paths can be supplied through `WMS_*`
environment variables. Custom font previews use a task-scoped fontconfig environment and
do not permanently install fonts in the user's profile.

## Optional local Docker

Build the included `core/Dockerfile` for `linux/amd64`. Mount the explicit task directory
read-only and a separate output directory, then invoke `run`. The image supplies the pinned
backends. It is a local execution option, not a requirement. Runtime tasks can use
`--network none` after building the image. See the README for complete host-path commands.

## Optional GitHub Actions

Only for users selecting Actions: configure a task repository with `document-task.yml`,
authenticate `gh`, pin a full engine commit and use `submit`, `status`, `fetch`.
Only manifest-listed files are uploaded. Repository visibility and artifact/commit retention
remain the user's choice. Installing the skill does not require this setup.

## Evidence

Both modes use the same document operations and review rules. Keep build success, automatic
checks, visual review and accepted delivery separate. Local reports must say local and retain
their own run identity; never fabricate `GITHUB_ACTIONS` or `GITHUB_RUN_ID` to unlock APIs.
