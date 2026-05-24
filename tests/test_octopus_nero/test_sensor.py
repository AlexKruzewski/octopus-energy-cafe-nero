"""Tests for OfferStatusSensor — state, attributes, and unavailability."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.octopus_nero.api import (
    AuthTokens,
    ClaimResult,
    OfferStatus,
    OfferStatusResult,
)
from custom_components.octopus_nero.const import (
    CONF_ACCOUNT_NUMBER,
    CONF_API_KEY,
    DOMAIN,
)

SENSOR_ENTITY_ID = "sensor.octopus_nero_offer_status"


def _fresh_tokens() -> AuthTokens:
    return AuthTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
    )


@pytest.fixture
async def setup_integration(hass: HomeAssistant):
    """Install the integration with mocked API client, yield the mock instance."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_ACCOUNT_NUMBER: "A-AAAA1111"},
        entry_id="test_entry",
        unique_id="A-AAAA1111",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.octopus_nero.coordinator.OctopusNeroClient", autospec=True
    ) as cls:
        instance = cls.return_value
        instance.obtain_token = AsyncMock(return_value=_fresh_tokens())
        instance.refresh_token = AsyncMock(return_value=_fresh_tokens())
        instance.get_offer_status = AsyncMock(
            return_value=OfferStatusResult(status=OfferStatus.AVAILABLE)
        )
        instance.claim_coffee = AsyncMock(
            return_value=ClaimResult(success=True, reward_id="rew_1")
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield instance, entry


# --- T023: sensor state reflects coordinator data ----------------------------


async def test_sensor_state_reflects_coordinator_data(
    hass: HomeAssistant, setup_integration
) -> None:
    instance, _ = setup_integration
    instance.get_offer_status.return_value = OfferStatusResult(
        status=OfferStatus.CLAIMED
    )
    coordinator = next(iter(hass.data[DOMAIN].values()))
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == OfferStatus.CLAIMED


async def test_sensor_attributes_include_last_checked_and_last_claimed(
    hass: HomeAssistant, setup_integration
) -> None:
    _, _ = setup_integration
    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    attrs = state.attributes
    assert "last_checked" in attrs
    assert "last_claimed" in attrs
    assert "cannot_claim_reason" in attrs


async def test_sensor_unavailable_on_update_failed(
    hass: HomeAssistant, setup_integration
) -> None:
    instance, _ = setup_integration
    instance.get_offer_status.side_effect = Exception("network down")
    coordinator = next(iter(hass.data[DOMAIN].values()))
    try:
        await coordinator.async_refresh()
    except Exception:
        pass
    await hass.async_block_till_done()

    state = hass.states.get(SENSOR_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"
