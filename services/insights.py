from collections import Counter


def generate_insights(df):

    if df.empty:

        return {

            "topDiagnoses":
                [],

            "topDepartments":
                [],

            "summaryInsights":
                []
        }

    # ======================
    # DIAGNOSES
    # ======================

    diagnosis_counter = (
        Counter()
    )

    for diagnosis_list in (
        df["diagnoses"]
    ):

        if isinstance(
            diagnosis_list,
            list
        ):

            diagnosis_counter.update(
                diagnosis_list
            )

    top_diagnoses = [

        {
            "diagnosis":
                diagnosis,

            "count":
                count
        }

        for diagnosis, count in
        diagnosis_counter.most_common(
            10
        )
    ]

    # ======================
    # DEPARTMENTS
    # ======================

    department_counter = (
        Counter()
    )

    for dept_list in (
        df["departments"]
    ):

        if isinstance(
            dept_list,
            list
        ):

            department_counter.update(
                dept_list
            )

    top_departments = [

        {
            "department":
                dept,

            "count":
                count
        }

        for dept, count in
        department_counter.most_common(
            10
        )
    ]

    # ======================
    # SUMMARY INSIGHTS
    # ======================

    summary = []

    avg_patients = round(
        df[
            "Patients"
        ].mean()
    )

    peak = (
        df.sort_values(
            "Patients",
            ascending=False
        )
        .iloc[0]
    )

    summary.append(
        f"Average patients per mission: {avg_patients}"
    )

    summary.append(
        f"Highest mission load was "
        f"{peak['Patients']} patients "
        f"in {peak['location']}"
    )

    if top_diagnoses:

        summary.append(
            f"Most common diagnosis: "
            f"{top_diagnoses[0]['diagnosis']}"
        )

    if top_departments:

        summary.append(
            f"Most active department: "
            f"{top_departments[0]['department']}"
        )

    return {

        "topDiagnoses":
            top_diagnoses,

        "topDepartments":
            top_departments,

        "summaryInsights":
            summary
    }