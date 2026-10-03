"""LoxBerry broker integration, retained state and fail-closed command ingress."""

import json
import logging
import queue
import ssl
import subprocess
import threading
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt

LOG = logging.getLogger(__name__)


def connection_settings():
    helper = Path(__file__).resolve().parent.parent / "mqtt-settings.pl"
    result = subprocess.run(["perl", str(helper)], capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise ValueError("LoxBerry MQTT settings unavailable; check the MQTT widget")
    settings = json.loads(result.stdout)
    if not settings.get("brokerhost"):
        raise ValueError("Configure the broker in LoxBerry's MQTT widget")
    return settings


def validate_command(payload, retained, now):
    if retained or len(payload) > 1024:
        raise ValueError("Retained or oversized command rejected")
    data = json.loads(payload)
    if not isinstance(data, dict) or set(data) != {"id", "timestamp", "value"}:
        raise ValueError("Use a command ID, Unix timestamp and value")
    if not isinstance(data["id"], str) or not isinstance(data["value"], str):
        raise ValueError("Command ID and value must be strings")
    data["id"] = str(uuid.UUID(data["id"]))
    stamp = data["timestamp"]
    if type(stamp) not in {int, float} or not now - 30 <= stamp <= now + 5:
        raise ValueError("Command expired or clock is incorrect")
    if data["value"] not in ("on", "off"):
        raise ValueError("Only on/off power commands are supported")
    return data


class Broker:
    def __init__(self, instance, inbound):
        self.base = f"samsunglocal/{instance}"
        self.inbound = inbound
        self.connected = threading.Event()
        self.reconnected = threading.Event()
        self.client = None
        self.settings = None
        self.last_attempt = 0
        self.error = "Waiting for LoxBerry MQTT settings"

    def refresh(self):
        if time.monotonic() - self.last_attempt < 30:
            return
        self.last_attempt = time.monotonic()
        try:
            settings = connection_settings()
            if settings == self.settings and self.client:
                return
            self.close()
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                 client_id="samsunglocal-" + self.base.split("/")[1], clean_session=True)
            client.max_queued_messages_set(256)
            client.max_inflight_messages_set(20)
            client.reconnect_delay_set(2, 60)
            client.will_set(self.base + "/bridge/availability", "offline", qos=1, retain=True)
            if settings.get("brokeruser"):
                client.username_pw_set(settings["brokeruser"], settings.get("brokerpass", ""))
            tls = str(settings.get("tls", 0)).lower() in {"1", "true"}
            if tls:
                cafile = settings.get("tls_cafile")
                context = ssl.create_default_context(cafile=cafile if cafile and Path(cafile).is_file() else None)
                # Honor LoxBerry's explicit TLS validation setting, without silently downgrading to plain TCP.
                if str(settings.get("tls_verify", 1)).lower() in {"0", "false"}:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                client.tls_set_context(context)
            client.on_connect = self.on_connect
            client.on_disconnect = self.on_disconnect
            client.on_message = self.on_message
            self.client, self.settings = client, settings
            port = settings.get("tls_brokerport") if tls else settings.get("brokerport")
            client.connect_async(settings["brokerhost"], int(port or (8883 if tls else 1883)), keepalive=30)
            client.loop_start()
            self.error = "Connecting to LoxBerry's configured broker"
        except Exception as error:
            self.settings = None
            self.error = "MQTT unavailable: " + type(error).__name__ + "; check the LoxBerry MQTT widget"
            LOG.warning(self.error)

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            self.error = "Broker refused the connection; check LoxBerry MQTT settings"
            return
        self.connected.set()
        self.reconnected.set()
        self.error = ""
        client.subscribe(self.base + "/+/set/power", qos=1)
        self.publish("bridge/availability", "online")

    def on_disconnect(self, client, userdata, flags, reason_code, properties):
        self.connected.clear()
        self.error = "MQTT disconnected; reconnecting automatically"

    def on_message(self, client, userdata, message):
        parts = message.topic.split("/")
        if len(parts) != 5 or parts[-2:] != ["set", "power"]:
            return
        try:
            command = validate_command(message.payload, message.retain, time.time())
            self.inbound.put_nowait(("command", parts[2], command))
        except (ValueError, TypeError, KeyError, queue.Full):
            LOG.warning("MQTT command rejected (invalid, retained, expired or queue full)")

    def publish(self, suffix, value, retain=True):
        if not self.connected.is_set() or not self.client:
            return False
        if not isinstance(value, str):
            value = json.dumps(value, separators=(",", ":"), allow_nan=False)
        return self.client.publish(self.base + "/" + suffix, value, qos=1, retain=retain).rc == 0

    def close(self):
        if self.client:
            if self.connected.is_set():
                info = self.client.publish(self.base + "/bridge/availability", "offline", qos=1, retain=True)
                try:
                    info.wait_for_publish(timeout=2)
                except RuntimeError:
                    pass
            self.client.disconnect()
            self.client.loop_stop()
            self.client = None
        self.connected.clear()
