"""Tests for BetterPresence Config Flow and Options Flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.better_presence.const import DOMAIN


async def test_config_flow_shows_form(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_config_flow_creates_entry_with_defaults(hass: HomeAssistant):
    with patch(
        "custom_components.better_presence.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "just_arrived_time": 300,
                "just_left_time": 60,
                "home_state": "Home",
                "just_arrived_state": "Just arrived",
                "just_left_state": "Just left",
                "away_state": "not_home",
                "far_away_state": "Far away",
                "far_away_distance": 0,
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Better Presence 2"
    data = result["data"]
    assert data["tracking"]["just_arrived_time"] == 300
    assert data["tracking"]["home_state"] == "Home"
    assert data["persons"] == []


async def test_config_flow_rejects_duplicate(hass: HomeAssistant):
    MockConfigEntry(
        domain=DOMAIN,
        data={
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
            "persons": [],
        },
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_add_person(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
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
            "persons": [],
        },
    )
    entry.add_to_hass(hass)

    hass.states.async_set(
        "device_tracker.thomas_ping", "home", {"friendly_name": "Thomas Ping"}
    )
    hass.states.async_set(
        "device_tracker.thomas_phone", "not_home", {"friendly_name": "Thomas Phone"}
    )

    with (
        patch("custom_components.better_presence.async_setup_entry", return_value=True),
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "add"}
        )
        assert result["step_id"] == "add_person"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"id": "thomas", "friendly_name": "Thomas"},
        )
        assert result["step_id"] == "add_person_details"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "devices": ["device_tracker.thomas_ping", "device_tracker.thomas_phone"]
            },
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    persons = entry.data.get("persons", [])
    assert len(persons) == 1
    assert persons[0]["id"] == "thomas"
    assert persons[0]["friendly_name"] == "Thomas"
    assert "device_tracker.thomas_ping" in persons[0]["devices"]
    assert "device_tracker.thomas_phone" in persons[0]["devices"]


async def test_options_flow_rejects_duplicate_person_id(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
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
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.better_presence.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "add"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"id": "thomas", "friendly_name": "Thomas 2"},
        )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "add_person"
    assert "person_id_exists" in result["errors"].values()


async def test_options_flow_remove_person(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
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
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.better_presence.async_setup_entry", return_value=True),
        patch.object(hass.config_entries, "async_reload", new=AsyncMock()),
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "remove"}
        )
        assert result["step_id"] == "remove_person"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"id": "thomas"}
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.data.get("persons", []) == []
