#!/bin/bash
set -Eeuo pipefail
folder=${3:?Plugin folder missing}
[[ "$folder" =~ ^samsunglocal[0-9]*$ ]] || exit 1
unit="loxberry-samsung-local-$folder.service"
systemctl disable --now "$unit" || true
rm -f -- "/etc/systemd/system/$unit"
systemctl daemon-reload
echo '<OK> Service removed. LoxBerry removes the plugin files and local credentials.'
