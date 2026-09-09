from collections import defaultdict
from datetime import datetime

from bson import ObjectId

from utils.mongo import (
    prescriptions_collection,
    medicines_collection,
    patients_collection,
)


def _normalize_medicine_name(name):
    if not name:
        return None

    return str(name).strip().lower()


def _build_medicine_lookup():
    """
    Build a lookup from Medicine ObjectId -> medicine name.

    Supports the current Medicine schema using:
        names: [...]
    
    and older records using:
        name: "..."
    """

    lookup = {}

    medicines = medicines_collection.find(
        {},
        {
            "_id": 1,
            "names": 1,
            "name": 1,
        }
    )

    for medicine in medicines:

        medicine_name = None

        names = medicine.get("names")

        if isinstance(names, list) and names:

            medicine_name = _normalize_medicine_name(
                names[0]
            )

        elif medicine.get("name"):

            medicine_name = _normalize_medicine_name(
                medicine.get("name")
            )

        if medicine_name:

            lookup[str(medicine["_id"])] = medicine_name

    return lookup


def _get_medicine_name(item, medicine_lookup):
    """
    Resolve medicine name from both old and new
    prescription formats.
    """

    # ------------------------------------------
    # OLD FORMAT
    # ------------------------------------------

    if item.get("name"):

        return _normalize_medicine_name(
            item.get("name")
        )

    if item.get("medicineName"):

        return _normalize_medicine_name(
            item.get("medicineName")
        )

    # ------------------------------------------
    # CURRENT FORMAT
    # ------------------------------------------

    medicine = item.get("medicine")

    if medicine is not None:

        return medicine_lookup.get(
            str(medicine)
        )

    return None


def _to_date(value):
    """
    Convert datetime, pandas Timestamp,
    Python date, or string into a Python
    date object.
    """

    if value is None:
        return None

    # ------------------------------------------
    # Already a Python date/datetime object
    # ------------------------------------------

    if isinstance(value, datetime):

        return value.date()

    # ------------------------------------------
    # Pandas Timestamp and similar objects
    # ------------------------------------------

    try:

        return value.date()

    except AttributeError:

        pass

    # ------------------------------------------
    # String dates
    #
    # Supports:
    # 2026-02-13
    # 2026-02-13 00:00:00
    # ------------------------------------------

    if isinstance(value, str):

        value = value.strip()

        if not value:

            return None

        # Try ISO datetime first
        try:

            return datetime.fromisoformat(
                value
            ).date()

        except ValueError:

            pass

        # Try date-only format
        try:

            return datetime.strptime(
                value,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            return None

    return None


def generate_medicine_forecast(
    mission_df,
    predicted_patients,
    mission_days=1
):

    # ==================================================
    # VALIDATION
    # ==================================================

    if mission_df is None or mission_df.empty:

        return []

    try:

        predicted_patients = float(
            predicted_patients
        )

    except (
        TypeError,
        ValueError
    ):

        return []

    if predicted_patients <= 0:

        return []

    # ==================================================
    # BUILD HISTORICAL MISSION LIST
    # ==================================================

    historical_missions = []

    for _, mission in mission_df.iterrows():

        start = _to_date(
            mission.get("missionStart")
        )

        end = _to_date(
            mission.get("missionEnd")
        )

        try:

            patients = int(
                mission.get(
                    "Patients",
                    0
                )
            )

        except (
            TypeError,
            ValueError
        ):

            patients = 0

        if (
            start is None
            or patients <= 0
        ):

            continue

        if end is None:

            end = start

        historical_missions.append(
            {
                "start": start,
                "end": end,
                "patients": patients,
                "location": str(
                    mission.get(
                        "location",
                        ""
                    )
                ).strip().lower()
            }
        )

    if not historical_missions:

        return []

    historical_missions.sort(
        key=lambda x: x["start"]
    )

    # ==================================================
    # SELECTED LOCATIONS
    # ==================================================

    selected_locations = {
        mission["location"]
        for mission in historical_missions
        if mission["location"]
    }

    # ==================================================
    # MEDICINE LOOKUP
    # ==================================================

    medicine_lookup = (
        _build_medicine_lookup()
    )

    # ==================================================
    # GET PATIENTS
    # ==================================================

    patients = patients_collection.find(
        {},
        {
            "_id": 1,
            "location": 1,
            "missionDate": 1,
        }
    )

    patient_lookup = {}

    for patient in patients:

        patient_location = str(
            patient.get(
                "location",
                ""
            )
        ).strip().lower()

        if (
            selected_locations
            and patient_location
            not in selected_locations
        ):

            continue

        mission_date = _to_date(
            patient.get(
                "missionDate"
            )
        )

        if mission_date is None:

            continue

        # ------------------------------------------
        # FIND THE HISTORICAL MISSION
        # ------------------------------------------

        matching_mission = None

        for mission in historical_missions:

            if (
                mission["start"]
                <= mission_date
                <= mission["end"]
            ):

                matching_mission = mission
                break

        if matching_mission:

            patient_lookup[
                str(patient["_id"])
            ] = matching_mission

    # ==================================================
    # STOP IF NO PATIENTS CAN BE MATCHED
    # ==================================================

    if not patient_lookup:

        return []

    # ==================================================
    # MEDICINE USAGE PER MISSION
    # ==================================================

    medicine_usage = defaultdict(
        lambda: defaultdict(float)
    )

    # ==================================================
    # READ PRESCRIPTIONS
    # ==================================================

    patient_ids = list(
    patient_lookup.keys()
)

    patient_ids = []

    for patient_id in patient_lookup.keys():

        try:
            patient_ids.append(
            ObjectId(patient_id)
        )

        except Exception:
         continue


    prescriptions = prescriptions_collection.find(
    {
        "patient": {
            "$in": patient_ids
        }
    },
    {
        "patient": 1,
        "items": 1,
    }
)

    for prescription in prescriptions:

        patient_id = prescription.get(
            "patient"
        )

        if not patient_id:

            continue

        patient_id = str(
            patient_id
        )

        mission = patient_lookup.get(
            patient_id
        )

        if not mission:

            continue

        items = prescription.get(
            "items",
            []
        )

        if not isinstance(
            items,
            list
        ):

            continue

        for item in items:

            if not isinstance(
                item,
                dict
            ):

                continue

            # ==========================================
            # EXPLICITLY NOT GIVEN = DO NOT COUNT
            # ==========================================

            if (
                "isGiven" in item
                and item.get("isGiven") is False
            ):

                continue

            medicine_name = (
                _get_medicine_name(
                    item,
                    medicine_lookup
                )
            )

            if not medicine_name:

                continue

            try:

                quantity = float(
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

            if quantity <= 0:

                continue

            mission_key = (
                mission["start"]
            )

            medicine_usage[
                medicine_name
            ][mission_key] += quantity

    # ==================================================
    # BUILD FORECAST
    # ==================================================

    result = []

    for medicine_name, mission_data in (
        medicine_usage.items()
    ):

        # ------------------------------------------
        # CREATE RATE FOR EVERY HISTORICAL MISSION
        # ------------------------------------------

        mission_rates = []

        for mission in historical_missions:

            mission_key = mission["start"]

            quantity = mission_data.get(
                mission_key,
                0
            )

            patients = mission["patients"]

            if patients <= 0:
                continue

            rate = (
                quantity
                /
                patients
            )

            mission_rates.append(
                {
                    "date":
                        mission_key,

                    "rate":
                        rate,

                    "quantity":
                        quantity
                }
            )

        if not mission_rates:

            continue

        # ------------------------------------------
        # SORT CHRONOLOGICALLY
        # ------------------------------------------

        mission_rates.sort(
            key=lambda x: x["date"]
        )

        # ------------------------------------------
        # RECENCY WEIGHTING
        # ------------------------------------------

        weighted_sum = 0
        weight_total = 0

        for index, record in enumerate(
            mission_rates
        ):

            weight = index + 1

            weighted_sum += (
                record["rate"]
                *
                weight
            )

            weight_total += weight

        if weight_total <= 0:

            continue

        weighted_rate = (
            weighted_sum
            /
            weight_total
        )

        # ------------------------------------------
        # PREDICTED MEDICINE NEED
        # ------------------------------------------

        base_need = (
            predicted_patients
            *
            weighted_rate
        )

        # ------------------------------------------
        # 5% SAFETY BUFFER
        # ------------------------------------------

        estimated_need = round(
            base_need
            * 1.05
        )

        estimated_need = max(
            estimated_need,
            0
        )

        # ------------------------------------------
        # HISTORICAL AVERAGE
        # ------------------------------------------

        historical_total = sum(
            record["quantity"]
            for record in mission_rates
        )

        historical_average = round(
            historical_total
            /
            len(mission_rates)
        )

        # ------------------------------------------
        # CHANGE %
        # ------------------------------------------

        if historical_average > 0:

            change_percent = round(
                (
                    (
                        estimated_need
                        -
                        historical_average
                    )
                    /
                    historical_average
                )
                *
                100
            )

        else:

            change_percent = 0

        # ------------------------------------------
        # RISK
        # ------------------------------------------

        risk = "LOW"

        if estimated_need > 120:

            risk = "HIGH"

        elif estimated_need > 40:

            risk = "MEDIUM"

        # ------------------------------------------
        # RESULT
        # ------------------------------------------

        result.append(
            {
                "medicine":
                    medicine_name,

                "estimatedNeed":
                    estimated_need,

                "historicalAverage":
                    historical_average,

                "changePercent":
                    change_percent,

                "risk":
                    risk
            }
        )

    # ==================================================
    # SORT RESULTS
    # ==================================================

    result.sort(
        key=lambda x:
        x["estimatedNeed"],
        reverse=True
    )

    return result[:20]