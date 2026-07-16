# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.1] - 2026-07-16

### Fixed

- Recover immediately when the device rejects a well-formed request with a parse
  error. The device intermittently answers a valid request with a `-32700` error
  and an id of 0; that reply previously went unmatched, so the request waited out
  its full 10-second timeout before retrying. Because all device I/O is
  serialised, an id-0 error is now matched to the single in-flight request and
  retried at once. This cuts the stalls and reduces spurious gaps during the
  device's frequent local-API hiccups. Genuine unsolicited status messages are
  unaffected.

## [0.5.0] - 2026-07-15

### Added

- **HA-owned Manual schedule** with per-slot entities. Each of 4 slots exposes an
  enable switch, start/end time, a power number (negative = charge, positive =
  discharge), and a day-preset select (Every day / Mon-Fri / Sat-Sun). An
  `Apply schedule` button writes the slots to the device. The local API cannot
  read the schedule back, so Home Assistant stores it and is the source of truth.
- `Passive Duration` number: how long a Passive charge/discharge setpoint holds.
- Option **Re-apply schedule after reconnect** (default off): after the device
  recovers from an outage, HA re-asserts the saved schedule, so a device reset
  that wipes the schedule is repaired automatically. Forces Manual on recovery.

### Changed

- **Breaking:** `Charge Power` / `Discharge Power` now drive **Passive** mode (a
  temporary setpoint held for `Passive Duration`) instead of writing Manual time
  slot 0. This stops them from overwriting a Manual schedule. Their entity IDs
  are unchanged. Selecting `Manual` on the mode select now applies the HA
  schedule.
- Reverted the minimum inter-request interval to **2.5s** (from 1.0s). The 1.0s
  value was validated only against packet loss; on real hardware the faster rate
  destabilised the device, which would reset and drop its CT pairing, Manual
  schedule, and local-API toggle. 2.5s is the stability floor.

### Fixed

- The Charge/Discharge controls no longer silently overwrite a Manual schedule
  configured in the Marstek app (the "slot 0 clobber").

## [0.4.2] - 2026-07-13

### Changed

- Poll faster: the minimum interval between UDP requests is now 1.0s instead of
  2.5s, roughly halving the poll cycle. A hardware probe showed single-attempt
  packet loss is flat (~15%) from 1.0s to 2.5s and only degrades below ~0.7s, so
  the old 2.5s spacing added latency without improving reliability. Retries
  continue to absorb the baseline loss.

### Fixed

- Request IDs now wrap at 16 bits, guarding against response mismatches on
  long-running sessions if the device truncates IDs.
- Operating-mode parsing tolerates case and surrounding whitespace in the value
  the device reports.

### Internal

- Added hassfest and HACS validation via GitHub Actions.
- Added `probe_interval.py`, a tool for measuring the device's usable request
  rate.

## [0.4.1] - 2026-07-13

### Fixed

- Quieted log spam during device outages: failures are no longer logged on every
  poll, reconnection is attempted at most once per outage, and the poll interval
  backs off (up to 5 minutes) while the device stays unreachable.

## [0.4.0] - 2026-07-12

### Added

- **Battery power control**: `Charge Power` and `Discharge Power` number
  entities (0-2500 W) that set the battery's charge/discharge power directly.
  They are mutually exclusive (setting one zeroes the other); both zero holds at
  idle. Intended for price-based automations. Setpoints persist on the device
  and are restored to the UI after a restart.
- **Downloadable diagnostics**: the standard "Download diagnostics" button on
  the device page, with host, MAC, SSID and IP redacted.
- **Repair issue**: a `device_unreachable` repair is raised when the device
  stops responding and cleared automatically when it returns; its fix flow
  retries the connection.
- **Reconfigure flow**: change a device's IP address or port from the UI without
  removing and re-adding it, preserving entity history.
- **Diagnostic sensors** (disabled by default): `IP Address` (with the WiFi
  sensors) and `Bluetooth MAC` (with the Bluetooth sensors).

### Changed

- Charge/discharge control uses **Manual** mode, matching the Marstek app. It
  holds without a countdown and survives restarts (no re-assert needed).

### Fixed

- Serialize all device I/O behind a lock so a poll and a control command can no
  longer overlap on the single-request-at-a-time UDP channel.

### Verified

- Command power sign confirmed on VenusE 3.0 (firmware 148): a positive value
  discharges, negative charges. This is inverted from the `Battery Power` sensor
  (positive = charging), so the control entities use charge = positive and
  invert once internally to keep the whole integration sign-consistent.

## [0.3.0] - 2026-07-11

### Added

- Autodiscovery via UDP broadcast and DHCP, with manual IP entry as a fallback.
- Connection-loss resilience: rides out short outages, serves cached data
  briefly, marks entities unavailable during long ones, and recovers
  automatically.

### Fixed

- Removed dead/non-functional options.

## [0.2.3] - 2026-02-03

### Fixed

- Battery power and state sensors showing "unknown".

## [0.2.2] - 2026-02-02

### Added

- Retry logic with exponential backoff, API-level diagnostics, and resilience to
  API failures.

## [0.2.1] - 2025-12-29

### Changed

- Improved options flow UI for scan interval and timeout.

## [0.2.0] - 2025-12-29

### Added

- Options flow and diagnostic infrastructure (enhanced configuration).

## [0.1.0] - 2025-12-29

### Added

- Initial Home Assistant integration for the Marstek Venus E 3: battery,
  power-flow and energy sensors, operating-mode control, and CT meter support.

[0.5.1]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.4.2...v0.5.0
[0.4.2]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.2.3...v0.3.0
[0.2.3]: https://github.com/arvdrpoo/ha-marstek-venus/compare/0.2.2...v0.2.3
[0.2.2]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.2.1...0.2.2
[0.2.1]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.1.3...v0.2.0
[0.1.0]: https://github.com/arvdrpoo/ha-marstek-venus/releases/tag/v0.1.0
