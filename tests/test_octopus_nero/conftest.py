"""Shared fixtures for the octopus_nero integration tests."""
from __future__ import annotations

import socket as _socket_module
import sys
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from unittest.mock import MagicMock
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.octopus_nero.const import DOMAIN

# ---------------------------------------------------------------------------
# Windows / pytest-socket compatibility
#
# pytest-homeassistant-custom-component calls disable_socket(allow_unix_socket=True)
# in its pytest_runtest_setup before every test. On Linux/macOS asyncio uses AF_UNIX
# for its event-loop self-pipe; allow_unix_socket=True is sufficient there. On
# Windows there is no AF_UNIX; asyncio falls back to socket.socketpair() which
# calls socket.socket(AF_INET, ...) — and that is the GuardedSocket that raises
# SocketBlockedError. Python's socket.socket.accept() also calls socket.socket()
# internally when creating the accepted socket, so capturing socket.socket before
# patching is not enough (accept() looks up the name at call time from the module).
#
# The fix: use _socket.socket — the C-extension class that pytest-socket never
# patches. Its accept() is implemented in C and returns _socket.socket objects
# directly, bypassing the Python-level GuardedSocket entirely.
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import _socket as _csocket  # C extension — not patched by pytest-socket

    # Capture the real socket.socket class at import time, before pytest-socket
    # replaces it with GuardedSocket. ProactorEventLoop needs objects that
    # support weak references (for its _registered WeakSet) — _socket.socket
    # objects don't, but socket.socket objects do.
    _RealSocket = _socket_module.socket

    def _socketpair_win(
        family: int = _socket_module.AF_INET,
        type: int = _socket_module.SOCK_STREAM,  # noqa: A002
        proto: int = 0,
    ) -> tuple[_socket_module.socket, _socket_module.socket]:
        """socketpair() bypassing GuardedSocket, returning weakref-compatible objects."""
        lsock = _csocket.socket(family, type, proto)
        try:
            lsock.bind(("127.0.0.1", 0))
            lsock.listen()
            addr = lsock.getsockname()
            csock = _csocket.socket(family, type, proto)
            try:
                csock.setblocking(False)
                try:
                    csock.connect(addr)
                except (BlockingIOError, InterruptedError):
                    pass
                csock.setblocking(True)
                fd, _ = lsock._accept()  # raw C accept — returns (fd, addr)
                ssock = _csocket.socket(family, type, proto, fileno=fd)
            except BaseException:
                csock.close()
                raise
        finally:
            lsock.close()
        # Transfer the raw FDs into real socket.socket wrappers so that
        # ProactorEventLoop's WeakSet can hold them.
        ssock_wrapped = _RealSocket(family, type, proto, fileno=ssock.detach())
        csock_wrapped = _RealSocket(family, type, proto, fileno=csock.detach())
        return ssock_wrapped, csock_wrapped

    _socket_module.socketpair = _socketpair_win  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom integrations in all tests."""
    yield


@pytest.fixture(autouse=True)
def _mock_aiohttp_session():
    """Prevent async_get_clientsession from creating a real aiohttp session.

    On Windows, aiodns requires SelectorEventLoop but the HA test harness uses
    ProactorEventLoop. Since all tests mock the API client, the real HTTP
    session is never used.
    """
    mock_session = MagicMock(spec=aiohttp.ClientSession)
    with (
        patch(
            "custom_components.octopus_nero.coordinator.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "custom_components.octopus_nero.config_flow.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def _register_persistent_notification(hass):
    """Register a stub persistent_notification service.

    The coordinator fires notifications via hass.services.async_call. Without
    this stub, teardown raises ServiceNotFound.
    """
    async def _noop_handler(call):
        pass

    hass.services.async_register(
        "persistent_notification", "create", _noop_handler
    )
    hass.services.async_register(
        "persistent_notification", "dismiss", _noop_handler
    )


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
