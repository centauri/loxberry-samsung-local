# Samsung Local for LoxBerry

## 0.2.13 installer correction

Remove the broken legacy-package variant. Its serialized configuration had
lowercase keys that LoxBerry's case-sensitive parser could not read. The build
now checks exact key casing; CI also reads the packaged metadata using Perl
Config::Simple, the same parser used by LoxBerry.

**For pre-GitHub development installations (0.2.10 or earlier), uninstall the old
plugin before installing this ZIP.** This is a fresh installation: settings,
discovery networks, credentials and MQTT instance identity reset. Configure
networks again and check Loxone topic references. Future updates use the stable
centauri identity and the existing preservation hooks. No personal email is
included; the author email is a GitHub no-reply address.

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
