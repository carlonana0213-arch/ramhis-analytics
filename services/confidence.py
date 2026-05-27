import numpy as np


def generate_confidence(
    mission_df,
    croston_prediction,
    prophet_prediction,
    final_prediction
):

    mission_count = len(
        mission_df
    )

    values = (
        mission_df[
            "PatientsPerDay"
        ]
        .tolist()
    )

    variability = (
        np.std(values)
        if len(values) > 1
        else 0
    )

    disagreement = abs(
        croston_prediction
        -
        prophet_prediction
    )

    score = 100
  
    # ======================
    # DATA AMOUNT
    # ======================

    if mission_count < 2:
        score -= 35

    elif mission_count < 4:
        score -= 20

    # ======================
    # VARIANCE
    # ======================

    if variability > 20:
        score -= 15

    elif variability > 10:
        score -= 8

    # ======================
    # MODEL AGREEMENT
    # ======================

    if disagreement > 50:
        score -= 20

    elif disagreement > 20:
        score -= 10

    if score >= 90:
        label = "HIGH"

    elif score >= 60:
        label = "MEDIUM"

    elif score >= 40:
        label = "LOW"

    else:
        label = "VERY LOW"

    # ==================================
    # RANGE BASED ON ACTUAL PREDICTION
    # ==================================

    spread = max(
        10,
        round(
            final_prediction * 0.15
        )
    )

    return {

        "label":
            label,

        "range": {

            "min":
                max(
                    0,
                    final_prediction
                    -
                    spread
                ),

            "max":
                final_prediction
                +
                spread
        }
    }