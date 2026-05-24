"""Tests for the octopus_nero.claim_coffee service."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
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
    SERVICE_CLAIM_COFFEE,
)


def _fresh_tokens() -> AuthTokens:
    return AuthTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=60),
    )


@pytest.fixture
async def setup_integration(hass: HomeAssistant):
    """Install the integration with a mocked API client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_ACCOUNT_NUMBER: "A-AAAA1111"},
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
            return_value=OfferStatusResult(status=OfferStatus.UNKNOWN)
        )
        instance.claim_coffee = AsyncMock(
            return_value=ClaimResult(success=True, reward_id="rew_1")
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        yield instance


async def test_claim_service_is_registered(
    hass: HomeAssistant, setup_integration
) -> None:
    assert hass.services.has_service(DOMAIN, SERVICE_CLAIM_COFFEE)


async def test_claim_service_calls_coordinator(
    hass: HomeAssistant, setup_integration
) -> None:
    setup_integration.claim_coffee.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_CLAIM_COFFEE, {}, blocking=True
    )

    setup_integration.claim_coffee.assert_awaited_once()


async def test_claim_service_force_bypasses_local_guard(
    hass: HomeAssistant, setup_integration
) -> None:
    coordinator = next(iter(hass.data[DOMAIN].values()))
    coordinator._last_claimed_at = datetime.now(timezone.utc)
    setup_integration.claim_coffee.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_CLAIM_COFFEE, {"force": True}, blocking=True
    )

    setup_integration.claim_coffee.assert_awaited_once()
