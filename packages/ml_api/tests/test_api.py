import json

import numpy as np
import pytest

from api.persistence.data_access import SECONDARY_VARIABLES_TO_RENAME
from api.persistence.models import (
    GradientBoostingModelPredictions,
    LassoModelPredictions,
)


@pytest.mark.integration
def test_health_endpoint(client):
    # When
    response = client.get("/")

    # Then
    assert response.status_code == 200
    assert json.loads(response.data) == {"status": "ok"}


@pytest.mark.integration
@pytest.mark.parametrize(
    "api_endpoint, expected_no_predictions",
    (
        (
            "v1/predictions/primary",
            # test csv contains 1459 rows
            # we expect 2 rows to be filtered
            1451,
        ),
        (
            "v1/predictions/secondary",
            # we expect 8 rows to be filtered
            1457,
        ),
    ),
)
def test_prediction_endpoint(
    api_endpoint, expected_no_predictions, client, test_inputs_df
):
    # Given
    if api_endpoint == "v1/predictions/secondary":
        # adjust column names to those expected by the secondary model
        test_inputs_df.rename(columns=SECONDARY_VARIABLES_TO_RENAME, inplace=True)

    # When
    response = client.post(
        api_endpoint, json=test_inputs_df.to_dict(orient="records")
    )

    # Then
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["errors"] is None
    assert len(data["predictions"]) == expected_no_predictions


# parameterizationa allows us to try many combinations of data
# within the same test, see the pytest docs for details:
# https://docs.pytest.org/en/latest/parametrize.html
@pytest.mark.parametrize(
    "field, field_value, index, expected_error",
    (
        (
            "BldgType",
            1,  # expected str
            33,
            {"33": {"BldgType": ["Not a valid string."]}},
        ),
        (
            "GarageArea",  # model feature
            "abc",  # expected float
            45,
            {"45": {"GarageArea": ["Not a valid number."]}},
        ),
        (
            "CentralAir",
            np.nan,  # nan not allowed
            34,
            {"34": {"CentralAir": ["Field may not be null."]}},
        ),
        ("LotArea", "", 2, {"2": {"LotArea": ["Not a valid integer."]}},),
    ),
)
@pytest.mark.integration
def test_prediction_validation(
    field, field_value, index, expected_error, client, test_inputs_df
):
    # Given
    # Check gradient_boosting_model.processing.validation import HouseDataInputSchema
    # and you will see the expected values for the inputs to the house price prediction
    # model. In this test, inputs are changed to incorrect values to check the validation.
    test_inputs_df.loc[index, field] = field_value

    # When
    response = client.post(
        "/v1/predictions/secondary", json=test_inputs_df.to_dict(orient="records")
    )

    # Then
    assert response.status_code == 400
    data = json.loads(response.data)
    assert data == expected_error


@pytest.mark.integration
def test_prediction_data_saved(client, app, test_inputs_df):
    # Given
    gradient_record_count = app.db_session.query(
        GradientBoostingModelPredictions
    ).count()
    lasso_record_count = app.db_session.query(LassoModelPredictions).count()

    # When
    response = client.post(
        "/v1/predictions/primary", json=test_inputs_df.to_dict(orient="records")
    )

    # Then
    assert response.status_code == 200
    assert (
        app.db_session.query(GradientBoostingModelPredictions).count()
        == gradient_record_count + 1
    )
    assert app.db_session.query(LassoModelPredictions).count() == lasso_record_count + 1
