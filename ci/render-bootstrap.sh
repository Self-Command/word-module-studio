#!/usr/bin/env bash
set -euo pipefail
task_sudo=()
if [[ "$(id -u)" != 0 ]]; then task_sudo=(sudo); fi
"${task_sudo[@]}" apt-get update -qq
"${task_sudo[@]}" apt-get install -y --no-install-recommends poppler-utils fontconfig fonts-noto-cjk fonts-noto-core fonts-liberation fonts-texgyre fonts-texgyre-math python3-uno
mkdir -p .tools/downloads build/provenance
archive=.tools/downloads/LibreOffice_26.8.1_Linux_x86-64_deb.tar.gz
curl --fail --location --retry 3 --connect-timeout 20 --max-time 300 https://download.documentfoundation.org/libreoffice/stable/26.8.1/deb/x86_64/LibreOffice_26.8.1_Linux_x86-64_deb.tar.gz -o "$archive"
printf '%s  %s\n' 30903df3b9f61360d9660cd707de48cd2831469114492a5008ed58a0ac77d044 "$archive" | sha256sum --check
mkdir -p .tools/lo-install
tar -xzf "$archive" -C .tools/lo-install
"${task_sudo[@]}" dpkg -i .tools/lo-install/*/DEBS/*.deb
"${task_sudo[@]}" ln -sf /opt/libreoffice26.8/program/soffice /usr/local/bin/libreoffice
archive=.tools/downloads/pandoc-3.12.1-1-amd64.deb
curl --fail --location --retry 3 --connect-timeout 20 --max-time 180 https://github.com/jgm/pandoc/releases/download/3.12.1/pandoc-3.12.1-1-amd64.deb -o "$archive"
printf '%s  %s\n' b4217ac7c54067c442f9d4cd38bcd0c184a43f3e7053431a12263a6f92a33ba2 "$archive" | sha256sum --check
"${task_sudo[@]}" dpkg -i "$archive"
libreoffice --version > build/provenance/renderer.txt
pandoc --version > build/provenance/pandoc.txt
dpkg-query -W > build/provenance/system-versions.txt
fc-list > build/provenance/fonts.txt
