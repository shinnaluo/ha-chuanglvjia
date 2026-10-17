"""强效模式风扇实体：开关 + 4 档调速。"""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChuanglvjiaConfigEntry
from .api import ChuanglvjiaError
from .const import (
    MODE_SEND_PAYLOADS,
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
            ChuanglvjiaStrongFan(coordinator, code)
            for code in (coordinator.data or {})
            if code not in known
        ]
        if new:
            known.update(e.device_code for e in new)
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


def _gear_from_percentage(percentage: int | None) -> int | None:
    if percentage is None or percentage <= 0:
        return None
    gear = round(percentage / 25)
    return max(1, min(4, gear))


class ChuanglvjiaStrongFan(ChuanglvjiaDeviceEntity, FanEntity):
    """强效模式：开=进入强效（默认4档），关=切回智能；4 档对应 25/50/75/100%。"""

    _attr_name = "强效净化"
    _attr_speed_count = 4
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    entity_key = "strong_fan"

    @property
    def _current_gear(self) -> int | None:
        mode = self._device_config.get("workMode")
        try:
            if int(mode) != 2:
                return None
        except (TypeError, ValueError):
            return None
        return minutes_to_gear(parse_device_time(self._device_config.get("time")))

    @property
    def is_on(self) -> bool | None:
        if not self._device:
            return None
        try:
            mode = int(self._device_config.get("workMode"))
        except (TypeError, ValueError):
            return None
        open_status = self._device_status.get("openStatus")
        return open_status == 1 and mode == 2

    @property
    def percentage(self) -> int | None:
        if not self.is_on:
            return 0
        gear = self._current_gear
        return gear * 25 if gear else None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        pct = kwargs.get("percentage", percentage)
        # 未指定档位时默认 4 档
        gear = _gear_from_percentage(pct) or 4
        await self._send_strong(gear)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(MODE_SEND_PAYLOADS[0])

    async def async_set_percentage(self, percentage: int) -> None:
        if percentage == 0:
            await self.async_turn_off()
            return
        gear = _gear_from_percentage(percentage)
        if gear is None:
            return
        await self._send_strong(gear)

    async def _send_strong(self, gear: int) -> None:
        minutes = STRONG_GEAR_MINUTES[gear]
        payload: dict[str, Any] = {
            "workMode": 2,
            "time": minutes,
            "workModeStatus": 3,
        }
        if self._device_status.get("openStatus") != 1:
            payload["openStatus"] = 1
        await self._send(payload)

    async def _send(self, payload: dict[str, Any]) -> None:
        try:
            await self.coordinator.client.send_ins(self.device_code, **payload)
        except ChuanglvjiaError as err:
            self.coordinator.logger.error("强效风扇指令失败: %s", err)
            raise
        await asyncio.sleep(2)
        await self.coordinator.async_request_refresh()
