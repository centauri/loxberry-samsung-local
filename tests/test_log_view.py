import json
import logging
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from samsung_local.__main__ import log_handler


def test_real_handler_rotates_with_three_backups(tmp_path):
    handler = log_handler(tmp_path)
    try:
        assert handler.maxBytes == 1_000_000 and handler.backupCount == 3
        for i in range(55):
            handler.handle(logging.LogRecord('test', logging.INFO, '', 0, str(i) + 'x' * 100_000, (), None))
    finally:
        handler.close()
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        'samsung-local.log', 'samsung-local.log.1', 'samsung-local.log.2', 'samsung-local.log.3']
    assert all(p.stat().st_size < 1_000_000 for p in tmp_path.iterdir())


def test_php_pagination_bounds_and_fixed_filenames(tmp_path):
    php = os.environ.get('PHP_EXECUTABLE') or shutil.which('php')
    if not php:
        pytest.skip('PHP unavailable')
    helper = Path(__file__).resolve().parents[1] / 'webfrontend/htmlauth/log_view.php'
    (tmp_path / 'samsung-local.log').write_text('A' * 16384 + 'B' * 16384 + 'C' * 100, encoding='utf-8')
    (tmp_path / 'samsung-local.log.1').write_text('backup', encoding='utf-8')
    script = tmp_path / 'probe.php'
    script.write_text('<?php require $argv[1]; echo json_encode(samsungLogPage($argv[2], $argv[3], $argv[4]));', encoding='utf-8')
    def read(file, page):
        return json.loads(subprocess.check_output([php, str(script), str(helper), str(tmp_path), str(file), str(page)]))
    newest = read(0, 0)
    assert newest['pages'] == 3 and len(newest['text']) == 16384
    assert newest['text'].endswith('C' * 100)
    assert read(0, 999)['text'] == 'A' * 100
    assert read(1, 0)['text'] == 'backup'
    assert read('../../secret', -1) == newest
    assert read(3, 0)['pages'] == 0
