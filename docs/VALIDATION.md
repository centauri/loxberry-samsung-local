# Validation record — 0.1.0

Date: 2026-10-03. Development host: Windows, Python 3.12, PHP 8.3.35.

## Completed

- 63 automated tests passed; none skipped in the final run.
- The actual pinned SmartThings-Local package was installed successfully:
  `0.1.21.post1.dev1+g3cc0931e4`, Git commit
  `3cc0931e4758cb11ba8b23520db9d6185b8f1ea0`.
- Real upstream plaintext OCF reads exercised against a loopback UDP appliance
  fixture, including secure-port discovery. No real LAN appliances were scanned.
- Generated certificate and private key loaded successfully into a real upstream
  DTLS client context. This is a local compatibility check, not a handshake with
  a Samsung device.
- Session integration exercised with a fake appliance transport: identity mismatch
  rejection, mapped state, and exclusion of security-resource reads from polling.
- PSK validation, certificate/key matching and persistent credential generation.
- Device address migration, duplicate identity quarantine, OCF-PKI diagnosis,
  disabled controls, stale/retained/malformed command rejection and persistent
  deduplication across supervisor restart.
- PHP page rendered with a test LoxBerry SDK facade, validating status output,
  HTML escaping, CSRF field presence, and conditional credential import UI.
- Installation ZIP structure, LF line endings, Unix executable permissions,
  upstream pin, license inclusion and absence of credential files verified.
- Ruff static checks, Python compilation, pip dependency consistency, PHP syntax,
  and individual Bash lifecycle-script syntax checks passed.

Two pyOpenSSL deprecation warnings originate in upstream's certificate/key loading
calls. They do not fail the compatibility test with the pinned pyOpenSSL version.

## Not established here

- A real LoxBerry install, upgrade, host reboot or uninstall.
- LoxBerry's live Perl/PHP SDK environment and MQTT broker/TLS authentication.
- Real Samsung DTLS handshakes, read permissions, power-command behavior, or
  firmware-specific automatic discovery.
- A live MQTT outage/reconnect cycle or Loxone Miniserver integration.
- ARM package installation, Linux permissions and systemd hardening at runtime.
- IPv6, composite appliances, complete LocalThings capability parity or OBSERVE;
  these are outside this MVP's scope.

The GitHub Actions workflow provides Linux/Python 3.11–3.13 validation once this
repository is pushed. That workflow has been written, not run on GitHub here.

The README contains the hardware acceptance steps. Treat this release as a
production-minded evaluation MVP until those checks pass on target hardware.
