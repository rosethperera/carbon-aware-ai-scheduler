# Carbon-Aware AI Scheduler

Carbon-Aware AI Scheduler is a Python command-line project that fetches carbon-intensity forecasts and ranks lower-emissions time windows for running an AI job.

## What It Does

This project helps estimate when an AI workload should run to reduce carbon emissions.

- Fetches hourly carbon-intensity forecast data from Electricity Maps for `US-MIDW-MISO`
- Loads forecast data from `data/carbon_forecast.csv`
- Ranks valid scheduling windows based on estimated total emissions
- Supports optional deadline filtering
- Can run end to end through a single runner script
- Can estimate job energy from NVIDIA GPU power sampling before scheduling

## Project Structure

```text
carbon-aware-ai-scheduler/
|-- data/
|   |-- carbon_forecast.csv
|-- src/
|   |-- carbon/
|   |   |-- fetch_carbon.py
|   |-- profiling/
|   |   |-- gpu_profiler.py
|   |-- runner/
|   |   |-- run_scheduler.py
|   |-- scheduling/
|   |   |-- emissions.py
|   |   |-- scheduler.py
|   |   |-- top_slots.py
|-- README.md
|-- requirements.txt
```

## Requirements

- Python 3
- `pandas`
- `requests`
- An Electricity Maps API key in the `ELECTRICITY_MAPS_API_KEY` environment variable
- For GPU profiling: an NVIDIA GPU, working drivers, and `nvidia-smi` available in `PATH`

## PowerShell Setup

Set the API key in your VS Code PowerShell terminal before fetching live forecast data:

```powershell
$env:ELECTRICITY_MAPS_API_KEY="your_api_key_here"
```

If you need to install dependencies manually, use:

```powershell
pip install pandas requests
```

## Usage

Fetch the latest carbon forecast:

```powershell
python src/carbon/fetch_carbon.py
```

Rank the top schedule windows using a manual energy estimate:

```powershell
python src/scheduling/emissions.py --energy 2.5 --duration 2 --top 5
```

Rank schedule windows with a deadline constraint:

```powershell
python src/scheduling/emissions.py --energy 2.5 --duration 2 --deadline 2026-03-18T12:00:00Z --top 3
```

Run the full workflow with manual energy input:

```powershell
python src/runner/run_scheduler.py --duration 2 --energy 2.5 --top 5
```

Run the full workflow with GPU power profiling:

```powershell
python src/runner/run_scheduler.py --duration 2 --profile-gpu --profile-seconds 10 --profile-interval 1 --top 5
```

## Sample Workflow

1. Set `ELECTRICITY_MAPS_API_KEY` in PowerShell.
2. Fetch or refresh the carbon forecast with `python src/carbon/fetch_carbon.py`.
3. Choose whether to provide a known job energy value or estimate it from GPU sampling.
4. Run the scheduler to rank the cleanest available time windows.
5. Review the best window and compare it with other top-ranked options.

## Example Output

```text
BEST CARBON-AWARE SCHEDULE

Start time:       2026-03-18 06:00 UTC
End time:         2026-03-18 07:00 UTC
Duration:         2 hour(s)
Job energy:       2.500 kWh
Average carbon:   312.40 gCO2/kWh
Total emissions:  781.00 gCO2
Emissions range:  best 781.00 gCO2 | worst 1048.50 gCO2 | savings 267.50 gCO2

TOP 3 VALID SCHEDULES

Rank  Start                 End                   Hours  Energy (kWh)  Avg Carbon       Emissions
----  --------------------  --------------------  -----  ------------  ---------------  ----------
1     2026-03-18 06:00 UTC  2026-03-18 07:00 UTC  2      2.500         312.40 gCO2/kWh  781.00 gCO2
2     2026-03-18 07:00 UTC  2026-03-18 08:00 UTC  2      2.500         318.10 gCO2/kWh  795.25 gCO2
3     2026-03-18 05:00 UTC  2026-03-18 06:00 UTC  2      2.500         324.80 gCO2/kWh  812.00 gCO2
```

## Why This Matters

AI workloads can be energy-intensive, and the carbon impact of electricity changes over time. Even simple scheduling decisions can reduce emissions without changing the workload itself. This project shows a practical workflow for combining live grid-carbon data with lightweight job-energy estimates to make cleaner execution choices.

## Current Limitations

- The scheduler currently assumes job energy is distributed evenly across the full job duration.
- Scheduling works on hourly forecast rows, so duration must be a whole number of hours.
- The project currently uses a single Electricity Maps zone: `US-MIDW-MISO`.
- GPU profiling is most meaningful when measured during a real GPU workload; idle or lightly loaded sampling can underrepresent actual job energy.
- GPU profiling estimates energy from observed GPU power draw only, not total system power.
- The README example output is illustrative and will differ from real forecast values.

## Future Improvements

- Add support for more grid regions and configurable forecast zones.
- Support sub-hour scheduling windows when higher-resolution forecast data is available.
- Profile a user-provided training or inference command directly as part of the runner workflow.
- Include CPU and full-system energy estimation alongside GPU measurements.
- Export ranked schedules to CSV or JSON for downstream automation.
- Add tests, dependency pinning, and a filled `requirements.txt` for easier setup.
