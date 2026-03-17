from pathlib import Path
import argparse

import pandas as pd


def load_forecast():
    """Load and clean the carbon forecast CSV used for scheduling."""
    project_root = Path(__file__).resolve().parents[2]
    csv_path = project_root / "data" / "carbon_forecast.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Forecast file not found: {csv_path}")

    df = pd.read_csv(csv_path)

    if "time" not in df.columns or "carbon" not in df.columns:
        raise ValueError("CSV must contain 'time' and 'carbon' columns.")

    df["time"] = pd.to_datetime(df["time"], utc=True)
    df["carbon"] = pd.to_numeric(df["carbon"], errors="coerce")

    df = df.dropna(subset=["time", "carbon"]).sort_values("time").reset_index(drop=True)
    return df


def calculate_window_emissions(window, job_energy_kwh):
    """Calculate total emissions for a schedule window in grams of CO2."""
    duration_hours = len(window)

    if duration_hours <= 0:
        raise ValueError("Window must contain at least one forecast row.")

    energy_per_hour = job_energy_kwh / duration_hours
    total_emissions_g = (window["carbon"] * energy_per_hour).sum()
    return total_emissions_g


def parse_deadline(deadline):
    """Parse a deadline string into a timezone-aware UTC timestamp."""
    if deadline is None:
        return None

    deadline_ts = pd.to_datetime(deadline, utc=True, errors="coerce")
    if pd.isna(deadline_ts):
        raise ValueError(
            "Invalid deadline format. Use an ISO-like datetime such as "
            "'2026-03-18T12:00:00Z'."
        )
    return deadline_ts


def validate_positive_float(value, argument_name):
    """Validate that a CLI numeric argument is a positive float."""
    if value <= 0:
        raise ValueError(f"{argument_name} must be greater than 0.")
    return value


def validate_positive_int(value, argument_name):
    """Validate that a CLI numeric argument is a positive integer."""
    if value <= 0:
        raise ValueError(f"{argument_name} must be greater than 0.")
    return value


def find_all_valid_schedules(job_energy_kwh, duration_hours, deadline=None):
    """Return all valid schedule windows ranked by total emissions."""
    df = load_forecast()

    job_energy_kwh = validate_positive_float(job_energy_kwh, "job_energy_kwh")
    duration_hours = validate_positive_int(duration_hours, "duration_hours")

    if len(df) < duration_hours:
        raise ValueError("Not enough forecast rows for this job duration.")

    deadline_ts = parse_deadline(deadline)
    schedules = []

    for i in range(len(df) - duration_hours + 1):
        window = df.iloc[i:i + duration_hours].copy()

        start_time = window.iloc[0]["time"]
        end_time = window.iloc[-1]["time"]

        if deadline_ts is not None and end_time > deadline_ts:
            continue

        total_emissions_g = calculate_window_emissions(window, job_energy_kwh)

        schedules.append({
            "start_time": start_time,
            "end_time": end_time,
            "duration_hours": duration_hours,
            "job_energy_kwh": job_energy_kwh,
            "avg_carbon": window["carbon"].mean(),
            "total_emissions_g": total_emissions_g
        })

    if not schedules:
        raise ValueError("No valid schedules found before the deadline.")

    result_df = pd.DataFrame(schedules).sort_values("total_emissions_g").reset_index(drop=True)
    return result_df


def format_timestamp(timestamp):
    """Format timestamps consistently for terminal output."""
    return timestamp.strftime("%Y-%m-%d %H:%M UTC")


def format_energy_kwh(value):
    """Format energy values without scientific notation."""
    if value < 0.001:
        return f"{value:.6f}"
    if value < 0.01:
        return f"{value:.5f}"
    if value < 0.1:
        return f"{value:.4f}"
    return f"{value:.3f}"


def format_emissions_g(value):
    """Format emissions values without scientific notation."""
    if value < 0.1:
        return f"{value:.4f}"
    if value < 1:
        return f"{value:.3f}"
    return f"{value:.2f}"


def build_table(rows, columns):
    """Build a fixed-width text table that prints cleanly in PowerShell."""
    widths = []
    for index, column in enumerate(columns):
        max_width = len(column)
        for row in rows:
            max_width = max(max_width, len(str(row[index])))
        widths.append(max_width)

    header = "  ".join(column.ljust(widths[index]) for index, column in enumerate(columns))
    separator = "  ".join("-" * widths[index] for index in range(len(columns)))
    body = [
        "  ".join(str(value).ljust(widths[index]) for index, value in enumerate(row))
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def print_best_schedule(schedule_df):
    """Print the single lowest-emissions schedule."""
    best = schedule_df.iloc[0]
    worst = schedule_df.iloc[-1]
    savings_g = worst["total_emissions_g"] - best["total_emissions_g"]

    print("\nBEST CARBON-AWARE SCHEDULE\n")
    print(f"Start time:       {format_timestamp(best['start_time'])}")
    print(f"End time:         {format_timestamp(best['end_time'])}")
    print(f"Duration:         {best['duration_hours']} hour(s)")
    print(f"Job energy:       {format_energy_kwh(best['job_energy_kwh'])} kWh")
    print(f"Average carbon:   {best['avg_carbon']:.2f} gCO2/kWh")
    print(f"Total emissions:  {format_emissions_g(best['total_emissions_g'])} gCO2")
    print(
        "Emissions range:  "
        f"best {format_emissions_g(best['total_emissions_g'])} gCO2 | "
        f"worst {format_emissions_g(worst['total_emissions_g'])} gCO2 | "
        f"savings {format_emissions_g(savings_g)} gCO2"
    )


def print_top_schedules(schedule_df, top_n=5):
    """Print the lowest-emissions schedules in a compact ranked table."""
    top_n = validate_positive_int(top_n, "top_n")
    top = schedule_df.head(top_n).copy()

    columns = [
        "Rank",
        "Start",
        "End",
        "Hours",
        "Energy (kWh)",
        "Avg Carbon",
        "Emissions",
    ]
    rows = [
        [
            str(index),
            format_timestamp(row["start_time"]),
            format_timestamp(row["end_time"]),
            str(int(row["duration_hours"])),
            format_energy_kwh(row["job_energy_kwh"]),
            f"{row['avg_carbon']:.2f} gCO2/kWh",
            f"{format_emissions_g(row['total_emissions_g'])} gCO2",
        ]
        for index, (_, row) in enumerate(top.iterrows(), start=1)
    ]

    print(f"\nTOP {len(rows)} VALID SCHEDULES\n")
    print(build_table(rows, columns))


def positive_float_arg(value):
    """Argparse wrapper for positive float validation."""
    try:
        return validate_positive_float(float(value), "energy")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def positive_int_arg(value):
    """Argparse wrapper for positive integer validation."""
    try:
        return validate_positive_int(int(value), "integer value")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def build_parser():
    """Create the CLI argument parser for the emissions scheduler."""
    parser = argparse.ArgumentParser(description="Carbon-aware job scheduler")
    parser.add_argument(
        "--energy",
        type=positive_float_arg,
        required=True,
        help="Total job energy in kWh. Must be greater than 0.",
    )
    parser.add_argument(
        "--duration",
        type=positive_int_arg,
        required=True,
        help="Job duration in whole hours. Must be greater than 0.",
    )
    parser.add_argument(
        "--deadline",
        type=str,
        default=None,
        help="Latest allowed schedule end time, for example 2026-03-18T12:00:00Z.",
    )
    parser.add_argument(
        "--top",
        type=positive_int_arg,
        default=5,
        help="Number of ranked schedules to print. Default: 5.",
    )
    return parser


def main():
    """Run the CLI workflow for ranking valid schedule windows."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        schedule_df = find_all_valid_schedules(
            job_energy_kwh=args.energy,
            duration_hours=args.duration,
            deadline=args.deadline,
        )
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print_best_schedule(schedule_df)
    print_top_schedules(schedule_df, top_n=args.top)


if __name__ == "__main__":
    main()
