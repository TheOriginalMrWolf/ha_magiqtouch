"""Platform for climate integration."""
import logging

from functools import cached_property

from . import MagIQtouchCoordinator
from .magiqtouch import MagIQtouch_Driver
from .structures import UnitDetails

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Import the device class from the component that you want to support
from homeassistant.components.climate import (
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from homeassistant.components.climate.const import (
    PRESET_NONE,
    FAN_ON,
    FAN_OFF
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_PASSWORD,
    CONF_USERNAME,
    PRECISION_WHOLE,
)
from .const import (
    DOMAIN,
    MODE_COOLER,
    MODE_COOLER_FAN,
    MODE_HEATER,
    MODE_HEATER_FAN,
    CONTROL_MODE_TEMP,
    ZONE_COMMON,
    ZONE_TYPE_MASTER,
    ZONE_NONE,
    ZoneType,
)

_LOGGER = logging.getLogger("magiqtouch")


# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

DEVICE_CLASS_THERMOSTAT = "thermostat"
DEVICE_CLASS_HEATER_COOLER = "heater_cooler"

# HVAC_MODES = [HVACMode.OFF, HVACMode.COOL, HVACMode.FAN_ONLY, HVACMode.HEAT]

FAN_SPEED_BY_TEMP = "Temperature"
FAN_SPEED_TO_PREV = "Previous"
# FAN_SPEEDS = [FAN_SPEED_BY_TEMP, FAN_SPEED_TO_PREV] + [str(spd + 1) for spd in range(10)]
# FAN_SPEEDS = [FAN_ON, FAN_OFF]
FAN_SPEEDS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]

PRESET_FAN_FRESH = "Fan: Fresh Air"
PRESET_FAN_RECIRC = "Fan: Recirculate"
# PRESET_EVAP_TEMP = "Evaporative: set temperature"
# PRESET_EVAP_FAN_SPEED = "Evaporative: set fan speed"
PRESET_HEAT_TEMP = "Heating: set temperature"
PRESET_HEAT_FAN_SPEED = "Heating: set fan speed"
PRESET_COOL_TEMP = "Cooling: set temperature"
PRESET_COOL_FAN_SPEED = "Cooling: set fan speed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up device based on a config entry."""
    driver: MagIQtouch_Driver = hass.data[DOMAIN][entry.entry_id]["driver"]
    coordinator: MagIQtouchCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    for zone in driver.zone_list:
        is_master_zone = (not zone) or zone in (ZONE_NONE, ZONE_COMMON)
        if is_master_zone:
            entity = MagIQtouchMasterController(
                entry_id=entry.entry_id,
                controller=driver,
                coordinator=coordinator,
                zone=zone,
                is_master_zone=is_master_zone
            )
        else:
            entity = MagIQtouchAutoThermostat(
                entry_id=entry.entry_id,
                controller=driver,
                coordinator=coordinator,
                zone=zone,
                is_master_zone=is_master_zone
            )

        _LOGGER.debug("%s - Created entity: %s, entry_id: %s, unique_id: %s, master zone: %s", zone.name, entity.name, entry.entry_id, entity.unique_id, is_master_zone)
        entities.append(entity)

    async_add_entities(entities, update_before_add=False)


class ThermostatHeaterCoolerBaseClass(CoordinatorEntity, ClimateEntity):
    """Base class for MagIQtouch Thermostat/Heater_Cooler."""

    _HVAC_MODE_MAP = {
        MODE_COOLER: HVACMode.COOL,
        MODE_HEATER: HVACMode.HEAT,
        MODE_COOLER_FAN: HVACMode.FAN_ONLY,
        MODE_HEATER_FAN: HVACMode.FAN_ONLY,
    }

    _HVAC_ACTION_MAP = {
        MODE_COOLER: HVACAction.COOLING,
        MODE_HEATER: HVACAction.HEATING,
        MODE_COOLER_FAN: HVACAction.FAN,
        MODE_HEATER_FAN: HVACAction.FAN,
    }

    def __init__(
        self,
        entry_id,
        controller: MagIQtouch_Driver,
        coordinator: MagIQtouchCoordinator,
        zone: ZoneType,
        supported_features: int = 0,
        is_master_zone=False
    ):
        self._attr_name = "MagIQtouch"
        super().__init__(coordinator)
        self.controller = controller
        self.coordinator = coordinator
        self._attr_device_info = {
            "identifiers": {("magiqtouch", self.controller.device_id)},
            "name": self.controller.device_name,
            "manufacturer": "alelec",
            # "model": "<installed model>",
        }

        self.zone: ZoneType = zone
        self.is_master_zone = is_master_zone

        self.master_mode_only_controller = False

        self._supported_features = supported_features

        # https://developers.home-assistant.io/blog/2024/01/24/climate-climateentityfeatures-expanded/
        self._enable_turn_on_off_backwards_compatibility = False

        _LOGGER.info(f"Instantiated thermostat - self.zone.name: '{self.zone.name}' with name: '{self.name}', unique id: '{self.unique_id}'")

    @cached_property
    def name(self):
        """Return the name of the device."""
        return f"MagIQtouch - {self.controller.get_zone_name(self.zone)}"

    @cached_property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        uid = self.controller.current_state.device
        zone_name = self.controller.get_zone_name(self.zone).replace(" ", "-")
        uid += f"-zone-{zone_name}"
        _LOGGER.debug("Returning Unique ID: %s", uid)
        return uid

    @property
    def cooler(self):
        # Always fetch fresh from controller
        coolers = self.controller.available_coolers(self.zone)
        if not coolers and (not self.zone or self.zone in (ZONE_NONE, ZONE_COMMON)):
            coolers = self.controller.current_state.cooler

        _LOGGER.debug("cooler(self):: returning 'coolers': %s", coolers)
        return coolers

    @property
    def heater(self):
        # Always fetch fresh from controller
        heaters = self.controller.available_heaters(self.zone)
        if not heaters and (not self.zone or self.zone in (ZONE_NONE, ZONE_COMMON)):
            heaters = self.controller.current_state.heater

        _LOGGER.debug("heater(self):: returning 'heaters': %s", heaters)
        return heaters

    @cached_property
    def supported_features(self):
        """Return the list of supported features for this entity."""
        return self._supported_features

    @property
    def available(self) -> bool:
        """Return if thermostat is available."""
        return self.controller.logged_in and self.controller.current_state.runningMode != ""

    @property
    def active_units(self):
        state = self.controller.current_state
        if state.runningMode in (MODE_COOLER, MODE_COOLER_FAN):
            return self.cooler
        elif state.runningMode in (MODE_HEATER, MODE_HEATER_FAN):
            return self.heater
        else:
            return []

    @property
    def inactive_units(self):
        state = self.controller.current_state
        if state.runningMode in (MODE_COOLER, MODE_COOLER_FAN):
            return self.heater
        elif state.runningMode in (MODE_HEATER, MODE_HEATER_FAN):
            return self.cooler
        else:
            return []

    @cached_property
    def temperature_unit(self):
        """Return the unit of measurement that is used."""
        return self.controller.native_unit_of_measurement

    @cached_property
    def precision(self):
        """Return unit precision as 1.0"""
        return PRECISION_WHOLE

    @property
    def current_temperature(self):
        units = self.active_units or self.inactive_units
        if len(units) > 1:
            itemps = [u.internal_temp for u in units if u.internal_temp < 100]
            current = sum(itemps) / len(itemps)
        else:
            current = units[0].internal_temp
        if current > 100:
            # No sensor
            try:
                # report common zone if it exists
                current = self.controller.active_device(ZONE_COMMON).internal_temp
            except:
                current = self.target_temperature
        return current

    @property
    def system_is_on(self):
        return self.controller.current_state.systemOn

    @property
    def current_system_mode(self):
        return self.controller.current_state.runningMode

    @property
    def hvac_action(self):
        """
        Return current running action (Current State)
        """
        device = self.controller.active_device(self.zone)
        system_running_state = getattr(device, "runningState", None)
        zone_running_state = getattr(device, "zoneRunningState", None)
        zone_is_turned_on = self.controller.get_zone_onoff(self.zone)


        # The hvac_action can be the actual/system action for all zone types.

        if (not self.system_is_on) or (not zone_is_turned_on):
            hvac_action = HVACAction.OFF
        else:
            # if the current zone state is REQUIRED_RUNNING then we use the currentSystemMode (ie heating, cooling, etc).
            # Any other state the then we return IDLE.
            hvac_action = self._HVAC_ACTION_MAP.get(self.current_system_mode, HVACAction.OFF) if zone_running_state == "REQUIRED_RUNNING" else HVACAction.IDLE

        _LOGGER.debug("%s - Current hvac_action requested - hvac_action: %s (system on %s, currentSystemMode: %s, system_running_state: %s, zone_is_turned_on: %s, zone_running_state: %s)", self.zone.name, hvac_action, self.system_is_on, self.current_system_mode, system_running_state, zone_is_turned_on, zone_running_state)

        return hvac_action


class MagIQtouchAutoThermostat(ThermostatHeaterCoolerBaseClass):
    """THERMOSTAT - only allow off/auto and no fan"""

    def __init__(
        self,
        entry_id,
        controller: MagIQtouch_Driver,
        coordinator: MagIQtouchCoordinator,
        zone: ZoneType,
        additional_supported_features:int=0,
        is_master_zone=False
    ):
        super().__init__(
            entry_id=entry_id,
            controller=controller,
            coordinator=coordinator,
            supported_features=(
                ClimateEntityFeature.TARGET_TEMPERATURE
                | additional_supported_features
            ),
            zone=zone,
            is_master_zone=is_master_zone
        )
        # self._attr_device_class = "thermostat"
        self._attr_target_temperature_step = PRECISION_WHOLE

        _LOGGER.debug("Instantiated THERMOSTAT - name: %s, unique id: %s", self.name, self.unique_id)

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        units = self.active_units or self.inactive_units
        return units[0].set_temp

    @property
    def max_temp(self):
        units = self.active_units or self.inactive_units
        return units[0].max_temp

    @property
    def min_temp(self):
        units = self.active_units or self.inactive_units
        return units[0].min_temp

    @cached_property
    def hvac_modes(self):
        """
        Return the list of available operation modes,
        Reflects the state of the master controller - only "off" if system is off, "off" and current mode if system is on
        """

        # if self.controller.current_state.systemOn:
        #     modes = [HVACMode.OFF, HVACMode.AUTO]
        #     _LOGGER.debug("%s - Was queried for hvac modes, system is ON so returned: %s", self.zone.name, modes)
        # else:
        #     modes = [HVACMode.OFF]
        #     _LOGGER.debug("%s - Was queried for hvac modes, system is OFF so returned: %s", self.zone.name, modes)
        # Look up the seeley mode (heat/cool, etc) to get the available hvac mode...

        # IF the system is OFF, then the only mode available is OFF.  If the system is on then mirror the system mode
        # if self.system_is_on:
        #     modes = [HVACMode.OFF, self._HVAC_MODE_MAP.get(self.current_system_mode, HVACMode.OFF)]
        # else:
        #     modes = [HVACMode.OFF]

        # NOTE: HomeKit doesn't support dynamic characteristic option changes.  See https://chatgpt.com/share/6873553c-2850-800a-90b7-39aa05c18009

        modes = [HVACMode.OFF, HVACMode.AUTO]
        _LOGGER.debug("%s - Was queried for hvac modes, sending: '%s'. self.controller.current_state.runningMode: '%s'",self.zone.name, modes, self.controller.current_state.runningMode)

        return modes

    @property
    def hvac_mode(self):
        """
        Get operating mode
        """
        device = self.controller.active_device(self.zone)
        system_running_state = getattr(device, "runningState", None)
        zone_running_state = getattr(device, "zoneRunningState", None)
        zone_is_turned_on = self.controller.get_zone_onoff(self.zone)

        # The mode needs to align with hvac_modes, otherwise HA & HK errors.
        if not self.system_is_on:
            hvac_mode = HVACMode.OFF
        elif zone_is_turned_on:
            hvac_mode = HVACMode.AUTO
        else:
            hvac_mode = HVACMode.OFF

        _LOGGER.debug("%s - Current hvac_mode requested - hvac_mode: %s (system on %s, current_system_mode: %s, system_running_state: %s, zone_is_turned_on: %s, zone_running_state: %s)", self.zone.name, hvac_mode, self.system_is_on, self.current_system_mode, system_running_state, zone_is_turned_on, zone_running_state)

        return hvac_mode

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        # Heating temperature can only be changed across the entire system.
        if self.master_mode_only_controller:
            return
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self.controller.async_set_zone_temperature(temperature, zone=self.zone)

    async def async_turn_on(self):
        if self.system_is_on:
            _LOGGER.debug("%s - async_turn_on called, system ON, zone turned on", self.zone.name)
            await self.controller.set_zone_onoff(self.zone, True)
        else:
            _LOGGER.debug("%s - async_turn_on called, system OFF, request ignored", self.zone.name)

    async def async_turn_off(self):
        _LOGGER.debug("%s - async_turn_off called", self.zone.name)
        await self.controller.set_zone_onoff(self.zone, False)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        # each zone can be turned on and off individually - but only allow
        # turning on iff the system is on
        # but switching between heating vs fan mode applies only across the whole system.

        if not self.system_is_on and hvac_mode != HVACMode.OFF:
            # await self.async_turn_off()
            _LOGGER.debug("%s - Ignofing hvac_mode change to '%s' because system is off", self.zone.name, hvac_mode)
            return

        if hvac_mode == HVACMode.OFF:
            _LOGGER.debug("%s - async_set_hvac_mode:: system_is_on: %s, zone turned off")
            await self.async_turn_off()
        else:
            _LOGGER.debug("%s - async_set_hvac_mode:: system_is_on: %s, zone turned on")
            await self.async_turn_on()

        await self.coordinator.async_request_refresh()



class MagIQtouchMasterController(ThermostatHeaterCoolerBaseClass):
    """HEATER_COOLER"""

    def __init__(
        self,
        entry_id,
        controller: MagIQtouch_Driver,
        coordinator: MagIQtouchCoordinator,
        zone: ZoneType,
        additional_supported_features:int=0,
        is_master_zone=False
    ):
        super().__init__(
            entry_id=entry_id,
            controller=controller,
            coordinator=coordinator,
            supported_features=(
                ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
                | ClimateEntityFeature.FAN_MODE
                | additional_supported_features
                # | ClimateEntityFeature.PRESET_MODE
            ),
            zone=zone,
            is_master_zone=is_master_zone
        )
        # self._attr_device_class = "heater_cooler"
        self._attr_swing_modes = None
        self._attr_swing_mode = None

        _LOGGER.debug("Instantiated HEATER_COOLER - name: %s, unique id: %s", self.name, self.unique_id)

    @cached_property
    def fan_modes(self):
        """Return the supported fan modes."""
        _LOGGER.debug("Fan modes requested, returning speeds: %s", FAN_SPEEDS)
        return FAN_SPEEDS

    @property
    def fan_mode(self):
        """Return the current fan modes."""
        # if self.controller.active_device(self.zone).control_mode == CONTROL_MODE_TEMP:
        #     # running in temperature set point mode
        #     return FAN_SPEED_BY_TEMP

        speed = str(self.controller.active_device(self.zone).fan_speed)
        # if speed == "0":
        #     _LOGGER.debug("%s - fan mode requested, returning: %s", self.name, FAN_SPEED_BY_TEMP)
        #     return FAN_SPEED_BY_TEMP

        _LOGGER.debug("%s - fan mode requested, returning: %s", self.name, speed)
        return speed

    @cached_property
    def hvac_modes(self):
        """Return the list of available operation modes."""
        modes = [HVACMode.OFF, HVACMode.FAN_ONLY]

        if self.heater:
            modes.append(HVACMode.HEAT)
        if self.cooler:
            modes.append(HVACMode.COOL)

        _LOGGER.debug("%s - Was queried for hvac modes, sending: '%s'. self.controller.current_state.runningMode: '%s'",self.zone.name, modes, self.controller.current_state.runningMode)

        return modes

    @property
    def hvac_mode(self):
        """
        Get operating mode
        """
        device = self.controller.active_device(self.zone)
        system_running_state = getattr(device, "runningState", None)
        zone_running_state = getattr(device, "zoneRunningState", None)
        zone_is_turned_on = self.controller.get_zone_onoff(self.zone)

        # The mode needs to align with hvac_modes, otherwise HA & HK errors.
        if not self.system_is_on:
            hvac_mode = HVACMode.OFF
        else:
            hvac_mode = self._HVAC_MODE_MAP.get(self.current_system_mode, HVACMode.OFF)

        _LOGGER.debug("%s - Current hvac_mode requested - hvac_mode: %s (system on %s, current_system_mode: %s, system_running_state: %s, zone_is_turned_on: %s, zone_running_state: %s)", self.zone.name, hvac_mode, self.system_is_on, self.current_system_mode, system_running_state, zone_is_turned_on, zone_running_state)

        return hvac_mode

    async def async_turn_on(self):
        await self.controller.set_on()

    async def async_turn_off(self):
        await self.controller.set_off()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set operation mode."""
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()

        else:
            # set the mode
            if hvac_mode == HVACMode.FAN_ONLY:
                await self.controller.set_fan_only(self.zone)
            elif hvac_mode == HVACMode.COOL:
                await self.controller.set_cooling(self.zone)
            elif hvac_mode == HVACMode.HEAT:
                await self.controller.set_heating(self.zone)
            else:
                _LOGGER.error("Unknown hvac_mode: %s" % hvac_mode)

            # and turn on the system (just in case)
            await self.async_turn_on()

        await self.coordinator.async_request_refresh()

        _LOGGER.debug("%s - hvac_mode set to: %s", self.zone.name, hvac_mode)

    async def async_set_fan_mode(self, fan_mode):
        if str(fan_mode) not in FAN_SPEEDS:
            _LOGGER.warning("Unknown fan speed: %s" % fan_mode)
        else:
            _LOGGER.debug("%s - Set fan to: %s", self.zone.name, fan_mode)
            if fan_mode == FAN_SPEED_BY_TEMP:
                await self.controller.set_cooling_by_temperature(self.zone)
            elif fan_mode == FAN_SPEED_TO_PREV:
                await self.controller.set_cooling_by_speed(self.zone)
            else:
                await self.controller.set_current_speed(fan_mode)

        await self.coordinator.async_request_refresh()


# ############
# TODO: Add to base or derived classes:

  # @property
    # def device_state_attributes(self):
    #     """Return the device specific state attributes."""
    #     ## TODO
    #     dev_specific = {
    #         ATTR_STATE_AWAY_END: self._thermostat.away_end,
    #         ATTR_STATE_LOCKED: self._thermostat.locked,
    #         ATTR_STATE_LOW_BAT: self._thermostat.low_battery,
    #         ATTR_STATE_VALVE: self._thermostat.valve_state,
    #         ATTR_STATE_WINDOW_OPEN: self._thermostat.window_open,
    #     }
    #
    #     return dev_specific

    # @property
    # def preset_mode(self):
    #     """Return the current preset mode, e.g., home, away, temp.
    #     Requires SUPPORT_PRESET_MODE.
    #     """
    #     runningMode = self.controller.current_state.runningMode
    #     if runningMode == MODE_HEATER_FAN:
    #         return PRESET_FAN_RECIRC
    #     elif runningMode == MODE_COOLER_FAN:
    #         return PRESET_FAN_FRESH

    #     temperature_mode = (
    #         self.controller.active_device(self.zone).control_mode == CONTROL_MODE_TEMP
    #     )
    #     cooling_mode = self.controller.current_state.runningMode == MODE_COOLER
    #     if cooling_mode:
    #         if temperature_mode:
    #             return PRESET_COOL_TEMP
    #         return PRESET_COOL_FAN_SPEED
    #     heating_mode = self.controller.current_state.runningMode == MODE_HEATER
    #     if heating_mode:
    #         if temperature_mode:
    #             return PRESET_HEAT_TEMP
    #         return PRESET_HEAT_FAN_SPEED
    #     return PRESET_NONE

    # @property
    # def preset_modes(self):
    #     """Return a list of available preset modes.
    #     Requires SUPPORT_PRESET_MODE.
    #     """
    #     presets = [PRESET_NONE]
    #     cur_state = self.controller.current_state
    #     # sys_state = self.controller.current_system_configuration
    #     # if sys_state.Heater.InSystem:
    #     if self.controller.available_heaters(self.zone):
    #         presets.append(PRESET_HEAT_TEMP)
    #         # presets.append(PRESET_HEAT_FAN_SPEED)
    #         if cur_state.fan.heater_available:
    #             presets.append(PRESET_FAN_RECIRC)

    #     # todo AOC
    #     # if sys_state.Heater.get("AOCInstalled", 0) > 0:
    #     # if sys_state.System.cooler.available or sys_state.AOCFixed.InSystem
    #     #        or sys_state.AOCInverter.InSystem:
    #     if self.controller.available_coolers(self.zone):
    #         presets.append(PRESET_COOL_TEMP)
    #         if self.controller.current_state.installed.evap:
    #             presets.append(PRESET_COOL_FAN_SPEED)
    #         if cur_state.fan.cooler_available:
    #             presets.append(PRESET_FAN_FRESH)

    #     return presets

    # async def async_set_preset_mode(self, preset_mode):
        # """Set new preset mode."""
        # if preset_mode == PRESET_FAN_FRESH:
        #     await self.controller.set_fan_only_evap(self.zone)
        # elif preset_mode == PRESET_FAN_RECIRC:
        #     await self.controller.set_fan_only_heater(self.zone)
        # elif preset_mode == PRESET_COOL_TEMP:
        #     await self.controller.set_cooling_by_temperature(self.zone)
        # elif preset_mode == PRESET_COOL_FAN_SPEED:
        #     await self.controller.set_cooling_by_speed(self.zone)
        # elif preset_mode == PRESET_HEAT_TEMP:
        #     await self.controller.set_heating_by_temperature(self.zone)
        # elif preset_mode == PRESET_HEAT_FAN_SPEED:
        #     await self.controller.set_heating_by_speed(self.zone)
        # # elif preset_mode == PRESET_COOL_TEMP:
        # #     await self.controller.set_aoc_by_temperature(self.zone)
        # # elif preset_mode == PRESET_COOL_FAN_SPEED:
        # #     await self.controller.set_aoc_by_speed(self.zone)
        # elif preset_mode == PRESET_NONE:
        #     await self.async_set_hvac_mode(HVACMode.OFF)