"""Tests for the Octopus Nero config flow (user setup + reauth)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.octopus_nero.api import (
    AuthTokens,
    OctopusNeroApiError,
    OctopusNeroAuthError,
)
from custom_components.octopus_nero.const import (
    CONF_ACCOUNT_NUMBER,
    CONF_API_KEY,
    DOMAIN,
)


_VALID_INPUT = {
    CONF_API_KEY: "sk_live_test_apikey",
    CONF_ACCOUNT_NUMBER: "A-AAAA1111",
}


def _fresh_tokens() -> AuthTokens:
    return AuthTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
    )


@pytest.fixture
def mock_obtain_token_ok():
    with patch(
        "custom_components.octopus_nero.config_flow.OctopusNeroClient.obtain_token",
        new=AsyncMock(return_value=_fresh_tokens()),
    ) as m:
        yield m


@pytest.fixture
def mock_obtain_token_auth_error():
    with patch(
        "custom_components.octopus_nero.config_flow.OctopusNeroClient.obtain_token",
        new=AsyncMock(side_effect=OctopusNeroAuthError("bad key")),
    ) as m:
        yield m


@pytest.fixture
def mock_obtain_token_network_error():
    with patch(
        "custom_components.octopus_nero.config_flow.OctopusNeroClient.obtain_token",
        new=AsyncMock(side_effect=OctopusNeroApiError("network")),
    ) as m:
        yield m


async def test_user_step_happy_path(
    hass: HomeAssistant, mock_obtain_token_ok
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=_VALID_INPUT
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Octopus Nero (A-AAAA1111)"
    assert result["data"] == _VALID_INPUT


async def test_user_step_invalid_account_number(
    hass: HomeAssistant, mock_obtain_token_ok
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={**_VALID_INPUT, CONF_ACCOUNT_NUMBER: "not-an-account"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_ACCOUNT_NUMBER: "invalid_account"}


async def test_user_step_invalid_api_key(
    hass: HomeAssistant, mock_obtain_token_auth_error
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=_VALID_INPUT
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_user_step_cannot_connect(
    hass: HomeAssistant, mock_obtain_token_network_error
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=_VALID_INPUT
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


# --- T031: reauth flow -------------------------------------------------------


async def test_reauth_flow_with_new_api_key(
    hass: HomeAssistant, mock_obtain_token_ok
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Octopus Nero (A-AAAA1111)",
        data=_VALID_INPUT,
        unique_id="A-AAAA1111",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=_VALID_INPUT,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "sk_live_new_key"},
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_with_invalid_key_shows_error(
    hass: HomeAssistant, mock_obtain_token_auth_error
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Octopus Nero (A-AAAA1111)",
        data=_VALID_INPUT,
        unique_id="A-AAAA1111",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_REAUTH, "entry_id": entry.entry_id},
        data=_VALID_INPUT,
    )

    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "sk_invalid"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}
