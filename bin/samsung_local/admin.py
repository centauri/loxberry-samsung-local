"""Validated, local-only UI actions. Sensitive values travel through stdin."""

import time
import uuid

from .credentials import validate_import
from .storage import atomic_json, read_json, valid_key, validate_config


def act(paths, request):
    if not isinstance(request, dict):
        raise ValueError("Expected a request object")
    action = request.get("action")
    config = paths.load_config()
    if action == 'dryer_command':
        from .dryer_control import ACTIONS
        key = valid_key(request.get('device'))
        operation = request.get('operation')
        status = read_json(paths.status, {})
        device = status.get('devices', {}).get(key, {})
        options = config['devices'].get(key, {})
        now = time.time()
        if (operation not in ACTIONS or not config['enabled'] or not options.get('enabled', True)
                or not options.get('control') or device.get('kind') != 'dryer'
                or not device.get('identity_verified') or device.get('status') != 'online'
                or not 0 <= now - status.get('heartbeat', 0) < 30):
            raise ValueError('Dryer control is disabled or unavailable')
        last = read_json(paths.data / 'http-command-rate.json', {})
        if now - last.get(key, 0) < 3:
            raise ValueError('Wait before sending another command')
        if len(list(paths.requests.glob('*.json'))) >= 32:
            raise ValueError('Request queue full')
        last[key] = now
        atomic_json(paths.data / 'http-command-rate.json', last)
        identifier = str(uuid.uuid4())
        atomic_json(paths.requests / f'{identifier}.json', {
            'action': 'dryer_command', 'device': key, 'created_at': now,
            'command': {'id': identifier, 'timestamp': now, 'operation': operation}})
        return 'Command queued; verify the appliance state. Not confirmation of execution.'
    if action == "language":
        config['language'] = request.get('language')
        atomic_json(paths.settings, validate_config(config))
        return "Language saved."
    if action == "settings":
        config.update({k: request[k] for k in ("enabled", "poll_seconds", "scan_seconds", "networks")})
        atomic_json(paths.settings, validate_config(config))
        return "Settings saved. The service applies changes automatically."
    if action == "scan":
        queued = {"action": "scan"}
    elif action in {"device", "retry", "import", "compatibility"}:
        key = valid_key(request.get("device"))
        status = read_json(paths.status, {})
        device = status.get("devices", {}).get(key)
        if not device:
            raise ValueError("Device is not in the discovery registry")
        if action == "device":
            control = request.get("control", False)
            if control and not device.get("control_available"):
                raise ValueError("This device has no supported control")
            config["devices"][key] = {"enabled": request["enabled"], "control": control}
            atomic_json(paths.settings, validate_config(config))
            return "Device settings saved."
        if action != "device" and device.get("kind") in {"television", "network_audio"}:
            raise ValueError("TV/audio devices require a separate protocol integration")
        if action == "import":
            if device.get("status") != "auth_required":
                raise ValueError("Credential import is only available for devices requiring authentication")
            if not device.get("di"):
                raise ValueError("Credential import requires a discovered OCF identity")
            credentials = validate_import(request.get("credentials"))
            atomic_json(paths.config / "credentials" / f"{key}.json", credentials)
        if action == "compatibility" and device.get("status") not in {"auth_required", "unsupported"}:
            raise ValueError("Compatibility test is only available when authentication is required")
        if action == "compatibility" and (paths.config / "credentials" / f"{key}.json").exists():
            raise ValueError("Existing imported credentials are present; use Retry connection")
        queued = {"action": "compatibility" if action == "compatibility" else "retry", "device": key}
    else:
        raise ValueError("Unknown action")
    if len(list(paths.requests.glob("*.json"))) >= 32:
        raise ValueError("The service is busy or stopped; wait before retrying")
    atomic_json(paths.requests / f"{uuid.uuid4().hex}.json", dict(queued, created_at=time.time()))
    return "Request queued. Refresh the page to see the result."
