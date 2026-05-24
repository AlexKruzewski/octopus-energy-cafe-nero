"""Config flow for the Octopus Nero integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OctopusNeroApiError, OctopusNeroAuthError, OctopusNeroClient
from .const import CONF_ACCOUNT_NUMBER, CONF_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)

_ACCOUNT_NUMBER_PATTERN = re.compile(r"^A-[A-Z0-9]+$")

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_ACCOUNT_NUMBER): str,
    }
)


class OctopusNeroConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle initial setup and reauth for the Octopus Nero integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._reauth_entry_data: Mapping[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First-time setup: collect API key + account number, validate, create entry."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            account_number = user_input[CONF_ACCOUNT_NUMBER].strip().upper()
            validation_errors = await self._validate(api_key, account_number)
            errors.update(validation_errors)

            if not errors:
                await self.async_set_unique_id(account_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Octopus Nero ({account_number})",
                    data={
                        CONF_API_KEY: api_key,
                        CONF_ACCOUNT_NUMBER: account_number,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Triggered when the coordinator raises ConfigEntryAuthFailed."""
        self._reauth_entry_data = entry_data
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user for a new API key."""
        errors: dict[str, str] = {}
        existing = self._reauth_entry_data or {}
        account_number = existing.get(CONF_ACCOUNT_NUMBER, "")

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            validation_errors = await self._validate(api_key, account_number)
            errors.update(validation_errors)

            if not errors:
                entry = self._get_reauth_entry()
                if entry is not None:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_API_KEY: api_key},
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
            description_placeholders={"account_number": account_number},
        )

    async def _validate(
        self, api_key: str, account_number: str
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not _ACCOUNT_NUMBER_PATTERN.match(account_number):
            errors[CONF_ACCOUNT_NUMBER] = "invalid_account"
            return errors

        client = OctopusNeroClient(async_get_clientsession(self.hass))
        try:
            await client.obtain_token(api_key)
        except OctopusNeroAuthError:
            errors[CONF_API_KEY] = "invalid_api_key"
        except OctopusNeroApiError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Unexpected error validating Octopus Energy credentials")
            errors["base"] = "unknown"
        return errors

    def _get_reauth_entry(self):
        entry_id = self.context.get("entry_id")
        if not entry_id:
            return None
        return self.hass.config_entries.async_get_entry(entry_id)
