# Upgrade preservation fix — 0.2.1

The previous release's preservation claim was incorrect. LoxBerry's
`sbin/plugininstall.pl` calls the incoming `preupgrade` hook, then
`purge_installation`, which deletes both config/plugins/<folder> and
data/plugins/<folder>. This plugin omitted the backup hook and recreated defaults
in postinstall. That loses discovery networks, devices, certificates and MQTT
instance identity during normal upgrades.

0.2.1 adds a preupgrade backup outside the purge scope, restore before initialization,
and postupgrade verification. All configuration files are copied and SHA-256
verified. Backup/restore failure exits 2, which the installer treats as fatal.
Backups stay in data/system/samsung-local-backups/<folder>/ for recovery and contain
private credentials. They are deliberately not removed on successful installation.
Transient data and virtual environments are rebuilt.

197 tests pass, including an upgrade-purge simulation for normal and suffixed
folders. It verifies byte-for-byte preservation of settings, device registry,
MQTT identity, generated certificate, imported credential and SQLite command ledger
after removal/recreation of both plugin directories and postinstall initialization.
Additional checks cover corrupted backups, missing upgrade markers, lifecycle
ordering and inclusion of preupgrade in the ZIP. Ruff and bash syntax checks pass.
Two existing upstream pyOpenSSL deprecation warnings remain.

Tests ran on Windows using the real Python preservation helper. The full LoxBerry
installer/systemd lifecycle has not been executed on a real LoxBerry here.

Install this ZIP as an update without uninstalling. Its incoming preupgrade hook
preserves the current installation even if the installed older version has no hook.
State already erased by previous versions needs a prior LoxBerry backup to recover.
