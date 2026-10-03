# Validation — 0.1.1

67 tests passed on Windows with Python 3.12 and PHP 8.3.35. No tests skipped.
Ruff checks and PHP syntax passed. Two existing upstream pyOpenSSL deprecation
warnings remain. The installation ZIP was rebuilt from the tested source.

New regressions cover a one-shot compatibility test sending only reads, keeping
queued commands undispatched, not retrying timeouts, consuming an explicit test
request once, preserving failure diagnostics, and following an address change for
a previously read-verified device despite the same public PKI hint.

This fixes an overly strong inference in 0.1.0: advertised ownership method 65282
was treated as definitive evidence that the generated certificate would fail, and
Retry connection could not get past that gate. Unknown devices remain blocked by
default; the new explicit read-only action obtains actual connection/read evidence.

The reported DV9BN8288AW/EN and software version 02198A230708(E257) prompted the
review. Samsung associates that model with DV8800N/DV6800N documentation, and
LocalThings contains a DV6800N fixture with the same software string. Neither
fact confirms this particular appliance's certificate compatibility.

No connection to the user's dryer was performed here. Its authentication,
resource compatibility, and the LoxBerry upgrade still require the user's test.
