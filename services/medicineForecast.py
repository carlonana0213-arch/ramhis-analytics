
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

    # ==========================
    # VALIDATION
    # ==========================

    if mission_df.empty:
        return []

    historical_patients = int(
        mission_df["Patients"].sum()
    )

    if historical_patients == 0:
        return []

    # ==========================
    # BUILD MEDICINE LOOKUP
    # ==========================

    medicine_lookup = {}

    medicines = list(
        medicines_collection.find()
    )

    for med in medicines:

        med_id = str(med["_id"])

        medicine_name = None

        # ==========================
        # NEW SCHEMA
        # names: []
        # ==========================

        if (
            isinstance(
                med.get("names"),
                list
            )
            and len(
                med.get("names")
            ) > 0
        ):

            medicine_name = str(
                med["names"][0]
            ).strip().lower()

        # ==========================
        # LEGACY SCHEMA
        # name
        # ==========================

        elif med.get("name"):

            medicine_name = str(
                med.get("name")
            ).strip().lower()

        if medicine_name:
            medicine_lookup[med_id] = medicine_name

    # ==========================
    # AGGREGATE MEDICINE USAGE
    # ==========================

    medicine_totals = defaultdict(int)

    prescriptions = list(
        prescriptions_collection.find()
    )

    for prescription in prescriptions:

        items = prescription.get(
            "items",
            []
        )

        if not isinstance(items, list):
            continue

        for item in items:

            if not isinstance(item, dict):
                continue

            medicine_name = None

            # ==========================
            # CASE 1
            # NEW SCHEMA
            # item.name
            # ==========================

            if item.get("name"):

                medicine_name = str(
                    item.get("name")
                ).strip().lower()

            # ==========================
            # CASE 2
            # LEGACY
            # medicineName
            # ==========================

            elif item.get(
                "medicineName"
            ):

                medicine_name = str(
                    item.get(
                        "medicineName"
                    )
                ).strip().lower()

            # ==========================
            # CASE 3
            # medicine string
            # ==========================

            elif isinstance(
                item.get("medicine"),
                str
            ):

                medicine_name = str(
                    item.get(
                        "medicine"
                    )
                ).strip().lower()

            # ==========================
            # CASE 4
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

            # ==========================
            # QUANTITY
            # ==========================

            try:

                quantity = int(
                    item.get(
                        "quantity",
                        0
                    )
                )

            except (
                TypeError,
                ValueError
            ):

                quantity = 0

            if (
                medicine_name
                and quantity > 0
            ):
                medicine_totals[
                    medicine_name
                ] += quantity

    # ==========================
    # BUILD FORECAST
    # ==========================

    result = []

    mission_count = max(
        len(mission_df),
        1
    )

    for med_name, total_qty in (
        medicine_totals.items()
    ):

        # historical average use
        historical_avg = round(
            total_qty
            / mission_count
        )

        # usage per patient
        avg_per_patient = (
            total_qty
            / historical_patients
        )

        # predicted demand
        estimated_need = round(
            predicted_patients
            * avg_per_patient
        )

        # contingency buffer
        estimated_need = round(
            estimated_need
            * 1.20
        )

        # percentage increase
        change_percent = round(
            (
                (
                    estimated_need
                    - historical_avg
                )
                /
                max(
                    historical_avg,
                    1
                )
            )
            * 100
        )

        # risk tiers
        risk = "LOW"

        if estimated_need > 120:
            risk = "HIGH"

        elif estimated_need > 40:
            risk = "MEDIUM"

        result.append(
            {
                "medicine":
                    med_name,

                "estimatedNeed":
                    estimated_need,

                "historicalAverage":
                    historical_avg,

                "changePercent":
                    change_percent,

                "risk":
                    risk
            }
        )

    # ==========================
    # SORT
    # ==========================

    result.sort(
        key=lambda x:
        x["estimatedNeed"],
        reverse=True
    )

    return result[:20]

