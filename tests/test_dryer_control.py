import copy
import time

import pytest

from samsung_local.capabilities import PREFIX
from samsung_local.dryer_control import command
from samsung_local.admin import act
from samsung_local.storage import atomic_json, read_json


def resources():
    return {'/power/0': {'value': True}, '/kidslock/0': {'value': False},
            '/remotectrl/0': {'value': True},
            '/operational/state/vs/0': {PREFIX + 'state': 'Pause'},
            '/washer/vs/0': {PREFIX + 'wrinklePrevent': 'Off'}}


@pytest.mark.parametrize('operation,state,path,field,value', [
    ('start', 'Pause', '/operational/state/vs/0', 'state', 'Run'),
    ('pause', 'Run', '/operational/state/vs/0', 'state', 'Pause'),
    ('stop', 'Run', '/operational/state/vs/0', 'state', 'Ready'),
    ('wrinkle_on', 'Run', '/washer/vs/0', 'wrinklePrevent', 'On'),
    ('wrinkle_off', 'Run', '/washer/vs/0', 'wrinklePrevent', 'Off')])
def test_command_allowlist(operation, state, path, field, value):
    reps = resources()
    reps['/operational/state/vs/0'][PREFIX + 'state'] = state
    original = copy.deepcopy(reps)
    assert command('dryer', reps, operation) == (path, {PREFIX + field: value})
    assert reps == original


@pytest.mark.parametrize('path,value', [('/remotectrl/0', False), ('/kidslock/0', True), ('/power/0', False)])
def test_interlocks_fail_closed(path, value):
    reps = resources()
    reps[path]['value'] = value
    with pytest.raises(ValueError):
        command('dryer', reps, 'start')
    del reps[path]
    with pytest.raises(ValueError):
        command('dryer', reps, 'start')


def test_wrong_kind_operation_and_state():
    for kind, operation in [('oven', 'start'), ('dryer', 'power_on'), ('dryer', 'pause')]:
        with pytest.raises(ValueError):
            command(kind, resources(), operation)


def test_http_queue_opt_in_expiry_and_rate_limit(paths):
    atomic_json(paths.status, {'heartbeat': time.time(), 'devices': {'dryer': {
        'kind': 'dryer', 'identity_verified': True, 'status': 'online'}}})
    request = {'action': 'dryer_command', 'device': 'dryer', 'operation': 'start'}
    with pytest.raises(ValueError):
        act(paths, request)
    config = paths.load_config()
    config['devices'] = {'dryer': {'enabled': True, 'control': True}}
    atomic_json(paths.settings, config)
    assert 'queued' in act(paths, request)
    queued = list(paths.requests.glob('*.json'))
    assert len(queued) == 1
    value = read_json(queued[0])
    assert value['command']['operation'] == 'start'
    assert abs(time.time() - value['command']['timestamp']) < 2
    with pytest.raises(ValueError):
        act(paths, request)
    from samsung_local.service import Service
    service = Service.__new__(Service)
    service.started_at = time.time() + 1
    with pytest.raises(ValueError):
        service.request(value)
