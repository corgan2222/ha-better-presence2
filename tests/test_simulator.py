"""Tests for the simulate_tracker service."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.better_presence.const import DEFAULT_HOME_STATE, DOMAIN

MOCK_CONFIG = {
    "tracking": {
        "just_arrived_time": 5,
        "just_left_time": 3,
        "home_state": DEFAULT_HOME_STATE,
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
            "devices": ["device_tracker.thomas_ping", "device_tracker.thomas_gps"],
        }
    ],
}


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Allow lingering timers for all tests using setup_integration."""
    return True


@pytest.fixture
async def setup_integration(hass: HomeAssistant, expected_lingering_timers: bool):
    hass.states.async_set("device_tracker.thomas_ping", "not_home", {})
    hass.states.async_set("device_tracker.thomas_gps", "not_home", {})
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.better_presence.async_forward_entry_setups",
        new=AsyncMock(),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry.runtime_data


async def test_simulate_service_registered(hass, setup_integration):
    assert hass.services.has_service(DOMAIN, "simulate_tracker")


async def test_simulate_home_sets_just_arrived(hass, setup_integration):
    coordinator = setup_integration
    coordinator._persons["thomas"].state = "not_home"

    await hass.services.async_call(
        DOMAIN,
        "simulate_tracker",
        {
            "person_id": "thomas",
            "device": "device_tracker.thomas_ping",
            "state": "home",
        },
        blocking=True,
    )

    assert coordinator.get_person_state("thomas").state == "Just arrived"


async def test_simulate_not_home_from_home_sets_just_left(hass, setup_integration):
    coordinator = setup_integration
    coordinator._persons["thomas"].state = DEFAULT_HOME_STATE

    await hass.services.async_call(
        DOMAIN,
        "simulate_tracker",
        {
            "person_id": "thomas",
            "device": "device_tracker.thomas_ping",
            "state": "not_home",
        },
        blocking=True,
    )

    assert coordinator.get_person_state("thomas").state == "Just left"


async def test_simulate_gps_with_coordinates(hass, setup_integration):
    coordinator = setup_integration
    coordinator._persons["thomas"].state = "not_home"

    await hass.services.async_call(
        DOMAIN,
        "simulate_tracker",
        {
            "person_id": "thomas",
            "device": "device_tracker.thomas_gps",
            "state": "home",
            "source_type": "gps",
            "latitude": 48.1351,
            "longitude": 11.5820,
        },
        blocking=True,
    )

    # GPS near home with state=home → just_arrived
    assert coordinator.get_person_state("thomas").state == "Just arrived"
