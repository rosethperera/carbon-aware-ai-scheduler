import os
from pathlib import Path

import requests
import pandas as pd


def get_project_root():
    """Return the repository root based on this file location."""
    return Path(__file__).resolve().parents[2]


def fetch_carbon():
    """Fetch the latest carbon forecast and save it to the data folder."""
    api_key = os.getenv("ELECTRICITY_MAPS_API_KEY")
    if not api_key:
        raise ValueError("ELECTRICITY_MAPS_API_KEY is not set in the terminal.")

    output_path = get_project_root() / "data" / "carbon_forecast.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    url = "https://api.electricitymaps.com/v3/carbon-intensity/forecast"

    headers = {
        "auth-token": api_key
    }

    params = {
        "zone": "US-MIDW-MISO"
    }

    response = requests.get(url, headers=headers, params=params, timeout=20)

    if response.status_code != 200:
        raise RuntimeError(f"Electricity Maps API request failed: {response.text}")

    data = response.json()

    records = []

    for entry in data["forecast"]:
        records.append({
            "time": entry["datetime"],
            "carbon": entry["carbonIntensity"]
        })

    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False)

    print(f"Carbon data saved to {output_path}")
    print(df.head())
    return df


if __name__ == "__main__":
    fetch_carbon()
