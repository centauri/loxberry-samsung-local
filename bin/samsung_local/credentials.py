"""Local-only cert minting based on upstream setup_cert.py's MIT recipe.

Copyright (c) 2026 Jack Nagy; see licenses/SmartThings-Local-LICENSE.
No ownership transfer, CA download, security POST or DELETE is implemented.
"""

import datetime as dt
import uuid

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from .storage import atomic_json, read_json, valid_key

CLIENT_UUID = "ab0b0ac4-aae9-4958-a04d-8ec36fe1b2f9"


def validate_pair(certificate, key):
    if not isinstance(certificate, str) or not isinstance(key, str):
        raise ValueError("Certificate and private key must be PEM text")
    if len(certificate) > 65536 or len(key) > 16384:
        raise ValueError("Credential is too large")
    try:
        cert = x509.load_pem_x509_certificate(certificate.encode())
        private = serialization.load_pem_private_key(key.encode(), password=None)
        fmt = (serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        if cert.public_key().public_bytes(*fmt) != private.public_key().public_bytes(*fmt):
            raise ValueError("mismatch")
        now = dt.datetime.now(dt.timezone.utc)
        if not cert.not_valid_before_utc <= now < cert.not_valid_after_utc:
            raise ValueError("validity")
    except Exception as error:
        raise ValueError("Invalid, expired or mismatched certificate/private key") from error


def ensure_certificate(folder):
    target = folder / "default.json"
    current = read_json(target)
    if current:
        validate_pair(current["certificate"], current["key"])
        return current
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, f"uuid:{CLIENT_UUID}"),
                      x509.NameAttribute(NameOID.COMMON_NAME, f"urn:uuid:{CLIENT_UUID}")])
    now = dt.datetime.now(dt.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(minutes=5)).not_valid_after(now + dt.timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=False)
            .add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False), False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH,
                                                ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .add_extension(x509.SubjectAlternativeName([
                x509.UniformResourceIdentifier(f"{prefix}{CLIENT_UUID}")
                for prefix in ("urn:uuid:", "uri:uuid:", "uuid:")
            ] + [x509.DNSName(CLIENT_UUID)]), False).sign(key, hashes.SHA256()))
    value = {"mode": "certificate", "certificate": cert.public_bytes(serialization.Encoding.PEM).decode(),
             "key": key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()).decode()}
    atomic_json(target, value)
    return value


def validate_import(value):
    if not isinstance(value, dict):
        raise ValueError("Expected a credential object")
    if value.get("mode") == "psk":
        try:
            identity = bytes.fromhex(value["identity_hex"])
            key = bytes.fromhex(value["key_hex"])
            from smartthings_local.protocol.auth import PskAuth
            PskAuth.validate_identity(identity)
            if len(key) not in (16, 32):
                raise ValueError("key length")
        except Exception as error:
            raise ValueError("Invalid PSK: use a 16-byte identity without NUL bytes and a 16- or 32-byte hexadecimal key") from error
        return {"mode": "psk", "identity_hex": identity.hex(), "key_hex": key.hex()}
    if value.get("mode") == "certificate":
        validate_pair(value.get("certificate"), value.get("key"))
        result = {k: value[k] for k in ("mode", "certificate", "key")}
        if value.get("server_uuid"):
            result["server_uuid"] = str(uuid.UUID(value["server_uuid"]))
        return result
    raise ValueError("Choose certificate or PSK import")


def load_auth(folder, device_key):
    from smartthings_local.protocol.auth import CertificateAuth, PskAuth, SamsungServerProfile
    value = read_json(folder / f"{valid_key(device_key)}.json") or ensure_certificate(folder)
    if value["mode"] == "psk":
        return PskAuth(identity=bytes.fromhex(value["identity_hex"]), key=bytes.fromhex(value["key_hex"]))
    profile = (SamsungServerProfile.bound_device(value["server_uuid"])
               if value.get("server_uuid") else None)
    return CertificateAuth.from_memory(value["certificate"], value["key"], server_profile=profile)
