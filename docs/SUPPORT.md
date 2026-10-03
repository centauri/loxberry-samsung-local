# Shared Samsung support, native LoxBerry adapter

Samsung protocol research and shared capability findings belong with the existing
upstream projects. Search before opening issues and cross-link related discussions.
Upstream maintainers have not yet agreed to a cross-project support contract.

## Where to report

* New appliance capabilities: search https://github.com/mbillow/localthings/issues.
  Use Device support / capability gap for a genuinely new shared gap. Explain that
  this partial report comes from LoxBerry, not Home Assistant. Include retail model,
  expected behavior and versions. If LocalThings already supports it, report the
  missing adapter implementation in the adapter repository instead.
* Protocol/authentication: search https://github.com/QuiteYellow/SmartThings-Local/issues.
  Include library version and connection stage. An adapter failure alone does not
  prove a library bug; reproduce with upstream tooling or seek adapter triage.
* Installation, updates, discovery, UI, MQTT and Loxone: adapter repository.

## Diagnostic contract

The dashboard's Help and support section explains setup, status, report collection,
support routing and how fixes arrive. Friendly names remain local because they can
contain personal information. Supply the retail model separately in your issue.
Version 0.2.5 adds discovered device types, explicit name-omission reasons and capture
availability. For skipped TV/audio profiles, reports explain that no appliance
connection was attempted and route scope questions to the adapter. This is not
proof that the TV cannot work through a different integration.

Review Export device compatibility report before downloading and posting. Nothing
is uploaded automatically. The download is the exact displayed snapshot.

Version 0.2.4 uses LocalThings' `data.resources` href-to-representation dictionary,
plus `device_type`, `identity`, `unbound_hrefs` and `smartthings_local_version`.
Unknown values and options are preserved to support new mappings. This is a partial
adapter capture, not an HA diagnostic or a claim of equal feature coverage. HA
entity counts, subdevices and probes are not invented. `unbound_hrefs` measures
adapter coverage only, not LocalThings coverage.

MIT redaction/encoding helpers are vendored unchanged from pinned LocalThings.
Extra filtering removes security/network resources, identifiers, sensitive keys and
binary data, with depth/size limits. Review all remaining free text: unknown personal
values cannot all be recognized automatically. No extra device requests occur.
Reports without successful reads have no resource evidence. Omitted resources and
composite-device relationships can require further reviewed investigation.

## Bringing findings back

Diagnostic JSON is evidence, not a driver. Users receive reviewed support through
normal adapter ZIP updates. Never install executable code from issue attachments.

1. Record the upstream issue/PR, reviewed commit and MIT attribution.
2. Download a reviewed LocalThings diagnostic or device0 fixture locally.
3. Run `python tools/replay_report.py report.json --output assessment.json`.
   HA data envelopes, direct resource maps and device0 fixtures are accepted.
   No network calls or configuration changes occur. Existing output is not replaced.
4. Review the sanitized fixture and readings; add explicit expected readings to
   regression tests. Tool output is not itself a test oracle. Composite siblings
   are not replayed by this tool.
5. Adapt the upstream mapping or update the pinned protocol dependency, retain MIT
   notices, run regression tests and release an adapter ZIP.
6. Ask for hardware verification and contribute useful evidence/fixes upstream.

LocalThings maps currently depend on HA descriptors. There is no standalone shared
registry dependency here, so mapping fixes do not arrive automatically. A versioned
HA-independent registry would reduce adaptation work; it needs upstream agreement.
See UPSTREAM-COLLABORATION.md for a draft proposal, not yet sent.
