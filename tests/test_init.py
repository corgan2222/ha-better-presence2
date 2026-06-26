"""Tests for integration setup and teardown."""

from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.better_presence.const import DOMAIN

MOCK_CONFIG = {
    "tracking": {
        "just_arrived_time": 300,
        "just_left_time": 60,
        "home_state": "Home",
        "just_arrived_state": "Just arrived",
        "just_left_state": "Just left",
        "away_state": "not_home",
        "far_away_state": "Far away",
        "far_away_distance": 0,
    },
    "persons": [
        {
            "id": "thomas",
            "friendly_name": "Thomas",
            "devices": ["device_tracker.thomas_ping"],
        }
    ],
}


@pytest.fixture
def mock_entry(hass) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    return entry


async def test_setup_entry_creates_coordinator(hass, mock_entry):
    hass.states.async_set("device_tracker.thomas_ping", "not_home", {})

    with patch(
        "custom_components.better_presence.async_forward_entry_setups",
        new=AsyncMock(),
    ):
        from custom_components.better_presence import async_setup_entry

        result = await async_setup_entry(hass, mock_entry)

    assert result is True
    assert mock_entry.runtime_data is not None


async def test_unload_entry_cleans_up(hass, mock_entry):
    hass.states.async_set("device_tracker.thomas_ping", "not_home", {})

    with (
        patch(
            "custom_components.better_presence.async_forward_entry_setups",
            new=AsyncMock(),
        ),
        patch(
            "custom_components.better_presence.async_unload_platforms",
            new=AsyncMock(return_value=True),
        ),
    ):
        from custom_components.better_presence import (
            async_setup_entry,
            async_unload_entry,
        )

        await async_setup_entry(hass, mock_entry)

        # Get the coordinator that was created so we can verify cleanup
        coordinator = mock_entry.runtime_data

        # Patch coordinator's async_unload to track if it was called
        with patch.object(coordinator, "async_unload", new=AsyncMock()) as mock_unload:
            result = await async_unload_entry(hass, mock_entry)

    assert result is True
    mock_unload.assert_called_once()
