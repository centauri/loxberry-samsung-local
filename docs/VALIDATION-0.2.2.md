# Native LoxBerry appearance — 0.2.2

Removed the bespoke teal palette, rounded appliance cards, three dashboard cards
and oversized introduction. The page uses a compact definition-list status row,
native section headings, flat appliance sections, and lb-btn/lb-input/lb-select/
lb-textarea/lb-table components. Logs and help text use semantic theme variables.
No global theme variables, theme class or system preference are modified.

The header owns theme loading/selection. Presence of the installed components.css
and design-tokens.css selects the native design-system path, including no-jQuery-
Mobile mode. Older builds use a scoped classic fallback. Controls explicitly opt
out of jQuery Mobile enhancement. Runtime minimum remains LoxBerry 4/Python 3.11;
this is not a claim of full plugin compatibility with LoxBerry 2 or 3.

References checked against LoxBerry HEAD 8040dede4a2c87f99593af2463c6cdc9c5e56d39:

* [Theme loading and lbheader](https://github.com/mschlenstedt/Loxberry/blob/8040dede4a2c87f99593af2463c6cdc9c5e56d39/libs/phplib/loxberry_web.php)
* [Design tokens and components](https://github.com/mschlenstedt/Loxberry/tree/8040dede4a2c87f99593af2463c6cdc9c5e56d39/webfrontend/html/system/css)
* [Native PHP sample plugin](https://github.com/mschlenstedt/LoxBerry-Plugin-SamplePlugin-V4/blob/master/webfrontend/htmlauth/index.php)

Validation:

* 11 targeted PHP-rendering, package and upgrade-preservation tests pass. Both
  theme-component-present and component-absent branches render successfully.
* PHP lint and Ruff pass. No daemon or protocol logic changed.
* Headless Edge rendered the PHP output with the upstream styles for Clean Admin,
  Classic LB, Soft Rounded and Glass, plus the classic fallback, at 1280 and 390
  pixels wide. All ten variants had no page-width overflow. Computed colours show
  that native controls follow each theme. Desktop/light and mobile/dark screenshots
  were visually inspected. Preview uses representative data and a header facade;
  the complete live LoxBerry shell was not exercised.
* The 0.2.1 preupgrade/restore fix remains included and its tests pass.

Install as an update without uninstalling. Theme-native controls may retain the
rounding selected by the system theme; the plugin itself no longer creates cards
or imposes its own rounded visual style.
