from .const import ATTR_MANUFACTURER, DOMAIN, CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR
from .const import WRITE_DATA_LOCAL, WRITE_MULTISINGLE_MODBUS, WRITE_SINGLE_MODBUS
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from typing import Any, Dict, Optional
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    if entry.data:  # old style - remove soon
        hub_name = entry.data[CONF_NAME]
        modbus_addr = entry.data.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR)
    else:
        hub_name = entry.options[CONF_NAME]  # new style
        modbus_addr = entry.options.get(CONF_MODBUS_ADDR, DEFAULT_MODBUS_ADDR)  # new style
    hub = hass.data[DOMAIN][hub_name]["hub"]

    plugin = hub.plugin  # getPlugin(hub_name)
    inverter_name_suffix = ""
    if hub.inverterNameSuffix is not None and hub.inverterNameSuffix != "":
        inverter_name_suffix = hub.inverterNameSuffix + " "

    entities = []

    for switch_info in plugin.SWITCH_TYPES:
        if plugin.matchInverterWithMask(
            hub._invertertype, switch_info.allowedtypes, hub.seriesnumber, switch_info.blacklist
        ):
            if not (switch_info.name.startswith(inverter_name_suffix)):
                switch_info.name = inverter_name_suffix + switch_info.name
            switch = SolaXModbusSwitch(hub_name, hub, modbus_addr, hub.device_info, switch_info)
            if switch_info.value_function:
                hub.computedSwitches[switch_info.key] = switch_info
            if switch_info.sensor_key is not None:
                hub.writeLocals[switch_info.sensor_key] = switch_info
            entities.append(switch)

    async_add_entities(entities)
    return True


class SolaXModbusSwitch(SwitchEntity):
    """Representation of an SolaX Modbus select."""

    def __init__(self, platform_name, hub, modbus_addr, device_info, switch_info) -> None:
        """Initialize the selector."""
        self._platform_name = platform_name
        self._hub = hub
        self._modbus_addr = modbus_addr
        self._attr_device_info = device_info
        self.entity_id = "switch." + platform_name + "_" + switch_info.key
        self._name = switch_info.name
        self._key = switch_info.key
        self._register = switch_info.register
        self.entity_description = switch_info
        self._write_method = switch_info.write_method
        self._sensor_key = switch_info.sensor_key
        self._attr_is_on = False
        self._bit = switch_info.register_bit
        self._value_function = switch_info.value_function

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self._attr_is_on = True
        await self._write_switch_to_modbus()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self._attr_is_on = False
        await self._write_switch_to_modbus()

    async def _write_switch_to_modbus(self):
        if self._value_function is None:
            _LOGGER.debug(f"No value function for switch {self.key}")
            return
        else:
            payload = self._value_function(self._bit, self._attr_is_on, self._sensor_key, self._hub.data)

        _LOGGER.debug(f"writing {self._platform_name} {self._key} number register {self._register} value {payload}")
        await self._hub.async_write_registers_single(unit=self._modbus_addr, address=self._register, payload=payload)
        self.async_write_ha_state()

    @property
    def is_on(self):
        if self._sensor_key is not None:
            if self._sensor_key in self._hub.data:
                sensor_value = int(self._hub.data[self._sensor_key])
                return (sensor_value // 2**self._bit % 2) == 1

        return self._attr_is_on

    @property
    def unique_id(self) -> Optional[str]:
        return f"{self._platform_name}_{self._key}"
