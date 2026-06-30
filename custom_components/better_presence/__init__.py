"""Better Presence 2 — smarter presence for Home Assistant."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN, PLATFORMS
from .coordinator import BetterPresenceCoordinator

_LOGGER = logging.getLogger(__name__)

# Config-entry-only integration: reject any YAML configuration for this domain.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SIMULATE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("person_id"): cv.string,
        vol.Required("device"): cv.string,
        vol.Required("state"): cv.string,
        vol.Optional("source_type", default="router"): vol.In(
            ["router", "bluetooth", "gps", "bluetooth_le"]
        ),
        vol.Optional("latitude"): vol.Coerce(float),
        vol.Optional("longitude"): vol.Coerce(float),
    }
)


async def async_forward_entry_setups(
    hass: HomeAssistant, entry: ConfigEntry, platforms: list
) -> None:
    """Forward entry setup to platforms (thin wrapper for testability)."""
    await hass.config_entries.async_forward_entry_setups(entry, platforms)


async def async_unload_platforms(
    hass: HomeAssistant, entry: ConfigEntry, platforms: list
) -> bool:
    """Unload platforms for an entry (thin wrapper for testability)."""
    return await hass.config_entries.async_unload_platforms(entry, platforms)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Better Presence from a config entry."""
    coordinator = BetterPresenceCoordinator(hass, dict(entry.data))
    await coordinator.async_setup()
    entry.runtime_data = coordinator

    await async_forward_entry_setups(hass, entry, PLATFORMS)

    # Register simulator service (once, shared across all entries)
    if not hass.services.has_service(DOMAIN, "simulate_tracker"):

        async def _handle_simulate(call: ServiceCall) -> None:
            person_id = call.data["person_id"]
            coord: BetterPresenceCoordinator | None = next(
                (
                    e.runtime_data
                    for e in hass.config_entries.async_entries(DOMAIN)
                    if e.state is ConfigEntryState.LOADED
                    and person_id in e.runtime_data.get_person_ids()
                ),
                None,
            )
            if coord is None:
                msg = (
                    f"Person '{person_id}' not found in Better Presence. "
                    "Check the person_id matches one configured in the integration."
                )
                raise ServiceValidationError(msg)
            coord.simulate_tracker(
                person_id=person_id,
                device=call.data["device"],
                state=call.data["state"],
                source_type=call.data["source_type"],
                latitude=call.data.get("latitude"),
                longitude=call.data.get("longitude"),
            )

        hass.services.async_register(
            DOMAIN,
            "simulate_tracker",
            _handle_simulate,
            schema=SIMULATE_SERVICE_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_unload()

    unload_ok = await async_unload_platforms(hass, entry, PLATFORMS)

    # Remove service if this was the last loaded entry
    if unload_ok and not any(
        e.entry_id != entry.entry_id and e.state is ConfigEntryState.LOADED
        for e in hass.config_entries.async_entries(DOMAIN)
    ):
        hass.services.async_remove(DOMAIN, "simulate_tracker")

    return unload_ok
