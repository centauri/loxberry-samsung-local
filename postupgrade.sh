#!/bin/bash
set -Eeuo pipefail
trap 'echo "<ERROR> Upgrade configuration verification failed"; exit 2' ERR
folder=${3:?Plugin folder missing}
stage=${6:?Installer staging path missing}
base=${LBHOMEDIR:-${5:?LoxBerry home missing}}
python3 "$base/bin/plugins/$folder/samsung_local/upgrade.py" verify "$base" "$folder" "$stage"
