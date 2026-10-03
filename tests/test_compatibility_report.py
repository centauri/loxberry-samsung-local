import json

from samsung_local.compatibility_report import evidence, report


def test_unknown_resources_expose_schema_without_arbitrary_values():
    batch = [{'href': '/newfeature/vs/0', 'rt': ['x.com.samsung.newfeature'],
              'rep': {'newMode': 'personal-private-string', 'level': 17,
                      'serialNum': 'SECRET', 'nested': {'credential': 'SECRET', 'active': True}}},
             {'href': '/oic/sec/cred', 'rep': {'key': 'SECRET'}},
             {'href': '/wirelessinfo/vs/0', 'rep': {'ssid': 'SECRET'}},
             {'href': '/power/0', 'rep': {'value': True}}]
    data = evidence({'mnmo': 'DV9BN8288AW/EN', 'mnfv': '1.2.3'}, [], batch, {}, 'dryer', {})
    serialized = json.dumps({k: v for k, v in data.items() if k != 'community'})
    assert 'SECRET' not in serialized and 'personal-private-string' not in serialized
    assert '/oic/sec/cred' not in serialized and '/wirelessinfo' not in serialized
    row = data['resources'][0]
    assert row['mapped_path'] is False
    assert row['representation']['fields']['newMode'] == {'type': 'string'}
    assert row['resource_types'] == ['x.com.samsung.newfeature']
    assert data['resources'][-1]['numeric_samples'] == {'power': 1}
    assert data['identity']['model'] == 'DV9BN8288AW/EN'


def test_schema_redacts_path_identifiers_and_bounds_depth():
    uuid = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    nested = 'hidden'
    for _ in range(30):
        nested = {'next': nested}
    data = evidence({}, [{'links': [{'href': '/' + uuid + '/feature/0', 'rt': ['oic.r.sensor']}]}],
                    [{'href': '/feature/0', 'rep': nested}], {}, 'unknown', {})
    text = json.dumps(data)
    assert uuid not in text and 'hidden' not in text
    assert 'REDACTED' in text and 'truncated' in text


def test_unattempted_report_does_not_invent_device_access():
    data = report({'kind': 'television', 'status': 'unsupported', 'host': 'private'})
    assert data['connection']['stage'] == 'not_attempted'
    assert not data['evidence']
    assert 'private' not in json.dumps(data)
