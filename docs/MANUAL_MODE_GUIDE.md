# Manual Mode Scheduling Guide

This guide explains how to use the Manual Mode scheduling features of the Marstek Venus integration for Home Assistant.

> **v0.5.0:** The easiest way to schedule is now the **per-slot entities**, not
> service calls. Because the Marstek local API cannot read the device's schedule
> back, Home Assistant owns it: edit the `Slot N` entities (enabled / start /
> end / power / days) and press the **Apply schedule** button to write them to
> the device. Selecting **Manual** on the Operating Mode select applies the
> schedule too. Note that `Charge Power` / `Discharge Power` now drive
> **Passive** mode (a temporary override), so they no longer touch the Manual
> schedule. The service calls documented below still work for advanced use
> (custom day combinations, automations).

## Table of Contents

- [Overview](#overview)
- [Understanding Manual Mode](#understanding-manual-mode)
- [Service Calls](#service-calls)
  - [Set Manual Mode (Single Schedule)](#set-manual-mode-single-schedule)
  - [Set Multiple Schedules (Bulk)](#set-multiple-schedules-bulk)
  - [Set Auto Mode](#set-auto-mode)
  - [Set AI Mode](#set-ai-mode)
  - [Set Passive Mode](#set-passive-mode)
- [Advanced Services](#advanced-services)
- [Examples](#examples)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Manual Mode allows you to create time-based power schedules for your Marstek Venus battery system. You can:

- Configure up to 10 different time schedules (time slots 0-9)
- Set specific power levels for charging (negative) or discharging (positive)
- Define which days of the week each schedule applies
- Enable or disable individual schedules
- Manage multiple schedules efficiently using bulk operations

## Understanding Manual Mode

### Power Settings

Power is specified in watts (W):

- **Negative values** = Charging (e.g., `-1000` charges battery at 1000W)
- **Positive values** = Discharging (e.g., `500` discharges battery at 500W)
- **Zero** = Standby (no charging or discharging)
- **Valid range**: -5000W to +5000W

### Time Slots

The Venus system supports 10 independent time schedules numbered 0-9. Each time slot can have:

- Start time (HH:MM format, 24-hour)
- End time (HH:MM format, 24-hour)
- Power setting
- Days of week selection
- Enable/disable flag

### Days of Week

Days are specified using 3-letter codes:

- `mon` - Monday
- `tue` - Tuesday
- `wed` - Wednesday
- `thu` - Thursday
- `fri` - Friday
- `sat` - Saturday
- `sun` - Sunday

You can specify one or more days as a list: `["mon", "tue", "wed"]`

## Service Calls

All services are called on the **Operating Mode** select entity. Replace `select.marstek_venus_e_operating_mode` with your actual entity ID.

### Set Manual Mode (Single Schedule)

Configure a single time schedule for Manual mode.

**Service**: `marstek_venus.set_mode_manual`

**Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `time_slot` | integer | Yes | Time period number (0-9) | `0` |
| `start_time` | string | Yes | Start time in HH:MM format | `"08:30"` |
| `end_time` | string | Yes | End time in HH:MM format | `"20:30"` |
| `power` | integer | Yes | Power setting in watts | `-1000` |
| `days` | list | Yes | List of day codes | `["mon", "tue"]` |
| `enabled` | boolean | No | Enable this schedule (default: true) | `true` |

**Example YAML** (Developer Tools → Services):

```yaml
service: marstek_venus.set_mode_manual
target:
  entity_id: select.marstek_venus_e_operating_mode
data:
  time_slot: 0
  start_time: "09:00"
  end_time: "17:00"
  power: -2000
  days:
    - mon
    - tue
    - wed
    - thu
    - fri
  enabled: true
```

**Example in Automation**:

```yaml
action:
  - service: marstek_venus.set_mode_manual
    target:
      entity_id: select.marstek_venus_e_operating_mode
    data:
      time_slot: 0
      start_time: "10:00"
      end_time: "14:00"
      power: -1500  # Charge at 1500W during cheap rate
      days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
```

### Set Multiple Schedules (Bulk)

Configure multiple time schedules in a single call. This is more efficient than calling `set_mode_manual` multiple times.

**Service**: `marstek_venus.set_manual_schedules_bulk`

**Parameters**:

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `schedules` | list | Yes | List of schedule objects |

Each schedule object has the same parameters as `set_mode_manual`.

**Example YAML**:

```yaml
service: marstek_venus.set_manual_schedules_bulk
target:
  entity_id: select.marstek_venus_e_operating_mode
data:
  schedules:
    # Weekday morning charging during cheap rate
    - time_slot: 0
      start_time: "00:00"
      end_time: "07:00"
      power: -2000
      days: ["mon", "tue", "wed", "thu", "fri"]
      enabled: true

    # Weekday evening discharge during peak rate
    - time_slot: 1
      start_time: "17:00"
      end_time: "21:00"
      power: 1500
      days: ["mon", "tue", "wed", "thu", "fri"]
      enabled: true

    # Weekend all-day charging
    - time_slot: 2
      start_time: "00:00"
      end_time: "23:59"
      power: -1000
      days: ["sat", "sun"]
      enabled: true
```

**Note**: The bulk service automatically handles rate limiting between requests (2.5 seconds between API calls).

### Set Auto Mode

Switch to automatic mode where the system manages charging/discharging automatically.

**Service**: `marstek_venus.set_mode_auto`

**Example**:

```yaml
service: marstek_venus.set_mode_auto
target:
  entity_id: select.marstek_venus_e_operating_mode
```

### Set AI Mode

Switch to AI-based optimization mode.

**Service**: `marstek_venus.set_mode_ai`

**Example**:

```yaml
service: marstek_venus.set_mode_ai
target:
  entity_id: select.marstek_venus_e_operating_mode
```

### Set Passive Mode

Set direct power control with a countdown timer. The system will maintain the specified power level for the countdown duration, then return to the previous mode.

**Service**: `marstek_venus.set_mode_passive`

**Parameters**:

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `power` | integer | Yes | Power setting in watts | `1000` |
| `countdown` | integer | Yes | Duration in seconds | `3600` |

**Example** (discharge at 500W for 30 minutes):

```yaml
service: marstek_venus.set_mode_passive
target:
  entity_id: select.marstek_venus_e_operating_mode
data:
  power: 500
  countdown: 1800
```

## Advanced Services

### Refresh Data

Force an immediate update of all sensor data from the device (bypasses the normal polling interval).

**Service**: `marstek_venus.refresh_data`

**Example**:

```yaml
service: marstek_venus.refresh_data
target:
  entity_id: select.marstek_venus_e_operating_mode
```

### Test Connection

Test connectivity to the device and get diagnostic information. Fires a `marstek_venus_connection_test` event with results.

**Service**: `marstek_venus.test_connection`

**Example**:

```yaml
service: marstek_venus.test_connection
target:
  entity_id: select.marstek_venus_e_operating_mode
```

**Event Data**:

```json
{
  "event_type": "marstek_venus_connection_test",
  "data": {
    "entity_id": "select.marstek_venus_e_operating_mode",
    "results": {
      "success": true,
      "ping_time_ms": 45.2,
      "device_reachable": true,
      "api_responsive": true,
      "firmware_version": "1.2.3",
      "device_model": "VenusE"
    }
  }
}
```

### Get Mode Details

Get detailed information about the current operating mode. Fires a `marstek_venus_mode_details` event with results.

**Service**: `marstek_venus.get_mode_details`

**Example**:

```yaml
service: marstek_venus.get_mode_details
target:
  entity_id: select.marstek_venus_e_operating_mode
```

**Event Data**:

```json
{
  "event_type": "marstek_venus_mode_details",
  "data": {
    "entity_id": "select.marstek_venus_e_operating_mode",
    "details": {
      "mode": "Manual",
      "ongrid_power": 1500,
      "offgrid_power": 0,
      "battery_soc": 85
    }
  }
}
```

## Examples

### Example 1: Time-of-Use Optimization

Charge during off-peak hours (23:00-07:00), discharge during peak hours (17:00-21:00), weekdays only.

```yaml
service: marstek_venus.set_manual_schedules_bulk
target:
  entity_id: select.marstek_venus_e_operating_mode
data:
  schedules:
    # Off-peak charging
    - time_slot: 0
      start_time: "23:00"
      end_time: "07:00"
      power: -3000
      days: ["mon", "tue", "wed", "thu", "fri"]
      enabled: true

    # Peak discharge
    - time_slot: 1
      start_time: "17:00"
      end_time: "21:00"
      power: 2000
      days: ["mon", "tue", "wed", "thu", "fri"]
      enabled: true
```

### Example 2: Solar Self-Consumption

Charge battery during solar production hours, discharge in the evening.

```yaml
service: marstek_venus.set_manual_schedules_bulk
target:
  entity_id: select.marstek_venus_e_operating_mode
data:
  schedules:
    # Morning/afternoon solar charging
    - time_slot: 0
      start_time: "09:00"
      end_time: "16:00"
      power: -2500
      days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
      enabled: true

    # Evening discharge
    - time_slot: 1
      start_time: "18:00"
      end_time: "23:00"
      power: 1500
      days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
      enabled: true
```

### Example 3: Automation Based on Energy Prices

Use an automation to switch schedules based on dynamic energy pricing.

```yaml
automation:
  - alias: "Battery - High Price Schedule"
    trigger:
      - platform: numeric_state
        entity_id: sensor.energy_price
        above: 0.25
    action:
      - service: marstek_venus.set_mode_manual
        target:
          entity_id: select.marstek_venus_e_operating_mode
        data:
          time_slot: 0
          start_time: "00:00"
          end_time: "23:59"
          power: 2500  # Discharge during high prices
          days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
          enabled: true

  - alias: "Battery - Low Price Schedule"
    trigger:
      - platform: numeric_state
        entity_id: sensor.energy_price
        below: 0.10
    action:
      - service: marstek_venus.set_mode_manual
        target:
          entity_id: select.marstek_venus_e_operating_mode
        data:
          time_slot: 0
          start_time: "00:00"
          end_time: "23:59"
          power: -3000  # Charge during low prices
          days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
          enabled: true
```

### Example 4: Emergency Discharge

Quickly discharge battery in case of excess production or grid issues.

```yaml
automation:
  - alias: "Battery - Emergency Discharge"
    trigger:
      - platform: numeric_state
        entity_id: sensor.solar_power
        above: 5000
    action:
      - service: marstek_venus.set_mode_passive
        target:
          entity_id: select.marstek_venus_e_operating_mode
        data:
          power: 3000  # Max discharge
          countdown: 7200  # For 2 hours
```

## Best Practices

### 1. Plan Your Schedules

Before configuring, plan out your schedules on paper:
- What are your energy rates throughout the day?
- When is your solar production highest?
- When is your consumption highest?
- What are your battery capacity limits?

### 2. Use Bulk Operations

When setting up multiple schedules, use `set_manual_schedules_bulk` instead of multiple individual calls. This is faster and respects the device's rate limiting.

### 3. Test Connection First

Before setting critical schedules, test the connection:

```yaml
service: marstek_venus.test_connection
target:
  entity_id: select.marstek_venus_e_operating_mode
```

### 4. Monitor Power Levels

Ensure your power settings don't exceed your battery's capabilities:
- Check battery specifications for max charge/discharge rates
- Venus E 3 supports -5000W to +5000W range
- Stay within safe operating parameters

### 5. Handle Time Overlaps

If multiple time slots overlap:
- The device will use the schedule from the lower time_slot number
- Plan your schedules to avoid conflicts
- Use `enabled: false` to temporarily disable schedules

### 6. Rate Limiting

The API requires 2.5 seconds between requests:
- Bulk service handles this automatically
- If calling services manually, add delays between calls
- Use automations with appropriate delays

### 7. Validation

All service calls validate inputs:
- Time format must be HH:MM (24-hour)
- Time slot must be 0-9
- Power must be -5000 to 5000
- Days must be valid 3-letter codes

Invalid inputs will raise errors in Home Assistant logs.

## Troubleshooting

### Schedule Not Activating

**Problem**: Schedule is configured but not activating at the specified time.

**Solutions**:
1. Check that `enabled: true` is set
2. Verify the day codes match current day
3. Check for overlapping schedules with lower time_slot numbers
4. Use `get_mode_details` service to verify current mode
5. Check Home Assistant logs for API errors

### Timeout Errors

**Problem**: Service calls timeout or fail to respond.

**Solutions**:
1. Use `test_connection` service to verify device is reachable
2. Check network connectivity to device
3. Increase timeout in integration configuration (Settings → Devices → Marstek Venus → Configure)
4. Verify device is not overloaded with requests

### Mode Reverts to Auto

**Problem**: Device switches back to Auto mode unexpectedly.

**Solutions**:
1. Some Venus E 3 hardware versions don't support mode control
2. Check logs for timeout warnings about ES.SetMode support
3. Contact Marstek support for firmware updates
4. Use automations to re-apply mode periodically if needed

### Power Level Not Applied

**Problem**: Schedule activates but power level is different than configured.

**Solutions**:
1. Check battery SOC limits (device may reduce power if battery is full/empty)
2. Verify power setting is within device capabilities
3. Check grid connection status (affects available power)
4. Review device operating mode in Marstek app

### Invalid Time Format

**Problem**: Error about invalid time format.

**Solutions**:
1. Use 24-hour format: `"14:00"` not `"2:00 PM"`
2. Always use quotes around times: `"09:00"` not `09:00`
3. Include leading zeros: `"09:00"` not `"9:00"`
4. Use colon separator: `"09:00"` not `"09-00"`

### Service Not Found

**Problem**: Service `marstek_venus.set_mode_manual` not found.

**Solutions**:
1. Verify integration is loaded (check Settings → Devices → Marstek Venus)
2. Restart Home Assistant after integration updates
3. Check integration version supports the service (v0.2.0+)
4. Review Home Assistant logs for integration errors

## Additional Resources

- [Marstek Venus Integration README](../README.md)
- [Home Assistant Service Documentation](https://www.home-assistant.io/docs/scripts/service-calls/)
- [Home Assistant Automation Documentation](https://www.home-assistant.io/docs/automation/)
- [Energy Dashboard Setup](https://www.home-assistant.io/docs/energy/)

## Support

For issues or questions:
- [GitHub Issues](https://github.com/arvdrpoo/ha-marstek-venus/issues)
- [Home Assistant Community Forum](https://community.home-assistant.io/)
