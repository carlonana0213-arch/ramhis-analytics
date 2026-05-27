from fastapi import (
    FastAPI
)

from fastapi.middleware.cors import (
    CORSMiddleware
)

from services.preprocessing import (
    prepare_mission_dataframe
)

from services.forecasting import (
    generate_patient_forecast
)

from services.medicineForecast import (
    generate_medicine_forecast
)

from services.insights import (
    generate_insights
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]
)


@app.get("/")
def root():

    return {
        "message":
            "Analytics Service v2 Running"
    }


@app.post(
    "/generate-forecast"
)
def generate_forecast(
    payload: dict
):

    location = payload.get(
        "location"
    )

    next_mission_date = (
        payload.get(
            "nextMissionDate"
        )
    )

    mission_days = int(
        payload.get(
            "missionDays",
            1
        )
    )

    mission_df = (
        prepare_mission_dataframe(
            location
        )
    )

    if mission_df.empty:

        return {
            "error":
                "No mission data found."
        }

    forecast = (
        generate_patient_forecast(
            mission_df=
            mission_df,

            location=
            location,

            nextMissionDate=
            next_mission_date,

            missionDays=
            mission_days
        )
    )

    medicine_forecast = (
        generate_medicine_forecast(
            mission_df,
            forecast[
                "predictedPatients"
            ],
            mission_days
        )
    )

    insights = (
        generate_insights(
            mission_df
        )
    )

    return {

        **forecast,

        "medicineForecast":
            medicine_forecast,

        **insights
    }