# Samsung appliance compatibility research — 3 October 2026

## Conclusion

Automatic onboarding can be generalized by protocol and resource schema. It cannot
be guaranteed for every Samsung device. A consumer-model whitelist is unnecessary
for read-only mappings; authentication and transport compatibility still vary.

Both upstream HEADs were checked against GitHub during this work. They match the
existing pinned dependency and reference revisions, so no speculative dependency
upgrade or stale samsung2mqtt wrapper is needed.

## Sources and implementation decisions

* [SmartThings-Local, pinned source](https://github.com/QuiteYellow/SmartThings-Local/tree/3cc0931e4758cb11ba8b23520db9d6185b8f1ea0):
  supported DTLS/CoAP APIs and local self-signed client-certificate generation.
* [Firmware families](https://github.com/QuiteYellow/SmartThings-Local/blob/3cc0931e4758cb11ba8b23520db9d6185b8f1ea0/docs/firmware-families.md):
  directory dialect and firmware stack are separate dimensions. Do not infer local
  access from a marketing model or public ownership-method advertisement.
* [Appliance compatibility](https://github.com/QuiteYellow/SmartThings-Local/blob/3cc0931e4758cb11ba8b23520db9d6185b8f1ea0/docs/appliance-compatibility.md):
  use resource-advertised secure endpoints and stateless first-flight probes; the
  response may arrive from a different port. Add bounded standard-port fallback
  only when no advertised candidates exist. Older TCP-8888 is a different protocol.
* [OCF-PKI laundry findings](https://github.com/QuiteYellow/SmartThings-Local/blob/3cc0931e4758cb11ba8b23520db9d6185b8f1ea0/docs/ocf-pki-laundry.md):
  endpoint discovery, authenticated transport, resource authorization and ownership
  are distinct. Some firmware needs an existing authorized PSK/certificate. Do not
  relax verification, reset ownership or repeatedly try rejected credentials.
* [TV/audio findings](https://github.com/QuiteYellow/SmartThings-Local/blob/3cc0931e4758cb11ba8b23520db9d6185b8f1ea0/docs/ocf-vd-devices.md):
  Samsung VD server authentication can expose public information, but does not
  authorize protected TV controls. The upstream appliance bridge has no TV mapping.
  This release classifies OCF TV/audio explicitly and stops appliance-profile loops.
  A separate TV integration would require its own protocol and pairing lifecycle.
* [LocalThings mapping and recording source](https://github.com/mbillow/localthings/tree/5c2e185ec5912b29407934897d8d888aa4cfc374/custom_components/localthings/registry):
  read `/device/0` even when not advertised; consume batch representations directly;
  use numeric compartment IDs, standard/vendor power fallback, board-family typing,
  explicit temperature units, filter percentages, air-quality arrays and alarms.
  Shared resource fields cover multiple consumer models without per-model rules.

## What the 105 recordings establish

Sanitized measurement excerpts exercise the actual plugin worker through mocked
authenticated sessions, including the unadvertised batch path. Every recording
produces mapped readings, and the one-shot worker completes without appliance
writes. Independent assertions verify fridge compartment values/units, air-monitor
CO2/particulates, energy conversion and zero suppression, and stable compartment IDs.

Recordings include air conditioners, air purifiers, air monitors, AirDressers,
refrigerators, washers, dryers, dishwashers, ovens, cooktops/ranges, microwaves,
range hoods, heat pumps, dehumidifiers, water purifiers and vacuum stations.
Some captures originate from cloud resource recordings; matching their payload
shape does not prove local reachability. TCP-8888 recordings are excluded.
Unknown device types can still publish recognized readings. A fixture filename is
never used as a runtime type hint or as evidence of authentication support.

## Real hardware evidence and remaining limits

The user supplied successful dryer readings from DV9BN8288AW/EN using 0.1.2.
Their Q90 TV was discovered but failed the appliance session. This 0.2.0 build has
not been installed or exercised on those devices by the development environment.

No claim is made of universal device compatibility, all capabilities, all commands,
or production certification. Composite subtrees, IPv6-only discovery, legacy
TCP-8888 transport, TV remote pairing and cloud-only appliances remain outside
this release. Installer/upgrade/reboot behavior still needs real Linux/LoxBerry
validation. Existing supported AC/purifier power commands remain opt-in; new
capabilities in this release are read-only.

## Next evidence to collect

Install 0.2.0 over the existing plugin and verify the dryer's readings and unchanged
MQTT topics. Check that the TV is identified and no longer produces session retries.
When another user installs it, compatible appliances should onboard automatically;
an authentication failure gets one attempt, then an actionable status. Use the
value-free support export to distinguish transport, authentication and missing
mappings without publishing credentials or device/network identifiers.
