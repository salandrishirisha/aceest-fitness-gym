"""Unit tests for the domain service layer introduced in v3.0.0."""

import pytest

from aceest.services import bmi_category, calculate_bmi


@pytest.mark.parametrize("weight, height, expected", [
    (70, 175, 22.9),
    (95, 188, 26.9),
    (None, 180, None),
    (80, None, None),
])
def test_calculate_bmi(weight, height, expected):
    assert calculate_bmi(weight, height) == expected


@pytest.mark.parametrize("bmi, category", [
    (None, "Unknown"),
    (17.0, "Underweight"),
    (22.9, "Normal"),
    (27.5, "Overweight"),
    (31.2, "Obese"),
])
def test_bmi_category(bmi, category):
    assert bmi_category(bmi) == category
