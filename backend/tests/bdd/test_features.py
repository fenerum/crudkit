"""Runs every scenario in features/. See README.md."""

import pytest
from pytest_bdd import scenarios

pytestmark = pytest.mark.django_db

scenarios("features")
