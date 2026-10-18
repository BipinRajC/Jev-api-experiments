# Daily data update timer

These files capture the systemd **user** service and timer installed on the research laptop on 2026-10-18. The service runs `python -m src.data.cli daily` each day at about 07:30 local time, saves output to `logs/daily.log`, prevents overlapping daily runs, and holds a sleep inhibitor while it works.

The service contains the current checkout path `/home/bipin/jev-api-experiments`. Edit its `WorkingDirectory`, log paths, and Python path when using a different checkout. The timer is installed outside this repository in `~/.config/systemd/user/`; committing these copies does not install or restart it.

To install after adjusting the service path:

```bash
mkdir -p ~/.config/systemd/user
cp ops/systemd/footyquant-daily.service ops/systemd/footyquant-daily.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now footyquant-daily.timer
systemctl --user status footyquant-daily.timer
```

The `Persistent=true` timer catches a run missed while the user manager was inactive. The laptop must still be awake and connected while a run downloads data; the service's sleep inhibitor applies only during the run.

## Pregame quote capture

`footyquant-pregame.timer` checks every five minutes for fixtures whose 60-minute cutoff falls within the next 15 minutes. It calls `capture-due`, which archives one ESPN page per due competition/date and refreshes `data/derived/forward_quotes.parquet`. Captures made after kickoff or after the requested cutoff are marked ineligible. The ESPN feed displays a `close` price even before kickoff, but its own quote time and executability are not verified; preserve its `price_semantics` field when analyzing markets.

The pregame timer was enabled on the research laptop on 2026-10-18; its first manual service test exited successfully. The instructions below apply to a new or restored checkout.

The pregame timer is not persistent: a capture missed while the machine sleeps cannot be reconstructed later. To install it after checking the service paths:

```bash
cp ops/systemd/footyquant-pregame.service ops/systemd/footyquant-pregame.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now footyquant-pregame.timer
systemctl --user status footyquant-pregame.timer
```

## Prospective Jev predictions (Experiment 024)

`footyquant-predict.timer` runs `experiments/024-prospective-series/predict_due.py` every five minutes. For each upcoming fixture whose kickoff is 62–80 minutes away it builds the allowlisted as-of state, calls all six core arms (Noul/Score/Choice × 1X2/binary markets, question set QSET-020-v1), and appends one immutable prediction record per arm to `results/024-prospective-series/predictions.jsonl` before the 60-minute cutoff. Records include the request/response UTC times, the pre-cutoff flag, token usage, and any ESPN quote captured within 15 minutes before the request; failed attempts go to `attempts.jsonl` and are retried on later ticks only while the fixture is still pre-cutoff. The runner is idempotent (arm-level done keys) and never rewrites a record.

This is a separate, explicit prediction path: the pregame quote-capture timer above does not perform Jev inference. Settlement is a later, separate step (`experiments/024-prospective-series/settle.py`), which appends label records to `settlements.jsonl` without touching predictions.

To install after checking the service paths:

```bash
cp ops/systemd/footyquant-predict.service ops/systemd/footyquant-predict.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now footyquant-predict.timer
systemctl --user status footyquant-predict.timer
```

Like the pregame timer, the predict timer is not persistent: a prediction window missed while the machine sleeps is gone; the affected fixture is recorded as missing, never backfilled post-match.
