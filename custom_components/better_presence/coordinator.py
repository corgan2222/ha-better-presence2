"""State machine coordinator for Better Presence 2."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

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
    DEFAULT_AWAY_STATE,
    DEFAULT_FAR_AWAY_DISTANCE,
    DEFAULT_FAR_AWAY_STATE,
    DEFAULT_HOME_STATE,
    DEFAULT_JUST_ARRIVED_STATE,
    DEFAULT_JUST_ARRIVED_TIME,
    DEFAULT_JUST_LEFT_STATE,
    DEFAULT_JUST_LEFT_TIME,
)

_LOGGER = logging.getLogger(__name__)

_IGNORED_TRACKER_STATES = {"unavailable", "unknown"}


class PersonTrackingState:
    """Holds runtime state for one tracked person."""

    def __init__(self, person_id: str, friendly_name: str) -> None:
        self.person_id = person_id
        self.friendly_name = friendly_name
        self.state: str = ""
        self.attributes: dict[str, Any] = {"friendly_name": friendly_name}
        self.available: bool = False
        self._cancel_timer: Callable | None = None


class BetterPresenceCoordinator:
    """Central coordinator: state machine + timer logic for all persons."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass = hass
        self.config = config
        self._persons: dict[str, PersonTrackingState] = {}
        self._unsub_listeners: list[Callable] = []
        self._update_callbacks: list[Callable] = []
        self._last_known_tracker_states: dict[str, Any] = {}
        self._unavailable_logged: dict[str, bool] = {}
        self._missing_tracker_logged: set[str] = set()

        for person in config.get(CONF_PERSONS, []):
            pid = person[CONF_PERSON_ID]
            self._persons[pid] = PersonTrackingState(
                person_id=pid,
                friendly_name=person[CONF_PERSON_FRIENDLY_NAME],
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_person_state(self, person_id: str) -> PersonTrackingState | None:
        return self._persons.get(person_id)

    def get_person_ids(self) -> list[str]:
        return list(self._persons.keys())

    def register_update_callback(self, cb: Callable) -> None:
        self._update_callbacks.append(cb)

    def unregister_update_callback(self, cb: Callable) -> None:
        if cb in self._update_callbacks:
            self._update_callbacks.remove(cb)

    async def async_setup(self) -> None:
        """Start listening to all configured device trackers."""
        all_devices: list[str] = []
        for person in self.config.get(CONF_PERSONS, []):
            all_devices.extend(person.get(CONF_PERSON_DEVICES, []))

        if all_devices:
            self._unsub_listeners.append(
                async_track_state_change_event(
                    self.hass, all_devices, self._handle_tracker_event
                )
            )

        for person in self.config.get(CONF_PERSONS, []):
            self._evaluate_person(person[CONF_PERSON_ID])

    async def async_unload(self) -> None:
        """Stop all listeners and cancel all timers."""
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

        for pid in self._persons:
            self._cancel_timer_for(pid)

    def simulate_tracker(
        self,
        person_id: str,
        device: str,
        state: str,
        source_type: str = "router",
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> None:
        """Inject a fake tracker state (simulator service handler)."""
        attrs: dict[str, Any] = {"source_type": source_type}
        if latitude is not None:
            attrs["latitude"] = latitude
        if longitude is not None:
            attrs["longitude"] = longitude

        self.hass.states.async_set(device, state, attrs)
        _LOGGER.info(
            "[BP Simulator] %s → %s = %s (source_type=%s)",
            person_id,
            device,
            state,
            source_type,
        )
        self._evaluate_person(person_id)

    # ------------------------------------------------------------------
    # Internal: event listener
    # ------------------------------------------------------------------

    @callback
    def _handle_tracker_event(self, event: Event) -> None:
        entity_id = event.data["entity_id"]
        person_id = self._get_person_for_device(entity_id)
        if person_id:
            self._evaluate_person(person_id)

    def _get_person_for_device(self, device_id: str) -> str | None:
        for person in self.config.get(CONF_PERSONS, []):
            if device_id in person.get(CONF_PERSON_DEVICES, []):
                return person[CONF_PERSON_ID]
        _LOGGER.warning("Device %s not found in any person config", device_id)
        return None

    def _get_person_config(self, person_id: str) -> dict | None:
        for person in self.config.get(CONF_PERSONS, []):
            if person[CONF_PERSON_ID] == person_id:
                return person
        return None

    # ------------------------------------------------------------------
    # Internal: state machine
    # ------------------------------------------------------------------

    def _evaluate_person(self, person_id: str, from_timer: bool = False) -> None:
        person_state = self._persons.get(person_id)
        person_config = self._get_person_config(person_id)
        if not person_state or not person_config:
            return

        devices = person_config.get(CONF_PERSON_DEVICES, [])
        settings = self.config.get(CONF_TRACKING, {})

        home_st = settings.get(CONF_HOME_STATE, DEFAULT_HOME_STATE)
        arrived_st = settings.get(CONF_JUST_ARRIVED_STATE, DEFAULT_JUST_ARRIVED_STATE)
        left_st = settings.get(CONF_JUST_LEFT_STATE, DEFAULT_JUST_LEFT_STATE)
        away_st = settings.get(CONF_AWAY_STATE, DEFAULT_AWAY_STATE)
        far_st = settings.get(CONF_FAR_AWAY_STATE, DEFAULT_FAR_AWAY_STATE)
        far_dist = settings.get(CONF_FAR_AWAY_DISTANCE, DEFAULT_FAR_AWAY_DISTANCE)
        arrived_time = settings.get(CONF_JUST_ARRIVED_TIME, DEFAULT_JUST_ARRIVED_TIME)
        left_time = settings.get(CONF_JUST_LEFT_TIME, DEFAULT_JUST_LEFT_TIME)

        raw = self._get_aggregate_state(devices)
        if raw is None:
            # All trackers unavailable and no cached state yet — preserve
            # current state so a restart never triggers arrival/departure transitions.
            if not self._unavailable_logged.get(person_id):
                _LOGGER.warning(
                    "Better Presence: %s — all trackers unavailable or unknown",
                    person_id,
                )
                self._unavailable_logged[person_id] = True
            person_state.available = False
            for cb in self._update_callbacks:
                cb(person_id)
            return
        # Trackers back online — log recovery once
        if self._unavailable_logged.get(person_id):
            _LOGGER.info(
                "Better Presence: %s — trackers back online",
                person_id,
            )
            self._unavailable_logged[person_id] = False
        current = person_state.state

        # Zone name: any raw state that is neither "home" nor "not_home"
        # e.g. "gym", "work", "office" — passed through from the GPS tracker.
        _named = {"", "home", "not_home"}
        zone_name: str | None = raw if raw not in _named else None

        if raw == "home":
            if current == "":
                # Initial state: already home, no transition needed
                self._set_state(person_id, home_st, devices)
            elif current in (away_st, far_st) or current not in (
                "",
                arrived_st,
                home_st,
                left_st,
            ):
                # Returning from away, far_away, or a named zone → just arrived
                self._set_state(person_id, arrived_st, devices)
                self._start_timer(person_id, arrived_time)
            elif current == left_st:
                # Quick return
                self._cancel_timer_for(person_id)
                self._set_state(person_id, arrived_st, devices)
                self._start_timer(person_id, arrived_time)
            elif current == arrived_st:
                if from_timer:
                    self._set_state(person_id, home_st, devices)
                # else: stay in just_arrived until timer fires
            else:
                self._set_state(person_id, home_st, devices)
        # not home (raw == "not_home" or a zone name)
        elif current == "":
            # Initial state: already away/in zone, no transition needed
            new = self._resolve_away_state(
                devices, far_st, away_st, far_dist, zone_name
            )
            self._set_state(person_id, new, devices)
        elif current in (arrived_st, home_st):
            self._set_state(person_id, left_st, devices)
            self._start_timer(person_id, left_time)
        elif current == left_st:
            if from_timer:
                new = self._resolve_away_state(
                    devices, far_st, away_st, far_dist, zone_name
                )
                self._set_state(person_id, new, devices)
            # else: stay in just_left
        elif current in (away_st, far_st) or current not in (
            "",
            arrived_st,
            home_st,
            left_st,
        ):
            # Handles away↔far_away, away/far→zone, zone→zone, zone→away transitions
            new = self._resolve_away_state(
                devices, far_st, away_st, far_dist, zone_name
            )
            if new != current:
                self._set_state(person_id, new, devices)
        else:
            # Unknown / custom state — fall back to away
            self._set_state(person_id, away_st, devices)

    def _resolve_away_state(
        self,
        devices: list[str],
        far_st: str,
        away_st: str,
        far_dist: float,
        zone_name: str | None = None,
    ) -> str:
        # A named HA zone (gym, work, …) takes precedence over far_away / away.
        if zone_name is not None:
            return zone_name
        if far_dist > 0:
            dist = self._get_distance(devices)
            if dist is not None and dist > far_dist:
                return far_st
        return away_st

    # ------------------------------------------------------------------
    # Internal: device state aggregation
    # ------------------------------------------------------------------

    def _get_aggregate_state(self, devices: list[str]) -> str | None:
        """Return 'home', 'not_home', a zone name, or None if no valid data yet."""
        valid_states = []
        for did in devices:
            s = self.hass.states.get(did)
            if s is None:
                # Log once per device — trackers are commonly absent during HA
                # startup before their platform has loaded; avoid per-event spam.
                if did not in self._missing_tracker_logged:
                    _LOGGER.warning("Tracker %s not found in HA", did)
                    self._missing_tracker_logged.add(did)
                continue
            self._missing_tracker_logged.discard(did)
            if s.state.lower() in _IGNORED_TRACKER_STATES:
                cached = self._last_known_tracker_states.get(did)
                if cached is not None:
                    _LOGGER.debug(
                        "Tracker %s is %s, using last known state: %s",
                        did,
                        s.state,
                        cached.state,
                    )
                    valid_states.append(cached)
                # else: no prior state known yet — skip entirely
            else:
                self._last_known_tracker_states[did] = s
                valid_states.append(s)

        # WiFi/BT with state=home → immediately home (stable)
        for s in valid_states:
            if self._translate_state(s.state) == "home":
                src = s.attributes.get("source_type", "")
                if src != "gps":
                    return "home"

        # GPS with state=home AND updated within 60 min → home
        for s in valid_states:
            if (
                self._translate_state(s.state) == "home"
                and s.attributes.get("source_type") == "gps"
            ):
                age = (datetime.now(UTC) - s.last_updated).total_seconds() / 60
                if age < 60:
                    return "home"

        # Not home: return GPS tracker state (zone name) if available
        # Only use GPS state if it's NOT home (stale home GPS should not count)
        for s in valid_states:
            if s.attributes.get("source_type") == "gps":
                translated = self._translate_state(s.state)
                if translated != "home":
                    return translated

        # Fallback: most recently changed device
        # GPS devices that report "home" are excluded here — they were already
        # checked above and only count as home if fresh (< 60 min).
        non_gps_states = [
            s for s in valid_states if s.attributes.get("source_type") != "gps"
        ]
        fallback_states = non_gps_states or valid_states
        if fallback_states:
            latest = max(fallback_states, key=lambda x: x.last_changed)
            translated = self._translate_state(latest.state)
            # A stale GPS "home" must not count as home
            if translated == "home" and latest.attributes.get("source_type") == "gps":
                return "not_home"
            return translated

        # All trackers are unavailable/unknown and no cached state exists yet.
        # Return None so _evaluate_person preserves the current state instead of
        # falsely transitioning to away (which would trigger just_arrived on reconnect).
        return None

    def _translate_state(self, state: str) -> str:
        return {
            "home": "home",
            "not_home": "not_home",
            "on": "home",
            "off": "not_home",
            "true": "home",
            "false": "not_home",
        }.get(state.lower(), state)

    # ------------------------------------------------------------------
    # Internal: GPS attributes & distance
    # ------------------------------------------------------------------

    def _get_gps_attributes(self, devices: list[str]) -> dict[str, Any]:
        """Return GPS attributes from the most recently updated GPS tracker."""
        gps_devices = []
        for did in devices:
            s = self.hass.states.get(did)
            if s and s.attributes.get("source_type") == "gps":
                gps_devices.append(s)

        if not gps_devices:
            return {}

        best = max(gps_devices, key=lambda x: x.last_updated)
        result: dict[str, Any] = {}
        for key in (
            "latitude",
            "longitude",
            "gps_accuracy",
            "battery_level",
            "entity_picture",
            "address",
        ):
            val = best.attributes.get(key)
            if val is not None:
                result[key] = val

        if "latitude" in result and "longitude" in result:
            result["source_type"] = "gps"
            result["distance"] = round(
                self._haversine(
                    result["latitude"],
                    result["longitude"],
                    self.hass.config.latitude,
                    self.hass.config.longitude,
                )
            )

        return result

    def _get_distance(self, devices: list[str]) -> float | None:
        attrs = self._get_gps_attributes(devices)
        return attrs.get("distance")

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Return distance in km using the Haversine formula."""
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # ------------------------------------------------------------------
    # Internal: state updates and timers
    # ------------------------------------------------------------------

    def _set_state(
        self, person_id: str, new_state: str, devices: list[str] | None = None
    ) -> None:
        ps = self._persons[person_id]
        ps.state = new_state
        ps.available = True
        ps.attributes = {"friendly_name": ps.friendly_name}
        if devices:
            ps.attributes.update(self._get_gps_attributes(devices))
        for cb in self._update_callbacks:
            cb(person_id)

    def _start_timer(self, person_id: str, delay: float) -> None:
        self._cancel_timer_for(person_id)

        @callback
        def _fired(_now):
            self._evaluate_person(person_id, from_timer=True)

        self._persons[person_id]._cancel_timer = async_call_later(
            self.hass, delay, _fired
        )

    def _cancel_timer_for(self, person_id: str) -> None:
        ps = self._persons.get(person_id)
        if ps and ps._cancel_timer:
            ps._cancel_timer()
            ps._cancel_timer = None
