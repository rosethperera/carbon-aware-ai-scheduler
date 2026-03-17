from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from carbon.fetch_carbon import fetch_carbon
from profiling.gpu_profiler import profile_gpu_power
from scheduling.emissions import (
    find_all_valid_schedules,
    parse_deadline,
    print_best_schedule,
    print_top_schedules,
    validate_positive_float,
    validate_positive_int,
)


def positive_float_arg(value: str) -> float:
    """Argparse validator for positive float values."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Value must be a number.") from exc

    try:
        return validate_positive_float(parsed, "value")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def positive_int_arg(value: str) -> int:
    """Argparse validator for positive integer values."""
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Value must be an integer.") from exc

    try:
        return int(validate_positive_int(parsed, "value"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def duration_hours_arg(value: str) -> int:
    """Validate that duration is a positive whole number of hours."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Duration must be a number of hours.") from exc

    try:
        validate_positive_float(parsed, "duration")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc

    if not parsed.is_integer():
        raise argparse.ArgumentTypeError(
            "Duration must be a whole number of hours because the forecast is hourly."
        )

    return int(parsed)


def determine_job_energy_kwh(args: argparse.Namespace) -> float:
    """Resolve job energy from either manual input or GPU profiling."""
    if args.energy is not None and args.profile_gpu:
        raise ValueError("Use either --energy or --profile-gpu, not both.")

    if args.energy is None and not args.profile_gpu:
        raise ValueError("Provide either --energy or --profile-gpu.")

    if args.energy is not None:
        return args.energy

    summary = profile_gpu_power(
        duration_seconds=args.profile_seconds,
        interval_seconds=args.profile_interval,
    )
    return float(summary["energy_kwh"])


def validate_runner_args(args: argparse.Namespace) -> None:
    """Validate runner arguments before starting network or profiling work."""
    if args.energy is not None and args.profile_gpu:
        raise ValueError("Use either --energy or --profile-gpu, not both.")

    if args.energy is None and not args.profile_gpu:
        raise ValueError("Provide either --energy or --profile-gpu.")

    if args.profile_interval > args.profile_seconds:
        raise ValueError("--profile-interval cannot be greater than --profile-seconds.")


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the end-to-end scheduler runner."""
    parser = argparse.ArgumentParser(
        description="Fetch the latest carbon forecast and rank the cleanest schedule windows."
    )
    parser.add_argument(
        "--duration",
        type=duration_hours_arg,
        required=True,
        help="Job duration in hours. Whole hours only because the forecast is hourly.",
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
    parser.add_argument(
        "--energy",
        type=positive_float_arg,
        default=None,
        help="Manual job energy in kWh.",
    )
    parser.add_argument(
        "--profile-gpu",
        action="store_true",
        help="Measure GPU energy and use the measured kWh instead of --energy.",
    )
    parser.add_argument(
        "--profile-seconds",
        type=positive_float_arg,
        default=10.0,
        help="GPU profiling duration in seconds. Default: 10.",
    )
    parser.add_argument(
        "--profile-interval",
        type=positive_float_arg,
        default=1.0,
        help="GPU profiling sample interval in seconds. Default: 1.",
    )
    return parser


def main() -> None:
    """Run the end-to-end carbon-aware scheduling workflow."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        validate_runner_args(args)
        parse_deadline(args.deadline)

        print("Fetching latest carbon forecast...\n")
        fetch_carbon()

        print("\nResolving job energy...\n")
        job_energy_kwh = determine_job_energy_kwh(args)
        print(f"Using job energy: {job_energy_kwh:.9f} kWh")

        schedule_df = find_all_valid_schedules(
            job_energy_kwh=job_energy_kwh,
            duration_hours=args.duration,
            deadline=args.deadline,
        )

    except (RuntimeError, FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    print_best_schedule(schedule_df)
    print_top_schedules(schedule_df, top_n=args.top)


if __name__ == "__main__":
    main()
