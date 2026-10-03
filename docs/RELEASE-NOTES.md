# Samsung Local for LoxBerry

## 0.2.12 installer correction

Fix the missing mandatory author email that caused 0.2.11 to be rejected before
installation. The public package uses centauri's GitHub no-reply address, not a
personal email. Builds now reject missing mandatory installer metadata.

**Already running a pre-GitHub test build (0.2.10 or earlier)? Install the
`-legacy-upgrade.zip` asset.** It preserves the original internal author identity
so LoxBerry recognizes an update and runs the existing configuration backup and
restore hooks. Keep using legacy-upgrade assets for that installation. The
placeholder address in that package is not a support mailbox; use GitHub Issues.

**New installation? Use the ZIP without `-legacy-upgrade`.** Do not install the
standard package alongside a legacy installation: LoxBerry treats it as a
different plugin. The failed 0.2.11 attempt did not migrate an existing identity.

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
