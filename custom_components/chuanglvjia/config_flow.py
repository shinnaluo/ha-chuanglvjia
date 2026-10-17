"""配置流：openId + 手机号 → 自动换 token。"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    ChuanglvjiaApiError,
    ChuanglvjiaAuthError,
    ChuanglvjiaClient,
)
from .const import (
    CONF_BIND_NAME,
    CONF_OPEN_ID,
    CONF_PHONE,
    CONF_TOKEN,
    DEFAULT_BIND_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_OPEN_ID): str,
        vol.Required(CONF_PHONE): str,
        vol.Optional(CONF_BIND_NAME, default=DEFAULT_BIND_NAME): str,
    }
)


async def validate_login(hass: HomeAssistant, data: dict[str, Any]) -> list[dict[str, Any]]:
    """尝试登录并拉取设备列表，返回设备。"""
    session = async_get_clientsession(hass)
    client = ChuanglvjiaClient(
        session,
        open_id=data[CONF_OPEN_ID].strip(),
        phone=data[CONF_PHONE].strip(),
        bind_name=data.get(CONF_BIND_NAME) or DEFAULT_BIND_NAME,
    )
    await client.login()
    devices = await client.get_devices()
    # 把新 token 暂存进 data 供建项使用
    data[CONF_TOKEN] = client.token
    return devices


class ChuanglvjiaConfigFlow(ConfigFlow, domain=DOMAIN):
    """配置流。"""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                devices = await validate_login(self.hass, user_input)
            except ChuanglvjiaAuthError:
                errors["base"] = "invalid_auth"
            except ChuanglvjiaApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("配置校验失败")
                errors["base"] = "unknown"
            else:
                open_id = user_input[CONF_OPEN_ID].strip().lower()
                await self.async_set_unique_id(open_id)
                self._abort_if_unique_id_configured()
                if not devices:
                    return self.async_abort(reason="no_devices")
                return self.async_create_entry(
                    title="创绿家除醛仪",
                    data={
                        CONF_OPEN_ID: open_id,
                        CONF_PHONE: user_input[CONF_PHONE].strip(),
                        CONF_BIND_NAME: user_input.get(CONF_BIND_NAME) or DEFAULT_BIND_NAME,
                        CONF_TOKEN: user_input.get(CONF_TOKEN),
                    },
                )

        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            merged = {**entry.data, **user_input}
            try:
                await validate_login(self.hass, merged)
            except ChuanglvjiaAuthError:
                errors["base"] = "invalid_auth"
            except ChuanglvjiaApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("重新登录失败")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_TOKEN: merged.get(CONF_TOKEN)}
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_OPEN_ID, default=entry.data.get(CONF_OPEN_ID, "")
                ): str,
                vol.Required(CONF_PHONE, default=entry.data.get(CONF_PHONE, "")): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return ChuanglvjiaOptionsFlow()


class ChuanglvjiaOptionsFlow(OptionsFlow):
    """选项：轮询间隔。"""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    "scan_interval",
                    default=self.config_entry.options.get(
                        "scan_interval", DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
