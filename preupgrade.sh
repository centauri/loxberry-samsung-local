#!/bin/bash
set -Eeuo pipefail
trap 'echo "<ERROR> Backup failed; upgrade cancelled before deleting plugin files"; exit 2' ERR
folder=${3:?Plugin folder missing}
stage=${6:?Installer staging path missing}
base=${LBHOMEDIR:-${5:?LoxBerry home missing}}
# preroot has already stopped the daemon, including its SQLite connection.
python3 "$stage/bin/samsung_local/upgrade.py" backup "$base" "$folder" "$stage"
