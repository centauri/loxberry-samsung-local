# Interface languages

English is the default. Choose Nederlands in the language selector under Settings
and select Apply language. The choice applies to this plugin for all
users and is saved in settings.json, with the same upgrade preservation as other
settings. It does not change LoxBerry's global language or theme.

Controls, help, status labels and known adapter connection messages are translated.
Device names, values, MQTT topics, logs and support JSON remain unchanged. Unknown
technical errors fall back to English so their original diagnostic detail survives.

Translations are server-rendered with HTML escaping. English source strings are
fallback keys; Dutch catalogs live in webfrontend/htmlauth/lang. Never translate
the full HTML response or report JSON. Add translations when introducing UI text;
tests check literal catalog coverage and render both languages in both themes.
