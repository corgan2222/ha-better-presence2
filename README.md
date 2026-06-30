# Better Presence 2

Smarter presence detection for Home Assistant. Better Presence wraps your existing device trackers in a state machine that adds transition states, configurable timers, and multi-tracker aggregation — eliminating flapping and false triggers in automations.

Complete rewrite as a Home Assistant custom integration ([drop-in replacement for helto4real/hassio-add-ons presence addon](https://github.com/helto4real/hassio-add-ons/tree/master/presence), because it is from 2017 and not maintained.)

- 5 configurable presence states: Home, Just Arrived, Just Left, Away, Far Away
- Far Away state with configurable distance threshold (GPS-based, Haversine)
- Multiple device trackers per person (mobile app, Wi-Fi / BT / GPS combined)
- Full GUI configuration via Config Flow and Options Flow
- `better_presence.simulate_tracker` service for testing without hardware
- HACS compatible

## Why Better Presence?

Home Assistant's built-in `person` entity only knows `home` and `not_home`. Device trackers flap — a brief Wi-Fi dropout or a GPS hiccup instantly marks someone as away. Any automation listening to that change fires incorrectly.

Better Presence solves this with buffer states:

| Feature                               | HA Native   | Better Presence |
| ------------------------------------- | ----------- | --------------- |
| `home` / `not_home`                   | ✅          | ✅              |
| Zones                                 | ✅          | ✅              |
| **"Just arrived"** (transition state) | ❌          | ✅              |
| **"Just left"** (transition state)    | ❌          | ✅              |
| **"Far away"** (distance threshold)   | ❌          | ✅              |
| Configurable timers per state         | ❌          | ✅              |
| Custom state labels                   | ❌          | ✅              |
| Prioritization logic (GPS vs. Wi-Fi)  | rudimentary | detailed        |

**The core problem with native HA:** Device trackers flap — especially ping/nmap and GPS. If someone briefly loses Wi-Fi or GPS jumps for a moment, `person.thomas` immediately switches to `not_home`. Automations ("turn on lights when Thomas comes home") then fire multiple times or at the wrong moment.

**Better Presence solves this** with buffer states: only after X seconds in `Just arrived`/`Just left` is the final state set. You can react to `Just arrived` in automations instead of `home` — that's more stable.

All state labels are fully customizable (e.g. "Zuhause", "Gerade angekommen").

**Useful if** you:

- Want greeting automations that fire only once
- Need the difference between "just left" (lights still on) and "really gone" (lights off)
- Want to reliably combine multiple trackers per person
- Want to use custom state labels in automations and dashboards

## Multi-Tracker Prioritization

When multiple trackers are assigned to a person, Better Presence aggregates them with this priority:

| Tracker type                           | Home detection                      |
| -------------------------------------- | ----------------------------------- |
| ping / nmap / router                   | Immediately `home` — no GPS delay   |
| Mobile App (GPS), updated < 60 min ago | Counts as `home`                    |
| Mobile App (GPS), older than 60 min    | Ignored — GPS data considered stale |
| Mobile App away / in zone              | Used for away state and zone name   |

If ping says `home` and GPS says `not_home`, the person is considered home. Non-GPS trackers win for home detection; GPS is used for zones and distance.

---

## The Resulting Entity

Each person gets a `device_tracker.better_presence_<id>` entity with:

- **State**: one of the configured labels (e.g. `Home`, `Just arrived`, `Away`)
- **Attributes**: `friendly_name`, and if a GPS tracker is assigned: `latitude`, `longitude`, `gps_accuracy`, `battery_level`, `distance` (km from home)

## Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=corgan2222&repository=ha-better-presence2&category=integration)

then

[![Add Integration to your Home Assistant instance.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=better_presence)

### Via HACS

1. In HACS → Integrations → Custom repositories → add `https://github.com/corgan2222/ha-better-presence2`
2. Install **Better Presence 2**
3. Restart Home Assistant
4. **Settings → Integrations → Add Integration** → search **Better Presence**

### Manual

1. Copy the `better_presence` folder into your `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration** and search for **Better Presence**.

---

## Setup

### Step 1 — Global Settings

Configure the timing and state labels for all persons. These can be changed later via the integration's **Configure** button.

| Field                 | Description                                                  | Default      |
| --------------------- | ------------------------------------------------------------ | ------------ |
| Just Arrived duration | Seconds to stay in "Just arrived" before switching to "Home" | 300          |
| Just Left duration    | Seconds to stay in "Just left" before switching to "Away"    | 60           |
| Home label            | State value shown when at home                               | Home         |
| Just Arrived label    | State value for the arrival buffer                           | Just arrived |
| Just Left label       | State value for the departure buffer                         | Just left    |
| Away label            | State value when confirmed away                              | Away         |
| Far Away label        | State value when away beyond the distance threshold          | Far away     |
| Far Away distance     | Distance in km that triggers "Far away" (0 = disabled)       | 0            |

## States

| State            | When                                                                             |
| ---------------- | -------------------------------------------------------------------------------- |
| **Just arrived** | Tracker says `home`, but person was away — waits N seconds before confirming     |
| **Home**         | Confirmed home after the Just arrived timer expires                              |
| **Just left**    | Tracker says `not_home`, but person was home — waits N seconds before confirming |
| **Away**         | Confirmed away after the Just left timer expires                                 |
| **Far away**     | Away and beyond a configurable distance threshold (GPS required)                 |

All state labels are fully customizable (e.g. "Zuhause", "Gerade angekommen").

## Step 2 — Add a Person

After installation, click **Configure** on the integration to manage persons.

**Step 1: Name**

- **Sensor entity ID** — the technical identifier used in automations and templates. Example: `stefan_bp2` creates `device_tracker.better_presence_stefan_bp2`.
- **Display name** — the friendly name shown in the UI. Example: `Stefan BP2`.

**Step 2: Device Trackers**
Select one or more device trackers to combine for this person.

Recommended setup:

- **Mobile App tracker** — provides GPS, zones, and battery level.
- **ping or nmap tracker** — binary but reliable for home detection.

When multiple trackers are assigned, Better Presence aggregates them with this priority:

| Tracker type                           | Home detection                      |
| -------------------------------------- | ----------------------------------- |
| ping / nmap / router                   | Immediately `home` — no GPS delay   |
| Mobile App (GPS), updated < 60 min ago | Counts as `home`                    |
| Mobile App (GPS), older than 60 min    | Ignored — GPS data considered stale |
| Mobile App away / in zone              | Used for away state and zone name   |

If ping says `home` and GPS says `not_home`, the person is considered home. Non-GPS trackers win for home detection; GPS is used for zones and distance.

---

## Using the States in Automations

```yaml
# Trigger when someone arrives home
trigger:
  - platform: state
    entity_id: device_tracker.better_presence_stefan_bp2
    to: "Just arrived"

# Trigger when someone leaves (after the Just Left timer)
trigger:
  - platform: state
    entity_id: device_tracker.better_presence_stefan_bp2
    to: "Away"

# Check if someone is home in a condition
condition:
  - condition: state
    entity_id: device_tracker.better_presence_stefan_bp2
    state: "Home"
```

**Tip:** Use `Just arrived` instead of `Home` for welcome automations — it fires once when the person arrives, not every time the underlying tracker updates.

---

## Managing Persons

Click **Configure** on the integration in **Settings → Devices & Services** at any time to:

- **Add person** — add a new tracked person with their device trackers
- **Remove person** — remove a person and their entity
- **Edit global settings** — change timers and state labels

Changes take effect immediately after saving (the integration reloads automatically).

---

## Developer Service: simulate_tracker

For testing automations without real hardware. Injects a fake tracker state directly into the Better Presence state machine.

**Service:** `better_presence.simulate_tracker`

| Parameter     | Required | Description                                                              |
| ------------- | -------- | ------------------------------------------------------------------------ |
| `person_id`   | Yes      | ID of the person (e.g. `stefan_bp2`)                                     |
| `device`      | Yes      | Entity ID of the tracker to simulate (e.g. `device_tracker.stefan_ping`) |
| `state`       | Yes      | `home`, `not_home`, or a zone name                                       |
| `source_type` | No       | `router`, `bluetooth`, `gps`, `bluetooth_le` (default: `router`)         |
| `latitude`    | No       | GPS latitude (only relevant when `source_type: gps`)                     |
| `longitude`   | No       | GPS longitude (only relevant when `source_type: gps`)                    |

**Example — simulate arriving home via ping:**

```yaml
service: better_presence.simulate_tracker
data:
  person_id: stefan_bp2
  device: device_tracker.stefan_ping
  state: home
  source_type: router
```

**Example — simulate being far away via GPS:**

```yaml
service: better_presence.simulate_tracker
data:
  person_id: stefan_bp2
  device: device_tracker.stefan_phone
  state: not_home
  source_type: gps
  latitude: 48.1351
  longitude: 11.5820
```

---

## Troubleshooting

**Entity not created after adding a person**
The integration reloads automatically after saving. If the entity is missing, check **Settings → System → Logs** for errors.

**State never leaves "Just arrived"**
The Just Arrived timer is set in seconds. Default is 300 (5 minutes). Lower it under **Configure → Edit global settings** for testing.

**All my trackers have the same display name**
The device tracker list shows both the friendly name and the entity ID (e.g. `Thomas Phone · device_tracker.thomas_phone [mobile_app]`). Use the entity ID to distinguish them.

**Tracker flapping still occurs**
Make sure you have a non-GPS tracker (ping, nmap, Fritz!Box) in addition to the Mobile App. Non-GPS trackers stabilize home detection and prevent GPS drift from causing false departures.
