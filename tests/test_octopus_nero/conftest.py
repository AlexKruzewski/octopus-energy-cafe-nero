"""Shared fixtures for the octopus_nero integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.octopus_nero.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom integrations in all tests."""
    yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry with valid-looking credentials."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Octopus Nero",
        data={
            "api_key": "sk_live_test_api_key_1234567890",
            "account_number": "A-AAAA1111",
        },
        unique_id="A-AAAA1111",
    )


@pytest.fixture
def mock_api_client() -> Generator[AsyncMock, None, None]:
    """Patch OctopusNeroClient with an AsyncMock."""
    with patch(
        "custom_components.octopus_nero.api.OctopusNeroClient",
        autospec=True,
    ) as mock_cls:
        instance = mock_cls.return_value
        instance.obtain_token = AsyncMock()
        instance.refresh_token = AsyncMock()
        instance.get_offer_status = AsyncMock()
        instance.claim_coffee = AsyncMock()
        yield instance
