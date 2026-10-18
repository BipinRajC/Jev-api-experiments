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
