import queue
import time
import uuid

from samsung_local import service
from samsung_local.storage import DEFAULTS, atomic_json


def test_duplicate_command_survives_service_restart(paths):
    key = "test-appliance"
    command = {"id": str(uuid.uuid4()), "timestamp": time.time(), "value": "on"}
    for attempt in range(2):
        obj = service.Service(paths)
        obj.registry[key] = {"status": "online", "host": "192.0.2.1", "secure_port": 49161}
        obj.config = dict(DEFAULTS, devices={key: {"control": True}})
        class Worker:
            commands = queue.Queue()
            def is_alive(self):
                return True
        obj.workers[key] = Worker()
        obj.handle_event(("command", key, command))
        assert obj.workers[key].commands.qsize() == (1 if attempt == 0 else 0)
        obj.db.close()
        obj.executor.shutdown()


def test_disabled_control_never_dispatches(paths):
    obj = service.Service(paths)
    obj.registry["test"] = {"status": "online"}
    obj.handle_event(("command", "test", {"id": str(uuid.uuid4()), "timestamp": time.time(), "value": "on"}))
    assert obj.db.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
    obj.db.close()
    obj.executor.shutdown()


def test_old_endpoint_update_is_ignored(paths):
    obj = service.Service(paths)
    obj.registry["test"] = {"host": "192.0.2.2", "secure_port": 49161, "status": "discovered"}
    obj.handle_event(("device", "test", {"_endpoint": ("192.0.2.1", 49161), "status": "online"}))
    assert obj.registry["test"]["status"] == "discovered"
    obj.db.close()
    obj.executor.shutdown()


def test_failed_pki_attempt_does_not_repeat_without_user_retry(paths, monkeypatch):
    obj = service.Service(paths)
    obj.registry["test"] = {"samsung": True, "secure_port": 49161, "ocf_pki": True, "compatibility_attempted": True, "status": "discovered"}
    def forbidden(*args, **kwargs):
        raise AssertionError("No session permitted")
    monkeypatch.setattr(service, "DeviceWorker", forbidden)
    obj.reconcile()
    assert obj.registry["test"]["status"] == "auth_required"
    obj.db.close()
    obj.executor.shutdown()


def test_registry_does_not_persist_live_sensor_payload(paths):
    obj = service.Service(paths)
    obj.registry["test"] = {"status": "online", "state": {"power": 1}, "sensors": {"power": {}}}
    obj.save_registry()
    assert '"state"' not in paths.registry.read_text()
    obj.db.close()
    obj.executor.shutdown()


def test_invalid_config_pauses_service(paths, monkeypatch):
    obj = service.Service(paths)
    atomic_json(paths.settings, {"poll_seconds": -1})
    monkeypatch.setattr(obj.broker, "refresh", lambda: None)
    obj.tick()
    assert not obj.config["enabled"]
    assert obj.config_error
    obj.db.close()
    obj.executor.shutdown()


def test_reconnect_clears_removed_sensor_from_persisted_topic_inventory(paths):
    atomic_json(paths.registry, {"test": {"published_sensors": ["old_sensor"], "status": "offline"}})
    obj = service.Service(paths)
    obj.registry["test"].update(status="online", state={"power": 1}, last_success=time.time())
    calls = []
    obj.broker.connected.set()
    obj.broker.publish = lambda *args, **kwargs: calls.append(args)
    obj.publish_device("test")
    assert ("test/state/old_sensor", "") in calls
    assert obj.registry["test"]["published_sensors"] == ["power"]
    obj.db.close()
    obj.executor.shutdown()


def test_explicit_compatibility_request_is_consumed_once(paths, monkeypatch):
    obj = service.Service(paths)
    obj.registry["test"] = {"host": "192.0.2.1", "samsung": True, "secure_port": 49161,
                            "ocf_pki": True, "compatibility_attempted": True, "status": "auth_required"}
    created = []
    class Worker:
        def __init__(self, device, options, poll, paths, events, signature):
            self.compatibility_probe = options.get("_compatibility_probe", False)
            self.signature = signature
            self.alive = False
            created.append(options)
        def start(self):
            self.alive = True
        def is_alive(self):
            return self.alive
        def stop(self):
            self.alive = False
    monkeypatch.setattr(service, "DeviceWorker", Worker)
    obj.request({"action": "compatibility", "device": "test"})
    obj.reconcile()
    assert len(created) == 1
    assert created[0]["control"] is False
    assert not obj.compatibility_requested
    obj.reconcile()  # Running probe must not be stopped by the PKI hint.
    assert obj.workers["test"].is_alive()
    obj.workers["test"].alive = False
    obj.registry["test"].update(status="auth_required", diagnostic="Test inconclusive")
    obj.reconcile()
    assert len(created) == 1
    assert obj.registry["test"]["diagnostic"] == "Test inconclusive"
    obj.db.close()
    obj.executor.shutdown()


def test_verified_legacy_device_is_not_reblocked_by_discovery_hint():
    from samsung_local.service import merge_discovery
    existing = {"test": {"host": "192.0.2.1", "secure_port": 49161, "legacy_verified": True,
                         "status": "offline"}}
    merge_discovery(existing, [{"key": "test", "host": "192.0.2.2", "secure_port": 49162,
                               "ocf_pki": True, "status": "auth_required", "seen_at": 1}])
    assert existing["test"]["status"] == "discovered"


def test_pki_hint_does_not_overwrite_resource_failure_status(paths):
    obj = service.Service(paths)
    obj.registry["test"] = {"host": "192.0.2.1", "secure_port": 49161, "samsung": True,
                            "ocf_pki": True, "status": "unsupported", "diagnostic": "No mapped resources"}
    obj.reconcile()
    assert obj.registry["test"]["status"] == "unsupported"
    assert obj.registry["test"]["diagnostic"] == "No mapped resources"
    assert not obj.workers
    obj.request({"action": "retry", "device": "test"})
    assert obj.compatibility_requested == {"test"}
    obj.db.close()
    obj.executor.shutdown()


def test_automatic_compatibility_persists_before_connect_and_promotes(paths, monkeypatch):
    from samsung_local.storage import read_json
    obj = service.Service(paths)
    obj.registry['test'] = {'host': '192.0.2.1', 'secure_port': 49161, 'samsung': True,
                            'ocf_pki': True, 'status': 'auth_required'}
    created = []
    class Worker:
        def __init__(self, device, options, poll, paths, events, signature):
            self.signature = signature
            self.compatibility_probe = options.get('_compatibility_probe', False)
            self.alive = False
            created.append(options)
        def start(self):
            assert read_json(paths.registry)['test']['compatibility_attempted']
            self.alive = True
        def is_alive(self):
            return self.alive
        def stop(self):
            self.alive = False
    monkeypatch.setattr(service, 'DeviceWorker', Worker)
    obj.reconcile()
    assert len(created) == 1
    assert created[0]['_compatibility_probe'] and not created[0]['control']
    obj.reconcile()
    assert len(created) == 1
    obj.handle_event(('device', 'test', {'_endpoint': ('192.0.2.1', 49161),
                                       'legacy_verified': True, 'status': 'online'}))
    obj.workers['test'].alive = False
    obj.reconcile()
    assert len(created) == 2
    assert not created[1].get('_compatibility_probe')
    obj.db.close()
    obj.executor.shutdown()


def test_restart_does_not_repeat_interrupted_automatic_test(paths, monkeypatch):
    atomic_json(paths.registry, {'test': {'host': '192.0.2.1', 'secure_port': 49161,
        'samsung': True, 'ocf_pki': True, 'status': 'discovered', 'compatibility_attempted': True}})
    obj = service.Service(paths)
    monkeypatch.setattr(service, 'DeviceWorker', lambda *a: (_ for _ in ()).throw(AssertionError('No session')))
    obj.reconcile()
    assert obj.registry['test']['status'] == 'auth_required'
    obj.db.close()
    obj.executor.shutdown()


def test_tv_is_classified_without_repeated_appliance_connections(paths, monkeypatch):
    obj = service.Service(paths)
    obj.registry['tv'] = {'samsung': True, 'host': '192.0.2.1', 'secure_port': 45955,
                           'rt': ['oic.d.tv'], 'status': 'offline'}
    monkeypatch.setattr(service, 'DeviceWorker', lambda *a: (_ for _ in ()).throw(AssertionError('No appliance session')))
    obj.reconcile()
    assert obj.registry['tv']['kind'] == 'television'
    assert obj.registry['tv']['status'] == 'unsupported'
    assert 'profile' in obj.registry['tv']['diagnostic']
    obj.db.close()
    obj.executor.shutdown()


def test_disabled_device_never_auto_tests(paths, monkeypatch):
    obj = service.Service(paths)
    obj.config = dict(DEFAULTS, devices={'test': {'enabled': False}})
    obj.registry['test'] = {'samsung': True, 'secure_port': 49161, 'ocf_pki': True}
    monkeypatch.setattr(service, 'DeviceWorker', lambda *a: (_ for _ in ()).throw(AssertionError('Disabled')))
    obj.reconcile()
    assert obj.registry['test']['status'] == 'disabled'
    assert not obj.compatibility_requested
    obj.db.close()
    obj.executor.shutdown()
