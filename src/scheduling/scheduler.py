import pandas as pd


def find_best_time():
    df = pd.read_csv("data/carbon_forecast.csv")

    best_row = df.loc[df["carbon"].idxmin()]

    print("\nBEST TIME TO RUN")
    print("Time:", best_row["time"])
    print("Carbon:", best_row["carbon"], "gCO2/kWh")


if __name__ == "__main__":
    find_best_time()