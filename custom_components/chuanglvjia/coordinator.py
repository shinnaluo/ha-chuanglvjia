"""数据更新协调器。"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ChuanglvjiaApiError, ChuanglvjiaAuthError, ChuanglvjiaClient
from .const import CONF_TOKEN, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ChuanglvjiaDataCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """轮询设备详情 + 实时环境数据，按 deviceCode 索引。"""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: ChuanglvjiaClient, interval: int
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_device",
            update_interval=timedelta(seconds=interval or DEFAULT_SCAN_INTERVAL),
            config_entry=entry,
        )
        self.client = client
        self._entry = entry

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.client.get_devices()
            result: dict[str, dict[str, Any]] = {}
            for dev in devices:
                code = dev.get("code")
                if not code:
                    continue
                try:
                    view = await self.client.get_device_view(str(dev.get("id")))
                except ChuanglvjiaApiError as err:
                    _LOGGER.warning("设备 %s 详情获取失败: %s", code, err)
                    view = dev
                try:
                    view["envView"] = await self.client.get_env_view(code)
                except ChuanglvjiaApiError as err:
                    _LOGGER.warning("设备 %s 实时环境数据获取失败: %s", code, err)
                    view.setdefault("envView", None)
                result[code] = view if view else dev
        except ChuanglvjiaAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except ChuanglvjiaApiError as err:
            raise UpdateFailed(str(err)) from err

        self._persist_token()
        return result

    def _persist_token(self) -> None:
        token = self.client.token
        if token and token != self._entry.data.get(CONF_TOKEN):
            self.hass.config_entries.async_update_entry(
                self._entry, data={**self._entry.data, CONF_TOKEN: token}
            )
