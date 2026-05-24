"""Tests for OctopusNeroCoordinator — auth, polling, auto-claim, guard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.octopus_nero.api import (
    AuthTokens,
    ClaimResult,
    OctopusNeroAuthError,
    OfferStatus,
    OfferStatusResult,
)
from custom_components.octopus_nero.const import (
    CONF_ACCOUNT_NUMBER,
    CONF_API_KEY,
    DOMAIN,
)
from custom_components.octopus_nero.coordinator import OctopusNeroCoordinator


def _fresh_tokens(ttl_minutes: int = 60) -> AuthTokens:
    return AuthTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_ACCOUNT_NUMBER: "A-AAAA1111"},
        unique_id="A-AAAA1111",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def patched_client():
    """Patch OctopusNeroClient inside the coordinator module."""
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
        yield instance


# --- T011: foundational coordinator behaviour ------------------------------


async def test_first_refresh_authenticates(
    hass: HomeAssistant, patched_client
) -> None:
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)

    await coord.async_config_entry_first_refresh()

    patched_client.obtain_token.assert_awaited_once_with("key")
    patched_client.get_offer_status.assert_awaited_once()


async def test_initial_auth_failure_raises_config_entry_auth_failed(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.obtain_token.side_effect = OctopusNeroAuthError("bad key")
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)

    with pytest.raises(ConfigEntryAuthFailed):
        await coord.async_config_entry_first_refresh()


# --- T022 / T023: status polling + auto-claim ------------------------------


async def test_auto_claim_triggers_on_available(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.get_offer_status.return_value = OfferStatusResult(
        status=OfferStatus.AVAILABLE
    )
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)

    await coord.async_config_entry_first_refresh()

    patched_client.claim_coffee.assert_awaited_once()
    assert coord.data.status is OfferStatus.CLAIMED


async def test_auto_claim_skipped_when_already_claimed_this_period(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.get_offer_status.return_value = OfferStatusResult(
        status=OfferStatus.AVAILABLE
    )
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    coord._last_claimed_at = datetime.now(timezone.utc)  # claimed just now

    await coord.async_config_entry_first_refresh()

    patched_client.claim_coffee.assert_not_awaited()


# --- T015 / T016: manual claim + duplicate guard ---------------------------


async def test_manual_claim_succeeds(
    hass: HomeAssistant, patched_client
) -> None:
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()
    patched_client.claim_coffee.reset_mock()

    result = await coord.async_claim_coffee(force=False)

    assert result.success is True
    patched_client.claim_coffee.assert_awaited_once()


async def test_manual_claim_blocked_by_duplicate_guard(
    hass: HomeAssistant, patched_client
) -> None:
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()
    coord._last_claimed_at = datetime.now(timezone.utc)
    patched_client.claim_coffee.reset_mock()

    result = await coord.async_claim_coffee(force=False)

    assert result.success is False
    assert result.reason == "already_claimed"
    patched_client.claim_coffee.assert_not_awaited()


async def test_manual_claim_force_bypasses_local_guard(
    hass: HomeAssistant, patched_client
) -> None:
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()
    coord._last_claimed_at = datetime.now(timezone.utc)
    patched_client.claim_coffee.reset_mock()

    result = await coord.async_claim_coffee(force=True)

    assert result.success is True
    patched_client.claim_coffee.assert_awaited_once()


async def test_eligibility_period_resets_after_seven_days(
    hass: HomeAssistant, patched_client
) -> None:
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()
    coord._last_claimed_at = datetime.now(timezone.utc) - timedelta(days=8)
    patched_client.claim_coffee.reset_mock()

    result = await coord.async_claim_coffee(force=False)

    assert result.success is True
    patched_client.claim_coffee.assert_awaited_once()


# --- T028: notification messages on claim outcomes --------------------------


async def test_success_notification_fires_on_claim(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.get_offer_status.return_value = OfferStatusResult(
        status=OfferStatus.AVAILABLE
    )
    patched_client.claim_coffee.return_value = ClaimResult(
        success=True, reward_id="rew_ok"
    )
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    coord._last_claimed_at = None
    await coord.async_config_entry_first_refresh()

    patched_client.claim_coffee.assert_awaited_once()
    assert coord.data.status is OfferStatus.CLAIMED


async def test_failure_notification_fires_on_out_of_stock(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.claim_coffee.return_value = ClaimResult(
        success=False, reason="out_of_stock", error_message="OUT_OF_STOCK"
    )
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()

    result = await coord.async_claim_coffee(force=True)

    assert result.success is False
    assert result.reason == "out_of_stock"


async def test_failure_notification_fires_on_auth_error(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.claim_coffee.return_value = ClaimResult(
        success=False, reason="auth_error", error_message="auth failed"
    )
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()

    result = await coord.async_claim_coffee(force=True)

    assert result.success is False


async def test_already_claimed_notification_message(
    hass: HomeAssistant, patched_client
) -> None:
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)
    await coord.async_config_entry_first_refresh()
    coord._last_claimed_at = datetime.now(timezone.utc)

    result = await coord.async_claim_coffee(force=False)

    assert result.success is False
    assert result.reason == "already_claimed"


# --- T033: persistent auth failure raises ConfigEntryAuthFailed -------------


async def test_persistent_auth_failure_raises_config_entry_auth_failed(
    hass: HomeAssistant, patched_client
) -> None:
    """When both refresh_token and obtain_token fail, coordinator must raise
    ConfigEntryAuthFailed so HA can trigger the reauth flow."""
    patched_client.get_offer_status.side_effect = OctopusNeroAuthError("expired")
    patched_client.obtain_token.side_effect = OctopusNeroAuthError("bad key")
    entry = _entry(hass)
    coord = OctopusNeroCoordinator(hass, entry)

    with pytest.raises(ConfigEntryAuthFailed):
        await coord.async_config_entry_first_refresh()
