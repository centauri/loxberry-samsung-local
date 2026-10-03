import queue
import socket
import threading
from types import SimpleNamespace

import cbor2
import pytest
from smartthings_local.protocol.coap import build_coap, parse_coap

from samsung_local import discovery, worker
from samsung_local.service import merge_discovery

DI = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def sample(host="192.0.2.10", **extra):
    return dict({"key": DI, "di": DI, "host": host, "plaintext_port": 5683,
                 "secure_port": 49161, "seen_at": 1, "status": "discovered", "samsung": True}, **extra)


def test_ip_change_tracks_same_identity():
    registry = {DI: sample(status="online", identity_verified=True)}
    merge_discovery(registry, [sample("192.0.2.11")])
    assert len(registry) == 1
    assert registry[DI]["host"] == "192.0.2.11"
    assert not registry[DI]["identity_verified"]


def test_duplicate_identity_refuses_connections():
    registry = {}
    merge_discovery(registry, [sample(), sample("192.0.2.11")])
    assert registry[DI]["status"] == "identity_conflict"


def test_failed_probe_does_not_erase_existing_endpoint():
    registry = {DI: sample(status="online")}
    merge_discovery(registry, [sample(secure_port=None)])
    assert registry[DI]["secure_port"] == 49161


def test_pki_is_diagnosed_without_stateful_authentication(monkeypatch):
    monkeypatch.setattr(discovery, "read_ocf_responder", lambda *a, **k: SimpleNamespace(
        has_identity=True, di=DI, rt=("x.com.samsung.device",), name="Washer", secure_ports=(49161,)))
    monkeypatch.setattr(discovery, "probe_dtls_ports", lambda *a, **k: SimpleNamespace(selected_port=49161))
    calls = []
    def read(host, href, **kwargs):
        calls.append(href)
        return SimpleNamespace(code=69, payload=cbor2.dumps({"oxms": [2, 65282], "owned": True,
                                                            "rowneruuid": "do-not-publish"}))
    monkeypatch.setattr(discovery, "read_plaintext_ocf_resource", read)
    result = discovery.inspect_host("192.0.2.10", 5683)
    assert result["status"] == "auth_required"
    assert "rowneruuid" not in result["security"]
    assert calls == ["/oic/sec/doxm"]


def test_missing_advertisement_uses_only_bounded_stateless_fallback(monkeypatch):
    monkeypatch.setattr(discovery, "read_ocf_responder", lambda *a, **k: SimpleNamespace(
        has_identity=True, di=DI, rt=("x.com.samsung.device",), name="Washer", secure_ports=()))
    probed = []
    def probe(host, ports, **kw):
        probed.extend(ports)
        return SimpleNamespace(selected_port=49158)
    monkeypatch.setattr(discovery, "probe_dtls_ports", probe)
    monkeypatch.setattr(discovery, "read_plaintext_ocf_resource", lambda *a, **k: SimpleNamespace(code=132))
    found = discovery.inspect_host('192.0.2.10', 5683)
    assert probed == [5684, *range(49152, 49161)]
    assert found['secure_port'] == 49158


def test_protected_batch_requires_credentials_not_missing_mapping(paths):
    from smartthings_local.errors import AuthorizationError
    obj = worker.DeviceWorker(sample(), {}, 30, paths, queue.Queue(), ('192.0.2.10', 49161))
    class DeniedSession:
        def get(self, path, **kw):
            return (69, cbor2.dumps({'di': DI})) if path == ['oic', 'd'] else (129, b'')
    obj.session = DeniedSession()
    with pytest.raises(AuthorizationError):
        obj.monitor()


def test_identity_authorization_denial_uses_upstream_exception_contract():
    from smartthings_local.errors import AuthorizationError
    class Denied:
        def get(self, *args, **kwargs):
            return 131, b''
    with pytest.raises(AuthorizationError):
        worker.get_resource(Denied(), '/oic/d', required=True)


def test_plaintext_discovery_against_udp_fixture(monkeypatch):
    """Exercise the real pinned library's CoAP codec and OCF discovery helper over loopback."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.settimeout(0.2)
    stop = threading.Event()
    observed = []
    def serve():
        while not stop.is_set():
            try:
                data, peer = sock.recvfrom(65536)
                _, method, mid, token, options, _ = parse_coap(data)
                href = "/" + "/".join(v.decode() for n, v in options if n == 11)
                observed.append((method, href))
                values = {"/oic/d": {"di": DI, "n": "Fixture appliance", "rt": ["x.com.samsung.device"]},
                          "/oic/res": {"links": [{"href": "/oic/sec/doxm", "rt": ["oic.r.doxm"],
                                                    "p": {"sec": True, "port": 49161}}]},
                          "/oic/sec/doxm": {"owned": True, "oxms": [0]}}
                sock.sendto(build_coap(1, 69, mid, token, [(12, b"\x27\x10")], cbor2.dumps(values.get(href, {}))), peer)
            except socket.timeout:
                pass
    thread = threading.Thread(target=serve)
    thread.start()
    monkeypatch.setattr(discovery, "probe_dtls_ports", lambda *a, **k: SimpleNamespace(selected_port=49161))
    try:
        result = discovery.inspect_host("127.0.0.1", port)
        assert result is not None, observed
        assert result["key"] == DI
        assert result["secure_port"] == 49161
        assert result["samsung"]
        assert all(method == 1 for method, _ in observed)
    finally:
        stop.set()
        thread.join(2)
        sock.close()


class FakeSession:
    def __init__(self, resources):
        self.resources, self.reads, self.writes = resources, [], []

    def get(self, path, **kwargs):
        href = "/" + "/".join(path)
        self.reads.append(href)
        return (69, cbor2.dumps(self.resources[href])) if href in self.resources else (132, b"")

    def ping(self):
        pass


def test_authenticated_identity_mismatch_stops_before_reading_resources(paths):
    obj = worker.DeviceWorker(sample(), {}, 30, paths, queue.Queue(), ("192.0.2.10", 49161))
    obj.session = FakeSession({"/oic/d": {"di": "11111111-2222-3333-4444-555555555555"}})
    with pytest.raises(worker.IdentityMismatch):
        obj.monitor()
    assert obj.session.reads == ["/oic/d"]


def test_worker_reads_mapped_state_but_never_security_links(paths):
    events = queue.Queue()
    obj = worker.DeviceWorker(sample(), {}, 30, paths, events, ("192.0.2.10", 49161))
    obj.session = FakeSession({"/oic/d": {"di": DI, "rt": ["oic.d.airconditioner"]},
        "/oic/res": {"links": [{"href": "/power/0"}, {"href": "/oic/sec/cred"}]},
        "/power/0": {"value": True}})
    original_emit = obj.emit
    def emit(**values):
        original_emit(**values)
        if values.get("status") == "online":
            obj.stop_event.set()
    obj.emit = emit
    obj.monitor()
    messages = [events.get_nowait()[2] for _ in range(events.qsize())]
    assert messages[-1]["state"]["power"] == 1
    assert messages[-1]["control_available"]
    assert "/oic/sec/cred" not in obj.session.reads


def test_compatibility_probe_reads_once_and_does_not_dispatch_commands(paths):
    events = queue.Queue()
    obj = worker.DeviceWorker(sample(), {"control": True, "_compatibility_probe": True}, 30,
                              paths, events, ("192.0.2.10", 49161))
    obj.session = FakeSession({"/oic/d": {"di": DI, "rt": ["oic.d.airconditioner"]},
        "/oic/res": {"links": [{"href": "/power/0"}]}, "/power/0": {"value": True}})
    obj.commands.put({"id": "not-dispatched", "value": "on", "timestamp": 0})
    obj.monitor()
    messages = [events.get_nowait()[2] for _ in range(events.qsize())]
    assert messages[-1]["legacy_verified"] is True
    assert obj.commands.qsize() == 1
    assert obj.session.writes == []


def test_compatibility_timeout_does_not_retry(paths, monkeypatch):
    attempts = []
    class TimeoutSession:
        def __init__(self, *args, **kwargs):
            pass
        def connect(self, **kwargs):
            attempts.append(1)
            raise TimeoutError()
        def close(self):
            pass
    monkeypatch.setattr(worker, "DtlsCoapSession", TimeoutSession)
    monkeypatch.setattr(worker, "load_auth", lambda *args: object())
    events = queue.Queue()
    obj = worker.DeviceWorker(sample(), {"_compatibility_probe": True}, 30,
                              paths, events, ("192.0.2.10", 49161))
    obj.run()
    assert attempts == [1]
    updates = [events.get_nowait()[2] for _ in range(events.qsize())]
    assert any(u.get('connection_report') == {'stage': 'authentication', 'error': 'TimeoutError'} for u in updates)
    result = updates[-1]
    assert result["status"] == "auth_required"
    assert "inconclusive" in result["diagnostic"]
