# Third-party provenance

Reviewed on 2026-10-03.

* Protocol dependency: [QuiteYellow/SmartThings-Local](https://github.com/QuiteYellow/SmartThings-Local)
  commit `3cc0931e4758cb11ba8b23520db9d6185b8f1ea0` (2026-10-02).
  Installed unmodified from that exact Git revision. Runtime uses its supported
  API documented in `docs/api.md`. Certificate subject, SAN and extension recipe
  in `samsung_local/credentials.py` is adapted from `setup_cert.py` at this revision.
  Original MIT license and NOTICE are preserved alongside this file and in the
  installed dependency. No CA private key or remote certificate bundle is copied.
* Capability reference: [mbillow/localthings](https://github.com/mbillow/localthings)
  commit `5c2e185ec5912b29407934897d8d888aa4cfc374` (2026-10-02), MIT.
  `registry/batch.py`, `registry/capabilities/common.py`, `operational.py` and
  `registry/by_type/__init__.py` informed the mappings in
  `samsung_local/capabilities.py` and `extended.py`. Version 0.2.0 also references
  airconditioner, air_monitor, air_purifier, fridge and appliance capability modules.
  Sanitized excerpts from 105 `tests/fixtures/*.json` recordings are retained in
  `tests/fixtures/appliances.json` under the same MIT license. Resource/field names, standard/vendor fallback,
  board tokens and power encodings are adapted; no Home Assistant dependency or
  full capability registry is copied. Original MIT license is preserved.
* Packaging convention references: [LoxBerry SamplePlugin V4](https://github.com/mschlenstedt/LoxBerry-Plugin-SamplePlugin-V4)
  and [LoxBerry core](https://github.com/mschlenstedt/Loxberry), particularly
  `sbin/plugininstall.pl`, `libs/perllib/LoxBerry/IO.pm`, and PHP SDK path globals.
  Plugin lifecycle scripts, PHP UI and Perl MQTT helper are new implementations.

The project is independent and is not endorsed by Samsung, SmartThings, or LoxBerry.
