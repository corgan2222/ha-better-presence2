"""Device tracker entity platform for Better Presence 2."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import BetterPresenceCoordinator

# Push-based integration — no polling, unlimited parallel updates.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Better Presence device tracker entities from a config entry."""
    coordinator: BetterPresenceCoordinator = entry.runtime_data
    entities = [
        BetterPresenceEntity(coordinator, person_id)
        for person_id in coordinator.get_person_ids()
    ]
    async_add_entities(entities)


class BetterPresenceEntity(TrackerEntity):
    """Represents a single person's Better Presence state as a device_tracker entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, coordinator: BetterPresenceCoordinator, person_id: str) -> None:
        self._coordinator = coordinator
        self._person_id = person_id

    @property
    def unique_id(self) -> str:
        return f"better_presence_{self._person_id}"

    @property
    def name(self) -> str:
        ps = self._coordinator.get_person_state(self._person_id)
        return ps.friendly_name if ps else self._person_id

    @property
    def available(self) -> bool:
        ps = self._coordinator.get_person_state(self._person_id)
        return ps.available if ps else False

    @property
    def source_type(self) -> SourceType:
        ps = self._coordinator.get_person_state(self._person_id)
        if ps and ps.attributes.get("source_type") == "gps":
            return SourceType.GPS
        return SourceType.ROUTER

    @property
    def location_name(self) -> str | None:
        ps = self._coordinator.get_person_state(self._person_id)
        return ps.state if ps else None

    @property
    def latitude(self) -> float | None:
        ps = self._coordinator.get_person_state(self._person_id)
        return ps.attributes.get("latitude") if ps else None

    @property
    def longitude(self) -> float | None:
        ps = self._coordinator.get_person_state(self._person_id)
        return ps.attributes.get("longitude") if ps else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ps = self._coordinator.get_person_state(self._person_id)
        if not ps:
            return {}
        # lat/lon already exposed via TrackerEntity properties
        return {
            k: v for k, v in ps.attributes.items() if k not in ("latitude", "longitude")
        }

    async def async_added_to_hass(self) -> None:
        self._coordinator.register_update_callback(self._handle_coordinator_update)

    async def async_will_remove_from_hass(self) -> None:
        self._coordinator.unregister_update_callback(self._handle_coordinator_update)

    @callback
    def _handle_coordinator_update(self, person_id: str) -> None:
        if person_id == self._person_id:
            self.async_write_ha_state()
