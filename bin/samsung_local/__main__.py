import argparse
import json
import logging
import logging.handlers
import os
import sys

from .storage import Paths, atomic_json


def log_handler(directory):
    handler = logging.handlers.RotatingFileHandler(directory / 'samsung-local.log',
                                                   maxBytes=1_000_000, backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    return handler


def main():
    parser = argparse.ArgumentParser(description="Samsung Local for LoxBerry")
    parser.add_argument("command", choices=("run", "init", "admin", "diagnose"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--data", required=True)
    parser.add_argument("--log", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    paths = Paths(args.config, args.data, args.log)
    if args.command == "admin":
        from .admin import act
        try:
            # Serialize read/modify/write configuration changes across PHP requests.
            import fcntl
            with (paths.config / "admin.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                payload = sys.stdin.read(100001)
                if len(payload) > 100000:
                    raise ValueError("Request is too large")
                message = act(paths, json.loads(payload))
            print(json.dumps({"ok": True, "message": message}))
        except (ValueError, KeyError, TypeError, OSError):
            print(json.dumps({"ok": False, "message": "Invalid request or unavailable storage. Check the field limits and device status."}))
            return 1
        return 0
    if args.command == "init":
        from .credentials import ensure_certificate
        config = paths.load_config()
        if not paths.settings.exists():
            atomic_json(paths.settings, config)
        ensure_certificate(paths.config / "credentials")
        print("Configuration and certificate ready.")
        return 0
    if args.command == "diagnose":
        from .credentials import ensure_certificate
        from .mqtt import connection_settings
        checks = {"python": sys.version.split()[0], "config": "ok"}
        paths.load_config()
        ensure_certificate(paths.config / "credentials")
        checks["certificate"] = "ok"
        try:
            settings = connection_settings()
            checks["mqtt_settings"] = "available"
            checks["mqtt_tls"] = bool(settings.get("tls"))
        except Exception:
            checks["mqtt_settings"] = "unavailable"
        print(json.dumps(checks, indent=2))
        return 0 if checks["mqtt_settings"] == "available" else 1
    handler = log_handler(paths.log)
    logging.getLogger("samsung_local").addHandler(handler)
    logging.getLogger("samsung_local").setLevel(logging.INFO)
    # Upstream debug logs can include raw appliance representations. Keep them out of the UI log.
    logging.getLogger("smartthings_local").addHandler(logging.NullHandler())
    logging.getLogger("smartthings_local").propagate = False
    import fcntl
    from .service import Service
    with (paths.data / "service.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Samsung Local is already running", file=sys.stderr)
            return 1
        Service(paths).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
