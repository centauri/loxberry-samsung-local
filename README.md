# Samsung Local for LoxBerry

![Samsung Local](icons/icon_128.png)

Maintained by [centauri](https://github.com/centauri). Independent integration;
not affiliated with Samsung. [Releases](https://github.com/centauri/loxberry-samsung-local/releases)
and [adapter support](https://github.com/centauri/loxberry-samsung-local/issues).

A native LoxBerry plugin with English and Dutch interfaces for Samsung appliances on the local
network. **Version 0.2.14 is an MVP for hardware evaluation, not a claim of universal
Samsung support or a hardware-certified release.** No Docker, containers,
Portainer, `.env` file, separate Mosquitto, or manually created certificate is used.

## Install

**Moving from pre-GitHub test builds (0.2.10 or earlier):** uninstall the old
Samsung Local plugin first, then install the regular release ZIP as a fresh
installation. This resets local settings, discovery networks, credentials and
the MQTT instance identity; configure discovery again and check any Loxone topic
references. Future updates retain the published centauri installer identity.

The 0.2.11 package and 0.2.12 legacy package failed installer metadata validation.
Use 0.2.14 or later. There is now one installation ZIP, with centauri's GitHub
no-reply address. Support is through GitHub Issues, not email.

1. Use **LoxBerry 4 on Debian 12 or newer**, with Python 3.11+ and systemd.
   A 64-bit ARM or x86 system is recommended. Dependency installation on other
   architectures may require compilation and is not validated yet.
2. Configure the broker once in LoxBerry's existing **MQTT widget** if it is not
   already configured. The plugin reads those settings, including TLS settings.
3. Upload the installation ZIP from this repository's Releases in LoxBerry Plugin Management.
   Internet access is needed during installation for Debian packages and pinned
   Python dependencies. Runtime appliance communication is local.
4. Open **Samsung Local**. Allow a few minutes for the first scan. Compatible
   appliances connect automatically; readings and MQTT topics appear on the page.

The installer creates a private virtual environment and a locally generated
RSA-2048/SHA-256 client certificate, then starts an unprivileged systemd service.
Broker credentials are read through `LoxBerry::IO::mqtt_connectiondetails`; they
are neither copied into plugin settings nor displayed in the UI.

## Automatic updates

Install 0.2.14 once manually to register the native LoxBerry update URLs. In
LoxBerry Plugin Management, enable automatic updates including **prereleases**
for Samsung Local to receive development releases. Stable-only users will not
receive these evaluation builds. LoxBerry controls update scheduling and user
preferences; the plugin does not override them.

After tagged-release tests pass, GitHub publishes the installation ZIP, then
updates `prerelease.cfg` on the `updates` branch. The stable `release.cfg` has
version `0.0.0` until a stable release is deliberately promoted. Ordinary commits
and upstream monitoring do not ship updates. Update installation uses the same
configuration backup/restore hooks as manual upgrades.

No LoxBerry AppStore listing is required for these update URLs to work.

## Appearance

Version 0.2.2 uses a compact status row, plain appliance sections and native
LoxBerry controls. The LoxBerry header selects the current theme; the plugin
uses its lb-* component classes and semantic colour variables. It does not bundle
a theme or override the system selection. Earlier builds without design-system
assets use a scoped classic fallback with native form controls. This appearance
fallback does not lower the runtime requirement: LoxBerry 4 / Python 3.11+ remains
required. The 0.2.1 upgrade-preservation fix is included.

## What the MVP supports

Version 0.2.0 expands automatic read-only onboarding and shared capability mappings.
105 sanitized LocalThings recordings pass a mocked session replay; this verifies
resource parsing, not authentication or LAN discovery on 105 physical devices.
The user's DV9BN8288AW/EN dryer has supplied real successful readings on 0.1.2.

Samsung's `/device/0` batch is read even when unadvertised, and refreshed on each
poll. Shared field mappings work without an exact consumer-model entry.

* IPv4 OCF multicast and bounded connected-LAN discovery; optional private CIDRs
  for routed networks. No normal appliance-IP or secure-port setup.
* Secure ports from OCF advertisements, checked with upstream's stateless DTLS
  probe. If no port is advertised, Samsung candidates receive bounded stateless
  probes on 5684 and 49152ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ49160. Only an unambiguous responding endpoint is used.
* Persistent OCF device-ID tracking with a connected-session identity check.
  Address/port changes replace sessions without changing MQTT device topics.
  Conflicting simultaneous identities are quarantined. Missing IDs use a host/port
  fallback, which cannot track address changes automatically.
* Appliance type detection from OCF types and reviewed Samsung board-family and
  model/description tokens. Unknown types remain visible.
* Reading mapped power, child lock, remote-control flag, temperature, humidity,
  instantaneous power, cumulative energy, filter use, operational state, progress,
  remaining-time strings, door state and mode **when supported resources and fields
  are present**. Units are not invented when the appliance omits them.
* A persistent DTLS session per appliance, polling, keepalive, bounded retries,
  broker reconnect, discovery after address changes, status and rotating logs.
* Optional MQTT **power on/off for air conditioners and air purifiers only**, with
  an explicit checkbox per appliance. Other appliances are read-only in this MVP.
  Firmware may still reject a mapped command. There is no generic CoAP-write API,
  cycle start, oven activation, ownership transfer, reset, or security mutation.

Additional read-only mappings cover per-compartment temperatures, fan speed,
airflow, multi-mode state, alarms, refrigeration, icemaker status, laundry options,
dishwasher options, cooking status, range hood, water tank and vacuum-station
status. Air-quality units are only assigned for reviewed families. Unknown fields
are omitted; raw payloads are never blindly flattened into MQTT.

Mappings are broader, but do not provide feature parity with LocalThings.
Unknown sensor fields, composite subdevices, full climate control, OBSERVE,
IPv6-only discovery and Home Assistant autodiscovery are not implemented.

## Authentication and firmware boundaries

The reviewed [SmartThings-Local certificate recipe](https://github.com/QuiteYellow/SmartThings-Local/blob/3cc0931e4758cb11ba8b23520db9d6185b8f1ea0/setup_cert.py)
uses the established Samsung client identity UUID with a locally generated key.
Some legacy firmware accepts this self-signed certificate; newer OCF-PKI firmware
does not. Successful DTLS negotiation alone does not establish application access:
the plugin must read the identity and appliance resources successfully.

Discovery reads `/oic/sec/doxm` only to classify public ownership-method hints.
Owner UUIDs and credential resources are not exported. A manufacturer-PKI hint
does not itself prove incompatibility. The plugin performs one automatic read-only
compatibility attempt for enabled Samsung appliance candidates with a verified
responding endpoint. Attempt state is saved before connecting, so restart and
rediscovery cannot repeat a failed attempt. Rejected or inconclusive authentication
shows **Authentication required**, without an automatic retry loop. The plugin never POSTs or DELETEs any ownership
or security resource, fetches CA private keys, or performs automatic provisioning.

The advanced import form appears only for an authentication-required device:

* Existing PSK: supply the **raw 16-byte OCF identity as 32 hexadecimal characters**
  and a **16- or 32-byte key** (32 or 64 hex characters). Upstream/OpenSSL cannot
  represent a DTLS 1.2 PSK identity containing a NUL byte; such identities are
  rejected before saving. A textual UUID encoded as UTF-8 is not the raw identity.
* Existing certificate: supply the PEM client chain and matching unencrypted PEM
  key. An optional, independently verified **server certificate UUID** enables
  upstream Samsung server-certificate verification. This UUID can differ from
  the OCF device ID; the plugin does not guess it from plaintext discovery.

Imports must already be authorized by the appliance. This plugin does not acquire
or provision PSKs. Use HTTPS for the authenticated LoxBerry UI when importing.
No certificate download, manual port entry, or security-resource edit is a normal
setup step. An unsupported appliance can remain discoverable but unreadable.

### Automatic compatibility test (0.2.0)

One read-only test replaces the first-time manual compatibility button for eligible
appliances. Identity plus actual mapped readings are required before normal polling
starts. An ownership-method advertisement or a completed handshake is insufficient.
Successful verification persists. Authentication rejection clears that verification.
A manual **Test certificate compatibility (read-only)** remains available after a
failed/inconclusive attempt; imported credentials use **Retry connection**.

Upgrade by uploading the new ZIP over the existing plugin. Do not uninstall.
Existing MQTT instance ID, credentials, settings and device topics are preserved.
Previously untested authentication-required appliance candidates get one test;
identity conflicts, disabled devices and already diagnosed unsupported resources do
not trigger unsolicited retries. A failed automatic test requires an explicit retry.

Samsung TV/network-audio OCF types are classified and shown as unsupported rather
than repeatedly attempting the appliance profile. This release does not implement
the TV WebSocket remote-control protocol, older TCP-8888 appliance pairing, cloud-only
devices, or provisioning of OCF-PKI credentials. SmartThings cloud connectivity is
not evidence of local access. Composite appliance subtrees are not yet traversed;
a combo unit may expose only its main tree's readings.

Legacy certificate authentication has the same trust limitations as upstream's
legacy profile; checking an OCF ID is continuity checking, not cryptographic
proof of manufacturer identity. Operate it on a trusted appliance LAN. MQTT TLS
uses LoxBerry's configured CA and certificate-validation preference, including
an explicitly disabled validation setting. It never silently switches TLS off.

## MQTT and Loxone

Each installation has a persistent random instance ID, avoiding client-ID clashes
between LoxBerrys. The UI shows the actual prefix:

```text
samsunglocal/<instance>/bridge/availability         online | offline (retained LWT)
samsunglocal/<instance>/<ocf-id>/availability       online | offline (retained)
samsunglocal/<instance>/<ocf-id>/meta               JSON type and sensor definitions
samsunglocal/<instance>/<ocf-id>/state              JSON readings + updated_at
samsunglocal/<instance>/<ocf-id>/state/<sensor>     scalar reading
samsunglocal/<instance>/<ocf-id>/updated_at         Unix seconds of last successful poll
samsunglocal/<instance>/<ocf-id>/set/power          non-retained JSON command
samsunglocal/<instance>/<ocf-id>/command_result     non-retained JSON result
```

The bundled `mqtt_subscriptions.cfg` subscribes the LoxBerry MQTT Gateway to
`samsunglocal/#`. Use the scalar `state/<sensor>` topics for Loxone inputs, or use
the gateway's JSON expansion for the combined state. Boolean readings are `1`/`0`.
Keep `remainingTime` as the device's string; this MVP does not guess its units.

**Gate automation on BOTH bridge and appliance availability, and check reading
age.** A bridge crash uses its LWT; old retained per-appliance values can remain.
A disconnected broker cannot receive fresh appliance availability. The next
successful connection republishes current state and metadata.

For an opted-in supported appliance, publish to `.../<ocf-id>/set/power` with QoS 1,
**retain=false**:

```json
{"id":"3f70ef2b-9203-4fa2-b4f8-404d73e81c10","timestamp":1791036000,"value":"on"}
```

Replace the example timestamp with the current Unix time and generate a fresh UUID
for every command. The example is intentionally not an evergreen runnable command.
Commands older than 30 seconds, more than 5 seconds ahead, retained commands and
duplicates are rejected. Accepted IDs are persisted before dispatch to prevent
restart replay. Only `on`/`off` values are allowed; no arbitrary resource paths.
An `accepted` result means CoAP accepted the request; the next poll is the actual
state confirmation. `uncertain` means the reply was lost or failed: there is no
automatic write retry. MQTT publisher ACLs should restrict who can control devices.

Loxone integrations that can only send a fixed scalar payload can consume readings
but cannot use this MVP's timestamped command envelope directly.

## Discovery limits and troubleshooting

* Wake the appliance, ensure Wi-Fi is connected, and use **Discover now**.
* Multicast is link-local. The fallback sweep uses at most 1024 addresses, up to
  12 simultaneous unicast probes. Connected networks larger than `/22` need a
  narrower network in advanced settings for unicast fallback. Multicast still runs.
* Routed VLANs need a configured CIDR and firewall rules for UDP 5683 and the
  appliance-advertised secure port. An appliance replying only to multicast on an
  ephemeral plaintext port may need to share a broadcast domain with LoxBerry.
* The plugin does not scan every UDP port. A small stateless fallback probe can
  recover missing advertisements; ambiguous or silent endpoints remain diagnostic.
* A generic OCF candidate with no Samsung manufacturer/vendor-resource hint is
  shown without trying Samsung authentication.
* Authentication-required devices need an appropriate credential or future protocol
  support. The **Retry connection** button is for an explicit retry after changes.
* Identity conflicts require investigation; a retry does not establish trust.
* Download the support report from the appliances page to share response codes,
  mapped resource roots and sensor counts. It excludes addresses, device IDs, names,
  reading values, credentials and logs. It is never uploaded automatically.
* Use the recent log on the plugin page. Logs rotate at 1 MB with three backups;
  upstream raw protocol debug logs are not copied into that log.

For administrator diagnosis (replace a suffixed installation folder if needed):

```sh
systemctl status loxberry-samsung-local-samsunglocal.service
journalctl -u loxberry-samsung-local-samsunglocal.service -n 100
cd /opt/loxberry/bin/plugins/samsunglocal
sudo -u loxberry /opt/loxberry/data/plugins/samsunglocal/venv/bin/python \
  -m samsung_local diagnose \
  --config /opt/loxberry/config/plugins/samsunglocal \
  --data /opt/loxberry/data/plugins/samsunglocal \
  --log /opt/loxberry/log/plugins/samsunglocal
```

`diagnose` checks local configuration, certificate and access to broker settings;
it does not mutate appliance state or prove appliance/broker connectivity.

## Lifecycle, storage and upgrades

The actual LoxBerry installation folder passed to the installer is used in all
paths and the service name, including numeric suffixes. Startup uses systemd
directly; no second LoxBerry boot daemon is needed. Automatic restart applies to
process failure. Device failures use a bounded exponential retry delay.

* `config/plugins/<folder>/`: settings, device registry, instance ID, replay ledger
  and private credentials. Directories are mode 0700; files mode 0600.
* `data/plugins/<folder>/`: versioned venv, current venv symlink, UI request queue,
  status snapshot and singleton lock.
* `log/plugins/<folder>/`: rotating plugin log (LoxBerry's log area may be volatile).
  The log is available in this plugin's page and the systemd journal; it is not
  registered as a separate LoxBerry Log Manager session in this MVP.

Version 0.2.1 fixes a destructive upgrade bug in all earlier versions: LoxBerry
purges plugin config and data directories when updating. Earlier packages lacked
preupgrade backup/restore hooks, causing fresh settings, lost device records and
new MQTT instance IDs. This was a plugin bug, not intentional test behavior.

The new package stops the daemon in preroot, then preupgrade copies and hashes
all configuration (including credentials, device registry, MQTT instance ID and
SQLite command ledger) into a private recovery directory outside the purge scope:
`data/system/samsung-local-backups/<folder>/upgrade-<random>/`. Failure aborts
before the purge. Postinstall restores and verifies it BEFORE initialization;
postupgrade verifies every original file again. These hooks are supplied by the
incoming ZIP, so upgrading an older release to 0.2.1 preserves its current state.

Virtual environments and transient status/requests are rebuilt after the purge.
Recovery backups remain after failed or successful installation, including
uninstall, and contain private keys. Retain them securely or remove them manually
once no longer needed. This is not transactional rollback of LoxBerry's own code
replacement. The fix cannot recover settings already erased by an earlier upgrade
without an existing LoxBerry backup.

Back up the plugin configuration using LoxBerry backup. Those backups contain
private keys and must be protected. Uninstall removes the systemd unit; LoxBerry
removes plugin files and credentials. Retained MQTT topics are intentionally not
deleted by the uninstaller; remove `samsunglocal/<instance>/#` on the broker if no
longer needed. Do not remove the shared broker or Debian packages.

Automatic release downloads are disabled until a real release repository exists.
Update by uploading a newer ZIP. The local project author identity is intentionally
non-contactable; establish maintained release metadata before public distribution,
and keep it stable after the first distributed release.

## Development and validation

```sh
python3 -m venv .venv
.venv/bin/pip install -r bin/requirements.txt 'pytest>=8,<9' 'ruff==0.15.0'
.venv/bin/pytest -q
.venv/bin/ruff check .
php -l webfrontend/htmlauth/index.php
for script in *.sh uninstall/*.sh; do bash -n "$script" || exit; done
.venv/bin/python tools/build.py
```

Tests use synthetic appliance identities. They cover the real pinned library's
plaintext CoAP discovery against a loopback UDP fixture, plus mocked DTLS-session
integration, identity changes/conflicts, security-resource exclusion, mapped reads
and writes, certificate generation/import, PSK validation, bounded configuration,
and persistent command deduplication. The suite also replays 105 sanitized upstream appliance recordings and checks
automatic-test persistence, TV classification and support-report privacy. These
tests do not replace hardware testing.

Before treating a build as production ready, validate on a disposable/backup-ready
LoxBerry: fresh install, actual broker/TLS settings, live appliance reads, opted-in
power control, appliance DHCP and port changes, network outages, process restart,
host reboot, ZIP upgrade with credentials preserved, and uninstall. Test an
unsupported OCF-PKI device to confirm diagnosis without security mutation. Linux
service integration, ARM dependency installation, and real DTLS firmware behavior
have not been established by Windows development tests.

Project layout: `bin/samsung_local/` runtime, `webfrontend/htmlauth/` authenticated
English UI, `dpkg/apt` Debian dependencies, root lifecycle scripts, `tests/`,
`tools/build.py`, and `.github/workflows/test.yml` for Linux/Python 3.11ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ3.13 checks.

Protocol code is pinned to [SmartThings-Local 3cc0931](https://github.com/QuiteYellow/SmartThings-Local/tree/3cc0931e4758cb11ba8b23520db9d6185b8f1ea0).
Mappings reference [LocalThings 5c2e185](https://github.com/mbillow/localthings/tree/5c2e185ec5912b29407934897d8d888aa4cfc374).
See `bin/licenses/PROVENANCE.md` and preserved MIT notices. This independent project
is not affiliated with Samsung. The stale samsung2mqtt wrapper is not used.

## Community compatibility reports (0.2.4)

Each device offers a preview and download of its compatibility report. It includes
model/firmware, connection errors and redacted resource representations in the
LocalThings diagnostic data shape, including unknown values needed for new mappings.
Review all values before sharing. This is a partial adapter capture, not HA output.
Collection uses existing reads only, with no automatic upload or extra probe.
See docs/SUPPORT.md for upstream capability/protocol support links and adapter triage.
Maintainers can replay community diagnostics and device0 fixtures with
`python tools/replay_report.py report.json --output assessment.json`.
Findings become tested mappings and normal adapter releases, not executable JSON
imports on user installations. See [upstream update checks](docs/UPSTREAM-UPDATES.md)
for the weekly GitHub workflow and maintainer review process.
