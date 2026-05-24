"""Unit tests for OctopusNeroClient — auth, status, and claim flows."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.octopus_nero.api import (
    OctopusNeroApiError,
    OctopusNeroAuthError,
    OctopusNeroClient,
    OfferStatus,
)


@pytest.fixture
def mock_session():
    """Bare aiohttp session mock — call `_set_response` to load a body."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def client(mock_session) -> OctopusNeroClient:
    return OctopusNeroClient(session=mock_session)


def _set_response(mock_session, payload):
    """Wire `session.post()` to return the given JSON payload."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock(return_value=payload)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=response)
    cm.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=cm)


# --- T007: token lifecycle -------------------------------------------------


async def test_obtain_token_with_api_key(client, mock_session):
    _set_response(
        mock_session,
        {
            "data": {
                "obtainKrakenToken": {
                    "token": "access_jwt",
                    "refreshToken": "refresh_jwt",
                    "refreshExpiresIn": 604800,
                }
            }
        },
    )

    tokens = await client.obtain_token("sk_test_apikey")

    assert tokens.access_token == "access_jwt"
    assert tokens.refresh_token == "refresh_jwt"
    assert tokens.expires_at > datetime.now(timezone.utc)


async def test_obtain_token_with_invalid_api_key_raises_auth_error(
    client, mock_session
):
    _set_response(
        mock_session,
        {"errors": [{"message": "Invalid token (KT-CT-1124)"}]},
    )

    with pytest.raises(OctopusNeroAuthError):
        await client.obtain_token("bad_key")


async def test_refresh_token_returns_new_tokens(client, mock_session):
    _set_response(
        mock_session,
        {
            "data": {
                "obtainKrakenToken": {
                    "token": "new_access",
                    "refreshToken": "new_refresh",
                    "refreshExpiresIn": 604800,
                }
            }
        },
    )

    tokens = await client.refresh_token("old_refresh")

    assert tokens.access_token == "new_access"
    assert tokens.refresh_token == "new_refresh"


async def test_refresh_token_falls_back_to_api_key_path(client, mock_session):
    """A rejected refresh token raises OctopusNeroAuthError so callers can re-auth."""
    _set_response(
        mock_session,
        {"errors": [{"message": "Invalid refresh token"}]},
    )

    with pytest.raises(OctopusNeroAuthError):
        await client.refresh_token("expired_refresh")


# --- T021: status query mapping --------------------------------------------


@pytest.mark.parametrize(
    ("can_claim", "reason", "expected"),
    [
        (True, None, OfferStatus.AVAILABLE),
        (False, "MAX_CLAIMS_PER_PERIOD_REACHED", OfferStatus.CLAIMED),
        (False, "OUT_OF_STOCK", OfferStatus.OUT_OF_STOCK),
        (False, "SOMETHING_ELSE", OfferStatus.UNKNOWN),
    ],
)
async def test_get_offer_status_maps_states(
    client, mock_session, can_claim, reason, expected
):
    _set_response(
        mock_session,
        {
            "data": {
                "octoplusOfferGroups": {
                    "edges": [
                        {
                            "node": {
                                "octoplusOffers": [
                                    {
                                        "slug": "caffe-nero",
                                        "claimAbility": {
                                            "canClaimOffer": can_claim,
                                            "cannotClaimReason": reason,
                                        },
                                    }
                                ]
                            }
                        }
                    ]
                }
            }
        },
    )

    result = await client.get_offer_status("access_jwt", "A-AAAA1111")
    assert result.status is expected


# --- T014: claim coffee ----------------------------------------------------


async def test_claim_coffee_returns_reward_id(client, mock_session):
    _set_response(
        mock_session,
        {"data": {"claimOctoplusReward": {"rewardId": "rew_abc123"}}},
    )

    result = await client.claim_coffee("access_jwt", "A-AAAA1111")

    assert result.success is True
    assert result.reward_id == "rew_abc123"


async def test_claim_coffee_handles_max_claims_reached(client, mock_session):
    _set_response(
        mock_session,
        {"errors": [{"message": "MAX_CLAIMS_PER_PERIOD_REACHED"}]},
    )

    result = await client.claim_coffee("access_jwt", "A-AAAA1111")

    assert result.success is False
    assert result.reason == "already_claimed"


async def test_claim_coffee_handles_out_of_stock(client, mock_session):
    _set_response(
        mock_session,
        {"errors": [{"message": "OUT_OF_STOCK"}]},
    )

    result = await client.claim_coffee("access_jwt", "A-AAAA1111")

    assert result.success is False
    assert result.reason == "out_of_stock"
