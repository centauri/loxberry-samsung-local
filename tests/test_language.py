import json
import re
from pathlib import Path

import pytest

from samsung_local.admin import act
from samsung_local.storage import atomic_json, validate_config


def test_language_default_validation_and_saved_preferences(paths):
    assert validate_config({})['language'] == 'en'
    config = paths.load_config()
    config['networks'] = ['192.168.2.0/24']
    config['devices'] = {'example': {'enabled': True, 'control': False}}
    atomic_json(paths.settings, config)
    act(paths, {'action': 'language', 'language': 'nl'})
    assert paths.load_config() == dict(config, language='nl')
    with pytest.raises(ValueError):
        act(paths, {'action': 'language', 'language': '../../other'})
    assert paths.load_config()['language'] == 'nl'
    act(paths, {'action': 'settings', 'enabled': True, 'poll_seconds': 30,
                'scan_seconds': 600, 'networks': []})
    assert paths.load_config()['language'] == 'nl'


def test_every_literal_ui_translation_has_a_dutch_entry():
    root = Path(__file__).resolve().parents[1] / 'webfrontend/htmlauth'
    catalog = {}
    for path in (root / 'lang').glob('nl*.json'):
        catalog.update(json.loads(path.read_text(encoding='utf-8')))
    keys = re.findall(r"\bt\('((?:\\.|[^'\\])*)'\)", (root / 'index.php').read_text(encoding='utf-8'))
    for key in keys:
        key = key.replace("\\'", "'").replace('\\\\', '\\')
        assert key in catalog, key
        assert catalog[key]
