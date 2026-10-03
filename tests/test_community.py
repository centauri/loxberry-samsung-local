import importlib.util
import json
from pathlib import Path

from samsung_local.community import capture, envelope
from samsung_local.compatibility_report import evidence, report

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('replay_report', ROOT / 'tools/replay_report.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_community_export_preserves_enums_and_redacts_nested_secrets():
    data = capture({'rt': ['oic.d.dryer'], 'di': 'private', 'n': 'Paul'}, [
        {'href': '/newfeature/vs/0', 'rep': {'mode': 'Dry', 'options': ['Dry', 'Iron'],
         'nested': {'accessToken': 'SECRET', 'connectedApSsid': 'SECRET', 'owner': 'SECRET'},
         'certificate': 'SECRET', 'n': 'SECRET'}},
        {'href': '/oic/sec/cred', 'rep': {'key': 'SECRET'}},
        {'href': '/wirelessinfo/vs/0', 'rep': {'value': 'SECRET'}}], {}, 'dryer')
    text = json.dumps(data)
    assert 'SECRET' not in text and 'Paul' not in text and 'private' not in text
    assert '/oic/sec/cred' not in text and '/wirelessinfo' not in text
    assert data['resources']['/newfeature/vs/0']['options'] == ['Dry', 'Iron']
    assert data['unbound_hrefs'] == ['/newfeature/vs/0']


def test_export_round_trips_into_fixture_and_mapper():
    collected = evidence({'rt': ['oic.d.dryer']}, [],
                         [{'href': '/power/0', 'rep': {'value': True}}], {}, 'dryer', {})
    exported = report({'kind': 'dryer', 'compatibility_evidence': collected})
    result = module.replay(exported)
    assert result['state']['power'] == 1
    assert module.replay(result['fixture'])['state'] == result['state']
    assert exported['adapter']['name'] == 'loxberry-samsung-local'
    assert 'integration_version' not in exported['data']


def test_ha_wrapper_and_direct_resources_are_accepted():
    data = {'resources': {'/power/0': {'value': True}},
            'identity': {'device_types': ['oic.d.dryer']}}
    assert module.replay({'data': data})['state'] == module.replay(data)['state']


def test_unread_device_has_no_invented_resources():
    assert 'resources' not in envelope({})['data']


def test_upstream_fixture_corpus_imports_without_network():
    rows = json.loads((ROOT / 'tests/fixtures/appliances.json').read_text(encoding='utf-8'))
    for row in rows:
        assert module.replay(row)['state'], row['source']


def test_tv_report_explains_discovery_only_and_omitted_name():
    exported = report({'kind': 'television', 'status': 'unsupported',
                       'name': "Paul's living room TV", 'host': '192.168.1.115',
                       'samsung': True, 'rt': ['oic.d.tv'],
                       'connection_report': {'stage': 'not_attempted', 'error': 'UnsupportedMediaProfile'}})
    assert exported['data']['device_type'] == 'television'
    assert exported['discovery']['device_types'] == ['oic.d.tv']
    assert 'Omitted' in exported['discovery']['friendly_name']
    assert exported['collection']['resource_capture'] == 'unavailable'
    assert exported['support']['route'] == 'adapter_scope'
    assert 'resources' not in exported['data']
    assert "Paul's" not in json.dumps(exported)
    assert '192.168.1.115' not in json.dumps(exported)


def test_connected_report_distinguishes_resource_evidence():
    collected = evidence({'rt': ['oic.d.dryer']}, [],
                         [{'href': '/power/0', 'rep': {'value': True}}], {}, 'dryer', {})
    exported = report({'kind': 'dryer', 'compatibility_evidence': collected})
    assert exported['collection']['resource_capture'] == 'available'
    assert exported['support']['route'] == 'capability_or_adapter_triage'
