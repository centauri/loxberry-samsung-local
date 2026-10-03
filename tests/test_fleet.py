import json
import queue
from pathlib import Path

import pytest

from samsung_local.capabilities import PREFIX, batch_resources, device_type, normalize
from samsung_local.diagnostics import support_report
from samsung_local.worker import DeviceWorker
from test_discovery_worker import DI, FakeSession, sample

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/appliances.json').read_text())


@pytest.mark.parametrize('recording', FIXTURES, ids=lambda r: r['source'])
def test_recorded_appliance_readonly_session(recording, paths):
    events = queue.Queue()
    obj = DeviceWorker(sample(), {'_compatibility_probe': True}, 30, paths, events, ('192.0.2.10', 49161))
    obj.session = FakeSession({'/oic/d': {'di': DI, 'rt': recording['rt']},
                              '/oic/res': [], '/device/0': recording['device0']})
    obj.monitor()
    updates = [events.get_nowait()[2] for _ in range(events.qsize())]
    last = updates[-1]
    assert last['status'] == 'online'
    assert last['state']
    assert last['legacy_verified']
    assert all(not v['writable'] for v in last['sensors'].values())
    assert not any('/sec/' in path for path in obj.session.reads)


def reading(name):
    row = next(r for r in FIXTURES if r['source'] == name + '.json')
    resources = batch_resources(row['device0'])
    return normalize(resources, device_type(row['rt'], resources.get('/information/vs/0', {})))


def test_recorded_fridge_compartments_and_units():
    state, meta = reading('refrigerator_device')
    assert float(state['temperatures_vs_0_item_0_current']) == 5
    assert float(state['temperatures_vs_0_item_1_current']) == 34
    assert meta['temperatures_vs_0_item_0_current']['unit'] == 'F'
    assert state['filter_waterfilter_vs_0_filter_used_percent'] == 71


def test_recorded_air_monitor_without_power_resource():
    state, meta = reading('air_monitor_device')
    assert state['sensors_vs_0_co2'] == 498
    assert state['sensors_vs_0_fine_dust'] == 23
    assert meta['sensors_vs_0_fine_dust']['unit'] == 'ug/m3'
    assert 'power' not in state


def test_energy_units_and_transient_zero():
    path = '/energy/consumption/vs/0'
    state, _ = normalize({path: {PREFIX+'cumulativePower': '1.5', PREFIX+'cumulativeUnit': 'kWh'}})
    assert state['energy_consumption_vs_0_energy_wh'] == 1500
    for unit, value in [('Wh', '0'), ('Wh', '-1'), ('unknown', '20')]:
        assert not normalize({path: {PREFIX+'cumulativePower': value, PREFIX+'cumulativeUnit': unit}})[0]


def test_support_export_omits_private_values():
    secret = 'never-export-this'
    device = dict(host=secret, di=secret, name=secret, model=secret, diagnostic=secret,
                  state={'secret': secret}, credentials=secret, rt=[secret], kind=secret,
                  status='online', resources=['/power/0', '/'+secret+'/0'],
                  resource_diagnostics={'reads': {'/power/0': {'code': '2.05', 'body': secret},
                                                '/oic/sec/cred': {'code': '2.05'}}})
    report = support_report({secret: device})
    assert secret not in json.dumps(report)
    assert '/oic/sec/cred' not in json.dumps(report)
    assert report['devices'][0]['reads']['/power/0']['code'] == '2.05'


def test_numeric_compartment_identity_survives_reordering():
    a = {PREFIX+'id': '0', PREFIX+'current': '10'}
    b = {PREFIX+'id': '1', PREFIX+'current': '20'}
    def run(items):
        return normalize({'/temperatures/vs/0': {PREFIX+'items': items}})[0]
    assert run([a, b]) == run([b, a])
    assert len(run([a, a])) == 1


def test_unknown_fields_are_not_published():
    state, _ = normalize({'/power/0': {'value': True, 'serialNum': 'secret'},
                          '/wirelessinfo/vs/0': {'connectedApSsid': 'secret'},
                          '/temperatures/vs/0': {PREFIX+'items': [{PREFIX+'id': 'secret', PREFIX+'current': 10}]}})
    assert state == {'power': 1}


def test_empty_standard_power_uses_vendor_representation():
    assert normalize({'/power/0': {'rt': ['oic.r.switch.binary']},
                      '/power/vs/0': {PREFIX+'power': 'On'}})[0]['power'] == 1
