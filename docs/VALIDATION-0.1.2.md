# Validation — 0.1.2

72 automated tests passed on Windows/Python 3.12 with PHP 8.3.35. Ruff and PHP
syntax checks passed. Two pre-existing upstream pyOpenSSL deprecation warnings
remain. No connection to the user's appliance was made from the development host.

The user reported "Authenticated; no supported readable appliance resources"
after the 0.1.1 compatibility test. That code path establishes that the session
and identity read succeeded, but does not establish appliance-data authorization.
The old supervisor incorrectly replaced the resource failure status with
"auth required" when it saw the preliminary ownership-method hint.

Changes:

- Read the known Samsung `/device/0` collection without depending on it being
  advertised by `/oic/res`, matching the upstream discovery approach.
- Extract supported nonempty batch representations and use them as sensor data.
  Refresh the batch on later polls; use individual reads only for missing fields.
- Keep security resources and stub representations out of the extracted data.
- Do not report an online device or verified certificate compatibility when no
  mapped readings exist. Optional forbidden reads can be skipped without masking
  other available batch data; identity reads still fail on authorization denial.
- Preserve unsupported/identity-conflict/disabled statuses instead of replacing
  them with a generic authentication label.
- Provide read-response diagnostics without raw representations or credentials.
- An explicit retry of an unverified PKI-hint resource failure stays read-only
  and one-shot instead of being blocked by the preliminary hint again.

New regressions cover an unadvertised collection, batch-only dryer readings,
refresh on subsequent polls, security/stub exclusion, empty-data rejection and
status preservation. The fixture shape references LocalThings' MIT-licensed
DV6800N fixture. Hardware acceptance remains pending: install as an update,
run the read-only compatibility test, and inspect readings or Resource diagnostics.
