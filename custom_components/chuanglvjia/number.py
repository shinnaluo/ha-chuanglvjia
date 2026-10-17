"""数字实体：强效档位 1–4。"""
from __future__ import annotations

import asyncio

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChuanglvjiaConfigEntry
from .api import ChuanglvjiaError
from .const import (
    STRONG_GEAR_MINUTES,
    minutes_to_gear,
    parse_device_time,
)
from .entity import ChuanglvjiaDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChuanglvjiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.data_coordinator
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [
            ChuanglvjiaGearNumber(coordinator, code)
            for code in (coordinator.data or {})
            if code not in known
        ]
        if new:
            known.update(e.device_code for e in new)
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class ChuanglvjiaGearNumber(ChuanglvjiaDeviceEntity, NumberEntity):
    """强效档位 1–4（协议编码：15/30/60/120；界面剩余时长恒为30分钟）。"""

    _attr_name = "强效档位"
    _attr_native_min_value = 1
    _attr_native_max_value = 4
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX
    entity_key = "gear"

    @property
    def native_value(self) -> int | None:
        mode = self._device_config.get("workMode")
        try:
            if int(mode) != 2:
                return None
        except (TypeError, ValueError):
            return None
        return minutes_to_gear(parse_device_time(self._device_config.get("time")))

    async def async_set_native_value(self, value: float) -> None:
        gear = int(value)
        minutes = STRONG_GEAR_MINUTES.get(gear)
        if minutes is None:
            return
        try:
            await self.coordinator.client.send_ins(
                self.device_code,
                workMode=2,
                time=minutes,
                workModeStatus=3,
            )
        except ChuanglvjiaError as err:
            self.coordinator.logger.error("设置强效档位失败: %s", err)
            raise
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()