#!/bin/bash
set -Eeuo pipefail
trap 'echo "<ERROR> Samsung Local setup failed. See the installation log."; exit 2' ERR
folder=${3:?Plugin folder missing}
[[ "$folder" =~ ^samsunglocal[0-9]*$ ]] || exit 2
base=${LBHOMEDIR:-/opt/loxberry}
bindir="$base/bin/plugins/$folder"
configdir="$base/config/plugins/$folder"
datadir="$base/data/plugins/$folder"
logdir="$base/log/plugins/$folder"
umask 077
mkdir -p "$configdir" "$datadir" "$logdir"
# LoxBerry purges config/data on upgrade. Restore BEFORE init can create defaults.
stage=${6:?Installer staging path missing}
python3 "$bindir/samsung_local/upgrade.py" restore "$base" "$folder" "$stage"
# Versioned venvs stay at their original absolute path; venv scripts cannot safely be relocated.
version=${4:?Plugin version missing}
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || exit 2
venv="$datadir/venv-$version"
python3 -m venv "$venv"
"$venv/bin/python" -m pip install --disable-pip-version-check -r "$bindir/requirements.txt"
"$venv/bin/python" -m pip check
cd "$bindir"
"$venv/bin/python" -m samsung_local init --config "$configdir" --data "$datadir" --log "$logdir"
ln -sfn "$venv" "$datadir/venv"
chmod 700 "$configdir" "$configdir/credentials" "$datadir"
echo '<OK> Native Python environment, persistent settings and certificate are ready'
