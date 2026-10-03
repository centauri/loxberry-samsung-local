# Samsung Local for LoxBerry

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
