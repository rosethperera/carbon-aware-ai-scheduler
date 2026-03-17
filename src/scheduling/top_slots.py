import pandas as pd


def show_top_slots():
    df = pd.read_csv("data/carbon_forecast.csv")
    best = df.sort_values("carbon").head(5)

    print("\nTOP 5 CLEANEST TIME SLOTS\n")
    print(best.to_string(index=False))


if __name__ == "__main__":
    show_top_slots()