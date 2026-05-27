import pandas as pd
from utils.mongo import patients_collection


def prepare_mission_dataframe(
    location=None
):

    query = {}

    if location:
        query["location"] = {
            "$regex":
                str(location).strip(),
            "$options":
                "i"
        }

    patients = list(
        patients_collection.find(
            query,
            {
                "missionDate": 1,
                "location": 1,
                "doctorSheets.department": 1,
                "doctorSheets.diagnosis": 1,
                "doctorSheets.medication": 1,
                "generalInfo.age": 1
            }
        )
    )

    rows = []

    for patient in patients:

        mission_date = patient.get(
            "missionDate"
        )

        if not mission_date:
            continue

        doctor_sheets = patient.get(
            "doctorSheets",
            []
        )

        age = (
            patient.get(
                "generalInfo",
                {}
            )
            .get("age", 0)
        )

        departments = set()
        diagnoses = set()
        medications = []

        for sheet in doctor_sheets:

            dept = sheet.get(
                "department"
            )

            if dept:
                departments.add(
                    str(dept).strip()
                )

            diagnosis = sheet.get(
                "diagnosis"
            )

            if diagnosis:
                diagnoses.add(
                    str(diagnosis)
                    .strip()
                )

            medication = sheet.get(
                "medication"
            )

            if medication:

                meds = [
                    m.strip().lower()
                    for m in str(
                        medication
                    ).split(",")
                ]

                medications.extend(
                    meds
                )

        rows.append({

            "location":
                patient.get(
                    "location"
                ),

            "missionDate":
                pd.to_datetime(
                    mission_date
                ).normalize(),

            "age":
                age,

            "departments":
                list(departments),

            "diagnoses":
    list(diagnoses),

            "medications":
                medications
        })

    df = pd.DataFrame(
        rows
    )

    if df.empty:
        return df

    df = df.sort_values(
        "missionDate"
    )

    # =================================
    # RECONSTRUCT MISSIONS
    # =================================

    missions = []

    MISSION_BREAK_DAYS = 3

    # already filtered by location
    location_name = (
        df["location"]
        .iloc[0]
    )

    temp = (
        df[
            df["location"]
            ==
            location_name
        ]
        .copy()
    )

    unique_days = sorted(
        temp[
            "missionDate"
        ].unique()
    )

    if len(unique_days) == 0:
        return pd.DataFrame()

    mission_groups = []

    current_group = [
        unique_days[0]
    ]

    for day in (
        unique_days[1:]
    ):

        previous = (
            current_group[-1]
        )

        gap_days = (
            day - previous
        ).days

        if gap_days <= (
            MISSION_BREAK_DAYS
        ):

            current_group.append(
                day
            )

        else:

            mission_groups.append(
                current_group
            )

            current_group = [
                day
            ]

    mission_groups.append(
        current_group
    )

    for group in (
        mission_groups
    ):

        group_set = set(group)

        mission_df = temp[
            temp[
                "missionDate"
            ].isin(group_set)
        ]

        mission_days = len(
            group
        )

        patient_count = len(
            mission_df
        )

        missions.append({

            "location":
                location_name,

            "missionStart":
                group[0],

            "missionEnd":
                group[-1],

            "missionDays":
                mission_days,

            "Patients":
                patient_count,

            "PatientsPerDay":
                round(
                    patient_count
                    /
                    mission_days,
                    2
                ),

            "departments":
                mission_df[
                    "departments"
                ].sum(),

            "diagnoses":
                mission_df[
                    "diagnoses"
                ].sum(),

            "medications":
                mission_df[
                    "medications"
                ].sum()
        })

    return pd.DataFrame(
        missions
    )