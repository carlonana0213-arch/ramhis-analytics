from collections import defaultdict

from utils.mongo import (
    prescriptions_collection,
    medicines_collection
)


def generate_medicine_forecast(
    mission_df,
    predicted_patients,
    mission_days=1
):

    if mission_df.empty:
        return []

    historical_patients = int(
        mission_df[
            "Patients"
        ].sum()
    )

    if historical_patients == 0:
        return []

    # ==================================
    # BUILD MEDICINE LOOKUP
    # ==================================

    medicine_lookup = {}

    medicines = list(
        medicines_collection.find()
    )

    for med in medicines:

        medicine_lookup[
            str(med["_id"])
        ] = (
            med.get(
                "name",
                "Unknown"
            )
            .strip()
            .lower()
        )

    # ==================================
    # AGGREGATE QUANTITY
    # ==================================

    medicine_totals = defaultdict(
        int
    )

    prescriptions = list(
        prescriptions_collection.find()
    )

    for prescription in prescriptions:
        
            

        items = prescription.get(
            "items",
            []
        )

        for item in items:

            medicine_name = None

            # ==========================
            # CASE 1:
            # direct medicine name
            # ==========================

            if item.get(
                "medicineName"
            ):

                medicine_name = str(
                    item.get(
                        "medicineName"
                    )
                ).strip().lower()

            # ==========================
            # CASE 2:
            # medicine field already
            # stores the name
            # ==========================

            elif isinstance(
                item.get(
                    "medicine"
                ),
                str
            ):

                medicine_name = str(
                    item.get(
                        "medicine"
                    )
                ).strip().lower()

            # ==========================
            # CASE 3:
            # ObjectId lookup
            # ==========================

            else:

                med_id = str(
                    item.get(
                        "medicine"
                    )
                )

                medicine_name = (
                    medicine_lookup.get(
                        med_id
                    )
                )

            quantity = int(
                item.get(
                    "quantity",
                    0
                )
            )

            if (
                medicine_name
                and quantity > 0
            ):

                medicine_totals[
                    medicine_name
                ] += quantity

    result = []

    # ==================================
    # FORECAST
    # ==================================

    for med_name, total_qty in (
        medicine_totals.items()
    ):

        avg_per_patient = (
            total_qty
            /
            historical_patients
        )

        estimated_need = round(

            predicted_patients
            *
            avg_per_patient
        )

        # contingency buffer

        estimated_need = round(
            estimated_need
            * 1.20
        )

        risk = "LOW"

        if estimated_need > 120:
            risk = "HIGH"

        elif estimated_need > 40:
            risk = "MEDIUM"

        result.append({

            "medicine":
                med_name,

            "estimatedNeed":
                estimated_need,

            "risk":
                risk
        })

    result.sort(

        key=lambda x:
        x[
            "estimatedNeed"
        ],

        reverse=True
    )

    return result[:20]