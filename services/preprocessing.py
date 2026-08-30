import pandas as pd

from utils.mongo import patients_collection


def prepare_mission_dataframe(
    location=None
):
    """
    Load patient records for a location and reconstruct
    contiguous mission periods.

    Existing behavior is preserved:
    - A patient's doctor-sheet departments are de-duplicated
      within that patient using a set.
    - Missions are reconstructed when consecutive mission
      dates are <= 3 days apart.
    - Patients remains the primary mission-level count.

    New behavior:
    - Each mission now contains departmentCounts, e.g.
      {
          "Pediatrics": 12,
          "Dental": 5,
          "Cardio": 8
      }
    """

    query = {}

    if location:
        query["location"] = {
            "$regex": str(location).strip(),
            "$options": "i"
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

            if not isinstance(sheet, dict):
                continue

            # =================================
            # DEPARTMENT
            # =================================

            dept = sheet.get(
                "department"
            )

            if dept:
                departments.add(
                    str(dept).strip()
                )

            # =================================
            # DIAGNOSIS
            # =================================

            diagnosis = sheet.get(
                "diagnosis"
            )

            if diagnosis:
                diagnoses.add(
                    str(diagnosis).strip()
                )

            # =================================
            # MEDICATION
            # =================================

            medication = sheet.get(
                "medication"
            )

            if medication:

                meds = [
                    m.strip().lower()
                    for m in str(
                        medication
                    ).split(",")
                    if m.strip()
                ]

                medications.extend(
                    meds
                )

        rows.append(
            {
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
                    sorted(
                        departments
                    ),

                "diagnoses":
                    sorted(
                        diagnoses
                    ),

                "medications":
                    medications
            }
        )

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

    # Existing implementation assumes
    # one canonical location after the
    # location filter.
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

    for day in unique_days[1:]:

        previous = (
            current_group[-1]
        )

        gap_days = (
            day - previous
        ).days

        if gap_days <= MISSION_BREAK_DAYS:

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

    # =================================
    # BUILD MISSION RECORDS
    # =================================

    for group in mission_groups:

        group_set = set(group)

        mission_patients = temp[
            temp[
                "missionDate"
            ].isin(group_set)
        ].copy()

        mission_days = len(
            group
        )

        patient_count = len(
            mission_patients
        )

        # =================================
        # DEPARTMENT COUNTS
        # =================================
        #
        # A patient contributes once to
        # each distinct department represented
        # in their doctor sheets.
        #
        # Example:
        # patient A -> Pediatrics, Dental
        # patient B -> Pediatrics
        #
        # Result:
        # Pediatrics: 2
        # Dental: 1
        #
        # =================================

        department_counts = {}

        for dept_list in (
            mission_patients[
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

        missions.append(
            {
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

                # New structured department data
                "departmentCounts":
                    department_counts,

                # Existing flattened department list
                "departments":
                    mission_patients[
                        "departments"
                    ].sum(),

                "diagnoses":
                    mission_patients[
                        "diagnoses"
                    ].sum(),

                "medications":
                    mission_patients[
                        "medications"
                    ].sum()
            }
        )

    return pd.DataFrame(
        missions
    )