# Compatibility reports and GitHub support — 0.2.3

Per-device compatibility reports now include model/firmware when available,
resource paths/types, bounded field schemas including unmapped resources,
known numeric reading samples, and connection stage/error classification.
Existing batch/directory reads supply the evidence; no diagnostic network probe,
security-resource read, or command is added. Unknown scalar values are omitted.

The authenticated English UI previews the full JSON and downloads that exact
snapshot locally. No report is uploaded. Failed/unattempted connections may have
no schema; the report says so. Reports are regenerated after service restart.
Known numeric samples may describe appliance use, and model/firmware identify the
product, so users must review before sharing publicly.

Source includes Device support and Bug report GitHub issue templates, plus
docs/SUPPORT.md for collection, triage, fixture creation and hardware verification.
No remote repository, issue, upload or publication was created by this change.

Validation: 202 tests passed, PHP syntax and Ruff passed. Tests cover sensitive
field removal, omitted arbitrary values, identifier redaction, schema depth,
unattempted-device semantics, connection error stages and escaped HTML/JSON.
Existing fleet and upgrade-preservation tests still pass. Headless Edge confirmed
that clicking Download saves the same JSON snapshot as the rendered preview.
Two existing upstream pyOpenSSL deprecation warnings remain. Not installed or
tested on a physical LoxBerry in this development environment.
