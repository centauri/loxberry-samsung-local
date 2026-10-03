# Validation — 0.2.0

Validated on Windows on 3 October 2026 with the pinned SmartThings-Local revision.

* 192 pytest tests passed, including all 105 sanitized upstream appliance session
  replays. These simulate authenticated sessions; they do not test each appliance's
  real DTLS authentication, LAN reachability, or hardware behavior.
* Ruff passed. PHP syntax validation passed. Installer/uninstaller bash syntax
  checks passed. PHP rendering and diagnostic-download tests passed.
* Existing certificate/OpenSSL contract test passed with two upstream pyOpenSSL
  deprecation warnings; no dependency or verification bypass was introduced.
* Automatic read-only onboarding is persisted before connecting and tested for
  success-to-polling transition, disabled-device exclusion and restart suppression.
* Identity conflicts and mismatches remain quarantined. Failed or interrupted
  compatibility attempts need explicit retry. No new write mappings were added.
* Access-denied paths use the pinned upstream exception constructor correctly;
  authorization failures are distinguished from absent mappings.
* Resource interpretation tests cover independent expected compartment values and
  units, air-quality readings, vendor fallback, unknown-field exclusion and energy
  unit conversion/sentinel suppression. Stable numeric item IDs survive reordering.
* Support export tests confirm exclusion of names, identifiers, addresses, values,
  credentials and raw logs. Downloads contain only the prepared support report.
* Archive test verifies root layout, executable modes, LF text, preserved license,
  dependency pin and exclusion of fixture/test data and private-key files.

Not verified in this environment: actual 0.2.0 LoxBerry installation, upgrade,
systemd start/reboot, ARM dependency builds, appliance outages or hardware writes.
The user's prior real dryer success is evidence for 0.1.2, not an installation test
of this new build. The TV remains unsupported and is now clearly classified.

Upgrade over the existing installation without uninstalling. Verify unchanged
MQTT instance/device topic prefixes, successful dryer polling, and TV classification.
See RESEARCH-0.2.0.md for source-backed scope and remaining protocol limitations.
