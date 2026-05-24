"""The Octopus Nero integration — auto-claims your free weekly Cafe Nero."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    DEPRECATION_WARNING,
    DOMAIN,
    SERVICE_CLAIM_COFFEE,
    SERVICE_FIELD_FORCE,
)
from .coordinator import OctopusNeroCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

_CLAIM_COFFEE_SCHEMA = vol.Schema(
    {
        vol.Optional(SERVICE_FIELD_FORCE, default=False): cv.boolean,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Octopus Nero from a config entry."""
    _LOGGER.warning(DEPRECATION_WARNING)

    coordinator = OctopusNeroCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_CLAIM_COFFEE)
    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register octopus_nero.claim_coffee once across all config entries."""
    if hass.services.has_service(DOMAIN, SERVICE_CLAIM_COFFEE):
        return

    async def _handle_claim_coffee(call: ServiceCall) -> None:
        force = call.data.get(SERVICE_FIELD_FORCE, False)
        # Fan out to every configured coordinator. In the common single-account
        # case there is exactly one.
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_claim_coffee(force=force)

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLAIM_COFFEE,
        _handle_claim_coffee,
        schema=_CLAIM_COFFEE_SCHEMA,
    )
