"""Standalone stdlib helper: preserve config across LoxBerry's upgrade purge."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile


def inventory(directory):
    if directory.is_symlink():
        raise ValueError('Configuration directory must not be a symlink')
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('Configuration symlinks are not supported for upgrade')
        if path.is_file():
            result[path.relative_to(directory).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def transfer(action, base, folder, stage):
    if not re.fullmatch(r'samsunglocal[0-9]*', folder):
        raise ValueError('Invalid plugin folder')
    base, stage = Path(base).resolve(), Path(stage).resolve()
    config = base / 'config/plugins' / folder
    marker = stage / '.samsung-local-upgrade.json'
    backup_root = base / 'data/system/samsung-local-backups' / folder
    if action == 'backup':
        if not config.is_dir():
            raise ValueError('Existing configuration is missing; refusing destructive upgrade')
        backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup = Path(tempfile.mkdtemp(prefix='upgrade-', dir=backup_root))
        before = inventory(config)
        shutil.copytree(config, backup / 'config')
        if inventory(backup / 'config') != before or inventory(config) != before:
            raise ValueError('Configuration backup verification failed')
        manifest = {'folder': folder, 'files': before}
        (backup / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        marker.write_text(json.dumps({'backup': str(backup)}), encoding='utf-8')
        os.chmod(marker, 0o600)
        print('<OK> Configuration, device identities and credentials backed up and verified')
        print('<INFO> Recovery backup: ' + str(backup))
        return
    if not marker.exists():
        if action == 'verify':
            raise ValueError('Upgrade backup marker is missing')
        return  # Fresh installation only; preupgrade creates the update marker.
    backup = Path(json.loads(marker.read_text(encoding='utf-8'))['backup']).resolve()
    if backup.parent != backup_root.resolve():
        raise ValueError('Backup is outside this plugin recovery directory')
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    if manifest['folder'] != folder or inventory(backup / 'config') != manifest['files']:
        raise ValueError('Backup integrity check failed; refusing fresh defaults')
    if action == 'restore':
        config.mkdir(parents=True, exist_ok=True, mode=0o700)
        inventory(config)  # Refuse destination symlinks as well.
        shutil.copytree(backup / 'config', config, dirs_exist_ok=True)
        for path in config.rglob('*'):
            os.chmod(path, 0o700 if path.is_dir() else 0o600)
        os.chmod(config, 0o700)
    restored = inventory(config)
    if any(restored.get(name) != digest for name, digest in manifest['files'].items()):
        raise ValueError('Restored configuration differs from the upgrade backup')
    print('<OK> Restored configuration verified byte-for-byte; recovery backup retained')


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('backup', 'restore', 'verify'))
    parser.add_argument('base')
    parser.add_argument('folder')
    parser.add_argument('stage')
    args = parser.parse_args()
    try:
        transfer(args.action, args.base, args.folder, args.stage)
    except Exception:
        print('<ERROR> Upgrade preservation failed. Installation stopped; retain the recovery backup.')
        raise SystemExit(2)
