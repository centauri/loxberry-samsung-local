import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from samsung_local.credentials import ensure_certificate
from samsung_local.storage import Paths, atomic_json
from samsung_local.upgrade import inventory, transfer


@pytest.mark.parametrize('folder', ['samsunglocal', 'samsunglocal01'])
def test_upgrade_preserves_state_across_loxberry_directory_purge(tmp_path, folder):
    base, stage = tmp_path / 'loxberry', tmp_path / 'installer'
    stage.mkdir()
    config, data = base / 'config/plugins' / folder, base / 'data/plugins' / folder
    paths = Paths(config, data, base / 'log/plugins' / folder)
    atomic_json(paths.settings, dict(paths.load_config(), language='nl', networks=['192.168.1.0/24'],
                                    devices={'dryer': {'enabled': True, 'control': False}}))
    atomic_json(paths.registry, {'dryer': {'legacy_verified': True, 'compatibility_attempted': True}})
    atomic_json(config / 'instance.json', {'id': 'unchanged-mqtt-instance'})
    ensure_certificate(config / 'credentials')
    atomic_json(config / 'credentials/dryer.json', {'mode': 'psk', 'key_hex': 'test-key'})
    with sqlite3.connect(config / 'commands.sqlite3') as db:
        db.execute('CREATE TABLE commands (id TEXT PRIMARY KEY, stamp REAL)')
        db.execute('INSERT INTO commands VALUES (?, ?)', ('old-command', 123))
    db.close()  # sqlite's context manager commits; it does not close the handle.
    before = inventory(config)
    transfer('backup', base, folder, stage)
    # Reproduce LoxBerry purge_installation in this test's isolated directory.
    for target in (config, data):
        assert target.resolve().is_relative_to(tmp_path.resolve())
        shutil.rmtree(target)
    config.mkdir(parents=True)
    (config / 'mqtt_subscriptions.cfg').write_text('samsunglocal/#\n')
    transfer('restore', base, folder, stage)
    fresh = Paths(config, data, paths.log)
    assert fresh.load_config()['networks'] == ['192.168.1.0/24']
    assert fresh.load_config()['language'] == 'nl'
    ensure_certificate(config / 'credentials')  # postinstall init must not replace it
    transfer('verify', base, folder, stage)
    assert all(inventory(config)[k] == v for k, v in before.items())
    assert json.loads((config / 'instance.json').read_text())['id'] == 'unchanged-mqtt-instance'


def test_corrupt_backup_blocks_restore_instead_of_creating_defaults(tmp_path):
    stage = tmp_path / 'stage'
    stage.mkdir()
    config = tmp_path / 'config/plugins/samsunglocal'
    config.mkdir(parents=True)
    (config / 'settings.json').write_text('{"networks": ["192.168.1.0/24"]}')
    transfer('backup', tmp_path, 'samsunglocal', stage)
    backup = Path(json.loads((stage / '.samsung-local-upgrade.json').read_text())['backup'])
    (backup / 'config/settings.json').write_text('corrupt')
    with pytest.raises(ValueError, match='integrity'):
        transfer('restore', tmp_path, 'samsunglocal', stage)


def test_fresh_install_has_no_restore_but_upgrade_requires_marker(tmp_path):
    transfer('restore', tmp_path, 'samsunglocal', tmp_path)
    with pytest.raises(ValueError, match='marker'):
        transfer('verify', tmp_path, 'samsunglocal', tmp_path)


def test_lifecycle_restores_before_initialization_and_build_ships_preupgrade():
    root = Path(__file__).resolve().parents[1]
    script = (root / 'postinstall.sh').read_text()
    assert script.index('upgrade.py" restore') < script.index('-m samsung_local init')
    assert 'backup' in (root / 'preupgrade.sh').read_text()
