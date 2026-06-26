"""Config Flow and Options Flow for Better Presence 2."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_AWAY_STATE,
    CONF_FAR_AWAY_DISTANCE,
    CONF_FAR_AWAY_STATE,
    CONF_HOME_STATE,
    CONF_JUST_ARRIVED_STATE,
    CONF_JUST_ARRIVED_TIME,
    CONF_JUST_LEFT_STATE,
    CONF_JUST_LEFT_TIME,
    CONF_PERSON_DEVICES,
    CONF_PERSON_FRIENDLY_NAME,
    CONF_PERSON_ID,
    CONF_PERSONS,
    CONF_TRACKING,
    DEFAULT_FAR_AWAY_DISTANCE,
    DEFAULT_JUST_ARRIVED_TIME,
    DEFAULT_JUST_LEFT_TIME,
    DOMAIN,
)

# Language-specific state label defaults
_STATE_DEFAULTS: dict[str, dict] = {
    "de": {
        CONF_HOME_STATE: "Zuhause",
        CONF_JUST_ARRIVED_STATE: "Gerade angekommen",
        CONF_JUST_LEFT_STATE: "Gerade weggegangen",
        CONF_AWAY_STATE: "Abwesend",
        CONF_FAR_AWAY_STATE: "Weit weg",
    },
    "en": {
        CONF_HOME_STATE: "Home",
        CONF_JUST_ARRIVED_STATE: "Just arrived",
        CONF_JUST_LEFT_STATE: "Just left",
        CONF_AWAY_STATE: "Away",
        CONF_FAR_AWAY_STATE: "Far away",
    },
}
_STATE_DEFAULTS_FALLBACK = _STATE_DEFAULTS["en"]


def _state_defaults(language: str) -> dict:
    """Return state label defaults for the given language, falling back to English."""
    return _STATE_DEFAULTS.get(language, _STATE_DEFAULTS_FALLBACK)


def _tracking_schema(language: str, current: dict | None = None) -> vol.Schema:
    """
    Build the tracking settings schema with language-aware defaults.

    When *current* is given (edit mode), existing values are used as defaults.
    """
    d = current or {}
    s = _state_defaults(language)
    return vol.Schema(
        {
            vol.Required(
                CONF_JUST_ARRIVED_TIME,
                default=d.get(CONF_JUST_ARRIVED_TIME, DEFAULT_JUST_ARRIVED_TIME),
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                CONF_JUST_LEFT_TIME,
                default=d.get(CONF_JUST_LEFT_TIME, DEFAULT_JUST_LEFT_TIME),
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                CONF_HOME_STATE, default=d.get(CONF_HOME_STATE, s[CONF_HOME_STATE])
            ): str,
            vol.Required(
                CONF_JUST_ARRIVED_STATE,
                default=d.get(CONF_JUST_ARRIVED_STATE, s[CONF_JUST_ARRIVED_STATE]),
            ): str,
            vol.Required(
                CONF_JUST_LEFT_STATE,
                default=d.get(CONF_JUST_LEFT_STATE, s[CONF_JUST_LEFT_STATE]),
            ): str,
            vol.Required(
                CONF_AWAY_STATE, default=d.get(CONF_AWAY_STATE, s[CONF_AWAY_STATE])
            ): str,
            vol.Required(
                CONF_FAR_AWAY_STATE,
                default=d.get(CONF_FAR_AWAY_STATE, s[CONF_FAR_AWAY_STATE]),
            ): str,
            vol.Required(
                CONF_FAR_AWAY_DISTANCE,
                default=d.get(CONF_FAR_AWAY_DISTANCE, DEFAULT_FAR_AWAY_DISTANCE),
            ): vol.All(int, vol.Range(min=0)),
        }
    )


class BetterPresenceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle initial setup of Better Presence."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Better Presence 2",
                data={
                    CONF_TRACKING: user_input,
                    CONF_PERSONS: [],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_tracking_schema(self.hass.config.language),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BetterPresenceOptionsFlow(config_entry)


class BetterPresenceOptionsFlow(config_entries.OptionsFlow):
    """Handle person management (add / remove)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._persons: list[dict] = list(config_entry.data.get(CONF_PERSONS, []))
        self._new_person_id: str | None = None
        self._new_person_friendly_name: str | None = None
        self._edit_person_id: str | None = None

    async def async_step_init(self, user_input=None):
        """Main options menu: show current persons, offer add/remove/edit."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_person()
            if action == "remove":
                return await self.async_step_remove_person()
            if action == "edit_settings":
                return await self.async_step_edit_settings()
            if action == "edit_person":
                return await self.async_step_edit_person_select()

        person_names = [p[CONF_PERSON_FRIENDLY_NAME] for p in self._persons] or [
            "(none)"
        ]
        actions = {
            "add": "Add person",
            "remove": "Remove person",
            "edit_settings": "Edit global settings",
        }
        if self._persons:
            actions["edit_person"] = "Edit person"
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action"): vol.In(actions),
                }
            ),
            description_placeholders={"persons": ", ".join(person_names)},
        )

    async def async_step_edit_settings(self, user_input=None):
        """Edit global tracking settings."""
        current = self._entry.data.get(CONF_TRACKING, {})

        if user_input is not None:
            updated_data = dict(self._entry.data)
            updated_data[CONF_TRACKING] = user_input
            self.hass.config_entries.async_update_entry(self._entry, data=updated_data)
            await self.hass.config_entries.async_reload(self._entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="edit_settings",
            data_schema=_tracking_schema(self.hass.config.language, current),
        )

    async def async_step_add_person(self, user_input=None):
        """Step 1: entity ID + friendly name for the BP sensor."""
        errors = {}
        if user_input is not None:
            person_id = user_input[CONF_PERSON_ID].strip().lower().replace(" ", "_")
            existing_ids = [p[CONF_PERSON_ID] for p in self._persons]
            if person_id in existing_ids:
                errors[CONF_PERSON_ID] = "person_id_exists"
            else:
                self._new_person_id = person_id
                self._new_person_friendly_name = user_input[
                    CONF_PERSON_FRIENDLY_NAME
                ].strip()
                return await self.async_step_add_person_details()

        return self.async_show_form(
            step_id="add_person",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSON_ID): str,
                    vol.Required(CONF_PERSON_FRIENDLY_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_add_person_details(self, user_input=None):
        """Step 2: select device trackers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_PERSON_DEVICES]:
                errors[CONF_PERSON_DEVICES] = "no_devices_selected"
            else:
                self._persons.append(
                    {
                        CONF_PERSON_ID: self._new_person_id,
                        CONF_PERSON_FRIENDLY_NAME: self._new_person_friendly_name,
                        CONF_PERSON_DEVICES: user_input[CONF_PERSON_DEVICES],
                    }
                )
                return await self._save_and_reload()

        device_tracker_selector = self._build_device_tracker_selector()
        return self.async_show_form(
            step_id="add_person_details",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSON_DEVICES): device_tracker_selector,
                }
            ),
            errors=errors,
        )

    def _build_device_tracker_selector(self) -> SelectSelector:
        """Build a SelectSelector showing friendly name, entity ID and integration.

        mobile_app entries are listed first.
        """
        entity_registry = er.async_get(self.hass)
        states = self.hass.states.async_all("device_tracker")

        entries = []
        for s in states:
            reg_entry = entity_registry.async_get(s.entity_id)
            platform = reg_entry.platform if reg_entry else "unknown"
            is_mobile = platform == "mobile_app"
            friendly = s.attributes.get("friendly_name", s.entity_id)
            prefix = "📱 " if is_mobile else ""
            label = f"{prefix}{friendly}  ·  {s.entity_id}  [{platform}]"
            entries.append(
                {"label": label, "value": s.entity_id, "is_mobile": is_mobile}
            )

        entries.sort(key=lambda o: (0 if o["is_mobile"] else 1, o["label"].lower()))
        options = [{"label": e["label"], "value": e["value"]} for e in entries]
        return SelectSelector(
            SelectSelectorConfig(
                options=options, multiple=True, mode=SelectSelectorMode.LIST
            )
        )

    async def async_step_edit_person_select(self, user_input=None):
        """Select which person to edit."""
        if user_input is not None:
            self._edit_person_id = user_input[CONF_PERSON_ID]
            return await self.async_step_edit_person_details()

        return self.async_show_form(
            step_id="edit_person_select",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSON_ID): vol.In(
                        {
                            p[CONF_PERSON_ID]: p[CONF_PERSON_FRIENDLY_NAME]
                            for p in self._persons
                        }
                    ),
                }
            ),
        )

    async def async_step_edit_person_details(self, user_input=None):
        """Edit friendly name and device trackers for an existing person."""
        person = next(
            (p for p in self._persons if p[CONF_PERSON_ID] == self._edit_person_id),
            None,
        )
        if person is None:
            return self.async_abort(reason="person_not_found")

        if user_input is not None:
            person[CONF_PERSON_FRIENDLY_NAME] = user_input[
                CONF_PERSON_FRIENDLY_NAME
            ].strip()
            person[CONF_PERSON_DEVICES] = user_input[CONF_PERSON_DEVICES]
            return await self._save_and_reload()

        device_tracker_selector = self._build_device_tracker_selector()
        return self.async_show_form(
            step_id="edit_person_details",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PERSON_FRIENDLY_NAME,
                        default=person[CONF_PERSON_FRIENDLY_NAME],
                    ): str,
                    vol.Required(
                        CONF_PERSON_DEVICES, default=person[CONF_PERSON_DEVICES]
                    ): device_tracker_selector,
                }
            ),
            description_placeholders={"person_id": self._edit_person_id},
        )

    async def async_step_remove_person(self, user_input=None):
        if not self._persons:
            return self.async_abort(reason="no_persons")

        if user_input is not None:
            pid = user_input[CONF_PERSON_ID]
            self._persons = [p for p in self._persons if p[CONF_PERSON_ID] != pid]
            return await self._save_and_reload(removed_person_id=pid)

        return self.async_show_form(
            step_id="remove_person",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSON_ID): vol.In(
                        {
                            p[CONF_PERSON_ID]: p[CONF_PERSON_FRIENDLY_NAME]
                            for p in self._persons
                        }
                    ),
                }
            ),
        )

    async def _save_and_reload(self, removed_person_id: str | None = None):
        if removed_person_id is not None:
            entity_registry = er.async_get(self.hass)
            entity_id = f"device_tracker.better_presence_{removed_person_id}"
            if entity_registry.async_get(entity_id):
                entity_registry.async_remove(entity_id)

        updated_data = dict(self._entry.data)
        updated_data[CONF_PERSONS] = self._persons
        self.hass.config_entries.async_update_entry(self._entry, data=updated_data)
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        return self.async_create_entry(title="", data={})
