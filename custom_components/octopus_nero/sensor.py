"""Sensor platform for the Octopus Nero integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CoordinatorData, OctopusNeroCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OctopusNeroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OfferStatusSensor(coordinator, entry)])


class OfferStatusSensor(CoordinatorEntity[OctopusNeroCoordinator], SensorEntity):
    """Sensor that exposes the Cafe Nero offer status from the coordinator."""

    _attr_name = "Octopus Nero Offer Status"
    _attr_has_entity_name = False

    def __init__(
        self, coordinator: OctopusNeroCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_offer_status"

    @property
    def state(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.status.value

    @property
    def extra_state_attributes(self) -> dict:
        data: CoordinatorData | None = self.coordinator.data
        if data is None:
            return {}
        return {
            "last_checked": data.last_checked.isoformat() if data.last_checked else None,
            "last_claimed": data.last_claimed.isoformat() if data.last_claimed else None,
            "cannot_claim_reason": data.cannot_claim_reason,
        }
