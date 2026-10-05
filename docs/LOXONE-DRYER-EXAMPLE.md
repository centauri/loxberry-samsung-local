# Samsung dryer: Loxone Config example

This example uses the adapter's actual HTTP input and output XML templates.
It is a wiring recipe for your existing project, not a replacement Miniserver
project. No copying of ordinary virtual inputs is required.

## Import and enable

1. Install 0.2.18, let the dryer connect, and open its appliance settings.
2. Select **Allow supported controls for this appliance** and save.
3. In **Loxone input export**, download the input XML and dryer output XML.
   Set a LoxBerry URL reachable from the Miniserver. Both files contain private
   tokens; the output token grants control. Keep them out of public repositories.
4. In Config, import the input XML under **Virtual HTTP Input Templates** and add
   it to the project. Import the output XML under **Virtual Output Templates**
   and add it too. Avoid duplicating an existing input template.
5. Set the dryer course and load at its physical panel. Enable Smart Control.
   The adapter never turns Smart Control on, disables child lock or powers on
   the dryer. These remain physical/device-managed controls.

## Readout page

Use the `vs_0` operational readings as the primary set. The `operational_state_0`
fields duplicate some of them and can be kept for diagnosis rather than displayed twice.

| Reading suffix / exported label | Example display or logic |
|---|---|
| Samsung Local service available | 1 means the service heartbeat is fresh |
| Dryer available | 1 means service fresh and dryer online |
| power | Power indicator: 0 off / 1 on |
| child_lock | Child-lock indicator: 0 unlocked / 1 locked |
| remote_control | Smart Control indicator: 0 off / 1 on |
| energy_consumption_vs_0_energy_wh | Divide by 1000 for cumulative kWh; do not label it cycle consumption |
| operational_state_vs_0_state | -1 unknown; 0 ready; 1 running; 2 paused; 3 finished; 4 off; 5 idle; 6 error; 7 stopped |
| operational_state_vs_0_remainingTime | Seconds; divide by 60 for minutes (11520 = 192 minutes) |
| operational_state_vs_0_progressPercentage | Progress, percent |
| operational_state_vs_0_progress | 1 drying; -1 an unmapped phase (not an appliance error) |
| operational_state_0_currentJobState | Same phase mapping; redundant readout |
| operational_state_0_currentMachineState | 1 active; 2 paused; 5 idle; -1 unknown |
| washer_vs_0_dryLevel | Raw dry-level code (e.g. 3); no unverified descriptive labels |
| washer_vs_0_dryTime | Duration in seconds, distinct from remaining time |
| washer_vs_0_wrinklePrevent | 0 off; 1 on; -1 unknown |
| last command result | 0 none; 1 accepted; 2 rejected; 3 uncertain; 4 busy; -1 unknown |
| last command Unix time | Timestamp of that result; do not mistake an old acceptance for the latest request |

Use numeric displays, indicators and comparisons in Config. Gate every readout
that drives automation with both availability values and the HTTP input's error
output being clear. Loss of the HTTP connection can leave old input values visible.

## Buttons and gates

Create equality comparisons for the conditions below, combine them with AND/OR
blocks, and connect a short button pulse through the corresponding AND gate to
the named imported virtual output command. Use one pulse per press (e.g. 0.2 s),
not a maintained switch. Keep output repetition disabled. Leave at least three
seconds between commands; the adapter rate-limits requests per device.

```text
Service=1 ─────────────┐
Dryer available=1 ─────┤
HTTP error=0 ──────────┤
Power=1 ───────────────┼─ AND ── Permission
Smart Control=1 ──────┤
Child lock=0 ──────────┘

Start/resume button pulse ─┐
Permission ────────────────┼─ AND ── output: Start or resume
(State=0 OR State=2) ──────┘

Pause button pulse ───────┐
Permission ───────────────┼─ AND ── output: Pause
State=1 ──────────────────┘

Stop button pulse ────────┐
Permission ───────────────┼─ AND ── output: Stop cycle
(State=1 OR State=2) ──────┘

Wrinkle ON button pulse ──┬─ AND ── output: Wrinkle prevention on
Permission ───────────────┘
Wrinkle OFF button pulse ─┬─ AND ── output: Wrinkle prevention off
Permission ───────────────┘
```

Smart Control enables permission; its rising edge must not start the dryer.
An explicit button pulse supplies the request. Automatic policies can later
replace the button, but should still use the same permission and state gates.
Do not loop retries on an unchanged state or a timeout.

## Check results

The HTTP endpoint returns 202 for a queued command, not an executed command.
The worker checks fresh power, Smart Control, child lock and operational state
again in the authenticated device session before sending the fixed allowlisted
write. A device acceptance response is recorded separately from the actual
readback. No write is automatically retried on an ambiguous result.

After Start/Resume, verify state becomes 1; after Pause, verify 2; after Stop,
verify 0 (Ready). After wrinkle commands, verify 1/0 on wrinklePrevent.
Input polling adds up to 30 seconds of display latency, plus any appliance
response/read time. An example confirmation timer can flag **not confirmed**
after 60 seconds without the expected state; it must not resend the command.
See the appliance's last command result and service log if confirmation fails.

The first hardware test should be a user-triggered Pause while present at the
running dryer, followed by checking the panel and state. This example's protocol
payloads and interlocks have automated tests; writes on your DV9BN8288AW/EN have
not yet been verified. No live commands were sent during development.

## Scope and community reference

Start/Resume writes Run, Pause writes Pause, and Stop writes Ready to
`/operational/state/vs/0`. Wrinkle prevention writes On/Off to `/washer/vs/0`.
These follow the upstream [dryer descriptor](https://github.com/QuiteYellow/SmartThings-Local/blob/main/mqtt_demo/samples/dryer.py).
The adapter adds stricter local interlocks and an explicit opt-in. It does not
offer course changes, dry-level changes, power control or ownership/security writes
for dryers. Readability alone is not a guarantee that a particular firmware accepts writes.
