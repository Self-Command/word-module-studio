#!/usr/bin/env bash
set -euo pipefail
[[ "${GITHUB_ACTIONS:-}" == true && -n "${GITHUB_RUN_ID:-}" ]] || { echo CLOUD_ONLY; exit 2; }
mkdir -p .tools build/provenance
curl --fail --location --retry 3 --connect-timeout 20 --max-time 300 https://github.com/iOfficeAI/OfficeCLI/releases/download/v1.0.156/officecli-linux-x64 -o .tools/officecli
printf '%s  %s\n' a5ed6e4157fe9b24a099cd24ff30e89a4349b7a7d782d2b7de8d56294c7e1423 .tools/officecli | sha256sum --check
chmod +x .tools/officecli
echo "$PWD/.tools" >> "$GITHUB_PATH"
python -m pip install -r requirements.lock
python -m pip freeze > build/provenance/python-resolved.lock
python -m pip download --no-deps -r build/provenance/python-resolved.lock -d .tools/python-packages
sha256sum .tools/python-packages/* > build/provenance/python-downloads.sha256
dotnet publish sdk/WordSdk.csproj -c Release -o .tools/sdk > build/provenance/sdk-build.log
cp sdk/packages.lock.json build/provenance/sdk-packages.lock.json
