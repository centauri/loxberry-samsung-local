import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("status,import_visible", [("online", False), ("auth_required", True)])
@pytest.mark.parametrize('themed', [False, True])
@pytest.mark.parametrize('language', ['en', 'nl'])
def test_php_renders_status_and_escapes_untrusted_names(tmp_path, status, import_visible, themed, language):
    php = os.environ.get("PHP_EXECUTABLE") or shutil.which("php")
    if not php:
        pytest.skip("PHP runtime not available")
    for folder in ("config", "data", "log", "sessions"):
        (tmp_path / folder).mkdir()
    (tmp_path / 'config/settings.json').write_text(json.dumps({'language': language}), encoding='utf-8')
    system_html = tmp_path / 'system'
    if themed:
        (system_html / 'css').mkdir(parents=True)
        for name in ('components.css', 'design-tokens.css'):
            (system_html / 'css' / name).touch()
    (tmp_path / "data/status.json").write_text(json.dumps({
        "heartbeat": time.time(), "enabled": True, "mqtt_connected": True,
        "compatibility_reports": {"example": {"format": "samsung-local-compatibility-v1",
                                               "test": "</script><script>alert('unsafe')</script>"}},
        "topic_prefix": "samsunglocal/fixture", "devices": {"example": {
            "status": status, "name": '<script>alert("unsafe")</script>', "samsung": True,
            "state": {"power": 1}, "host": "192.0.2.5", "secure_port": 49161}}}), encoding="utf-8")
    result = subprocess.run([php, "-d", "disable_functions=str_starts_with,str_ends_with",
                             "-d", f"include_path={ROOT / 'tests/php_stubs'}",
                             "-d", f"session.save_path={tmp_path / 'sessions'}",
                             str(ROOT / "webfrontend/htmlauth/index.php")],
                            capture_output=True, text=True, encoding='utf-8', check=True,
                            env=dict(os.environ, SAMSUNG_TEST_RUNTIME=str(tmp_path),
                                     SAMSUNG_TEST_SYSTEM_HTML=str(system_html)))
    assert not result.stderr
    assert '<script>alert(' not in result.stdout
    assert '&lt;script&gt;' in result.stdout
    assert 'name="csrf"' in result.stdout
    assert ('Connected' if language == 'en' else 'Verbonden') in result.stdout
    assert (('Advanced: import existing credentials' if language == 'en' else 'Geavanceerd: bestaande toegangsgegevens importeren') in result.stdout) is import_visible
    assert ('sl-themed' in result.stdout) is themed
    assert ('sl-legacy' in result.stdout) is not themed
    assert ('Download this report' if language == 'en' else 'Dit rapport downloaden') in result.stdout
    assert 'type="application/json"' in result.stdout
    assert ('Help and support' if language == 'en' else 'Hulp en ondersteuning') in result.stdout
    assert ('Choose the right support location' if language == 'en' else 'Waar kun je terecht?') in result.stdout
    assert ('friendly name is deliberately omitted' if language == 'en' else 'bewust weggelaten uit rapporten') in result.stdout
    assert f'lang="{language}"' in result.stdout
    assert result.stdout.index('id="settings-title"') < result.stdout.index('id="ui-language"')
    assert 'samsung-local-compatibility-v1' in result.stdout


def test_installation_archive_layout_modes_and_no_secrets(tmp_path):
    spec = importlib.util.spec_from_file_location("build", ROOT / "tools/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = module.build(tmp_path)
    with zipfile.ZipFile(target) as archive:
        names = set(archive.namelist())
        assert {"plugin.cfg", "dpkg/apt", "postroot.sh", "preupgrade.sh", "bin/samsung_local/upgrade.py", "bin/requirements.txt",
                "webfrontend/htmlauth/index.php", "webfrontend/htmlauth/samsung-local.css", "bin/licenses/LocalThings-LICENSE"} <= names
        assert not any(n.startswith(("tests/", ".git/")) or n.endswith((".pem", ".key")) for n in names)
        assert archive.getinfo("postroot.sh").external_attr >> 16 & 0o111 == 0o111
        assert all(b"\r\n" not in archive.read(n) for n in names if not n.endswith(".png"))
        assert b"3cc0931e4758cb11ba8b23520db9d6185b8f1ea0" in archive.read("bin/requirements.txt")


def test_php_support_download_contains_only_prepared_report(tmp_path):
    php = os.environ.get('PHP_EXECUTABLE') or shutil.which('php')
    if not php:
        pytest.skip('PHP runtime not available')
    for folder in ('config', 'data', 'log', 'sessions'):
        (tmp_path / folder).mkdir()
    (tmp_path / 'data/status.json').write_text(json.dumps({
        'devices': {'private-device': {'host': 'private-address'}},
        'support_report': {'format': 1, 'devices': []}}))
    page = json.dumps(str(ROOT / 'webfrontend/htmlauth/index.php').replace('\\', '/'))
    result = subprocess.run([php, '-d', f"include_path={ROOT / 'tests/php_stubs'}",
        '-d', f"session.save_path={tmp_path / 'sessions'}", '-r',
        '$_GET["download"]="diagnostics"; include ' + page + ';'], capture_output=True, text=True,
        check=True, env=dict(os.environ, SAMSUNG_TEST_RUNTIME=str(tmp_path)))
    assert not result.stderr
    assert json.loads(result.stdout) == {'format': 1, 'devices': []}
