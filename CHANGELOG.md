# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.4.0]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.2.3...v0.3.0
[0.2.3]: https://github.com/arvdrpoo/ha-marstek-venus/compare/0.2.2...v0.2.3
[0.2.2]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.2.1...0.2.2
[0.2.1]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/arvdrpoo/ha-marstek-venus/compare/v0.1.3...v0.2.0
[0.1.0]: https://github.com/arvdrpoo/ha-marstek-venus/releases/tag/v0.1.0
