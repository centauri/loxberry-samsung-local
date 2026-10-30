"""Tizen v2 TV adapter. OCF remains discovery only; no security-resource writes.

Remote transport is provided by samsungtvws (LGPL-3.0), not copied here.
HTTP identity is continuity checking on a trusted LAN, not authenticated identity.
"""
import ipaddress
import json
import logging
import queue
import subprocess
import threading
import time

import requests
from samsungtvws import SamsungTVWS

from .storage import atomic_json, read_json

KEYS = {'volume_up': 'KEY_VOLUP', 'volume_down': 'KEY_VOLDOWN', 'mute': 'KEY_MUTE',
        'home': 'KEY_HOME', 'source': 'KEY_SOURCE', 'up': 'KEY_UP', 'down': 'KEY_DOWN',
        'left': 'KEY_LEFT', 'right': 'KEY_RIGHT', 'enter': 'KEY_ENTER', 'back': 'KEY_RETURN',
        'play': 'KEY_PLAY', 'pause': 'KEY_PAUSE', 'power_off': 'KEY_POWEROFF'}
# Upstream logs tokens and complete WebSocket URLs, even at INFO on pairing.
logging.getLogger('samsungtvws').disabled = True
for _name in ('connection', 'remote', 'helper'):
    logging.getLogger('samsungtvws.' + _name).disabled = True


def cross_subnet(host):
    # Use actual interface masks, never infer a /24 from the address.
    from .discovery import interfaces
    try:
        networks = [network for _, network in interfaces()]
        return not any(ipaddress.ip_address(host) in network for network in networks) if networks else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def device_info(host):
    address = ipaddress.ip_address(host)
    if address.version != 4 or not address.is_private or address.is_loopback or address.is_link_local:
        raise ValueError('TV requires a private LAN IPv4 address')
    with requests.Session() as session:
        session.trust_env = False
        with session.get(f'http://{address}:8001/api/v2/', timeout=(3, 3),
                         allow_redirects=False, stream=True) as response:
            response.raise_for_status()
            payload = bytearray()
            for chunk in response.iter_content(4096):
                payload.extend(chunk)
                if len(payload) > 65536:
                    raise ValueError('TV response too large')
    value = json.loads(payload)
    device = value.get('device', {})
    if value.get('type') != 'Samsung SmartTV' or device.get('OS') != 'Tizen':
        raise ValueError('Not a supported Samsung Tizen v2 endpoint')
    identity = device.get('id') or value.get('id')
    if not isinstance(identity, str) or not 1 <= len(identity) <= 256:
        raise ValueError('Missing TV identity')
    return {'identity': identity, 'model': str(device.get('modelName', ''))[:120],
            'power': {'on': 1, 'off': 0, 'standby': 0}.get(str(device.get('PowerState')).lower()),
            'port': 8002 if str(device.get('TokenAuthSupport')).lower() == 'true' else 8001}


class TelevisionWorker(threading.Thread):
    compatibility_probe = False

    def __init__(self, device, options, poll_seconds, paths, events, signature):
        super().__init__(name='tv-' + device['key'][:8], daemon=True)
        self.device, self.options = dict(device), options
        self.poll_seconds, self.paths, self.events, self.signature = poll_seconds, paths, events, signature
        self.stop_event = threading.Event()
        self.commands = queue.Queue(maxsize=8)
        self.credential = paths.config / 'credentials' / ('tv-' + device['key'] + '.json')
        self.last_command = 0

    def stop(self):
        self.stop_event.set()

    def emit(self, **values):
        self.events.put(('device', self.device['key'], dict(values, _endpoint=self.signature[:2])), timeout=1)

    def remote(self, info, pair=False, operation=None):
        saved = read_json(self.credential, {})
        if saved and saved.get('identity') != info['identity']:
            raise ValueError('TV identity changed; credentials were not sent')
        if not pair and (not saved or saved.get('port') != info['port']):
            raise ValueError('Pair the TV first')
        client = SamsungTVWS(self.device['host'], port=info['port'], token=saved.get('token'),
                             timeout=30 if pair else 5, name='LoxBerry Samsung Local')
        try:
            client.open()
            if pair:
                if info['port'] == 8002 and not client.token:
                    raise ValueError('TV did not issue a pairing token')
                atomic_json(self.credential, {'identity': info['identity'], 'port': info['port'],
                                             'token': client.token})
            elif operation in KEYS:
                # Recheck settings after the handshake; never replay failed keys.
                config = self.paths.load_config()
                options = config['devices'].get(self.device['key'], {})
                if (self.stop_event.is_set() or not config['enabled'] or not options.get('enabled', True)
                        or not options.get('control')):
                    raise ValueError('TV control disabled')
                client.send_key(KEYS[operation])
        finally:
            client.close()

    def run(self):
        next_poll = 0
        while not self.stop_event.is_set():
            command = None
            try:
                command = self.commands.get(timeout=0.5)
            except queue.Empty:
                pass
            if command:
                result = 'rejected'
                try:
                    now = time.time()
                    if not now - 30 <= command.get('timestamp', 0) <= now + 5 or now - self.last_command < 3:
                        raise ValueError('Expired or rate-limited TV request')
                    self.last_command = now
                    operation = command.get('operation')
                    config = self.paths.load_config()
                    options = config['devices'].get(self.device['key'], {})
                    if not config['enabled'] or not options.get('enabled', True):
                        raise ValueError('TV disabled')
                    if operation != 'pair' and (operation not in KEYS or not options.get('control')):
                        raise ValueError('TV control unavailable')
                    self.emit(tv_pairing=operation == 'pair')
                    info = device_info(self.device['host'])
                    self.remote(info, pair=operation == 'pair', operation=operation)
                    result = 'paired' if operation == 'pair' else 'sent_unconfirmed'
                except Exception as error:
                    result = 'failed_' + type(error).__name__  # Never log exception text: may contain a token.
                self.emit(tv_pairing=False)
                self.events.put(('result', self.device['key'], {'id': command['id'], 'result': result}), timeout=1)
                next_poll = 0
            if time.monotonic() < next_poll:
                continue
            next_poll = time.monotonic() + self.poll_seconds
            try:
                info = device_info(self.device['host'])
                saved = read_json(self.credential, {})
                mismatch = bool(saved and saved.get('identity') != info['identity'])
                state = {} if info['power'] is None else {'power': info['power']}
                self.emit(tv_cross_subnet=cross_subnet(self.device['host']), kind='television', model=info['model'], status='identity_mismatch' if mismatch else 'online',
                          state=state, sensors={k: {'unit': ''} for k in state}, last_success=time.time(),
                          tv_paired=bool(saved) and not mismatch, control_available=bool(saved) and not mismatch,
                          diagnostic=('TV identity changed; remote access blocked.' if mismatch else
                                      'TV public status available. Pair TV to enable remote controls.' if not saved else
                                      'TV status available. Remote commands require controls to be enabled.'),
                          connection_report={'stage': 'tv_http', 'error': 'IdentityMismatch' if mismatch else None})
            except Exception as error:
                self.emit(status='offline', control_available=False,
                          diagnostic='TV endpoint unavailable. Switch the TV on and check its network. Unreachable does not prove power is off.',
                          connection_report={'stage': 'tv_http', 'error': type(error).__name__})
