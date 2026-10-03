# Keeping the adapter current

After publishing this source on your repository's default branch, enable GitHub
Actions. Review upstream changes runs weekly on Monday at 07:23 UTC, or manually
from Actions > Review upstream changes > Run workflow. No personal token is needed.

The read-only job compares tools/upstream.json reviewed commits with each upstream
default branch. It lists relevant changed paths and links exact comparisons. It
never executes upstream code or changes pins. Reports are in the run summary and
the upstream-review artifact (30-day retention).

A changed head fails the check deliberately to draw attention. API/network errors
also fail: consult the log to distinguish a review alert from a failed check.
Enable GitHub Actions failure notifications for your account if you want email.
Outstanding changes will continue to fail weekly until the reviewed baseline is
advanced; no issues, comments or duplicate support requests are created.

Review the diff, new device fixtures and diagnostics changes. Use replay_report.py
for reviewed captures, add explicit regression expectations, adapt the mapping or
pin the reviewed protocol revision, and run the normal Validate plugin workflow.
Record decisions and licensing provenance, then advance reviewed_commit. This
baseline means reviewed, not full upstream feature parity: document deferred work.
Installed dependency pins and mapping provenance remain separate and must describe
what was actually adopted. Release an adapter ZIP after tests and hardware checks.

This detects committed changes, not every issue discussion or unmerged proposal.
GitHub schedules can be delayed and public repositories' schedules can be disabled
after 60 days of inactivity. Use the manual trigger to check or reactivate as needed.
See https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule.

Local check: python tools/check_upstream.py --output dist/upstream
Add --fail-on-change when an exit code of 2 should signal pending upstream review.
