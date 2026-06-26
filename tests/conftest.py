"""Shared test fixtures for Better Presence 2."""

import asyncio

import pytest
import pytest_socket

pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in the test directory."""
    return


@pytest.fixture
def event_loop():
    """Override event_loop to allow socket creation on Windows (ProactorEventLoop)."""
    pytest_socket.enable_socket()
    loop = asyncio.get_event_loop_policy().new_event_loop()
    loop.__original_fixture_loop = True  # type: ignore[attr-defined]
    yield loop
    loop.close()
