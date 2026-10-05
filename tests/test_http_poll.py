import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_output_template_uses_post_separate_token_and_no_repeats():
    xml = php_run("require 'bin/loxone_outputs.php'; echo samsungOutputXml("
                  "['dryer'=>['kind'=>'dryer','control_available'=>true,'name'=>'Dryer',"
                  "'resources'=>['/washer/vs/0']]],['dryer'=>['control'=>true]],"
                  "'http://loxberry','samsunglocal','control-token');")
    root = ET.fromstring(xml)
    assert root.tag == 'VirtualOut'
    assert len(root) == 5
    for child in root:
        assert child.get('CmdOnMethod') == 'POST'
        assert child.get('CmdOff') == ''
        assert child.get('Repeat') == '0'
        assert child.get('CmdOn') == '/plugins/samsunglocal/control.php'
        assert 'token=control-token&device=dryer&operation=' in child.get('CmdOnPost')
        assert 'control-token' not in child.get('CmdOn')


def test_control_endpoint_rejects_get_and_readonly_token(tmp_path):
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config/http-control.json').write_text(json.dumps({'token': 'b' * 64}), encoding='utf-8')
    env = {'SAMSUNG_TEST_RUNTIME': str(tmp_path)}
    output = php_run("require 'webfrontend/html/control.php';", env=env)
    assert json.loads(output) == {'ok': False}
    output = php_run("require 'loxberry_system.php'; $_SERVER['REQUEST_METHOD']='POST'; "
                     "$_POST=['token'=>'" + 'a' * 64 + "']; require 'webfrontend/html/control.php';", env=env)
    assert json.loads(output) == {'ok': False}


def php_run(script, payload=None, env=None):
    php = os.environ.get('PHP_EXECUTABLE') or shutil.which('php')
    if not php:
        pytest.skip('PHP unavailable')
    result = subprocess.run([php, '-d', f'include_path={ROOT / "tests/php_stubs"}',
                             '-d', f'session.save_path={os.environ.get("TEMP", "/tmp")}', '-r', script],
                            input=json.dumps(payload), capture_output=True, text=True,
                            encoding='utf-8', cwd=ROOT, env=dict(os.environ, **(env or {})), check=True)
    assert not result.stderr
    return result.stdout


def fixture_status():
    return {'heartbeat': 1000, 'enabled': True, 'devices': {'dryer': {
        'name': '<Dryer & test>', 'status': 'online', 'state': {
            'power': 1, 'energy': 893800, 'operational_state_vs_0_state': 'Ready',
            'operational_state_vs_0_remainingTime': '03:08:00', 'model': '001',
            'other_state': 'Unrecognized', 'bad_remainingTime': '00:99:12'},
        'sensors': {'energy': {'unit': 'Wh'}}}}}


def test_mapping_template_and_body_agree():
    output = php_run("require 'bin/loxone_http.php'; $s=json_decode(stream_get_contents(STDIN),true); "
                     "$r=samsungHttpRows($s,1000); echo json_encode([$r,samsungHttpBody($r),"
                     "samsungHttpXml($r,'http://loxberry/plugins/samsunglocal/poll.php?token=test')]);",
                     fixture_status())
    rows, body, xml = json.loads(output)
    root = ET.fromstring(xml)
    assert root.tag == 'VirtualInHttp'
    assert root.get('PollingTime') == '30'
    assert len(root) == len(rows) == 7
    assert sorted(row['value'] for row in rows.values()) == [-1, 0, 1, 1, 1, 11280, 893800]
    for node, (key, row) in zip(root, rows.items()):
        assert node.tag == 'VirtualInHttpCmd'
        assert node.get('Check') == key + r'=\v'
        assert key + '=' in body
        assert node.get('Title') == row['label']
    assert 'model' not in xml
    assert 'bad_remainingTime' not in xml
    assert '&lt;Dryer &amp; test&gt;' in xml


def test_stale_and_offline_values_are_not_served():
    for now, online in [(1031, 'online'), (1000, 'offline')]:
        status = fixture_status()
        status['devices']['dryer']['status'] = online
        out = php_run("require 'bin/loxone_http.php'; $s=json_decode(stream_get_contents(STDIN),true); "
                      f"echo json_encode(samsungHttpRows($s,{now}));", status)
        rows = list(json.loads(out).values())
        assert rows[1]['value'] == 0
        assert all(r['value'] is None for r in rows[2:])
        if now == 1031:
            assert rows[0]['value'] == 0


def test_running_dryer_report_preserves_ids_and_converts_time():
    status = fixture_status()
    script = ("require 'bin/loxone_http.php'; $s=json_decode(stream_get_contents(STDIN),true); "
              "echo json_encode(samsungHttpRows($s,1000));")
    before = json.loads(php_run(script, status))
    state = status['devices']['dryer']['state']
    state.update({'operational_state_vs_0_state': 'Run',
                  'operational_state_vs_0_remainingTime': '03:13:00',
                  'operational_state_0_remainingTime': '03:13:00',
                  'operational_state_vs_0_progressPercentage': 1,
                  'operational_state_vs_0_progress': 'Drying',
                  'operational_state_0_currentJobState': 'Drying',
                  'operational_state_0_currentMachineState': 'active'})
    after = json.loads(php_run(script, status))
    by_key = {r['label'].split(': ')[-1]: r for r in after.values()}
    assert by_key['operational_state_vs_0_state']['value'] == 1
    assert by_key['operational_state_vs_0_remainingTime']['value'] == 11580
    assert by_key['operational_state_0_remainingTime']['value'] == 11580
    assert by_key['operational_state_vs_0_progressPercentage']['value'] == 1
    assert by_key['other_state']['value'] == -1
    assert by_key['operational_state_vs_0_progress']['value'] == 1
    assert by_key['operational_state_0_currentMachineState']['value'] == 1
    for key, row in before.items():
        assert after[key]['label'] == row['label']  # Existing imported XML remains valid.


@pytest.mark.parametrize('setting,expected', [('On', 1), ('Off', 0), ('Unknown', -1)])
def test_paused_dryer_wrinkle_prevention(setting, expected):
    status = fixture_status()
    status['devices']['dryer']['state'].update({
        'operational_state_vs_0_state': 'Pause',
        'operational_state_vs_0_remainingTime': '03:12:00',
        'washer_vs_0_wrinklePrevent': setting,
        'unrelated_option': 'On'})
    script = ("require 'bin/loxone_http.php'; $s=json_decode(stream_get_contents(STDIN),true); "
              "$rows=samsungHttpRows($s,1000); echo json_encode([$rows,"
              "samsungHttpBody($rows),samsungHttpXml($rows,'http://example.test')]);")
    rows, body, xml = json.loads(php_run(script, status))
    by_key = {r['label'].split(': ')[-1]: r for r in rows.values()}
    assert by_key['operational_state_vs_0_state']['value'] == 2
    assert by_key['operational_state_vs_0_remainingTime']['value'] == 11520
    assert by_key['washer_vs_0_wrinklePrevent']['value'] == expected
    assert 'unrelated_option' not in by_key
    identifier = next(k for k, r in rows.items() if r['label'].endswith('washer_vs_0_wrinklePrevent'))
    assert f'{identifier}={expected}\n' in body
    command = next(n for n in ET.fromstring(xml) if n.get('Check') == identifier + r'=\v')
    assert command.get('Comment') == '-1=unknown; 0=wrinkle prevention off; 1=wrinkle prevention on'


def test_endpoint_requires_token_and_does_not_expose_status(tmp_path):
    for name in ['data', 'config']:
        (tmp_path / name).mkdir()
    token = 'a' * 64
    (tmp_path / 'config/http-poll.json').write_text(json.dumps({'token': token}), encoding='utf-8')
    status = fixture_status()
    status['private'] = 'DO-NOT-EXPOSE'
    (tmp_path / 'data/status.json').write_text(json.dumps(status), encoding='utf-8')
    env = {'SAMSUNG_TEST_RUNTIME': str(tmp_path)}
    for provided in ['', 'b' * 64]:
        output = php_run("$_GET['token']='" + provided + "'; require 'webfrontend/html/poll.php';", env=env)
        assert output == 'Forbidden'
    output = php_run("$_GET['token']='" + token + "'; require 'webfrontend/html/poll.php';", env=env)
    assert 'DO-NOT-EXPOSE' not in output
    assert token not in output
    assert len(output.splitlines()) == 2  # Fixture is stale: availability only.
    assert all(line.endswith('=0') for line in output.splitlines())


def test_xml_download_address_and_invalid_urls(tmp_path):
    for name in ['data', 'config']:
        (tmp_path / name).mkdir()
    token = 'c' * 64
    (tmp_path / 'config/http-poll.json').write_text(json.dumps({'token': token}), encoding='utf-8')
    (tmp_path / 'data/status.json').write_text(json.dumps(fixture_status()), encoding='utf-8')
    env = {'SAMSUNG_TEST_RUNTIME': str(tmp_path)}
    xml = php_run("$_GET=['download'=>'http-xml','base_url'=>'http://loxberry:8080']; "
                  "require 'webfrontend/htmlauth/index.php';", env=env)
    root = ET.fromstring(xml)
    assert root.get('Address') == 'http://loxberry:8080/plugins/config/poll.php?token=' + token
    assert len(root) == 7
    for url in ['file:///etc/passwd', 'http://user:pass@loxberry', 'http://loxberry/unexpected']:
        output = php_run("$_GET=['download'=>'http-xml','base_url'=>'" + url + "']; "
                         "require 'webfrontend/htmlauth/index.php';", env=env)
        assert 'Enter the LoxBerry base URL' in output
        assert token not in output
