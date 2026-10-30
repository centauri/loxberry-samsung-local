import json
import queue
import time
import uuid

import pytest

from samsung_local import television as tv
from samsung_local.admin import act
from samsung_local.mqtt import validate_command
from samsung_local.storage import atomic_json, read_json


def worker(paths):
    return tv.TelevisionWorker({'key': 'tv', 'host': '192.168.1.122'}, {}, 30, paths,
                               queue.Queue(), ('192.168.1.122', 45955))


def test_pair_saves_private_token_and_sends_no_key(paths, monkeypatch):
    calls = []
    class Remote:
        token = 'private-token'
        def __init__(self, *args, **kwargs):
            calls.append(kwargs)
        def open(self):
            calls.append('open')
        def close(self):
            calls.append('close')
        def send_key(self, key):
            raise AssertionError('Pairing must not send a remote key')
    monkeypatch.setattr(tv, 'SamsungTVWS', Remote)
    w = worker(paths)
    w.remote({'identity': 'tv-id', 'port': 8002}, pair=True)
    assert read_json(w.credential)['token'] == 'private-token'
    w.remote({'identity': 'tv-id', 'port': 8002})
    assert calls[3]['token'] == 'private-token'
    with pytest.raises(ValueError, match='identity changed'):
        w.remote({'identity': 'another-tv', 'port': 8002})
    assert len(calls) == 6


def test_controls_recheck_settings_after_connect(paths, monkeypatch):
    w = worker(paths)
    atomic_json(w.credential, {'identity': 'tv', 'port': 8002, 'token': 'secret'})
    class Remote:
        def __init__(self, *a, **k):
            pass
        def open(self):
            pass
        def close(self):
            pass
        def send_key(self, key):
            raise AssertionError('Disabled control')
    monkeypatch.setattr(tv, 'SamsungTVWS', Remote)
    with pytest.raises(ValueError, match='disabled'):
        w.remote({'identity': 'tv', 'port': 8002}, operation='mute')


def test_remote_mqtt_is_explicit_bounded_and_nonretained():
    payload = json.dumps({'id': str(uuid.uuid4()), 'timestamp': time.time(), 'value': 'volume_up'})
    assert validate_command(payload, False, time.time(), remote=True)['operation'] == 'volume_up'
    with pytest.raises(ValueError):
        validate_command(payload, True, time.time(), remote=True)
    with pytest.raises(ValueError):
        validate_command(payload.replace('volume_up', 'KEY_FACTORY'), False, time.time(), remote=True)
    with pytest.raises(ValueError):
        validate_command(payload.replace('volume_up', 'pair'), False, time.time(), remote=True)


def test_tv_mqtt_readiness_and_offline_transition(paths):
    from samsung_local.service import Service
    obj = Service(paths)
    obj.config['devices'] = {'tv': {'enabled': True, 'control': True}}
    obj.registry['tv'] = {'kind': 'television', 'status': 'online', 'tv_paired': True,
                          'state': {'power': 1}, 'last_success': time.time()}
    obj.broker.connected.set()
    calls = []
    obj.broker.publish = lambda *args, **kwargs: calls.append((args, kwargs))
    try:
        obj.publish_device('tv')
        values = dict(args for args, _ in calls)
        assert values['tv/remote/available'] == 1
        assert values['tv/remote/paired'] == 1
        assert values['tv/state/power'] == 1
        assert 'volume_up' in values['tv/remote/commands']
        assert not any('volume' in topic for topic in values)
        calls.clear()
        obj.registry['tv']['status'] = 'offline'
        obj.publish_device('tv')
        values = dict(args for args, _ in calls)
        assert values['tv/remote/available'] == 0
        assert 'tv/state/power' not in values
        obj.handle_event(('result', 'tv', {'id': 'test', 'result': 'sent_unconfirmed'}))
        assert calls[-1][1] == {'retain': False}
    finally:
        obj.db.close()
        obj.executor.shutdown()


def test_pair_ui_requires_fresh_enabled_tv(paths):
    atomic_json(paths.status, {'heartbeat': time.time(), 'devices': {'tv': {'kind': 'television', 'status': 'online'}}})
    act(paths, {'action': 'tv_command', 'device': 'tv', 'operation': 'pair'})
    assert len(list(paths.requests.glob('*.json'))) == 1
    with pytest.raises(ValueError):
        act(paths, {'action': 'tv_command', 'device': 'tv', 'operation': 'mute'})


def test_http_tv_generates_id_timestamp_and_refuses_pairing(paths):
    atomic_json(paths.status, {'heartbeat': time.time(), 'devices': {'tv': {
        'kind': 'television', 'status': 'online', 'tv_paired': True}}})
    config = paths.load_config()
    config['devices']['tv'] = {'control': True}
    atomic_json(paths.settings, config)
    with pytest.raises(ValueError):
        act(paths, {'action': 'tv_http_command', 'device': 'tv', 'operation': 'pair'})
    act(paths, {'action': 'tv_http_command', 'device': 'tv', 'operation': 'pause'})
    queued = read_json(next(paths.requests.glob('*.json')))
    assert queued['action'] == 'tv_command'
    assert queued['command']['operation'] == 'pause'
    assert uuid.UUID(queued['command']['id'])
    assert abs(time.time() - queued['command']['timestamp']) < 3
    with pytest.raises(ValueError, match='three seconds'):
        act(paths, {'action': 'tv_http_command', 'device': 'tv', 'operation': 'pause'})


def test_report_never_includes_token():
    from samsung_local.compatibility_report import report
    value = report({'kind': 'television', 'tv_paired': True, 'token': 'private-token',
                    'connection_report': {'stage': 'tv_http'}, 'model': 'QE65Q90RALXXN'})
    assert value['tv']['paired']
    assert 'private-token' not in json.dumps(value)


def test_invalid_tv_target_is_not_requested():
    for target in ('127.0.0.1', 'example.com', '169.254.169.254', '8.8.8.8'):
        with pytest.raises(ValueError):
            tv.device_info(target)


def test_subnet_guidance_uses_real_masks(monkeypatch):
    import ipaddress
    from samsung_local import discovery
    monkeypatch.setattr(discovery, 'interfaces', lambda: [('192.168.0.1', ipaddress.ip_network('192.168.0.0/22'))])
    assert tv.cross_subnet('192.168.1.122') is False
    monkeypatch.setattr(discovery, 'interfaces', lambda: [('192.168.10.10', ipaddress.ip_network('192.168.10.0/24'))])
    assert tv.cross_subnet('192.168.1.122') is True
    monkeypatch.setattr(discovery, 'interfaces', lambda: [])
    assert tv.cross_subnet('192.168.1.122') is None


@pytest.mark.parametrize('token_support,port', [('true', 8002), ('false', 8001)])
def test_http_profile_and_port_selection(monkeypatch, token_support, port):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def raise_for_status(self):
            pass
        def iter_content(self, size):
            yield json.dumps({'type': 'Samsung SmartTV', 'device': {'OS': 'Tizen',
                'id': 'tv-id', 'modelName': 'test-model', 'PowerState': 'standby',
                'TokenAuthSupport': token_support}}).encode()
    class Session(Response):
        def get(self, url, **kwargs):
            assert self.trust_env is False
            assert kwargs['allow_redirects'] is False
            return Response()
    monkeypatch.setattr(tv.requests, 'Session', Session)
    info = tv.device_info('192.168.1.10')
    assert info['port'] == port and info['power'] == 0


def test_enabled_key_uses_library_once(paths, monkeypatch):
    w = worker(paths)
    atomic_json(w.credential, {'identity': 'tv', 'port': 8002, 'token': 'secret'})
    config = paths.load_config()
    config['devices']['tv'] = {'enabled': True, 'control': True}
    atomic_json(paths.settings, config)
    calls = []
    class Remote:
        def __init__(self, *args, **kwargs):
            assert kwargs['token'] == 'secret'
        def open(self):
            pass
        def close(self):
            calls.append('closed')
        def send_key(self, key):
            calls.append(key)
    monkeypatch.setattr(tv, 'SamsungTVWS', Remote)
    w.remote({'identity': 'tv', 'port': 8002}, operation='volume_up')
    assert calls == ['KEY_VOLUP', 'closed']


@pytest.mark.parametrize('operation,status,age,message', [
    ('', 'online', 0, 'operation missing'),
    ('pair', 'offline', 0, 'not online'),
    ('pair', 'online', 60, 'stale'),
])
def test_pairing_errors_explain_the_actual_precondition(paths, operation, status, age, message):
    from samsung_local.admin import UserRequestError
    atomic_json(paths.status, {'heartbeat': time.time() - age,
                              'devices': {'tv': {'kind': 'television', 'status': status}}})
    with pytest.raises(UserRequestError, match=message):
        act(paths, {'action': 'tv_command', 'device': 'tv', 'operation': operation})
    assert not list(paths.requests.glob('*.json'))


def test_rendered_pair_form_serializes_without_submit_button(paths, tmp_path):
    import os
    import re
    import shutil
    import subprocess
    from pathlib import Path
    php = os.environ.get('PHP_EXECUTABLE') or shutil.which('php')
    if not php:
        pytest.skip('PHP runtime unavailable')
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'sessions').mkdir()
    atomic_json(paths.status, {'heartbeat': time.time(), 'enabled': True, 'devices': {
        'tv': {'kind': 'television', 'status': 'online', 'samsung': True}}})
    result = subprocess.run([php, '-d', f"include_path={root / 'tests/php_stubs'}",
                             '-d', f"session.save_path={tmp_path / 'sessions'}",
                             str(root / 'webfrontend/htmlauth/index.php')],
                            env=dict(os.environ, SAMSUNG_TEST_RUNTIME=str(tmp_path)),
                            capture_output=True, text=True, check=True)
    assert not result.stderr
    form = next(form for form in re.findall(r'<form.*?</form>', result.stdout, re.S)
                if 'value="tv_command"' in form)
    assert 'data-ajax="false"' in form
    fields = dict(re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', form))
    assert fields['operation'] == 'pair'
    fields.pop('csrf')
    act(paths, fields)
    queued = read_json(next(paths.requests.glob('*.json')))
    assert queued['command']['operation'] == 'pair'
