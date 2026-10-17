"""开关实体：电源、童锁。"""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChuanglvjiaConfigEntry
from .api import ChuanglvjiaError
from .const import POWER_OFF_PAYLOAD
from .entity import ChuanglvjiaDeviceEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ChuanglvjiaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """按协调器中的设备动态添加。"""
    coordinator = entry.runtime_data.data_coordinator
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new = [
            cls(coordinator, code)
            for code in (coordinator.data or {})
            if code not in known
            for cls in (
                ChuanglvjiaPowerSwitch,
                ChuanglvjiaChildLockSwitch,
                ChuanglvjiaSleepSwitch,
            )
        ]
        if new:
            known.update(e.device_code for e in new)
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class _BaseSwitch(ChuanglvjiaDeviceEntity, SwitchEntity):
    async def _send(self, **fields: Any) -> None:
        try:
            await self.coordinator.client.send_ins(self.device_code, **fields)
        except ChuanglvjiaError as err:
            self.coordinator.logger.error("指令发送失败: %s", err)
            raise
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()


class ChuanglvjiaPowerSwitch(_BaseSwitch):
    """电源开关。"""

    _attr_name = "电源"

    @property
    def is_on(self) -> bool | None:
        status = self._device_status
        if not status:
            return None
        return status.get("openStatus") == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send(openStatus=1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(**POWER_OFF_PAYLOAD)


class ChuanglvjiaChildLockSwitch(_BaseSwitch):
    """童锁。"""

    _attr_name = "童锁"

    @property
    def is_on(self) -> bool | None:
        status = self._device_status
        if not status:
            return None
        return status.get("childrenLockStatus") == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send(childrenLockStatus=1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(childrenLockStatus=0)


class ChuanglvjiaSleepSwitch(_BaseSwitch):
    """睡眠模式（sendIns sleepMode 0/1，位于设备顶层字段）。"""

    _attr_name = "睡眠模式"

    @property
    def is_on(self) -> bool | None:
        if not self._device:
            return None
        return self._device.get("sleepMode") == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._send(sleepMode=1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(sleepMode=0)
