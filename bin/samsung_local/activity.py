"""Concise operational events without names, addresses or appliance payloads."""
import hashlib
import logging
import re
import time

LOG = logging.getLogger(__name__)


def reference(key):
    return hashlib.sha256(str(key).encode()).hexdigest()[:10]


def label(value):
    text = str(value or 'none')
    return text if re.fullmatch(r'[A-Za-z0-9_]{1,64}', text) else 'other'


class Activity:
    def __init__(self):
        self.devices = {}
        self.mqtt = None
        self.enabled = None
        self.summary_at = time.monotonic()

    def observe(self, registry, connected, enabled, now=None):
        now = time.monotonic() if now is None else now
        if connected != self.mqtt:
            LOG.info('MQTT %s', 'connected' if connected else 'disconnected; waiting/retrying')
            self.mqtt = connected
        if enabled != self.enabled:
            LOG.info('Automatic appliance reads %s', 'enabled' if enabled else 'paused')
            self.enabled = enabled
        for key, device in registry.items():
            status = label(device.get('status'))
            report = device.get('connection_report') or {}
            # Successful polling phases recur; only stable outcomes/errors matter.
            error = label(report.get('error'))
            state = (status, error)
            old = self.devices.get(key)
            if old != state:
                method = LOG.warning if status in {'offline', 'auth_required', 'identity_conflict', 'identity_mismatch'} else LOG.info
                method('Device %s: %s -> %s; type=%s; stage=%s; error=%s; readings=%d',
                       reference(key), old[0] if old else 'untracked', status,
                       label(device.get('kind')), label(report.get('stage')), error,
                       len(device.get('state', {})))
                self.devices[key] = state
        self.devices = {k: v for k, v in self.devices.items() if k in registry}
        if now - self.summary_at >= 900:
            LOG.info('Health summary: MQTT=%s; devices=%d; online=%d; mapped_readings=%d',
                     'connected' if connected else 'disconnected', len(registry),
                     sum(d.get('status') == 'online' for d in registry.values()),
                     sum(len(d.get('state', {})) for d in registry.values() if d.get('status') == 'online'))
            self.summary_at = now
