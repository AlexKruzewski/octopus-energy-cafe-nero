"""Tests for OctopusNeroCoordinator — auth, polling, auto-claim, guard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntryState
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


def _fresh_tokens(ttl_minutes: int = 60) -> AuthTokens:
    return AuthTokens(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    )


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
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


async def _setup(hass: HomeAssistant):
    """Set up integration through the HA config entry flow and return the coordinator."""
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return coordinator, entry


# --- T011: foundational coordinator behaviour ------------------------------


async def test_first_refresh_authenticates(
    hass: HomeAssistant, patched_client
) -> None:
    coordinator, _ = await _setup(hass)

    patched_client.obtain_token.assert_awaited_once_with("key")
    patched_client.get_offer_status.assert_awaited_once()


async def test_initial_auth_failure_marks_entry_setup_error(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.obtain_token.side_effect = OctopusNeroAuthError("bad key")
    entry = _make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


# --- T022 / T023: status polling + auto-claim ------------------------------


async def test_auto_claim_triggers_on_available(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.get_offer_status.return_value = OfferStatusResult(
        status=OfferStatus.AVAILABLE
    )
    coordinator, _ = await _setup(hass)

    patched_client.claim_coffee.assert_awaited_once()
    assert coordinator.data.status is OfferStatus.CLAIMED


async def test_auto_claim_skipped_when_already_claimed_this_period(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.get_offer_status.return_value = OfferStatusResult(
        status=OfferStatus.AVAILABLE
    )
    coordinator, _ = await _setup(hass)
    patched_client.claim_coffee.reset_mock()

    coordinator._last_claimed_at = datetime.now(timezone.utc)
    patched_client.get_offer_status.return_value = OfferStatusResult(
        status=OfferStatus.AVAILABLE
    )
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    patched_client.claim_coffee.assert_not_awaited()


# --- T015 / T016: manual claim + duplicate guard ---------------------------


async def test_manual_claim_succeeds(
    hass: HomeAssistant, patched_client
) -> None:
    coordinator, _ = await _setup(hass)
    patched_client.claim_coffee.reset_mock()

    result = await coordinator.async_claim_coffee(force=False)

    assert result.success is True
    patched_client.claim_coffee.assert_awaited_once()


async def test_manual_claim_blocked_by_duplicate_guard(
    hass: HomeAssistant, patched_client
) -> None:
    coordinator, _ = await _setup(hass)
    coordinator._last_claimed_at = datetime.now(timezone.utc)
    patched_client.claim_coffee.reset_mock()

    result = await coordinator.async_claim_coffee(force=False)

    assert result.success is False
    assert result.reason == "already_claimed"
    patched_client.claim_coffee.assert_not_awaited()


async def test_manual_claim_force_bypasses_local_guard(
    hass: HomeAssistant, patched_client
) -> None:
    coordinator, _ = await _setup(hass)
    coordinator._last_claimed_at = datetime.now(timezone.utc)
    patched_client.claim_coffee.reset_mock()

    result = await coordinator.async_claim_coffee(force=True)

    assert result.success is True
    patched_client.claim_coffee.assert_awaited_once()


async def test_eligibility_period_resets_after_seven_days(
    hass: HomeAssistant, patched_client
) -> None:
    coordinator, _ = await _setup(hass)
    coordinator._last_claimed_at = datetime.now(timezone.utc) - timedelta(days=8)
    patched_client.claim_coffee.reset_mock()

    result = await coordinator.async_claim_coffee(force=False)

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
    coordinator, _ = await _setup(hass)

    patched_client.claim_coffee.assert_awaited_once()
    assert coordinator.data.status is OfferStatus.CLAIMED


async def test_failure_notification_fires_on_out_of_stock(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.claim_coffee.return_value = ClaimResult(
        success=False, reason="out_of_stock", error_message="OUT_OF_STOCK"
    )
    coordinator, _ = await _setup(hass)

    result = await coordinator.async_claim_coffee(force=True)

    assert result.success is False
    assert result.reason == "out_of_stock"


async def test_failure_notification_fires_on_auth_error(
    hass: HomeAssistant, patched_client
) -> None:
    patched_client.claim_coffee.return_value = ClaimResult(
        success=False, reason="auth_error", error_message="auth failed"
    )
    coordinator, _ = await _setup(hass)

    result = await coordinator.async_claim_coffee(force=True)

    assert result.success is False


async def test_already_claimed_notification_message(
    hass: HomeAssistant, patched_client
) -> None:
    coordinator, _ = await _setup(hass)
    coordinator._last_claimed_at = datetime.now(timezone.utc)

    result = await coordinator.async_claim_coffee(force=False)

    assert result.success is False
    assert result.reason == "already_claimed"


# --- T033: persistent auth failure raises ConfigEntryAuthFailed -------------


async def test_persistent_auth_failure_marks_entry_setup_error(
    hass: HomeAssistant, patched_client
) -> None:
    """When both refresh_token and obtain_token fail, the coordinator
    should cause the entry to enter SETUP_ERROR state."""
    patched_client.obtain_token.side_effect = OctopusNeroAuthError("bad key")
    entry = _make_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
