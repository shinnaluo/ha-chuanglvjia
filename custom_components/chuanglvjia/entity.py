"""设备实体基类。"""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ChuanglvjiaDataCoordinator


class ChuanglvjiaDeviceEntity(CoordinatorEntity[ChuanglvjiaDataCoordinator]):
    """绑定到单台除醛仪的实体。"""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ChuanglvjiaDataCoordinator, device_code: str) -> None:
        super().__init__(coordinator)
        self.device_code = device_code
        key = getattr(self, "entity_key", self.__class__.__name__)
        self._attr_unique_id = f"{device_code}_{key}"

    @property
    def _device(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self.device_code) or {}

    @property
    def _device_status(self) -> dict[str, Any]:
        return self._device.get("deviceStatus") or {}

    @property
    def _device_config(self) -> dict[str, Any]:
        return self._device.get("deviceConfig") or {}

    @property
    def available(self) -> bool:
        return super().available and bool(self._device)

    @property
    def device_info(self) -> DeviceInfo:
        dev = self._device
        model = dev.get("typeVal") or "除醛仪"
        hardware = dev.get("hardwareVersion")
        if hardware:
            model = f"{model} ({hardware})"
        info = DeviceInfo(
            identifiers={(DOMAIN, self.device_code)},
            manufacturer="创绿家",
            model=model,
            name=dev.get("name") or f"除醛仪 {self.device_code[-6:]}",
        )
        if dev.get("firmwareVersion"):
            info["sw_version"] = dev["firmwareVersion"]
        return info
