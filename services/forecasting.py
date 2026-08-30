import pandas as pd
from prophet import Prophet

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


# =========================================================
# GENERAL HELPERS
# =========================================================

def _safe_int(value):
    """
    Safely convert a value to an integer.
    """

    try:
        return int(
            round(
                float(value)
            )
        )

    except (
        TypeError,
        ValueError
    ):
        return 0


def _clean_department_name(
    department
):
    """
    Normalize a department name by trimming whitespace.
    """

    if department is None:
        return ""

    return str(
        department
    ).strip()


# =========================================================
# DEPARTMENT HISTORY
# =========================================================

def _build_department_history(
    mission_df
):
    """
    Build an independent historical time series
    for every department.

    Example:

    {
        "General": [
            {
                "date": Timestamp(...),
                "patients": 889
            },
            {
                "date": Timestamp(...),
                "patients": 877
            }
        ],

        "Cardio": [
            {
                "date": Timestamp(...),
                "patients": 130
            }
        ]
    }
    """

    department_history = {}

    if (
        mission_df is None
        or mission_df.empty
    ):
        return department_history

    for _, row in (
        mission_df
        .sort_values(
            "missionStart"
        )
        .iterrows()
    ):

        mission_date = pd.to_datetime(
            row.get(
                "missionStart"
            )
        )

        department_counts = row.get(
            "departmentCounts",
            {}
        )

        if not isinstance(
            department_counts,
            dict
        ):
            continue

        for department, count in (
            department_counts.items()
        ):

            department = (
                _clean_department_name(
                    department
                )
            )

            if not department:
                continue

            if department not in (
                department_history
            ):
                department_history[
                    department
                ] = []

            department_history[
                department
            ].append(
                {
                    "date":
                        mission_date,

                    "patients":
                        max(
                            0,
                            _safe_int(
                                count
                            )
                        )
                }
            )

    return department_history


# =========================================================
# DEPARTMENT FORECAST
# =========================================================

def _forecast_department(
    history,
    next_mission_date,
    mission_days
):
    """
    Forecast one department independently.

    Rules:

    1. No history:
       return 0

    2. One or two observations:
       use recent average

    3. Three or more observations:
       use Prophet

    4. Forecast is capped at 125% of the historical
       maximum to reduce extreme spikes.
    """

    if not history:
        return 0

    history_df = pd.DataFrame(
        history
    )

    history_df["date"] = pd.to_datetime(
        history_df["date"]
    )

    history_df["patients"] = (
        pd.to_numeric(
            history_df["patients"],
            errors="coerce"
        )
        .fillna(0)
        .clip(lower=0)
    )

    # Combine duplicate dates if they exist.
    history_df = (
        history_df
        .groupby(
            "date",
            as_index=False
        )["patients"]
        .sum()
        .sort_values(
            "date"
        )
    )

    if history_df.empty:
        return 0

    mission_days = max(
        _safe_int(
            mission_days
        ),
        1
    )

    # =====================================================
    # LIMITED HISTORY
    # =====================================================

    if len(history_df) < 3:

        recent_values = (
            history_df[
                "patients"
            ]
            .tail(3)
            .tolist()
        )

        if not recent_values:
            return 0

        predicted_daily = round(
            sum(
                recent_values
            )
            /
            len(
                recent_values
            )
        )

    else:

        # =================================================
        # PROPHET
        # =================================================

        prophet_df = pd.DataFrame(
            {
                "ds":
                    history_df[
                        "date"
                    ],

                "y":
                    history_df[
                        "patients"
                    ]
            }
        )

        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=False,
            daily_seasonality=False,

            changepoint_prior_scale=0.03,

            uncertainty_samples=0
        )

        model.fit(
            prophet_df
        )

        future = pd.DataFrame(
            {
                "ds": [
                    pd.to_datetime(
                        next_mission_date
                    )
                ]
            }
        )

        forecast = model.predict(
            future
        )

        predicted_daily = max(
            0,
            round(
                forecast[
                    "yhat"
                ].iloc[0]
            )
        )

    # =====================================================
    # LIMIT EXTREME SPIKES
    # =====================================================

    historical_max = (
        history_df[
            "patients"
        ]
        .max()
    )

    if historical_max > 0:

        predicted_daily = min(
            predicted_daily,
            round(
                historical_max
                * 1.25
            )
        )

    return max(
        0,
        predicted_daily
        * mission_days
    )


# =========================================================
# BUILD DEPARTMENT FORECASTS
# =========================================================

def _build_department_forecasts(
    mission_df,
    next_mission_date,
    mission_days
):
    """
    Produce independent forecasts for each department.

    Output:

    {
        "Cardio": {
            "prediction": 41,
            "history": [
                {
                    "date": "2025-04-01",
                    "patients": 130
                }
            ]
        }
    }
    """

    department_history = (
        _build_department_history(
            mission_df
        )
    )

    department_forecasts = {}

    for department in sorted(
        department_history.keys()
    ):

        history = (
            department_history[
                department
            ]
        )

        prediction = (
            _forecast_department(
                history=history,
                next_mission_date=
                    next_mission_date,
                mission_days=
                    mission_days
            )
        )

        department_forecasts[
            department
        ] = {
            "prediction":
                max(
                    0,
                    _safe_int(
                        prediction
                    )
                ),

            "history": [
                {
                    "date":
                        pd.to_datetime(
                            point["date"]
                        ).strftime(
                            "%Y-%m-%d"
                        ),

                    "patients":
                        max(
                            0,
                            _safe_int(
                                point[
                                    "patients"
                                ]
                            )
                        )
                }

                for point in history
            ]
        }

    return department_forecasts


# =========================================================
# OVERALL GROWTH FACTOR
# =========================================================

def _calculate_overall_growth_factor(
    mission_df,
    total_prediction
):
    """
    Compare the overall forecast to the most recent
    historical mission.

    Example:

        latest historical = 450
        prediction        = 405

        factor = 0.90

    The factor is bounded between 0.75 and 1.25 to
    prevent a single unusual mission from excessively
    distorting department forecasts.
    """

    if (
        mission_df is None
        or mission_df.empty
    ):
        return 1.0

    mission_df = (
        mission_df
        .sort_values(
            "missionStart"
        )
    )

    latest_patients = _safe_int(
        mission_df.iloc[-1][
            "Patients"
        ]
    )

    if latest_patients <= 0:
        return 1.0

    raw_factor = (
        total_prediction
        /
        latest_patients
    )

    return min(
        max(
            raw_factor,
            0.75
        ),
        1.25
    )


# =========================================================
# APPLY OVERALL TREND
# =========================================================

def _apply_overall_growth_to_departments(
    department_forecasts,
    growth_factor
):
    """
    Apply the overall forecast direction to every
    independently forecasted department.

    This does not affect historical values.
    """

    if not department_forecasts:
        return department_forecasts

    for department, data in (
        department_forecasts.items()
    ):

        raw_prediction = max(
            0,
            _safe_int(
                data.get(
                    "prediction",
                    0
                )
            )
        )

        adjusted_prediction = round(
            raw_prediction
            * growth_factor
        )

        data[
            "prediction"
        ] = max(
            0,
            adjusted_prediction
        )

    return department_forecasts


# =========================================================
# NORMALIZE DEPARTMENT PREDICTIONS
# =========================================================

def _normalize_department_predictions(
    department_forecasts,
    total_prediction
):
    """
    Normalize future department predictions so that the
    sum of all departments equals the overall predicted
    patient count.

    Historical values are never modified.
    """

    if not department_forecasts:
        return {}

    total_prediction = max(
        _safe_int(
            total_prediction
        ),
        0
    )

    if total_prediction == 0:

        return {
            department: 0

            for department
            in department_forecasts
        }

    raw_predictions = {}

    for department, data in (
        department_forecasts.items()
    ):

        if isinstance(
            data,
            dict
        ):

            prediction = data.get(
                "prediction",
                0
            )

        else:

            prediction = 0

        raw_predictions[
            department
        ] = max(
            0,
            _safe_int(
                prediction
            )
        )

    raw_total = sum(
        raw_predictions.values()
    )

    # =====================================================
    # NO RAW PREDICTION
    # =====================================================

    if raw_total == 0:

        departments = sorted(
            raw_predictions.keys()
        )

        if not departments:
            return {}

        base = (
            total_prediction
            //
            len(
                departments
            )
        )

        remainder = (
            total_prediction
            -
            (
                base
                *
                len(
                    departments
                )
            )
        )

        normalized = {}

        for index, department in enumerate(
            departments
        ):

            normalized[
                department
            ] = (
                base
                +
                (
                    1
                    if index < remainder
                    else 0
                )
            )

        return normalized

    # =====================================================
    # PROPORTIONAL NORMALIZATION
    # =====================================================

    normalized = {}

    fractional_parts = []

    running_total = 0

    for department, raw_value in (
        raw_predictions.items()
    ):

        exact_value = (
            raw_value
            /
            raw_total
            *
            total_prediction
        )

        floor_value = int(
            exact_value
        )

        normalized[
            department
        ] = floor_value

        running_total += (
            floor_value
        )

        fractional_parts.append(
            (
                exact_value
                -
                floor_value,

                department
            )
        )

    # =====================================================
    # REDISTRIBUTE ROUNDING REMAINDER
    # =====================================================

    remainder = (
        total_prediction
        -
        running_total
    )

    fractional_parts.sort(
        reverse=True
    )

    for index in range(
        max(
            0,
            remainder
        )
    ):

        department = (
            fractional_parts[
                index
            ][1]
        )

        normalized[
            department
        ] += 1

    return normalized


# =========================================================
# CHART DATA
# =========================================================

def _build_chart_data(
    mission_df,
    department_forecasts,
    next_mission_date
):
    """
    Build chart-ready historical and forecast data.

    Historical points:

    {
        "date": "2025-04-01",
        "type": "historical",
        "Cardio": 130,
        "Dental": 116,
        "General": 889,
        "Ortho": 120
    }

    Forecast point:

    {
        "date": "2026-09-15",
        "type": "forecast",
        "Cardio": 41,
        "Dental": 38,
        "General": 284,
        "Ortho": 41
    }
    """

    if (
        mission_df is None
        or mission_df.empty
    ):
        return []

    departments = sorted(
        department_forecasts.keys()
    )

    historical = {}

    # =====================================================
    # CREATE HISTORICAL DATES
    # =====================================================

    for date in (
        mission_df[
            "missionStart"
        ]
        .dropna()
        .sort_values()
    ):

        date = pd.to_datetime(
            date
        )

        historical.setdefault(
            date,
            {}
        )

        for department in departments:

            historical[
                date
            ].setdefault(
                department,
                0
            )

    # =====================================================
    # POPULATE HISTORICAL DEPARTMENT DATA
    # =====================================================

    for _, row in (
        mission_df
        .sort_values(
            "missionStart"
        )
        .iterrows()
    ):

        date = pd.to_datetime(
            row[
                "missionStart"
            ]
        )

        department_counts = row.get(
            "departmentCounts",
            {}
        )

        if not isinstance(
            department_counts,
            dict
        ):
            continue

        for department, count in (
            department_counts.items()
        ):

            department = (
                _clean_department_name(
                    department
                )
            )

            if not department:
                continue

            if department not in departments:
                continue

            historical[
                date
            ][department] = (
                historical[
                    date
                ].get(
                    department,
                    0
                )
                +
                max(
                    0,
                    _safe_int(
                        count
                    )
                )
            )

    # =====================================================
    # BUILD HISTORICAL POINTS
    # =====================================================

    chart_data = []

    for date in sorted(
        historical.keys()
    ):

        point = {
            "date":
                date.strftime(
                    "%Y-%m-%d"
                ),

            "type":
                "historical"
        }

        for department in departments:

            point[
                department
            ] = _safe_int(
                historical[
                    date
                ].get(
                    department,
                    0
                )
            )

        chart_data.append(
            point
        )

    # =====================================================
    # BUILD FUTURE FORECAST POINT
    # =====================================================

    forecast_point = {
        "date":
            pd.to_datetime(
                next_mission_date
            ).strftime(
                "%Y-%m-%d"
            ),

        "type":
            "forecast"
    }

    for department in departments:

        forecast_point[
            department
        ] = _safe_int(
            department_forecasts[
                department
            ].get(
                "prediction",
                0
            )
        )

    chart_data.append(
        forecast_point
    )

    return chart_data


# =========================================================
# MAIN FORECAST FUNCTION
# =========================================================

def generate_patient_forecast(
    mission_df,
    location,
    nextMissionDate,
    missionDays
):

    # =====================================================
    # VALIDATION
    # =====================================================

    if (
        mission_df is None
        or mission_df.empty
    ):

        return {
            "location":
                location,

            "predictedPatients":
                0,

            "departmentPredictions":
                {},

            "departmentForecasts":
                {},

            "chartData":
                [],

            "confidence":
                "VERY LOW",

            "confidenceRange":
                {
                    "min": 0,
                    "max": 0
                },

            "modelsUsed":
                [],

            "medicineForecast":
                []
        }

    # =====================================================
    # OVERALL BASE MODEL
    # =====================================================

    base_prediction = (
        weighted_patient_forecast(
            mission_df,
            missionDays
        )
    )

    # =====================================================
    # OVERALL PROPHET MODEL
    # =====================================================

    prophet_prediction = (
        prophet_forecast(
            mission_df,
            nextMissionDate,
            missionDays
        )
    )

    # =====================================================
    # ENSEMBLE MODEL
    # =====================================================

    ensemble_result = (
        combine_forecasts(
            base_prediction,
            prophet_prediction,
            mission_df
        )
    )

    predicted_patients = _safe_int(
        ensemble_result[
            "prediction"
        ]
    )

    model_used = (
        ensemble_result[
            "model_used"
        ]
    )

    # =====================================================
    # INDEPENDENT DEPARTMENT FORECASTS
    # =====================================================

    department_forecasts = (
        _build_department_forecasts(
            mission_df=mission_df,
            next_mission_date=
                nextMissionDate,
            mission_days=
                missionDays
        )
    )

    # =====================================================
    # APPLY OVERALL FORECAST DIRECTION
    # =====================================================

    growth_factor = (
        _calculate_overall_growth_factor(
            mission_df=mission_df,
            total_prediction=
                predicted_patients
        )
    )

    department_forecasts = (
        _apply_overall_growth_to_departments(
            department_forecasts=
                department_forecasts,
            growth_factor=
                growth_factor
        )
    )

    # =====================================================
    # NORMALIZE DEPARTMENTS TO TOTAL
    # =====================================================

    department_predictions = (
        _normalize_department_predictions(
            department_forecasts=
                department_forecasts,

            total_prediction=
                predicted_patients
        )
    )

    # =====================================================
    # SYNCHRONIZE DEPARTMENT OBJECTS
    # =====================================================

    for department, prediction in (
        department_predictions.items()
    ):

        if department in department_forecasts:

            department_forecasts[
                department
            ][
                "prediction"
            ] = _safe_int(
                prediction
            )

    # =====================================================
    # FINAL CONSISTENCY CHECK
    # =====================================================

    department_total = sum(
        department_predictions.values()
    )

    if (
        department_total
        !=
        predicted_patients
    ):

        raise ValueError(
            "Department forecast total does not match "
            f"overall prediction: "
            f"{department_total} != "
            f"{predicted_patients}"
        )

    # =====================================================
    # CHART DATA
    # =====================================================

    chart_data = (
        _build_chart_data(
            mission_df=
                mission_df,

            department_forecasts=
                department_forecasts,

            next_mission_date=
                nextMissionDate
        )
    )

    # =====================================================
    # MEDICINE FORECAST
    # =====================================================

    medicine_forecast = (
        generate_medicine_forecast(
            mission_df,
            predicted_patients,
            missionDays
        )
    )

    # =====================================================
    # CONFIDENCE
    # =====================================================

    confidence = (
        generate_confidence(
            mission_df,
            base_prediction,
            prophet_prediction,
            predicted_patients
        )
    )

    # =====================================================
    # RESPONSE
    # =====================================================

    return {
        "location":
            location,

        "predictedPatients":
    predicted_patients,

"predictedPatientsPerDay":
    round(
        predicted_patients
        /
        max(
            _safe_int(
                missionDays
            ),
            1
        ),
        2
    ),

"requestedMissionDays":
    max(
        _safe_int(
            missionDays
        ),
        1
    ),

        "departmentPredictions":
            department_predictions,

        "departmentForecasts":
            department_forecasts,

        "chartData":
            chart_data,

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