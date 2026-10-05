"""Supervisor, registry, discovery scheduling and status publication."""

import copy
import json
import logging
import queue
import signal
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from . import __version__
from .activity import Activity, reference
from .capabilities import device_type
from .credentials import ensure_certificate
from .diagnostics import support_report
from .compatibility_report import report as compatibility_report
from .discovery import scan
from .mqtt import Broker
from .storage import atomic_json, read_json
from .worker import DeviceWorker

LOG = logging.getLogger(__name__)
QUARANTINED = {"auth_required", "identity_mismatch", "identity_conflict", "unsupported"}


def merge_discovery(registry, discovered):
    grouped = {}
    for device in discovered:
        grouped.setdefault(device["key"], []).append(device)
    for key, devices in grouped.items():
        if key not in registry and len(registry) >= 128:
            continue
        hosts = {d["host"] for d in devices}
        old = registry.get(key, {})
        best = next((d for d in devices if d.get("secure_port")), devices[0])
        if len(hosts) > 1:
            registry[key] = dict(old or best, status="identity_conflict",
                                 diagnostic="Same OCF identity seen at multiple addresses; connection refused")
            continue
        # A failed probe is not evidence that an established endpoint moved.
        if old.get("secure_port") and not best.get("secure_port"):
            old["seen_at"] = best["seen_at"]
            continue
        merged = dict(old, **best)
        if old.get("legacy_verified") and merged.get("status") == "auth_required":
            merged["status"] = "discovered"
        if old.get("host") != best["host"] or old.get("secure_port") != best.get("secure_port"):
            merged["identity_verified"] = False
        if old.get("status") in QUARANTINED:
            merged["status"] = old["status"]
            merged["diagnostic"] = old.get("diagnostic", "")
        elif old.get("host") == best["host"] and old.get("secure_port") == best.get("secure_port"):
            merged["status"] = old.get("status", best["status"])
        registry[key] = merged


class Service:
    def __init__(self, paths):
        self.paths = paths
        self.started_at = time.time()
        self.stop_event = threading.Event()
        self.events = queue.Queue(maxsize=512)
        self.workers = {}
        self.config = paths.load_config()
        self.registry = read_json(paths.registry, {})
        if not isinstance(self.registry, dict):
            raise ValueError("Invalid registry; preserve and repair devices.json")
        for device in self.registry.values():
            if device.get("status") not in QUARANTINED:
                device["status"] = "offline"
        instance_path = paths.config / "instance.json"
        instance = read_json(instance_path)
        if not instance:
            instance = {"id": uuid.uuid4().hex[:12]}
            atomic_json(instance_path, instance)
        self.broker = Broker(instance["id"], self.events)
        self.db = sqlite3.connect(paths.config / "commands.sqlite3")
        self.db.execute("CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, stamp REAL)")
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="discovery")
        self.scan_future = None
        self.next_scan = 0
        self.last_scan = None
        self.discovery_error = ""
        self.config_error = ""
        self.last_registry = 0
        self.generation = {}
        self.compatibility_requested = set()
        self.activity = Activity()
        self.previous_sensor_keys = {key: set(device.get("published_sensors", []))
                                     for key, device in self.registry.items()}

    def stop(self, *_):
        self.stop_event.set()

    def request(self, value):
        action = value.get("action")
        if action == 'dryer_command':
            stamp = value.get('created_at', 0)
            if not max(self.started_at, time.time() - 30) <= stamp <= time.time() + 5:
                raise ValueError('Expired command or queued before service restart')
            self.handle_event(('command', value.get('device'), value['command']))
        elif action == "scan":
            LOG.info('Discovery requested from the UI')
            self.next_scan = 0
        elif action in {"retry", "compatibility"} and value.get("device") in self.registry:
            key = value["device"]
            LOG.info('Device %s: %s requested from the UI', reference(key), action)
            current = self.registry[key]
            if (action == "retry" and current.get("status") == "unsupported" and current.get("ocf_pki")
                    and not current.get("legacy_verified")
                    and not (self.paths.config / "credentials" / f"{key}.json").exists()):
                action = "compatibility"  # Explicit retry of an inconclusive read remains one-shot.
            if action == "compatibility":
                if self.registry[key].get("status") not in {"auth_required", "unsupported"}:
                    raise ValueError("Compatibility test requires an authentication-required device")
                if (self.paths.config / "credentials" / f"{key}.json").exists():
                    raise ValueError("Use Retry connection with imported credentials")
                self.compatibility_requested.add(key)
            self.registry[key]["status"] = "discovered"
            self.registry[key]["diagnostic"] = ""
            self.generation[key] = self.generation.get(key, 0) + 1
        else:
            raise ValueError("Unknown request")

    def reconcile(self):
        for key, device in self.registry.items():
            options = self.config["devices"].get(key, {})
            allowed = self.config["enabled"] and options.get("enabled", True)
            if not allowed:
                device["status"] = "disabled"
            elif device.get("status") == "disabled":
                device["status"] = "discovered"
            credential = self.paths.config / "credentials" / f"{key}.json"
            has_import = credential.exists()
            kind = device_type(device.get("rt", []), {})
            if kind in {"television", "network_audio"}:
                device.update(kind=kind, status="unsupported" if allowed else "disabled",
                              connection_report={"stage": "not_attempted", "error": "UnsupportedMediaProfile"},
                              diagnostic="Samsung TV/audio OCF profile discovered. Appliance authentication and mappings do not support this profile; automatic connection attempts are stopped.")
                public = device.get('media_inventory')
                if public:
                    device['model'] = public.get('identity', {}).get('mnmo', '')
                    device['connection_report'] = {'stage': 'public_inventory', 'error': 'ProtectedAccessNotTested'}
                    device['diagnostic'] = 'TV/audio public inventory collected. Protected access and remote control are not established; a TV-specific integration is required.'
            worker = self.workers.get(key)
            if (allowed and device.get("samsung") and device.get("secure_port")
                    and device.get("ocf_pki") and not has_import and not device.get("legacy_verified")
                    and not device.get("compatibility_attempted") and not worker
                    and device.get("status") not in {"unsupported", "identity_mismatch", "identity_conflict"}):
                self.compatibility_requested.add(key)
                device["status"] = "discovered"
                device["diagnostic"] = "Checking certificate compatibility automatically with read-only requests."
            probing = key in self.compatibility_requested or (
                worker is not None and getattr(worker, "compatibility_probe", False) and worker.is_alive())
            if (allowed and device.get("ocf_pki") and not has_import and not device.get("legacy_verified")
                    and not probing and device.get("status") not in {"unsupported", "identity_mismatch", "identity_conflict"}):
                device["status"] = "auth_required"
                if not device.get("diagnostic") or device["diagnostic"].startswith("Newer OCF-PKI profile detected"):
                    device["diagnostic"] = "Automatic compatibility attempt completed or interrupted. Retry the read-only test or import existing credentials if needed."
            allowed = (allowed and device.get("samsung") and device.get("secure_port")
                       and device.get("status") not in QUARANTINED)
            signature = (device.get("host"), device.get("secure_port"), json.dumps(options, sort_keys=True),
                         self.config["poll_seconds"], credential.stat().st_mtime_ns if has_import else 0,
                         self.generation.get(key, 0))
            worker = self.workers.get(key)
            if worker and (not allowed or signature != worker.signature):
                worker.stop()
                if worker.is_alive():
                    continue  # Never open a second session until the old owner exits.
                del self.workers[key]
                worker = None
            if worker and not worker.is_alive():
                del self.workers[key]
                worker = None
            if allowed and not worker and len(self.workers) < 32:
                worker_options = dict(options)
                if key in self.compatibility_requested:
                    worker_options.update(control=False, _compatibility_probe=True)
                    self.compatibility_requested.remove(key)
                    device["compatibility_attempted"] = True
                    # Persist before opening a session: restart/discovery must not
                    # repeatedly probe a device that refuses this credential.
                    self.save_registry()
                worker = DeviceWorker(device, worker_options, self.config["poll_seconds"], self.paths,
                                      self.events, signature)
                self.workers[key] = worker
                worker.start()

    def publish_device(self, key):
        if not self.broker.connected.is_set():
            return
        device = self.registry[key]
        online = device.get("status") == "online"
        self.broker.publish(f"{key}/availability", "online" if online else "offline")
        self.broker.publish(f"{key}/meta", {"name": device.get("name"), "type": device.get("kind", "unknown"),
            "status": device.get("status"), "sensors": device.get("sensors", {}),
            "control_enabled": self.config["devices"].get(key, {}).get("control", False),
            "power_control_available": device.get("control_available", False)})
        if online:
            state = device.get("state", {})
            self.broker.publish(f"{key}/state", dict(state, updated_at=device.get("last_success")))
            current = set(state)
            for stale in self.previous_sensor_keys.get(key, set()) - current:
                self.broker.publish(f"{key}/state/{stale}", "")
            self.previous_sensor_keys[key] = current
            device["published_sensors"] = sorted(current)
            for name, value in state.items():
                self.broker.publish(f"{key}/state/{name}", value)
            self.broker.publish(f"{key}/updated_at", device.get("last_success", 0))

    def handle_event(self, event):
        kind, key, value = event
        if key not in self.registry:
            return
        if kind == "device":
            endpoint = value.pop("_endpoint", None)
            current = self.registry[key]
            if endpoint != (current.get("host"), current.get("secure_port")):
                return
            if not self.config["enabled"] or not self.config["devices"].get(key, {}).get("enabled", True):
                return
            self.registry[key].update(value)
            if "legacy_verified" in value:
                self.save_registry()
            self.publish_device(key)
        elif kind == "result":
            LOG.info('Device %s: command result=%s', reference(key), value.get('result'))
            self.registry[key]['last_command'] = dict(value, at=time.time())
            self.broker.publish(f"{key}/command_result", value, retain=False)
        elif kind == "command":
            worker = self.workers.get(key)
            options = self.config["devices"].get(key, {})
            if (not self.config["enabled"] or not options.get("enabled", True) or not options.get("control")
                    or self.registry[key].get("status") != "online" or not worker or not worker.is_alive()):
                self.handle_event(('result', key, {"id": value["id"], "result": "disabled_or_offline"}))
                return
            try:
                self.db.execute("DELETE FROM commands WHERE stamp < ?", (time.time() - 120,))
                self.db.execute("INSERT INTO commands VALUES (?, ?)", (value["id"], value["timestamp"]))
                self.db.commit()  # Record before dispatch: restart must not replay a write.
            except sqlite3.IntegrityError:
                self.db.rollback()
                return
            try:
                worker.commands.put_nowait(value)
            except queue.Full:
                self.handle_event(('result', key, {"id": value["id"], "result": "busy"}))

    def save_status(self):
        atomic_json(self.paths.status, {"version": __version__, "heartbeat": time.time(),
            "enabled": self.config["enabled"], "mqtt_connected": self.broker.connected.is_set(),
            "mqtt_error": self.broker.error, "topic_prefix": self.broker.base,
            "scanning": self.scan_future is not None, "last_scan": self.last_scan,
            "discovery_error": self.discovery_error, "config_error": self.config_error,
            "compatibility_reports": {key: compatibility_report(d) for key, d in self.registry.items()},
            "devices": self.registry, "support_report": support_report(self.registry)})
        if time.monotonic() - self.last_registry >= 60:
            self.save_registry()

    def save_registry(self):
        # Avoid persisting the rapidly changing sensor state on the SD card.
        atomic_json(self.paths.registry, {key: {k: v for k, v in d.items()
            if k not in {"state", "sensors", "compatibility_evidence", "connection_report"}} for key, d in self.registry.items()})
        self.last_registry = time.monotonic()

    def tick(self):
        try:
            self.config = self.paths.load_config()
            self.config_error = ""
        except (ValueError, OSError):
            self.config_error = "Invalid settings file; service paused until repaired"
            self.config = dict(self.config, enabled=False)
        self.broker.refresh()
        for path in list(self.paths.requests.glob("*.json"))[:32]:
            try:
                self.request(read_json(path, {}))
            except (ValueError, OSError, AttributeError):
                LOG.warning("Invalid local UI request discarded")
            finally:
                path.unlink(missing_ok=True)
        if self.scan_future and self.scan_future.done():
            try:
                found = self.scan_future.result()
                previous = {k: (d.get('host'), d.get('secure_port')) for k, d in self.registry.items()}
                merge_discovery(self.registry, found)
                added = set(self.registry) - set(previous)
                moved = {k for k in set(self.registry) & set(previous)
                         if previous[k] != (self.registry[k].get('host'), self.registry[k].get('secure_port'))}
                LOG.info('Discovery completed: responses=%d; new=%d; endpoint_changes=%d; registered=%d',
                         len(found), len(added), len(moved), len(self.registry))
                for key in sorted(added | moved):
                    LOG.info('Device %s: %s', reference(key), 'discovered' if key in added else 'endpoint changed')
                self.discovery_error = ""
                self.last_scan = time.time()
                self.save_registry()
            except Exception as error:
                self.discovery_error = "Discovery failed: " + type(error).__name__
                LOG.warning(self.discovery_error)
            self.scan_future = None
        if self.config["enabled"] and not self.scan_future and time.monotonic() >= self.next_scan:
            LOG.info('Discovery started: configured_networks=%d; known_devices=%d',
                     len(self.config['networks']), len(self.registry))
            self.scan_future = self.executor.submit(scan, copy.deepcopy(self.config),
                                                   copy.deepcopy(list(self.registry.values())), self.stop_event)
            self.next_scan = time.monotonic() + self.config["scan_seconds"]
        for _ in range(512):
            try:
                self.handle_event(self.events.get_nowait())
            except queue.Empty:
                break
        self.reconcile()
        self.activity.observe(self.registry, self.broker.connected.is_set(), self.config['enabled'])
        if self.broker.reconnected.is_set():
            self.broker.reconnected.clear()
            for key in self.registry:
                self.publish_device(key)
        # Availability also changes when disabled, quarantined or rediscovered.
        for key, device in self.registry.items():
            self.broker.publish(f"{key}/availability", "online" if device.get("status") == "online" else "offline")
        self.save_status()

    def run(self):
        ensure_certificate(self.paths.config / "credentials")
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        LOG.info("Samsung Local %s started", __version__)
        try:
            while not self.stop_event.is_set():
                self.tick()
                self.stop_event.wait(2)
        finally:
            self.stop_event.set()
            for worker in self.workers.values():
                worker.stop()
            deadline = time.monotonic() + 12
            for worker in self.workers.values():
                worker.join(max(0, deadline - time.monotonic()))
            for key, device in self.registry.items():
                if device.get("status") == "online":
                    device["status"] = "offline"
                self.broker.publish(f"{key}/availability", "offline")
            self.broker.close()
            self.save_registry()
            self.save_status()
            self.db.close()
            self.executor.shutdown(wait=True, cancel_futures=True)
            LOG.info("Samsung Local stopped")
