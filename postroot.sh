#!/bin/bash
set -Eeuo pipefail
trap 'echo "<ERROR> Samsung Local service setup failed"; exit 2' ERR
folder=${3:?Plugin folder missing}
[[ "$folder" =~ ^samsunglocal[0-9]*$ ]] || exit 2
base=${LBHOMEDIR:-/opt/loxberry}
# systemd directive paths below intentionally support LoxBerry's normal absolute layout only.
[[ "$base" =~ ^/[A-Za-z0-9/_-]+$ ]] || exit 2
unit="loxberry-samsung-local-$folder.service"
configdir="$base/config/plugins/$folder"
datadir="$base/data/plugins/$folder"
logdir="$base/log/plugins/$folder"
install -d -m 700 -o loxberry -g loxberry "$configdir" "$datadir" "$logdir"
chown -R loxberry:loxberry "$configdir" "$datadir" "$logdir"
chmod 700 "$configdir" "$configdir/credentials" "$datadir"
find "$configdir" -type f -exec chmod 600 {} +
cat > "/etc/systemd/system/$unit" <<EOF
[Unit]
Description=Samsung Local native LoxBerry plugin ($folder)
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=120
StartLimitBurst=5

[Service]
Type=simple
User=loxberry
Group=loxberry
WorkingDirectory=$base/bin/plugins/$folder
EnvironmentFile=-/etc/environment
Environment=LBHOMEDIR=$base
Environment=PERL5LIB=$base/libs/perllib
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStartPre=/usr/bin/mkdir -p $logdir
ExecStart=$datadir/venv/bin/python -m samsung_local run --config $configdir --data $datadir --log $logdir
Restart=on-failure
RestartSec=10
TimeoutStopSec=35
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$unit"
systemctl restart "$unit"
systemctl is-active --quiet "$unit"
echo '<OK> Samsung Local service started as the LoxBerry user'
