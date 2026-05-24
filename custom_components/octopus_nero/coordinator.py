"""DataUpdateCoordinator for Octopus Nero.

Owns the auth-token lifecycle, the offer-status polling loop, the auto-claim
trigger, and persistent-notification fan-out. The HA API client lives in
api.py so it can be unit-tested without HA fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AuthTokens,
    ClaimResult,
    OctopusNeroApiError,
    OctopusNeroAuthError,
    OctopusNeroClient,
    OfferStatus,
    OfferStatusResult,
)
from .const import (
    CONF_ACCOUNT_NUMBER,
    CONF_API_KEY,
    DOMAIN,
    ELIGIBILITY_PERIOD_DAYS,
    MSG_ALREADY_CLAIMED,
    MSG_AUTH_FAILED,
    MSG_OUT_OF_STOCK,
    MSG_SUCCESS,
    MSG_UNKNOWN_ERROR,
    NOTIFICATION_ID_PREFIX,
    NOTIFICATION_TITLE,
    POLL_INTERVAL_MINUTES,
    TOKEN_REFRESH_LEAD_MINUTES,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CoordinatorData:
    """Runtime state surfaced to entities."""

    status: OfferStatus
    last_checked: datetime
    last_claimed: datetime | None = None
    cannot_claim_reason: str | None = None


class OctopusNeroCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Polls Octopus Energy and auto-claims the free Cafe Nero."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=POLL_INTERVAL_MINUTES),
        )
        self._entry = entry
        self._api_key: str = entry.data[CONF_API_KEY]
        self._account_number: str = entry.data[CONF_ACCOUNT_NUMBER]
        self._client = OctopusNeroClient(async_get_clientsession(hass))
        self._tokens: AuthTokens | None = None
        self._last_claimed_at: datetime | None = None

    # ------------------------------------------------------------------
    # DataUpdateCoordinator hooks
    # ------------------------------------------------------------------

    async def _async_setup(self) -> None:
        """First-time auth on coordinator startup."""
        await self._authenticate_initial()

    async def _async_update_data(self) -> CoordinatorData:
        """Refresh tokens if needed, poll offer status, auto-claim if eligible."""
        await self._ensure_authenticated()
        try:
            status = await self._client.get_offer_status(
                self._tokens.access_token, self._account_number
            )
        except OctopusNeroAuthError as err:
            # Token thought to be fresh but server disagrees — try one full re-auth.
            _LOGGER.warning("Offer-status call failed auth; re-authenticating once")
            await self._authenticate_with_api_key()
            try:
                status = await self._client.get_offer_status(
                    self._tokens.access_token, self._account_number
                )
            except OctopusNeroAuthError as inner:
                raise ConfigEntryAuthFailed(str(inner)) from inner
        except OctopusNeroApiError as err:
            raise UpdateFailed(f"Octopus Energy API error: {err}") from err

        data = CoordinatorData(
            status=status.status,
            last_checked=_utc_now(),
            last_claimed=self._last_claimed_at,
            cannot_claim_reason=status.cannot_claim_reason,
        )

        if status.status == OfferStatus.AVAILABLE and self._is_eligible_now():
            _LOGGER.info("Cafe Nero offer is available — auto-claiming")
            result = await self._perform_claim()
            if result.success:
                self._last_claimed_at = _utc_now()
                data.status = OfferStatus.CLAIMED
                data.last_claimed = self._last_claimed_at

        return data

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    async def async_claim_coffee(self, force: bool = False) -> ClaimResult:
        """Manual claim entry point (used by octopus_nero.claim_coffee service)."""
        if not force and not self._is_eligible_now():
            self._emit_notification(
                MSG_ALREADY_CLAIMED, notification_id="already_claimed"
            )
            return ClaimResult(
                success=False,
                reason="already_claimed",
                error_message="Local guard: claim already made in current period",
            )
        await self._ensure_authenticated()
        result = await self._perform_claim()
        if result.success:
            self._last_claimed_at = _utc_now()
            await self.async_request_refresh()
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _perform_claim(self) -> ClaimResult:
        try:
            result = await self._client.claim_coffee(
                self._tokens.access_token, self._account_number
            )
        except OctopusNeroAuthError:
            self._emit_notification(MSG_AUTH_FAILED, notification_id="auth_failed")
            raise ConfigEntryAuthFailed("Auth failed during claim")

        self._emit_claim_notification(result)
        return result

    def _emit_claim_notification(self, result: ClaimResult) -> None:
        if result.success:
            self._emit_notification(MSG_SUCCESS, notification_id="success")
            return
        message = {
            "already_claimed": MSG_ALREADY_CLAIMED,
            "out_of_stock": MSG_OUT_OF_STOCK,
            "auth_error": MSG_AUTH_FAILED,
        }.get(result.reason or "", MSG_UNKNOWN_ERROR)
        self._emit_notification(
            message, notification_id=result.reason or "unknown"
        )

    def _emit_notification(self, message: str, *, notification_id: str) -> None:
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": NOTIFICATION_TITLE,
                    "message": message,
                    "notification_id": f"{NOTIFICATION_ID_PREFIX}{notification_id}",
                },
                blocking=False,
            )
        )

    def _is_eligible_now(self) -> bool:
        if self._last_claimed_at is None:
            return True
        elapsed = _utc_now() - self._last_claimed_at
        return elapsed >= timedelta(days=ELIGIBILITY_PERIOD_DAYS)

    async def _authenticate_initial(self) -> None:
        try:
            self._tokens = await self._client.obtain_token(self._api_key)
        except OctopusNeroAuthError as err:
            raise ConfigEntryAuthFailed("Octopus Energy API key rejected") from err
        except OctopusNeroApiError as err:
            raise UpdateFailed(f"Could not reach Octopus Energy: {err}") from err

    async def _authenticate_with_api_key(self) -> None:
        try:
            self._tokens = await self._client.obtain_token(self._api_key)
        except OctopusNeroAuthError as err:
            raise ConfigEntryAuthFailed("Octopus Energy API key no longer valid") from err

    async def _ensure_authenticated(self) -> None:
        if self._tokens is None:
            await self._authenticate_initial()
            return
        refresh_at = self._tokens.expires_at - timedelta(
            minutes=TOKEN_REFRESH_LEAD_MINUTES
        )
        if _utc_now() < refresh_at:
            return

        try:
            self._tokens = await self._client.refresh_token(self._tokens.refresh_token)
            return
        except OctopusNeroAuthError:
            _LOGGER.info("Refresh token rejected; falling back to API key auth")
        except OctopusNeroApiError as err:
            raise UpdateFailed(f"Could not refresh token: {err}") from err

        await self._authenticate_with_api_key()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
