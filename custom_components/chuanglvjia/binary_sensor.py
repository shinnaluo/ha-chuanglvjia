"""二元传感器：甲醛超标、在线状态。"""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChuanglvjiaConfigEntry
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
            cls(coordinator, code)
            for code in (coordinator.data or {})
            if code not in known
            for cls in (ChuanglvjiaExceedBinary, ChuanglvjiaOnlineBinary)
        ]
        if new:
            known.update(e.device_code for e in new)
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class ChuanglvjiaExceedBinary(ChuanglvjiaDeviceEntity, BinarySensorEntity):
    """甲醛超标（云端 exceed 字段）。"""

    _attr_name = "甲醛超标"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    entity_key = "exceed"

    @property
    def is_on(self) -> bool | None:
        if not self._device:
            return None
        return bool(self._device.get("exceed"))


class ChuanglvjiaOnlineBinary(ChuanglvjiaDeviceEntity, BinarySensorEntity):
    """设备在线。"""

    _attr_name = "在线"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    entity_key = "online"

    @property
    def is_on(self) -> bool | None:
        if not self._device:
            return None
        return self._device.get("status") == 1
