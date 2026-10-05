import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def php_export(status):
    php = os.environ.get('PHP_EXECUTABLE') or shutil.which('php')
    if not php:
        pytest.skip('PHP unavailable')
    script = ("require 'webfrontend/htmlauth/loxone_export.php'; "
              "$s=json_decode(stream_get_contents(STDIN),true); "
              "echo samsungTopicsCsv(samsungTopicRows($s));")
    return subprocess.run([php, '-r', script], input=json.dumps(status), text=True,
                          encoding='utf-8', capture_output=True, check=True, cwd=ROOT).stdout


def test_topic_inventory_uses_published_paths_and_escapes_csv():
    result = php_export({'topic_prefix': 'samsunglocal/abc', 'devices': {
        'dryer-1': {'name': '=unsafe,"name"', 'state': {
            'power': 1, 'energy': 893800, 'state': 'Ready',
            'remaining': '03:08:00', 'numeric_text': '001', 'missing': None},
            'sensors': {'energy': {'unit': 'Wh'}}}}})
    rows = list(csv.reader(io.StringIO(result)))
    by_topic = {r[0]: r for r in rows[1:]}
    assert len(by_topic) == 7  # Two availability topics and five scalar readings.
    power = by_topic['samsunglocal/abc/dryer-1/state/power']
    assert power[1] == 'samsunglocal_abc_dryer-1_state_power'
    assert power[2].startswith("'=unsafe")
    assert power[3] == 'number'
    assert by_topic['samsunglocal/abc/dryer-1/state/energy'][4] == 'Wh'
    assert by_topic['samsunglocal/abc/dryer-1/state/numeric_text'][3] == 'text'
    assert not any('/set/' in row[0] for row in rows)


def test_invalid_prefix_does_not_create_topic_inventory():
    assert len(list(csv.reader(io.StringIO(php_export({'topic_prefix': '../bad'}))))) == 1

