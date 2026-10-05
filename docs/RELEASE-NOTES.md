# Samsung Local for LoxBerry

## 0.2.18 — normal release

Published on the stable LoxBerry update channel. Earlier 0.2.14 builds remain
prereleases. This release includes the HTTP input/export work developed in
0.2.15–0.2.17 and opt-in dryer outputs.

Add opt-in dryer Start/Resume, Pause, Stop and wrinkle-prevention commands through
POST-only virtual HTTP outputs. Use a separate control token. Check live appliance
interlocks before writes, reject stale requests, discard requests from before a
service restart and never retry uncertain writes. Results appear in status/logs
and HTTP readouts. Include a Config wiring example with manual pulse buttons,
availability gates and expected-state confirmation.

Extend numeric readout mappings for current machine state, the observed Drying
phase, dry-time duration and command feedback. Protocol mappings follow upstream;
no live writes were sent. Hardware command acceptance and virtual-output POST
behavior remain to be verified on the user's dryer and Miniserver.

## 0.2.17 wrinkle prevention input

Export wrinkle prevention as 0=off, 1=on, -1=unknown. The mapping is restricted
to wrinklePrevent readings; unrelated text is not interpreted as a switch.
Download a fresh XML to obtain the new input. Existing input keys are unchanged.
Config screenshots confirm Pause=2 and 03:12:00=11520 seconds with the running-state
fix. Regression tests cover the paused dryer with wrinkle prevention on/off/unknown.

## 0.2.16 running dryer state

Recognize Samsung's `Run` state as running (code 1), alongside `Running`. Previously
it appeared as unknown (-1) through HTTP polling. Existing XML recognition keys,
URLs and tokens remain unchanged; no reimport is needed for this correction.
Regression coverage uses the running dryer report, including 03:13:00 = 11580 seconds.
XML import and changing readings are confirmed by the user's Config screenshots;
the corrected state still needs verification on the installed device.

## 0.2.15 HTTP input XML export

Add a genuine VirtualInHttp XML template for Loxone Config, a token-protected
read-only polling endpoint, numeric availability/state mappings, duration conversion
and English/Dutch instructions. Keep existing MQTT behavior and add a CSV inventory.
The XML includes a private read-only token; import it as a Virtual HTTP Input Template.
The abandoned .Loxone transfer-project experiment is not included.

Input XML import and changing readings were subsequently verified by the user.

## 0.2.14 native automatic updates

Register native LoxBerry stable and prerelease update URLs. Install this ZIP once
manually, then enable automatic updates including prereleases for Samsung Local
in LoxBerry Plugin Management. There is no stable release yet; stable-only users
will not receive development releases.

Future tagged releases update the prerelease feed only after tests pass and the
installation ZIP is published. Author identity remains unchanged from 0.2.13, so
normal upgrades run the configuration-preservation hooks. Users still on the
pre-GitHub builds (0.2.10 or earlier) must uninstall those before a fresh install.

Native local Samsung appliance integration, with English and Dutch UI, existing
LoxBerry MQTT settings, automatic OCF discovery, compatibility reports and bounded
rotating logs. No Docker or separate broker. Maintained by centauri.

Install the attached loxberry-samsung-local installation ZIP through LoxBerry
Plugin Management. GitHub's automatically generated source archives are not the
installation package. Updates preserve configuration and credentials; back up
LoxBerry before installation.

This is an evaluation prerelease. Dryer DV9BN8288AW/EN readings have been confirmed
by the user; tests replay additional community fixtures, not physical appliances.
TV/audio discovery exports public metadata only; TV remote pairing and controls
are not implemented. See README for supported scope and limitations.

Report adapter issues here; follow docs/SUPPORT.md for shared upstream findings.
