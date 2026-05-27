def combine_forecasts(
    fallback_prediction,
    prophet_prediction,
    mission_df
):

    mission_count = len(
        mission_df
    )

    variability = (
        mission_df[
            "PatientsPerDay"
        ]
        .std()
    )

    # ==================================
    # TOO LITTLE DATA
    # ==================================

    if mission_count < 4:

        return {

            "prediction":
                fallback_prediction,

            "model_used":
                "Croston"
        }

    # ==================================
    # ENOUGH DATA → PROPHET ONLY
    # ==================================

    if (
        mission_count >= 6
        and variability < 150
    ):

        return {

            "prediction":
                prophet_prediction,

            "model_used":
                "Prophet"
        }

    # ==================================
    # MID-ZONE HYBRID
    # ==================================

    prediction = round(

        fallback_prediction
        * 0.70

        +

        prophet_prediction
        * 0.30
    )

    return {

        "prediction":
            prediction,

        "model_used":
                "Hybrid"
    }