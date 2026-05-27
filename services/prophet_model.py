import pandas as pd
from prophet import Prophet


def prophet_forecast(
    mission_df,
    next_mission_date,
    mission_days
):

    if len(mission_df) < 4:
        return 0

    # ==================================
    # KEEP ONLY RECENT HISTORY
    # ==================================

    mission_df = (
        mission_df
        .sort_values(
            "missionStart"
        )
        .tail(24)
    )

    df = pd.DataFrame({

        "ds":
            pd.to_datetime(
                mission_df[
                    "missionStart"
                ]
            ),

        "y":
            mission_df[
                "PatientsPerDay"
            ]
    })

    model = Prophet(

        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,

        changepoint_prior_scale=0.03,

        uncertainty_samples=0
    )

    model.fit(df)

    future = pd.DataFrame({

        "ds": [
            pd.to_datetime(
                next_mission_date
            )
        ]
    })

    forecast = model.predict(
        future
    )

    predicted_daily = max(

        0,

        round(
            forecast[
                "yhat"
            ].iloc[0]
        )
    )

    historical_max = (
        mission_df[
            "PatientsPerDay"
        ]
        .max()
    )

    predicted_daily = min(
        predicted_daily,
        historical_max * 1.25
    )

    return round(
        predicted_daily
        * mission_days
    )