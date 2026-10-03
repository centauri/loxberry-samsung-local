---
name: Device support
about: Report an adapter mapping gap or request help determining the right upstream
title: "[Device] Model — missing capability"
---

## Device

First search https://github.com/mbillow/localthings/issues for this capability.
New shared appliance findings belong in its Device support / capability gap
template, identifying your report as LoxBerry adapter output. If support already
exists there but is missing here, use this adapter issue and link the upstream fix.
Authentication research: https://github.com/QuiteYellow/SmartThings-Local/issues.
When uncertain, use this issue for adapter triage rather than duplicating reports.

- Retail model (not serial number):
- Firmware version, if known:
- Plugin version:
- LoxBerry version:
- Device status shown in the plugin:

## Expected and observed behavior

Which readings are missing? Does the device appear, authenticate, and show any readings?
Describe the appliance state when you collected the report (idle, running, etc.).

## Reviewed compatibility report

Open the appliance's **Export device compatibility report**, inspect the preview,
download it, and attach the JSON here. Reports contain redacted resource values,
including unknown fields and appliance state. Remove anything you do not want public. Do not attach
raw captures, config backups, credentials, serial numbers or entire logs.

<!-- Attach the report here. Check existing issues for the same model first. -->

## Follow-up testing

Are you able to test a future plugin ZIP on this appliance? Hardware access helps
confirm a mapping; a recording alone does not prove authentication or control.
