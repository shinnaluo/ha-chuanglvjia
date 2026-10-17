"""工作模式选择器：智能 / 强效 / 母婴。"""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChuanglvjiaConfigEntry
from .api import ChuanglvjiaError
from .const import (
    MODE_SEND_PAYLOADS,
    WORK_MODES,
    parse_device_time,
)
from .entity import ChuanglvjiaDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChuanglvjiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.data_coordinator
    client = entry.runtime_data.client
    try:
        places = await client.get_places()
    except ChuanglvjiaError:
        places = []
    place_map = {str(p.get("id")): p.get("name") for p in places if p.get("id")}
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = []
        for code in (coordinator.data or {}):
            if code in known:
                continue
            new.append(ChuanglvjiaModeSelect(coordinator, code))
            new.append(ChuanglvjiaPlaceSelect(coordinator, code, place_map))
        if new:
            known.update(e.device_code for e in new)
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class ChuanglvjiaModeSelect(ChuanglvjiaDeviceEntity, SelectEntity):
    """智能(0) / 强效(2,带档位时长) / 母婴(4)。"""

    _attr_name = "工作模式"
    entity_key = "mode"

    @property
    def options(self) -> list[str]:
        return list(WORK_MODES.values())

    @property
    def current_option(self) -> str | None:
        mode = self._device_config.get("workMode")
        if mode is None:
            mode = self._device.get("workMode")
        try:
            return WORK_MODES.get(int(mode))
        except (TypeError, ValueError):
            return None

    async def async_select_option(self, option: str) -> None:
        mode_id = next((k for k, v in WORK_MODES.items() if v == option), None)
        if mode_id is None:
            return
        if mode_id == 2:
            # 强效：沿用云端当前时长，否则默认2档(30分钟)
            minutes = parse_device_time(self._device_config.get("time")) or 30
            payload: dict[str, Any] = {
                "workMode": 2,
                "time": minutes,
                "workModeStatus": 3,
            }
        else:
            payload = dict(MODE_SEND_PAYLOADS[mode_id])
        try:
            await self.coordinator.client.send_ins(self.device_code, **payload)
        except ChuanglvjiaError as err:
            self.coordinator.logger.error("切换模式失败: %s", err)
            raise
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()


class ChuanglvjiaPlaceSelect(ChuanglvjiaDeviceEntity, SelectEntity):
    """设备放置位置（PUT /ae_oss/wx/device 修改 placeId）。"""

    _attr_name = "设备位置"
    entity_key = "place"

    def __init__(self, coordinator, device_code: str, place_map: dict[str, str]) -> None:
        super().__init__(coordinator, device_code)
        self._place_map = place_map

    @property
    def options(self) -> list[str]:
        return list(self._place_map.values())

    @property
    def current_option(self) -> str | None:
        place_id = str(self._device.get("placeId"))
        return self._place_map.get(place_id)

    async def async_select_option(self, option: str) -> None:
        place_id = next(
            (pid for pid, name in self._place_map.items() if name == option), None
        )
        device_id = self._device.get("id")
        if place_id is None or not device_id:
            return
        try:
            await self.coordinator.client.update_device(str(device_id), placeId=place_id)
        except ChuanglvjiaError as err:
            self.coordinator.logger.error("修改设备位置失败: %s", err)
            raise
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
