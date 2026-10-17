"""传感器：甲醛浓度（实时）、运行状态。"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import CONCENTRATION_MICROGRAMS_PER_CUBIC_METER, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ChuanglvjiaConfigEntry
from .const import (
    ATTR_FAN_STATUS,
    ATTR_FIRMWARE,
    ATTR_HARDWARE,
    ATTR_PLACE,
    ATTR_UPDATE_TIME,
    ATTR_WIFI_NAME,
    ATTR_WORK_DURATION,
    ATTR_WORK_MODE_STATUS,
    ATTR_WORK_STATUS,
    WORK_MODES,
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
        new: list[SensorEntity] = []
        for code in (coordinator.data or {}):
            if code not in known:
                new.append(ChuanglvjiaStatusSensor(coordinator, code))
                new.append(ChuanglvjiaHchoSensor(coordinator, code))
        if new:
            known.update(e.device_code for e in new)
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


class ChuanglvjiaStatusSensor(ChuanglvjiaDeviceEntity, SensorEntity):
    """运行状态摘要（诊断）。"""

    _attr_name = "运行状态"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    entity_key = "status"

    @property
    def native_value(self) -> str | None:
        status = self._device_status
        if not status:
            return None
        open_val = status.get("openStatusVal") or (
            "开机" if status.get("openStatus") == 1 else "关机"
        )
        if status.get("openStatus") != 1:
            return open_val
        try:
            mode = int(self._device_config.get("workMode"))
        except (TypeError, ValueError):
            mode = None
        extras = []
        work_status = status.get("workStatus")
        if work_status == 1:
            extras.append("运行中")
        elif work_status == 0:
            extras.append("待机")
        mode_status = status.get("workModeStatus")
        if mode_status == 3:
            extras.append("定时中")
        suffix = f"（{'、'.join(extras)}）" if extras else ""
        mode_part = ""
        if mode in WORK_MODES:
            mode_part = f" {WORK_MODES[mode]}"
            if mode == 2:
                gear = minutes_to_gear(parse_device_time(self._device_config.get("time")))
                if gear:
                    mode_part = f" 强效{gear}档"
        return f"{open_val}{mode_part}{suffix}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        dev = self._device
        status = self._device_status
        return {
            "workMode": self._device_config.get("workMode"),
            "time": self._device_config.get("time"),
            ATTR_WORK_MODE_STATUS: status.get("workModeStatus"),
            ATTR_WORK_STATUS: status.get("workStatus"),
            ATTR_FAN_STATUS: status.get("fanStatus"),
            ATTR_FIRMWARE: dev.get("firmwareVersion"),
            ATTR_HARDWARE: dev.get("hardwareVersion"),
            ATTR_WORK_DURATION: dev.get("workDuration"),
            ATTR_PLACE: dev.get("placeVal"),
            ATTR_WIFI_NAME: dev.get("wifiName"),
            ATTR_UPDATE_TIME: status.get("updateDate"),
        }


class ChuanglvjiaHchoSensor(ChuanglvjiaDeviceEntity, SensorEntity):
    """甲醛浓度（云端实时数据 environmentalData/view，单位 μg/m³）。"""

    _attr_name = "甲醛浓度"
    _attr_native_unit_of_measurement = CONCENTRATION_MICROGRAMS_PER_CUBIC_METER
    _attr_state_class = SensorStateClass.MEASUREMENT
    entity_key = "hcho"

    @property
    def _env(self) -> dict[str, Any] | None:
        return self._device.get("envView")

    @property
    def native_value(self) -> int | None:
        env = self._env
        if not env:
            return None
        try:
            return int(env.get("hcho"))
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        env = self._env or {}
        return {
            "云端更新时间": env.get("updateDate"),
            "newData": env.get("newData"),
            "pm25": env.get("pm25"),
            "tvoc": env.get("tvoc"),
            "co2": env.get("co2"),
        }
