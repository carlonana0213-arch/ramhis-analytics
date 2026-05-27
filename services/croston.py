from statsforecast import StatsForecast
from statsforecast.models import CrostonSBA
import pandas as pd


def weighted_patient_forecast(
    mission_df,
    mission_days
):

    history = (
        mission_df[
            "PatientsPerDay"
        ]
        .tolist()
    )

    if len(history) == 0:
        return 0

    if len(history) == 1:

        return round(
            history[0]
            * mission_days
        )

    # ======================
    # RECENCY WEIGHTS
    # ======================

    weights = []

    for i in range(
        len(history)
    ):

        weights.append(
            i + 1
        )

    total_weight = sum(
        weights
    )

    weighted_daily = sum(

        h * w

        for h, w in zip(
            history,
            weights
        )

    ) / total_weight

    return round(
        weighted_daily
        * mission_days
    )