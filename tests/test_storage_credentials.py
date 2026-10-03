import copy
import json
import os

import pytest
from cryptography import x509
from cryptography.x509.oid import NameOID

from samsung_local.admin import act
from samsung_local.credentials import CLIENT_UUID, ensure_certificate, load_auth, validate_import
from samsung_local.storage import DEFAULTS, atomic_json, read_json, validate_config


def test_private_atomic_write(paths):
    atomic_json(paths.settings, DEFAULTS)
    assert paths.load_config()["poll_seconds"] == 30
    assert not list(paths.config.glob(".write-*"))
    if os.name == "posix":
        assert paths.settings.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("override", [
    {"poll_seconds": 0}, {"poll_seconds": True}, {"scan_seconds": 30}, {"enabled": "false"},
    {"schema": 2}, {"networks": ["0.0.0.0/0"]}, {"networks": ["192.168.0.0/16"]},
    {"networks": ["8.8.8.0/24"]}, {"devices": {"../x": {}}},
    {"devices": {"ok": {"control": "true"}}},
])
def test_bad_config_rejected(override):
    with pytest.raises(ValueError):
        validate_config(dict(DEFAULTS, **override))


def test_corrupt_storage_not_silently_replaced(paths):
    paths.settings.write_text("{broken")
    with pytest.raises(json.JSONDecodeError):
        paths.load_config()


def test_certificate_recipe_persistence_and_auth(paths):
    folder = paths.config / "credentials"
    first = ensure_certificate(folder)
    second = ensure_certificate(folder)
    assert first == second
    cert = x509.load_pem_x509_certificate(first["certificate"].encode())
    assert cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value == f"urn:uuid:{CLIENT_UUID}"
    assert len(cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value) == 4
    assert cert.signature_hash_algorithm.name == "sha256"
    assert validate_import(first) == first
    assert load_auth(folder, "test") is not None


def test_import_mismatched_certificate(paths, tmp_path):
    first = ensure_certificate(paths.config / "credentials")
    other = tmp_path / "other"
    other.mkdir()
    second = ensure_certificate(other)
    with pytest.raises(ValueError):
        validate_import(dict(first, key=second["key"]))


def test_valid_psk_import():
    value = {"mode": "psk", "identity_hex": "ab" * 16, "key_hex": "ab" * 16}
    assert validate_import(value) == value


@pytest.mark.parametrize("value", [
    {"mode": "psk", "identity_hex": "00", "key_hex": "ff" * 16},
    {"mode": "psk", "identity_hex": "zz", "key_hex": "ff" * 16},
    {"mode": "psk", "identity_hex": "ab", "key_hex": "ff"},
    {"mode": "other"},
])
def test_invalid_import(value):
    with pytest.raises(ValueError):
        validate_import(value)


def test_admin_does_not_overwrite_unrelated_device_settings(paths):
    config = copy.deepcopy(DEFAULTS)
    config["devices"]["first"] = {"control": False}
    atomic_json(paths.settings, config)
    atomic_json(paths.status, {"devices": {"second": {"control_available": True}}})
    act(paths, {"action": "device", "device": "second", "enabled": True, "control": True})
    assert paths.load_config()["devices"] == {
        "first": {"control": False}, "second": {"enabled": True, "control": True}}


def test_import_only_for_auth_required_device(paths):
    atomic_json(paths.status, {"devices": {"test": {"status": "online", "di": "example"}}})
    with pytest.raises(ValueError):
        act(paths, {"action": "import", "device": "test", "credentials": {}})
    assert not read_json(paths.config / "credentials" / "test.json")
