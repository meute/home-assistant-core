"""Support for the Netatmo climate schedule selector."""

from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from homeassistant.components.climate import (
    PRESET_AWAY,
    PRESET_BOOST,
)

from .const import (
    CONF_URL_ENERGY,
    DATA_SCHEDULES,
    DOMAIN,
    EVENT_TYPE_SCHEDULE,
    EVENT_TYPE_THERM_MODE,
    MANUFACTURER,
    NETATMO_CREATE_HOME_CLIMATE_SCHEDULE_SELECT,
    NETATMO_CREATE_HOME_CLIMATE_PRESET_SELECT,
)
from .climate import (
    PRESET_FROST_GUARD,
    PRESET_MAP_NETATMO,
    NETATMO_MAP_PRESET,
    PRESET_SCHEDULE)
from .data_handler import HOME, SIGNAL_NAME, NetatmoHome
from .entity import NetatmoBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Netatmo energy platform schedule selector."""

    @callback
    def _create_entity(netatmo_home: NetatmoHome) -> None:
        entity = NetatmoHomeScheduleSelect(netatmo_home)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_HOME_CLIMATE_SCHEDULE_SELECT, _create_entity)
     )
     
    @callback
    def _create_home_mode_entity(netatmo_home: NetatmoHome) -> None:
        entity = NetatmoHomePresetSelect(netatmo_home)
        async_add_entities([entity])

    entry.async_on_unload(
        async_dispatcher_connect(hass, NETATMO_CREATE_HOME_CLIMATE_PRESET_SELECT, _create_home_mode_entity)
    )


class NetatmoHomeScheduleSelect(NetatmoBaseEntity, SelectEntity):
    """Representation a Netatmo home global thermostat schedule selector."""

    _attr_translation_key = "home_schedule_select"

    def __init__(self, netatmo_home: NetatmoHome) -> None:
        """Initialize the select entity."""
        super().__init__(netatmo_home.data_handler)

        self.home = netatmo_home.home

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: netatmo_home.signal_name,
                },
            ]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.home.entity_id)},
            name=self.home.name,
            manufacturer=MANUFACTURER,
            model="Climate",
            configuration_url=CONF_URL_ENERGY,
        )

        self._attr_unique_id = f"{self.home.entity_id}-schedule-select"

        self._attr_current_option = getattr(self.home.get_selected_schedule(), "name")
        self._attr_options = [
            schedule.name for schedule in self.home.schedules.values() if schedule.name
        ]

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"signal-{DOMAIN}-webhook-{EVENT_TYPE_SCHEDULE}",
                self.handle_event,
            )
        )

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if self.home.entity_id != data["home_id"]:
            return

        if data["event_type"] == EVENT_TYPE_SCHEDULE and "schedule_id" in data:
            self._attr_current_option = getattr(self.hass.data[DOMAIN][DATA_SCHEDULES][self.home.entity_id].get(data["schedule_id"]), "name")
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        for sid, schedule in self.hass.data[DOMAIN][DATA_SCHEDULES][
            self.home.entity_id
        ].items():
            if schedule.name != option:
                continue
            _LOGGER.debug(
                "Setting %s schedule to %s (%s)",
                self.home.entity_id,
                option,
                sid,
            )
            await self.home.async_switch_schedule(schedule_id=sid)
            break

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._attr_current_option = getattr(self.home.get_selected_schedule(), "name")
        self.hass.data[DOMAIN][DATA_SCHEDULES][self.home.entity_id] = (self.home.schedules)
        self._attr_options = [schedule.name for schedule in self.home.schedules.values() if schedule.name]

class NetatmoHomePresetSelect(NetatmoBaseEntity, SelectEntity):
    """Representation of a Netatmo home global thermostat mode selector."""

    _attr_translation_key = "home_thermostat_mode"

    def __init__(self, netatmo_home: NetatmoHome) -> None:
        """Initialize the select entity."""
        super().__init__(netatmo_home.data_handler)

        self.home = netatmo_home.home

        self._publishers.extend(
            [
                {
                    "name": HOME,
                    "home_id": self.home.entity_id,
                    SIGNAL_NAME: netatmo_home.signal_name,
                },
            ]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.home.entity_id)},
            name=self.home.name,
            manufacturer=MANUFACTURER,
            model="Climate",
            configuration_url=CONF_URL_ENERGY,
        )

        self._attr_unique_id = f"{self.home.entity_id}-heating-mode"
        self._attr_options = [
            PRESET_SCHEDULE,
            PRESET_AWAY,
            PRESET_FROST_GUARD,
        ]
        self._update_current_option()

    def _update_current_option(self) -> None:
        """Update the current selected option."""
        if self.home.therm_mode:
            self._attr_current_option = NETATMO_MAP_PRESET.get(self.home.therm_mode)
        else:
            self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"signal-{DOMAIN}-webhook-{EVENT_TYPE_THERM_MODE}",
                self.handle_event,
            )
        )

    @callback
    def handle_event(self, event: dict) -> None:
        """Handle webhook events."""
        data = event["data"]

        if self.home.entity_id != data["home_id"]:
            return

        if data.get("event_type") == EVENT_TYPE_THERM_MODE and "mode" in data:
            self._attr_current_option = NETATMO_MAP_PRESET[data["mode"]]
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        netatmo_mode = PRESET_MAP_NETATMO.get(option)
        if netatmo_mode is None:
            _LOGGER.error("Invalid heating mode selected: %s", option)
            return

        _LOGGER.debug(
            "Setting %s heating mode to %s (%s)",
            self.home.entity_id,
            option,
            netatmo_mode,
        )
        await self.home.async_set_thermmode(mode=netatmo_mode)
        self._attr_current_option = option
        self.async_write_ha_state()

    @callback
    def async_update_callback(self) -> None:
        """Update the entity's state."""
        self._update_current_option()