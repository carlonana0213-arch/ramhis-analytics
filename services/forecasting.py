import numpy as np

from services.croston import (
    weighted_patient_forecast
)

from services.ensemble import (
    combine_forecasts
)

from services.confidence import (
    generate_confidence
)

from services.prophet_model import (
    prophet_forecast
)

from services.medicineForecast import (
    generate_medicine_forecast
)

def generate_patient_forecast(
    mission_df,
    location,
    nextMissionDate,
    missionDays
):

    # ==================================
    # BASE MODELS
    # ==================================

    base_prediction = (
        weighted_patient_forecast(
            mission_df,
            missionDays
        )
    )

    prophet_prediction = (
        prophet_forecast(
            mission_df,
            nextMissionDate,
            missionDays
        )
    )

    # ==================================
    # MODEL SELECTION
    # ==================================

    ensemble_result = (
        combine_forecasts(
            base_prediction,
            prophet_prediction,
            mission_df
        )
    )

    predicted_patients = (
        ensemble_result[
            "prediction"
        ]
    )

    model_used = (
        ensemble_result[
            "model_used"
        ]
    )

    # ==================================
    # DEPARTMENT WORKLOAD FORECAST
    # ==================================

    department_counts = {}

    total_department_events = 0

    for dept_list in (
        mission_df[
            "departments"
        ]
    ):

        if not isinstance(
            dept_list,
            list
        ):
            continue

        for dept in dept_list:

            dept = str(
                dept
            ).strip()

            if not dept:
                continue

            department_counts[
                dept
            ] = (

                department_counts.get(
                    dept,
                    0
                )
                + 1
            )

            total_department_events += 1

    department_predictions = {}

    if total_department_events > 0:

        for dept, count in (
            department_counts.items()
        ):

            ratio = (
                count
                /
                total_department_events
            )

            department_predictions[
                dept
            ] = round(
                predicted_patients
                * ratio
            )
    # ==================================
# MEDICINE FORECAST
# ==================================

    medicine_forecast = (
    generate_medicine_forecast(
        mission_df,
        predicted_patients,
        missionDays
    )
)
    # ==================================
    # CONFIDENCE
    # ==================================

    confidence = (
        generate_confidence(
            mission_df,
            base_prediction,
            prophet_prediction,
            predicted_patients
        )
    )

    return {

    "location":
        location,

    "predictedPatients":
        predicted_patients,

    "departmentPredictions":
        department_predictions,

    "confidence":
        confidence[
            "label"
        ],

    "confidenceRange":
        confidence[
            "range"
        ],

    "modelsUsed": [
        model_used
    ],

    "medicineForecast":
        medicine_forecast
}