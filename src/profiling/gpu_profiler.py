from __future__ import annotations

import argparse
import csv
import subprocess
import time
from pathlib import Path


def get_project_root() -> Path:
    """Return the repository root based on this file location."""
    return Path(__file__).resolve().parents[2]


def query_gpu_name() -> str:
    """Return the first NVIDIA GPU name reported by nvidia-smi."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "nvidia-smi was not found. Install NVIDIA drivers and ensure "
            "nvidia-smi is available in your PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "Unknown nvidia-smi error."
        raise RuntimeError(f"Unable to query NVIDIA GPU name: {message}") from exc

    gpu_names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not gpu_names:
        raise RuntimeError("No NVIDIA GPU was found by nvidia-smi.")

    return gpu_names[0]


def query_power_draw_watts() -> float:
    """Return the current power draw in watts for the first NVIDIA GPU."""
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=power.draw",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "nvidia-smi was not found. Install NVIDIA drivers and ensure "
            "nvidia-smi is available in your PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or "Unknown nvidia-smi error."
        raise RuntimeError(f"Unable to query GPU power draw: {message}") from exc

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("No NVIDIA GPU power data was returned by nvidia-smi.")

    raw_value = lines[0]
    try:
        return float(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"Unexpected GPU power value: {raw_value}") from exc


def validate_positive_float(value: str) -> float:
    """Argparse validator for positive float values."""
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("Value must be greater than 0.")
    return parsed


def calculate_energy_wh(samples: list[dict[str, float]]) -> float:
    """Estimate energy from sampled power using trapezoidal integration."""
    if len(samples) < 2:
        return 0.0

    total_wh = 0.0
    for previous, current in zip(samples, samples[1:]):
        delta_hours = (current["elapsed_seconds"] - previous["elapsed_seconds"]) / 3600.0
        average_power = (previous["power_watts"] + current["power_watts"]) / 2.0
        total_wh += average_power * delta_hours

    return total_wh


def save_power_log(samples: list[dict[str, float]], output_path: Path) -> None:
    """Save sampled GPU power readings to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=["sample_index", "elapsed_seconds", "power_watts"],
        )
        writer.writeheader()
        writer.writerows(samples)


def collect_samples(interval_seconds: float, stop_condition) -> list[dict[str, float]]:
    """Collect GPU power samples until the provided stop condition returns True."""
    samples: list[dict[str, float]] = []
    start_time = time.time()
    sample_index = 1

    while True:
        now = time.time()
        elapsed_seconds = now - start_time
        power_watts = query_power_draw_watts()

        samples.append(
            {
                "sample_index": sample_index,
                "elapsed_seconds": round(elapsed_seconds, 3),
                "power_watts": round(power_watts, 3),
            }
        )

        if stop_condition(elapsed_seconds):
            break

        sample_index += 1
        time.sleep(interval_seconds)

    return samples


def collect_gpu_power_samples(duration_seconds: float, interval_seconds: float) -> tuple[str, list[dict[str, float]], Path]:
    """Collect repeated GPU power samples for a fixed duration."""
    if interval_seconds > duration_seconds:
        raise ValueError("interval_seconds cannot be greater than duration_seconds.")

    project_root = get_project_root()
    output_path = project_root / "data" / "gpu_power_log.csv"

    gpu_name = query_gpu_name()
    print(f"Profiling GPU power for: {gpu_name}")
    print(f"Duration: {duration_seconds:.1f} seconds")
    print(f"Sample interval: {interval_seconds:.1f} seconds")
    print("Sampling power draw...\n")

    samples = collect_samples(
        interval_seconds=interval_seconds,
        stop_condition=lambda elapsed_seconds: elapsed_seconds >= duration_seconds,
    )

    save_power_log(samples, output_path)
    return gpu_name, samples, output_path


def collect_gpu_power_for_command(command: str, interval_seconds: float) -> tuple[str, list[dict[str, float]], Path, int]:
    """Run a command and sample GPU power until the command exits."""
    project_root = get_project_root()
    output_path = project_root / "data" / "gpu_power_log.csv"

    gpu_name = query_gpu_name()
    print(f"Profiling GPU power for: {gpu_name}")
    print(f"Command: {command}")
    print(f"Sample interval: {interval_seconds:.1f} seconds")
    print("Starting command and sampling power draw...\n")

    try:
        process = subprocess.Popen(command, shell=True)
    except OSError as exc:
        raise RuntimeError(f"Unable to start command: {exc}") from exc

    samples = collect_samples(
        interval_seconds=interval_seconds,
        stop_condition=lambda _elapsed_seconds: process.poll() is not None,
    )

    return_code = process.wait()
    save_power_log(samples, output_path)
    return gpu_name, samples, output_path, return_code


def summarize_gpu_profile(gpu_name: str, samples: list[dict[str, float]], output_path: Path) -> dict[str, float | int | str]:
    """Build a summary dictionary from collected GPU power samples."""
    energy_wh = calculate_energy_wh(samples)
    energy_kwh = energy_wh / 1000.0
    average_power = sum(sample["power_watts"] for sample in samples) / len(samples)
    peak_power = max(sample["power_watts"] for sample in samples)

    return {
        "gpu_name": gpu_name,
        "samples": len(samples),
        "elapsed_seconds": samples[-1]["elapsed_seconds"],
        "average_power_w": average_power,
        "peak_power_w": peak_power,
        "energy_wh": energy_wh,
        "energy_kwh": energy_kwh,
        "output_path": str(output_path),
    }


def print_gpu_profile_summary(summary: dict[str, float | int | str]) -> None:
    """Print a clean terminal summary of GPU profiling results."""
    print("GPU POWER PROFILING SUMMARY")
    print(f"GPU:              {summary['gpu_name']}")
    print(f"Samples:          {summary['samples']}")
    print(f"Elapsed time:     {summary['elapsed_seconds']:.3f} seconds")
    print(f"Average power:    {summary['average_power_w']:.2f} W")
    print(f"Peak power:       {summary['peak_power_w']:.2f} W")
    print(f"Estimated energy: {summary['energy_wh']:.6f} Wh")
    print(f"Estimated energy: {summary['energy_kwh']:.9f} kWh")
    print(f"Saved log:        {summary['output_path']}")


def profile_gpu_power(duration_seconds: float, interval_seconds: float) -> dict[str, float | int | str]:
    """Sample GPU power, save the log, print the summary, and return it."""
    gpu_name, samples, output_path = collect_gpu_power_samples(
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
    )
    summary = summarize_gpu_profile(gpu_name, samples, output_path)

    print_gpu_profile_summary(summary)
    return summary


def profile_gpu_power_for_command(command: str, interval_seconds: float) -> dict[str, float | int | str]:
    """Profile GPU power while a command runs, then print and return the summary."""
    gpu_name, samples, output_path, return_code = collect_gpu_power_for_command(
        command=command,
        interval_seconds=interval_seconds,
    )
    summary = summarize_gpu_profile(gpu_name, samples, output_path)
    summary["command"] = command
    summary["command_exit_code"] = return_code

    print_gpu_profile_summary(summary)
    print(f"Command exit code: {return_code}")
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for GPU profiling."""
    parser = argparse.ArgumentParser(description="Profile NVIDIA GPU power usage over time.")
    parser.add_argument(
        "--duration",
        type=validate_positive_float,
        default=10.0,
        help="Total profiling time in seconds. Default: 10",
    )
    parser.add_argument(
        "--interval",
        type=validate_positive_float,
        default=1.0,
        help="Sampling interval in seconds. Default: 1",
    )
    parser.add_argument(
        "--command",
        type=str,
        default=None,
        help="Command to run while profiling GPU power, for example \"python some_script.py\".",
    )
    return parser


def main() -> None:
    """Run the GPU power profiler CLI."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command:
            profile_gpu_power_for_command(
                command=args.command,
                interval_seconds=args.interval,
            )
        else:
            profile_gpu_power(
                duration_seconds=args.duration,
                interval_seconds=args.interval,
            )
    except (RuntimeError, ValueError) as exc:
        parser.exit(status=1, message=f"Error: {exc}\n")


if __name__ == "__main__":
    main()
