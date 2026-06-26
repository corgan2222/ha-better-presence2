"""Constants for Better Presence 2."""

from homeassistant.const import Platform

DOMAIN = "better_presence"

# Top-level config keys
CONF_TRACKING = "tracking"
CONF_PERSONS = "persons"

# Per-person keys
CONF_PERSON_ID = "id"
CONF_PERSON_FRIENDLY_NAME = "friendly_name"
CONF_PERSON_DEVICES = "devices"

# Tracking settings keys
CONF_JUST_ARRIVED_TIME = "just_arrived_time"
CONF_JUST_LEFT_TIME = "just_left_time"
CONF_HOME_STATE = "home_state"
CONF_JUST_ARRIVED_STATE = "just_arrived_state"
CONF_JUST_LEFT_STATE = "just_left_state"
CONF_AWAY_STATE = "away_state"
CONF_FAR_AWAY_STATE = "far_away_state"
CONF_FAR_AWAY_DISTANCE = "far_away_distance"

# Default values
DEFAULT_JUST_ARRIVED_TIME = 300
DEFAULT_JUST_LEFT_TIME = 60
DEFAULT_HOME_STATE = "Home"
DEFAULT_JUST_ARRIVED_STATE = "Just arrived"
DEFAULT_JUST_LEFT_STATE = "Just left"
DEFAULT_AWAY_STATE = "not_home"
DEFAULT_FAR_AWAY_STATE = "Far away"
DEFAULT_FAR_AWAY_DISTANCE = 0

PLATFORMS = [Platform.DEVICE_TRACKER]
