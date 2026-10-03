#!/bin/bash
set -Eeuo pipefail
trap 'echo "<ERROR> Samsung Local pre-install check failed"; exit 2' ERR
folder=${3:?Plugin folder missing}
[[ "$folder" =~ ^samsunglocal[0-9]*$ ]] || exit 2
python3 -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 or newer required (Debian 12+)"'
if systemctl cat "loxberry-samsung-local-$folder.service" >/dev/null 2>&1; then
    systemctl stop "loxberry-samsung-local-$folder.service"
fi
echo '<OK> Platform checked; any previous daemon stopped before replacing code'
