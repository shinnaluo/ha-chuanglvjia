"""创绿家除醛仪 Home Assistant 集成入口。"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ChuanglvjiaClient
from .const import (
    CONF_BIND_NAME,
    CONF_OPEN_ID,
    CONF_PHONE,
    CONF_TOKEN,
    DEFAULT_BIND_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import ChuanglvjiaDataCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


@dataclass
class ChuanglvjiaRuntimeData:
    client: ChuanglvjiaClient
    data_coordinator: ChuanglvjiaDataCoordinator


type ChuanglvjiaConfigEntry = ConfigEntry[ChuanglvjiaRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: ChuanglvjiaConfigEntry) -> bool:
    """加载一个配置项。"""
    session = async_get_clientsession(hass)
    client = ChuanglvjiaClient(
        session,
        open_id=entry.data[CONF_OPEN_ID],
        phone=entry.data[CONF_PHONE],
        bind_name=entry.data.get(CONF_BIND_NAME) or DEFAULT_BIND_NAME,
        token=entry.data.get(CONF_TOKEN),
    )
    scan_interval = entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    data_coordinator = ChuanglvjiaDataCoordinator(hass, entry, client, scan_interval)

    await data_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ChuanglvjiaRuntimeData(client, data_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ChuanglvjiaConfigEntry) -> bool:
    """卸载配置项。"""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: ChuanglvjiaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
