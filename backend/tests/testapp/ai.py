"""Stub AI model factory for the test suite. Tests patch this; entering it
for real is an error."""

from contextlib import asynccontextmanager


@asynccontextmanager
async def create_model():
    raise NotImplementedError("The test suite must patch tests.testapp.ai.create_model")
    yield  # pragma: no cover
