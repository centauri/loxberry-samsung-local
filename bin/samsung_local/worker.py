"""One owner thread per DTLS session; all appliance writes pass a fixed allowlist."""

import logging
import queue
import random
import threading
import time

import cbor2
from smartthings_local.errors import AuthenticationError, AuthorizationError
from smartthings_local.protocol.dtls_session import DtlsCoapSession

from .capabilities import PREFIX, batch_resources, device_type, directory_links, normalize, power_command, readable
from .compatibility_report import evidence
from .credentials import load_auth
from .discovery import identity
from .dryer_control import available as dryer_available, command as dryer_command

LOG = logging.getLogger(__name__)


class IdentityMismatch(ValueError):
    pass


def get_resource(session, href, required=False, diagnostics=None):
    code, body = session.get(href.strip("/").split("/"), timeout=5)
    if diagnostics is not None:
        diagnostics[href] = {"code": f"{code >> 5}.{code & 31:02d}", "bytes": len(body)}
    if code in (129, 131):
        if required:
            raise AuthorizationError()
        return None
    if code != 69:
        if required:
            raise ValueError("Required OCF resource unavailable")
        return None
    if len(body) > 65536:
        raise ValueError("OCF resource too large")
    return cbor2.loads(body)


class DeviceWorker(threading.Thread):
    def __init__(self, device, options, poll_seconds, paths, events, signature):
        super().__init__(name="appliance-" + device["key"][:8], daemon=True)
        self.device = dict(device)
        self.options, self.poll_seconds, self.paths, self.events = options, poll_seconds, paths, events
        self.signature = signature
        self.compatibility_probe = bool(options.get("_compatibility_probe"))
        self.stop_event = threading.Event()
        self.commands = queue.Queue(maxsize=8)
        self.session = None
        self.stage = "not_attempted"

    def emit(self, **values):
        try:
            self.events.put(("device", self.device["key"], dict(values, _endpoint=self.signature[:2])), timeout=1)
        except queue.Full:
            LOG.warning("Service event queue full; appliance update deferred")

    def stop(self):
        self.stop_event.set()
        if self.session:
            self.session.quiesce_for_close()

    def run(self):
        delay = 5
        while not self.stop_event.is_set():
            try:
                self.stage = "authentication"
                self.emit(connection_report={"stage": self.stage, "error": None}, compatibility_evidence={})
                self.session = DtlsCoapSession(self.device["host"], self.device["secure_port"],
                    auth=load_auth(self.paths.config / "credentials", self.device["key"]),
                    rate_limit_rps=3, write_max_attempts=1)
                self.session.connect(timeout=8)
                self.session.start_reader()
                self.monitor()
                return
            except (AuthenticationError, AuthorizationError) as error:
                self.emit(connection_report={"stage": self.stage, "error": type(error).__name__})
                self.emit(status="auth_required", legacy_verified=False,
                          diagnostic="Authentication or resource authorization rejected; import existing credentials if available")
                return  # Explicit retry or credential import required; do not hammer PKI appliances.
            except IdentityMismatch:
                self.emit(connection_report={"stage": "identity", "error": "IdentityMismatch"})
                self.emit(status="identity_mismatch", diagnostic="Connected device identity differs from discovery; connection refused")
                return
            except Exception as error:
                self.emit(connection_report={"stage": self.stage, "error": type(error).__name__})
                if not self.stop_event.is_set():
                    if self.compatibility_probe:
                        self.emit(status="auth_required", diagnostic="Read-only compatibility test inconclusive: " + type(error).__name__ + ". No automatic retry; check connectivity before trying again.")
                        return
                    self.emit(status="offline", diagnostic="Connection/read failed: " + type(error).__name__)
                    LOG.warning("Appliance session failed: %s; retrying with backoff", type(error).__name__)
            finally:
                if self.session:
                    self.session.close()
                    self.session = None
            self.stop_event.wait(delay + random.uniform(0, min(delay / 4, 5)))
            delay = min(delay * 2, 300)

    def monitor(self):
        session = self.session
        self.stage = "identity"
        device = get_resource(session, "/oic/d", required=True)
        if not isinstance(device, dict):
            raise ValueError("Invalid device identity representation")
        actual = identity(device.get("di"), self.device["host"], self.device["plaintext_port"])
        if actual != self.device["key"]:
            raise IdentityMismatch()
        self.stage = "resource_discovery"
        diagnostics = {}
        directory = get_resource(session, "/oic/res", diagnostics=diagnostics)
        links = directory_links(directory)
        # Samsung's known read-only seed is not always advertised in /oic/res.
        # Its batch representations may also be the only readable form of a child.
        collection = get_resource(session, "/device/0", diagnostics=diagnostics)
        seed = batch_resources(collection)
        links = sorted(set(links) | set(directory_links(collection)))
        info = seed.get("/information/vs/0")
        if info is None:
            info = get_resource(session, "/information/vs/0") if "/information/vs/0" in links else {}
        info = info if isinstance(info, dict) else {}
        kind = device_type(device.get("rt", self.device.get("rt", [])), info)
        self.emit(connection_report={"stage": "resource_discovery", "error": None},
                  compatibility_evidence=evidence(device, directory, collection, info, kind, diagnostics))
        hrefs = sorted({href for href in links if readable(href)} | {href for href in seed if readable(href)})[:128]
        self.emit(resource_diagnostics={"reads": diagnostics, "directory_links": len(directory_links(directory)),
                  "batch_representations": len(seed), "mapped_paths": hrefs})
        if not hrefs:
            if any(row["code"] in {"4.01", "4.03"} for row in diagnostics.values()):
                raise AuthorizationError()
            self.emit(connection_report={"stage": "mapping", "error": "NoMappedResources"}, status="unsupported", diagnostic="Connection and device identity checked; no mapped appliance resources found. Appliance-data authorization remains unconfirmed.", kind=kind)
            return
        stable_identity = not self.device["key"].startswith("host-")
        self.emit(kind=kind, model=str(info.get(PREFIX + "modelNum", ""))[:160],
                  resources=hrefs, identity_verified=stable_identity)
        self.stage = "readings"
        next_poll, next_ping = 0, 0
        resources = {}
        first_poll = True
        use_batch = bool(seed)
        while not self.stop_event.is_set():
            now = time.monotonic()
            if now >= next_poll:
                current_batch = seed if first_poll else (
                    batch_resources(get_resource(session, "/device/0", diagnostics=diagnostics)) if use_batch else {})
                first_poll = False
                fresh = {href: rep for href, rep in current_batch.items() if href in hrefs}
                for href in hrefs:
                    if self.stop_event.is_set():
                        return
                    if href in fresh:
                        continue
                    rep = get_resource(session, href, diagnostics=diagnostics)
                    if isinstance(rep, dict) and rep and set(rep) != {"href"}:
                        fresh[href] = rep
                if not fresh:
                    if any(row["code"] in {"4.01", "4.03"} for row in diagnostics.values()):
                        raise AuthorizationError()
                    self.emit(connection_report={"stage": "readings", "error": "NoUsableData"}, status="unsupported", diagnostic="Connected, but appliance resources returned no usable data. See resource diagnostics.",
                              resource_diagnostics={"reads": diagnostics, "mapped_paths": hrefs})
                    return
                resources = fresh
                self.emit(compatibility_evidence=evidence(device, directory,
                    [r for r in collection if isinstance(r, dict) and not readable(r.get("href"))]
                    + [{"href": h, "rep": r} for h, r in fresh.items()]
                    if isinstance(collection, list) else [{"href": h, "rep": r} for h, r in fresh.items()],
                    info, kind, diagnostics))
                state, sensors = normalize(resources, kind)
                if not state:
                    self.emit(connection_report={"stage": "mapping", "error": "NoMappedFields"}, status="unsupported", diagnostic="Appliance resources were read, but no sensor fields match this version's mappings.",
                              resource_diagnostics={"reads": diagnostics, "mapped_paths": hrefs})
                    return
                can_power = False
                try:
                    power_command(kind, resources, "off")
                    can_power = stable_identity
                except ValueError:
                    pass
                self.emit(connection_report={"stage": "readings", "error": None}, status="online", diagnostic="", state=state, sensors=sensors,
                          control_available=can_power or (stable_identity and dryer_available(kind, resources)), last_success=time.time(),
                          **({"legacy_verified": True} if self.compatibility_probe and stable_identity else {}))
                if self.compatibility_probe:
                    return  # The explicit diagnostic sends reads only, even if commands were queued.
                next_poll = time.monotonic() + self.poll_seconds
                next_ping = time.monotonic() + 15
            try:
                command = self.commands.get(timeout=0.5)
            except queue.Empty:
                command = None
            if command:
                outcome = "rejected"
                if stable_identity and self.options.get("control") and time.time() - command["timestamp"] <= 30:
                    attempted = False
                    try:
                        if 'operation' in command:
                            # Read interlocks again in the same authenticated session;
                            # never authorize a dryer write from a cached dashboard value.
                            latest = batch_resources(get_resource(session, '/device/0'))
                            for path in ['/power/vs/0', '/kidslock/vs/0', '/remotectrl/vs/0',
                                         '/operational/state/vs/0', '/washer/vs/0']:
                                if path not in latest:
                                    rep = get_resource(session, path)
                                    if isinstance(rep, dict):
                                        latest[path] = rep
                            live_config = self.paths.load_config()
                            if (not live_config['enabled'] or not live_config['devices'].get(self.device['key'], {}).get('control')
                                    or not live_config['devices'].get(self.device['key'], {}).get('enabled', True)
                                    or self.stop_event.is_set() or time.time() - command['timestamp'] > 30):
                                raise ValueError('Control disabled or command expired')
                            href, body = dryer_command(kind, latest, command['operation'])
                        else:
                            href, body = power_command(kind, resources, command["value"])
                        payload = cbor2.dumps(body)
                        attempted = True
                        code, _ = session.post(href.strip("/").split("/"), payload, timeout=5)
                        outcome = "accepted" if 64 <= code < 96 else "device_rejected"
                    except ValueError:
                        outcome = 'uncertain' if attempted else 'rejected'
                    except Exception:
                        outcome = "uncertain"  # Never retry a potentially completed write.
                    next_poll = 0
                try:
                    self.events.put(("result", self.device["key"], {"id": command["id"], "result": outcome}), timeout=1)
                except queue.Full:
                    LOG.warning("Command result queue full; result not published")
            if time.monotonic() >= next_ping:
                session.ping()
                next_ping = time.monotonic() + 15
