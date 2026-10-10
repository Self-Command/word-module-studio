#!/usr/bin/env bash
set -euo pipefail
mkdir -p .tools build/provenance
curl --fail --location --retry 3 --connect-timeout 20 --max-time 300 https://github.com/iOfficeAI/OfficeCLI/releases/download/v1.0.156/officecli-linux-x64 -o .tools/officecli
printf '%s  %s\n' a5ed6e4157fe9b24a099cd24ff30e89a4349b7a7d782d2b7de8d56294c7e1423 .tools/officecli | sha256sum --check
chmod +x .tools/officecli
if [[ -n "${GITHUB_PATH:-}" ]]; then echo "$PWD/.tools" >> "$GITHUB_PATH"; fi
python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
python -m pip freeze > build/provenance/python-resolved.lock
python -m pip download --require-hashes --only-binary=:all: -r requirements.lock -d .tools/python-packages
sha256sum .tools/python-packages/* > build/provenance/python-downloads.sha256
dotnet restore sdk/WordSdk.csproj --locked-mode > build/provenance/sdk-restore.log
dotnet publish sdk/WordSdk.csproj --no-restore -c Release -o .tools/sdk > build/provenance/sdk-build.log
cp sdk/packages.lock.json build/provenance/sdk-packages.lock.json
