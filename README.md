# Carbon-Aware AI Scheduler

## PowerShell Setup

Set your Electricity Maps API key in the VS Code PowerShell terminal:

```powershell
$env:ELECTRICITY_MAPS_API_KEY="your_api_key_here"
```

## Run `emissions.py` Directly

Use a manual energy value in kWh:

```powershell
python src/scheduling/emissions.py --energy 2.5 --duration 2 --top 5
```

Optionally add a deadline:

```powershell
python src/scheduling/emissions.py --energy 2.5 --duration 2 --deadline 2026-03-18T12:00:00Z --top 3
```

## Run the End-to-End Runner

Manual energy mode:

```powershell
python src/runner/run_scheduler.py --duration 2 --energy 2.5 --top 5
```

GPU profiling mode:

```powershell
python src/runner/run_scheduler.py --duration 2 --profile-gpu --profile-seconds 10 --profile-interval 1 --top 5
```

## Sample Workflow

1. Set `ELECTRICITY_MAPS_API_KEY` in PowerShell.
2. Run the scheduler with `--energy` if you already know the job energy in kWh.
3. Run the scheduler with `--profile-gpu` if you want to estimate energy from NVIDIA GPU power measurements first.
4. Review the best schedule and top ranked schedule windows printed in the terminal.
