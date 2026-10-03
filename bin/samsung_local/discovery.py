"""Unprivileged IPv4 discovery: multicast plus a bounded connected-LAN sweep."""

import concurrent.futures
import hashlib
import ipaddress
import json
import logging
import secrets
import socket
import subprocess
import time
import uuid

import cbor2
from .media_inventory import inventory as media_inventory
from smartthings_local.errors import MalformedMessageError
from smartthings_local.protocol.coap import build_get_request, parse_coap
from smartthings_local.protocol.dtls_probe import probe_dtls_ports
from smartthings_local.protocol.ocf_discovery import read_plaintext_ocf_resource
from smartthings_local.protocol.ocf_multicast import read_ocf_responder

LOG = logging.getLogger(__name__)


def identity(di, host, port):
    try:
        parsed = uuid.UUID(str(di).removeprefix("urn:uuid:"))
        if not parsed.int:
            raise ValueError("Empty device identity")
        return str(parsed)
    except ValueError:
        return "host-" + hashlib.sha256(f"{host}:{port}".encode()).hexdigest()[:20]


def interfaces():
    rows = json.loads(subprocess.run(["ip", "-j", "-4", "address", "show", "up"],
                                    capture_output=True, text=True, check=True, timeout=5).stdout)
    return [(a["local"], ipaddress.ip_network(f'{a["local"]}/{a["prefixlen"]}', strict=False))
            for row in rows for a in row.get("addr_info", [])
            if a.get("scope") == "global" and a.get("family") == "inet"][:8]


def multicast(local, network, stop):
    results = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((local, 0))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(local))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        sock.settimeout(0.3)
        tokens = set()
        for versioned in (True, False):
            token = secrets.token_bytes(8)
            tokens.add(token)
            packet = build_get_request(1, secrets.randbelow(65536), token, ["oic", "res"],
                accept=(10000).to_bytes(2, "big") if versioned else b"\x3c",
                extra_options=((2049, b"\x08\x00"),) if versioned else ())
            sock.sendto(packet, ("224.0.1.187", 5683))
        deadline = time.monotonic() + 3
        count = 0
        while not stop.is_set() and time.monotonic() < deadline and count < 256:
            try:
                data, (host, port) = sock.recvfrom(8192)
                count += 1
                if ipaddress.ip_address(host) not in network:
                    continue
                _, code, _, received_token, _, _ = parse_coap(data)
                if code != 69 or received_token not in tokens:
                    continue
                # Re-read the complete directory through upstream's source-bound, blockwise parser.
                results[(host, port)] = ()
            except socket.timeout:
                pass
            except (ValueError, OSError, MalformedMessageError):
                continue
    return results


def inspect_host(host, plaintext_port):
    responder = read_ocf_responder(host, plaintext_port, timeout=1.0, retries=0)
    if not responder.has_identity and not responder.rt:
        return None
    # Do not enroll an arbitrary OCF light or other vendor solely because it has a UUID.
    samsung = any("samsung" in t.lower() for t in responder.rt)
    manufacturer = ""
    if not samsung:
        result = read_plaintext_ocf_resource(host, "/oic/p", port=plaintext_port, timeout=1, retries=0)
        try:
            rep = cbor2.loads(result.payload) if result.code == 69 else {}
            manufacturer = str(rep.get("mnmn", "")) if isinstance(rep, dict) else ""
        except Exception:
            pass
        samsung = "samsung" in manufacturer.lower()
    if not samsung:
        result = read_plaintext_ocf_resource(host, "/oic/res", port=plaintext_port, timeout=1, retries=0)
        # Vendor resource types are also usable manufacturer hints when /oic/p is private.
        if result.code == 69:
            samsung = b"x.com.samsung." in result.payload or b"x.com.st.d." in result.payload
    # Generic oic.d appliance types are common on Samsung boards whose public platform read is denied.
    # Keep these as candidates but do not authenticate until Samsung provenance is visible.
    if not samsung and not any(t.startswith("oic.d.") for t in responder.rt):
        return None
    ports = tuple(responder.secure_ports)
    selected = None
    diagnosis = "no_secure_port"
    if not ports and samsung:
        ports = (5684, *range(49152, 49161))
    if ports:
        result = probe_dtls_ports(host, ports[:10], timeout=1.0, retries=0)
        selected = result.selected_port
        diagnosis = "discovered" if selected else "ambiguous_or_unreachable_port"
    security = {}
    result = read_plaintext_ocf_resource(host, "/oic/sec/doxm", port=plaintext_port, timeout=1, retries=0)
    if result.code == 69:
        try:
            rep = cbor2.loads(result.payload)
            security = {"owned": rep.get("owned") if type(rep.get("owned")) is bool else None,
                        "oxms": [v for v in rep.get("oxms", [])[:16] if type(v) is int]}
        except (ValueError, TypeError, AttributeError):
            pass
    pki = isinstance(security.get("oxms"), list) and 65282 in security["oxms"]
    media = any(t in {'oic.d.tv', 'oic.d.networkaudio'} for t in responder.rt)
    extra = {'media_inventory': media_inventory(host, plaintext_port)} if media and samsung else {}
    return {**extra, "key": identity(responder.di, host, plaintext_port), "di": responder.di,
            "host": host, "plaintext_port": plaintext_port, "secure_port": selected,
            "name": (responder.name or "Samsung appliance")[:120], "rt": list(responder.rt),
            "samsung": samsung, "security": security,
            "status": "auth_required" if pki else diagnosis, "ocf_pki": pki,
            "seen_at": time.time()}


def scan(config, known, stop):
    endpoints = {}
    local_interfaces = interfaces()
    for local, network in local_interfaces:
        if stop.is_set():
            return []
        try:
            endpoints.update(multicast(local, network, stop))
        except OSError:
            LOG.warning("Multicast unavailable on one interface; continuing with bounded unicast discovery")
    networks = [ipaddress.ip_network(n) for n in config["networks"]]
    if not networks:
        networks = [net for _, net in local_interfaces if net.is_private and net.prefixlen >= 22]
    hosts = set()
    for net in networks:
        if len(hosts) + net.num_addresses > 1024:
            LOG.warning("LAN sweep bounded to 1024 addresses; configure smaller discovery networks if needed")
            break
        hosts.update(str(ip) for ip in net.hosts())
    for host in hosts:
        endpoints.setdefault((host, 5683), ())
    for device in known:
        endpoints.setdefault((device["host"], device.get("plaintext_port", 5683)), ())
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        pending = {executor.submit(inspect_host, host, port)
                   for host, port in list(endpoints)[:1152]}
        for future in concurrent.futures.as_completed(pending):
            if stop.is_set():
                for task in pending:
                    task.cancel()
                break
            try:
                device = future.result()
                if device:
                    results.append(device)
            except Exception as error:
                LOG.debug("Discovery probe ended: %s", type(error).__name__)
    return results
