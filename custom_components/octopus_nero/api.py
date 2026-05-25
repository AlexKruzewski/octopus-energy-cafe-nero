"""Octopus Energy Kraken GraphQL API client.

Stateless client that exchanges API keys for JWTs, refreshes them, queries the
Octoplus reward status, and claims the Cafe Nero offer. Errors are surfaced
as typed exceptions so the coordinator can route them to the right HA flow
(reauth vs update-failed vs notification).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
import logging
from typing import Any

import aiohttp

from .const import (
    ACCESS_TOKEN_TTL_MINUTES,
    API_ENDPOINT,
    OFFER_SLUG,
)

_LOGGER = logging.getLogger(__name__)


class OctopusNeroError(Exception):
    """Base exception for OctopusNeroClient."""


class OctopusNeroAuthError(OctopusNeroError):
    """The Octopus API rejected our credentials."""


class OctopusNeroApiError(OctopusNeroError):
    """The Octopus API returned an unexpected error."""


class OfferStatus(StrEnum):
    """Claimability state of the Cafe Nero offer."""

    AVAILABLE = "available"
    CLAIMED = "claimed"
    OUT_OF_STOCK = "out_of_stock"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AuthTokens:
    """Access + refresh tokens with an absolute UTC expiry."""

    access_token: str
    refresh_token: str
    expires_at: datetime


@dataclass(frozen=True)
class OfferStatusResult:
    """Parsed offer-status response."""

    status: OfferStatus
    cannot_claim_reason: str | None = None


@dataclass(frozen=True)
class ClaimResult:
    """Outcome of a claim attempt."""

    success: bool
    reward_id: str | None = None
    reason: str | None = None  # machine-readable: already_claimed / out_of_stock / auth_error / unknown
    error_message: str | None = None


_OBTAIN_TOKEN_QUERY = """
mutation ObtainKrakenToken($input: ObtainJSONWebTokenInput!) {
  obtainKrakenToken(input: $input) {
    token
    refreshToken
    refreshExpiresIn
  }
}
"""

_CHECK_OFFERS_QUERY = """
query CheckOffers($accountNumber: String!) {
  octoplusOfferGroups(accountNumber: $accountNumber, first: 20) {
    edges {
      node {
        octoplusOffers {
          slug
          claimAbility {
            canClaimOffer
            cannotClaimReason
          }
        }
      }
    }
  }
}
"""

_CLAIM_REWARD_MUTATION = """
mutation ClaimOctoplusReward($accountNumber: String!, $offerSlug: String!) {
  claimOctoplusReward(accountNumber: $accountNumber, offerSlug: $offerSlug) {
    rewardId
  }
}
"""


class OctopusNeroClient:
    """GraphQL client. Stateless — token state is held by the coordinator."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def obtain_token(self, api_key: str) -> AuthTokens:
        """Exchange an API key for an access + refresh token."""
        return await self._token_request({"APIKey": api_key})

    async def refresh_token(self, refresh_token: str) -> AuthTokens:
        """Exchange a refresh token for a new access + refresh token."""
        return await self._token_request({"refreshToken": refresh_token})

    async def get_offer_status(
        self, access_token: str, account_number: str
    ) -> OfferStatusResult:
        """Look up the current Cafe Nero offer status for this account."""
        data = await self._post(
            API_ENDPOINT,
            query=_CHECK_OFFERS_QUERY,
            variables={"accountNumber": account_number},
            access_token=access_token,
        )
        return _parse_offer_status(data)

    async def claim_coffee(
        self, access_token: str, account_number: str
    ) -> ClaimResult:
        """Claim the free Cafe Nero offer for this account."""
        try:
            data = await self._post(
                API_ENDPOINT,
                query=_CLAIM_REWARD_MUTATION,
                variables={
                    "accountNumber": account_number,
                    "offerSlug": OFFER_SLUG,
                },
                access_token=access_token,
            )
        except OctopusNeroApiError as err:
            return _claim_result_from_api_error(err)

        payload = data.get("claimOctoplusReward") or {}
        reward_id = payload.get("rewardId")
        if reward_id:
            return ClaimResult(success=True, reward_id=reward_id)
        return ClaimResult(
            success=False,
            reason="unknown",
            error_message="Octopus API returned no reward ID",
        )

    async def _token_request(self, input_payload: dict[str, str]) -> AuthTokens:
        data = await self._post(
            API_ENDPOINT,
            query=_OBTAIN_TOKEN_QUERY,
            variables={"input": input_payload},
        )
        payload = data.get("obtainKrakenToken")
        if not payload or not payload.get("token"):
            raise OctopusNeroAuthError("Octopus Energy did not return a token")
        return AuthTokens(
            access_token=payload["token"],
            refresh_token=payload["refreshToken"],
            expires_at=_utc_now() + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES),
        )

    async def _post(
        self,
        url: str,
        *,
        query: str,
        variables: dict[str, Any],
        access_token: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if access_token:
            headers["Authorization"] = f"JWT {access_token}"
        body = {"query": query, "variables": variables}
        try:
            async with self._session.post(
                url,
                json=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except aiohttp.ClientError as err:
            raise OctopusNeroApiError(f"Network error: {err}") from err

        if errors := data.get("errors"):
            messages = [e.get("message", "Unknown error") for e in errors]
            joined = "; ".join(messages)
            if _looks_like_auth_error(messages):
                raise OctopusNeroAuthError(joined)
            raise OctopusNeroApiError(joined)
        return data.get("data") or {}


def _parse_offer_status(data: dict[str, Any]) -> OfferStatusResult:
    """Pick the Cafe Nero entry out of the offer-groups response."""
    groups = ((data.get("octoplusOfferGroups") or {}).get("edges")) or []
    for group in groups:
        offers = ((group.get("node") or {}).get("octoplusOffers")) or []
        for offer in offers:
            if offer.get("slug") != OFFER_SLUG:
                continue
            ability = offer.get("claimAbility") or {}
            if ability.get("canClaimOffer"):
                return OfferStatusResult(status=OfferStatus.AVAILABLE)
            reason = ability.get("cannotClaimReason")
            if reason == "MAX_CLAIMS_PER_PERIOD_REACHED":
                return OfferStatusResult(status=OfferStatus.CLAIMED, cannot_claim_reason=reason)
            if reason == "OUT_OF_STOCK":
                return OfferStatusResult(status=OfferStatus.OUT_OF_STOCK, cannot_claim_reason=reason)
            return OfferStatusResult(status=OfferStatus.UNKNOWN, cannot_claim_reason=reason)
    return OfferStatusResult(status=OfferStatus.UNKNOWN, cannot_claim_reason="offer_not_found")


def _claim_result_from_api_error(err: OctopusNeroApiError) -> ClaimResult:
    msg = str(err).upper()
    if "MAX_CLAIMS_PER_PERIOD_REACHED" in msg or "ALREADY" in msg:
        return ClaimResult(success=False, reason="already_claimed", error_message=str(err))
    if "OUT_OF_STOCK" in msg:
        return ClaimResult(success=False, reason="out_of_stock", error_message=str(err))
    return ClaimResult(success=False, reason="unknown", error_message=str(err))


def _looks_like_auth_error(messages: list[str]) -> bool:
    for m in messages:
        lower = m.lower()
        if "kt-ct-1124" in lower or "authentication" in lower:
            return True
        if "invalid" in lower and "token" in lower:
            return True
    return False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
