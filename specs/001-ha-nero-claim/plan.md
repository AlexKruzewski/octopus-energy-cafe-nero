# Implementation Plan: Home Assistant Cafe Nero Auto-Claim

**Branch**: `001-ha-nero-claim` | **Date**: 2026-05-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-ha-nero-claim/spec.md`

## Summary

Build a Home Assistant custom integration (`octopus_nero`) that authenticates with the Octopus Energy Kraken GraphQL API using an API key, exposes an offer-status sensor, provides a `claim_coffee` service call, and runs an automatic polling loop that claims the free Cafe Nero within 5 minutes of stock becoming available.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: homeassistant (core), aiohttp (async HTTP), pytest-homeassistant-custom-component (tests)

**Storage**: HA Config Entry (API key + account number), in-memory token cache (auth tokens), HA State Machine (sensor state)

**Testing**: pytest + pytest-homeassistant-custom-component

**Target Platform**: Home Assistant (all installation types — OS, Container, Supervised, Core)

**Project Type**: Home Assistant custom integration (HACS-compatible)

**Performance Goals**: Claim completes within 30 seconds of trigger; offer status reflects changes within 5 minutes

**Constraints**: All I/O must be async; tokens refreshed proactively before expiry; no duplicate claims per eligibility period; `claimOctoplusReward` mutation deprecated (removal August 2026 — isolate for easy swap)

**Scale/Scope**: Single Octopus Energy account per integration instance

## Constitution Check

The project constitution (`memory/constitution.md`) has not been populated — the template placeholder is still in place. No architectural gates apply at this stage. The constitution should be completed before project conventions are formalised.

## Project Structure

### Documentation (this feature)

```text
specs/001-ha-nero-claim/
├── plan.md                       # This file
├── research.md                   # Phase 0: API + HA pattern decisions
├── data-model.md                 # Phase 1: entities and state machines
├── quickstart.md                 # Phase 1: setup and usage guide
├── contracts/
│   └── ha-service-schema.md      # Phase 1: service, sensor, config flow contracts
└── tasks.md                      # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
custom_components/
└── octopus_nero/
    ├── __init__.py          # Integration setup, coordinator wiring, service registration
    ├── manifest.json        # Integration metadata (domain, version, dependencies)
    ├── config_flow.py       # HA config flow UI (API key + account number entry)
    ├── const.py             # Constants: endpoints, offer slug, poll interval, token TTL
    ├── coordinator.py       # DataUpdateCoordinator: polling, token lifecycle, auto-claim
    ├── sensor.py            # OfferStatusSensor (CoordinatorEntity)
    ├── services.yaml        # Service schema for octopus_nero.claim_coffee
    └── strings.json         # UI strings and error messages

tests/
└── test_octopus_nero/
    ├── conftest.py
    ├── test_config_flow.py
    ├── test_coordinator.py
    ├── test_sensor.py
    └── test_services.py
```

**Structure Decision**: Single custom component under `custom_components/octopus_nero/`. Standard HA integration layout; no frontend/backend split needed. HA's config flow handles the setup UI; the coordinator centralises all API logic.

## Complexity Tracking

No constitution violations.

## Implementation Phases

### Phase 1 — Core Auth + Status Sensor
**Goal**: Integration installs, authenticates with Octopus Energy via API key, and exposes a working offer-status sensor.

**Success**: Sensor appears in HA showing correct offer state; credentials persist across HA restart.

**Key files**: `manifest.json`, `const.py`, `config_flow.py`, `coordinator.py` (auth + status poll only), `sensor.py`, `__init__.py`

**Tests**: `test_config_flow.py` (valid/invalid credentials), `test_sensor.py` (state mapping), `test_coordinator.py` (auth + token refresh)

---

### Phase 2 — Auto-Claim + Notifications
**Goal**: Coordinator auto-claims when offer becomes available; fires HA notification on success or failure.

**Success**: Running integration claims coffee within 5 minutes of stock release; persistent notification appears in HA.

**Key files**: `coordinator.py` (claim logic + auto-claim trigger), `services.yaml`, notification calls in `__init__.py`

**Tests**: `test_coordinator.py` (auto-claim trigger, duplicate guard), `test_services.py` (manual claim service call)

---

### Phase 3 — Manual Service Call + HACS Packaging
**Goal**: `octopus_nero.claim_coffee` service is callable from HA UI and automations; integration is HACS-ready.

**Success**: Service call from Developer Tools triggers a claim and returns correct notification; `hacs.json` present and valid.

**Key files**: `services.yaml`, `strings.json`, `hacs.json` (repo root)

**Tests**: `test_services.py` (force flag, already-claimed guard)
