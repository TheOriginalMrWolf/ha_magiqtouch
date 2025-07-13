"""Diagnostics support for MagIQtouch."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF
from .magiqtouch import MagIQtouch_Driver

_LOGGER = logging.getLogger(__name__)

# Keys to redact from diagnostics data for privacy/security
TO_REDACT = {
    CONF.USERNAME,
    CONF.PASSWORD,
    "user",
    "password",
    "email",
    "MacAddressId",
    "device",
    "SerialNo",
    "ElectronicsSerialNo",
    "CabinetSerialNo",
    "Address",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    driver: MagIQtouch_Driver = hass.data[DOMAIN][entry.entry_id]["driver"]
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Basic integration info
    diagnostics_data = {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "version": entry.version,
        "domain": entry.domain,
        "options": dict(entry.options),
        "state": entry.state.value,
    }

    # Driver status and configuration
    try:
        diagnostics_data["driver_status"] = {
            "logged_in": getattr(driver, 'logged_in', False),
            "device_id": getattr(driver, 'device_id', None),
            "device_name": getattr(driver, 'device_name', None),
            "native_unit_of_measurement": getattr(driver, 'native_unit_of_measurement', None),
            "verbose": getattr(driver, 'verbose', False),
            "zone_list": [
                {
                    "type": zone.type,
                    "name": zone.name,
                }
                for zone in driver.zone_list
            ] if hasattr(driver, 'zone_list') and driver.zone_list else [],
        }
    except Exception as ex:
        _LOGGER.warning("Failed to get driver status: %s", ex)
        diagnostics_data["driver_status"] = {"error": str(ex)}

    # Current system state
    try:
        if hasattr(driver, 'current_state') and driver.current_state:
            # Convert to dict and redact sensitive info
            current_state_dict = driver.current_state.to_dict()
            diagnostics_data["current_state"] = current_state_dict
        else:
            diagnostics_data["current_state"] = None
    except Exception as ex:
        _LOGGER.warning("Failed to get current state: %s", ex)
        diagnostics_data["current_state"] = {"error": str(ex)}

    # System details/configuration
    try:
        if hasattr(driver, 'current_system_configuration') and driver.current_system_configuration:
            system_state_dict = driver.current_system_configuration.to_dict()
            diagnostics_data["system_state"] = system_state_dict
        else:
            diagnostics_data["system_state"] = None
    except Exception as ex:
        _LOGGER.warning("Failed to get system state: %s", ex)
        diagnostics_data["system_state"] = {"error": str(ex)}

    # Coordinator information
    try:
        diagnostics_data["coordinator"] = {
            "name": coordinator.name,
            "update_interval": str(coordinator.update_interval),
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "update_count": getattr(coordinator, 'update_count', 'unknown'),
        }
    except Exception as ex:
        _LOGGER.warning("Failed to get coordinator info: %s", ex)
        diagnostics_data["coordinator"] = {"error": str(ex)}

    return async_redact_data(diagnostics_data, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    # For now, return the same data as config entry since we have one main device
    # In the future, this could be extended to provide zone-specific diagnostics
    return await async_get_config_entry_diagnostics(hass, entry)
