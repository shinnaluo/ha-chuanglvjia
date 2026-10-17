"""创绿家云端 API 客户端（基于抓包逆向，供自用集成）。"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import aiohttp

from .const import API_BASE, DEFAULT_BIND_NAME

_LOGGER = logging.getLogger(__name__)

PATH_LOGIN = "/ae_oss/wx/user/oneKeyEmpower"
PATH_HOME_LIST = "/ae_oss/wx/home/list"
PATH_DEVICE_LIST = "/ae_oss/wx/device/list"
PATH_DEVICE = "/ae_oss/wx/device"
PATH_DEVICE_VIEW = "/ae_oss/wx/device/view/{device_id}"
PATH_PLACE_LIST = "/ae_oss/wx/place/list"
PATH_SEND_INS = "/ae_oss/wx/operate/sendIns"
PATH_ENV_VIEW = "/ae_oss/wx/environmentalData/view/{device_code}"
PATH_TREND = "/ae_oss/wx/environmentalData/trend/{device_code}/{end_ms}/{stat_type}/{page}"


class ChuanglvjiaError(Exception):
    """基类异常。"""


class ChuanglvjiaAuthError(ChuanglvjiaError):
    """登录失效且无法自动续期。"""


class ChuanglvjiaApiError(ChuanglvjiaError):
    """云端返回业务错误或网络失败。"""


class ChuanglvjiaClient:
    """异步云端客户端，token 失效时自动重新登录一次。"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        open_id: str,
        phone: str,
        bind_name: str = DEFAULT_BIND_NAME,
        token: str | None = None,
    ) -> None:
        self._session = session
        self._open_id = open_id
        self._phone = phone
        self._bind_name = bind_name or DEFAULT_BIND_NAME
        self._token = token
        self._login_lock = asyncio.Lock()

    @property
    def token(self) -> str | None:
        return self._token

    async def _raw_request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        with_token: bool = True,
    ) -> Any:
        url = API_BASE + path
        headers: dict[str, str] = {
            "content-type": "application/json;charset=UTF-8",
            "User-Agent": "HomeAssistant-Chuanglvjia/0.1",
        }
        if with_token and self._token:
            headers["tokenwx"] = self._token
        try:
            async with self._session.request(
                method, url, json=json_body, headers=headers, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise ChuanglvjiaApiError(f"请求失败: {err}") from err

        if not isinstance(data, dict):
            raise ChuanglvjiaApiError(f"响应格式异常: {data!r}")
        return data

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        allow_relogin: bool = True,
    ) -> Any:
        data = await self._raw_request(method, path, json_body=json_body)
        code = data.get("code")
        if code == 9 and allow_relogin:
            _LOGGER.info("token 已失效，自动重新登录")
            await self.login()
            data = await self._raw_request(method, path, json_body=json_body)
            code = data.get("code")
        if code == 9:
            raise ChuanglvjiaAuthError(data.get("message") or "请重新登录")
        if code != 0:
            raise ChuanglvjiaApiError(data.get("message") or f"接口错误 code={code}")
        return data.get("data")

    async def login(self) -> str:
        """用静态 openId + 手机号换 token（无需微信参与）。"""
        async with self._login_lock:
            payload = {
                "name": self._bind_name,
                "openId": self._open_id,
                "sysUser": {"phone": self._phone},
            }
            data = await self._raw_request(
                "POST", PATH_LOGIN, json_body=payload, with_token=False
            )
            if data.get("code") != 0:
                raise ChuanglvjiaAuthError(data.get("message") or "登录失败")
            token = (data.get("data") or {}).get("sysUser", {}).get("token")
            if not token:
                raise ChuanglvjiaAuthError("登录响应中没有 token")
            self._token = token
            _LOGGER.debug("登录成功，token=%s…", token[:8])
            return token

    async def get_homes(self) -> list[dict[str, Any]]:
        data = await self._request("GET", f"{PATH_HOME_LIST}?pageCurrent=1&pageSize=50")
        return list((data or {}).get("list") or [])

    async def get_devices(self) -> list[dict[str, Any]]:
        """拉取全部家庭下的设备（device/list 必须带 homeId）。"""
        homes = await self.get_homes()
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for home in homes:
            home_id = home.get("id")
            if not home_id:
                continue
            data = await self._request(
                "GET",
                f"{PATH_DEVICE_LIST}?pageCurrent=1&pageSize=50&homeId={home_id}",
            )
            for dev in (data or {}).get("list") or []:
                code = dev.get("code")
                if code and code not in seen:
                    seen.add(code)
                    result.append(dev)
        return result

    async def get_device_view(self, device_id: str) -> dict[str, Any]:
        data = await self._request("GET", PATH_DEVICE_VIEW.format(device_id=device_id))
        return data or {}

    async def send_ins(self, device_code: str, **fields: Any) -> None:
        body: dict[str, Any] = {"deviceCode": device_code, **fields}
        await self._request("POST", PATH_SEND_INS, json_body=body)

    async def get_places(self) -> list[dict[str, Any]]:
        data = await self._request("GET", PATH_PLACE_LIST)
        return list(data or [])

    async def update_device(self, device_id: str, **fields: Any) -> None:
        """PUT /ae_oss/wx/device，用于修改位置等设备属性。"""
        await self._request("PUT", PATH_DEVICE, json_body={"id": device_id, **fields})

    async def get_env_view(self, device_code: str) -> dict[str, Any] | None:
        """实时环境数据（hcho 等，随设备上报更新）。"""
        data = await self._request("GET", PATH_ENV_VIEW.format(device_code=device_code))
        return data or None

    async def get_trend_latest(self, device_code: str, stat_type: int = 1) -> dict[str, Any] | None:
        """取环境统计最新一个非空桶。type: 1=小时 2=日 3=月。该接口无需 token。"""
        end_ms = int(time.time() * 1000)
        path = PATH_TREND.format(device_code=device_code, end_ms=end_ms, stat_type=stat_type, page=1)
        data = await self._request("GET", path)
        value = ((data or {}).get("ENV") or {}).get("value") or {}
        latest_ts: int | None = None
        latest_raw: str | None = None
        for ts_str, raw in value.items():
            if not raw or raw == "{}":
                continue
            try:
                ts = int(ts_str)
            except ValueError:
                continue
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts
                latest_raw = raw
        if latest_raw is None:
            return None
        try:
            stats = json.loads(latest_raw)
        except ValueError:
            return None
        return {"bucket_ms": latest_ts, **stats}
