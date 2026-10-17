"""常量定义。"""
from __future__ import annotations

DOMAIN = "chuanglvjia"

API_BASE = "https://air.chuanglvjia.cn"

CONF_OPEN_ID = "open_id"
CONF_PHONE = "phone"
CONF_BIND_NAME = "bind_name"
CONF_TOKEN = "token"

DEFAULT_BIND_NAME = "微信用户"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 15

# 工作模式（2026-10-17 定向抓包实测）：
#   智能 = workMode 0 + workModeStatus 0
#   强效 = workMode 2 + time(档位编码) + workModeStatus 3
#   母婴 = workMode 4 + workModeStatus 1
# 强效档位编码在 time 字段（协议值，非界面剩余时长；界面恒显示30分钟）：
#   1档=15 / 2档=30 / 4档=120 实测；3档=60 为推测。
WORK_MODES: dict[int, str] = {
    0: "智能",
    2: "强效",
    4: "母婴",
}

STRONG_GEAR_MINUTES: dict[int, int] = {
    1: 15,
    2: 30,
    3: 60,  # 推测，未实测
    4: 120,
}

# 切换非强效模式时的完整报文（与小程序一致）
MODE_SEND_PAYLOADS: dict[int, dict[str, int]] = {
    0: {"workMode": 0, "workModeStatus": 0},
    4: {"workMode": 4, "workModeStatus": 1},
}

# 关机复位报文（与小程序一致，workMode:4 为小程序固定附带值）
POWER_OFF_PAYLOAD: dict[str, int] = {
    "openStatus": 0,
    "workModeStatus": 0,
    "workMode": 4,
    "childrenLockStatus": 0,
    "time": 0,
}


def parse_device_time(raw) -> int | None:
    """云端 deviceConfig.time 为 HH:MM 四位字符串（"0030"→30）或分钟数。"""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text == "0":
        return 0
    if text.isdigit() and len(text) == 4:
        return int(text[:2]) * 60 + int(text[2:])
    try:
        return int(float(text))
    except ValueError:
        return None


def minutes_to_gear(minutes: int | None) -> int | None:
    if minutes is None:
        return None
    for gear, mins in STRONG_GEAR_MINUTES.items():
        if mins == minutes:
            return gear
    return None

ATTR_FAN_STATUS = "fan_status"
ATTR_WORK_STATUS = "work_status"
ATTR_WORK_MODE_STATUS = "work_mode_status"
ATTR_FIRMWARE = "firmware_version"
ATTR_HARDWARE = "hardware_version"
ATTR_WORK_DURATION = "work_duration_min"
ATTR_UPDATE_TIME = "cloud_update_time"
ATTR_WIFI_NAME = "wifi_name"
ATTR_PLACE = "place"
ATTR_BUCKET_TIME = "stat_bucket_time"
