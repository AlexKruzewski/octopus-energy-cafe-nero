# Implementation Plan: Home Assistant Cafe Nero Auto-Claim

**Branch**: `001-ha-nero-claim` | **Date**: 2026-05-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-ha-nero-claim/spec.md`

## Summary

Build a Home Assistant custom integration (`octopus_nero`) that authenticates with the Octopus Energy Kraken GraphQL API using a personal API key, exposes the Cafe Nero offer status as a sensor, provides a `claim_coffee` service call, and runs an automatic polling loop that claims the free Cafe Nero within 5 minutes of stock becoming available — with no extra automation configuration required from the user.

The integration follows the canonical HA pattern: a single `DataUpdateCoordinator` owns all API I/O and token lifecycle, a `ConfigFlow` collects credentials with live validation, a `CoordinatorEntity` sensor exposes state, and a service call delegates to the coordinator for manual triggers. Notifications fire through HA's built-in `persistent_notification` service.

## Technical Context

**Language/Version**: Python 3.12 (HA Core 2026.x minimum)

**Primary Dependencies**:
- `homeassistant` (core, provides DataUpdateCoordinator, ConfigFlow, CoordinatorEntity)
- `aiohttp` (async HTTP — already bundled with HA)
- `pytest-homeassistant-custom-component` (test harness; dev only)

**Storage**:
- HA Config Entry (`api_key`, `account_number`) — persisted by HA's storage layer
- Coordinator runtime data (`auth_tokens`, `offer_status`, `last_claimed_at`) — in-memory only
- HA State Machine (sensor state + attributes)

**Testing**: `pytest` with `pytest-homeassistant-custom-component` fixtures; `aiohttp` mocked at the `ClientSession.post` level

**Target Platform**: Home Assistant 2026.x+ across all installation types (OS, Container, Supervised, Core)

**Project Type**: Home Assistant custom integration (HACS-distributable)

**Performance Goals**:
- Claim completes within 30 seconds of trigger (SC-001)
- Offer status sensor reflects API state within 5 minutes of change (satisfies SC-002 ≤ 2 minutes with tightening to 90s if needed)
- Token refresh adds < 500ms latency to a polling cycle

**Constraints**:
- All I/O must be async (HA blocks sync calls in the event loop)
- No persistent secret storage outside HA's config entry encryption
- `claimOctoplusReward` mutation deprecated — scheduled removal August 2026; isolate behind a single adapter function so the replacement can be swapped in with one edit
- API key auth only (email/password is behind hCaptcha since April 2026)
- Single Octopus Energy account per config entry (multi-account support could be added later via multiple entries)

**Scale/Scope**: Single household; one config entry per integration install; one sensor entity; one service.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution at `.specify/memory/constitution.md` has not been populated — it is still the bare template. No formal gates apply at this stage.

Applied informal gates from the user's global CLAUDE.md (Engineering Philosophy):
- **Incremental Progress**: Plan is split into 3 phases, each independently testable. ✅
- **Read Before Writing**: Researched HA patterns, existing Octopus integrations, and reference blog before designing. ✅
- **Test-First**: Each phase lists pytest files written before implementation. ✅
- **Pragmatism**: Avoiding over-engineering — single coordinator, no DI framework, in-memory tokens (not persisted). ✅
- **Simplicity**: Standard HA pattern, no novel abstractions. ✅

**Recommendation**: Populate the constitution before the project grows. For now, no violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-ha-nero-claim/
├── plan.md                       # This file (regenerated 2026-05-24)
├── research.md                   # Phase 0: API auth, polling, deprecation, HA patterns
├── data-model.md                 # Phase 1: Config Entry, Auth Token, Offer Status, Claim Result
├── quickstart.md                 # Phase 1: install, configure, and dev setup
├── contracts/
│   └── ha-service-schema.md      # Phase 1: service, sensor, config flow contracts
├── checklists/
│   └── requirements.md           # Spec quality checklist (from /speckit-specify)
└── tasks.md                      # Phase 2 output (created by /speckit-tasks)
```

### Source Code (repository root)

```text
custom_components/
└── octopus_nero/
    ├── __init__.py              # async_setup_entry, coordinator wiring, service registration
    ├── manifest.json            # domain, version, requirements, iot_class=cloud_polling, integration_type=service
    ├── config_flow.py           # ConfigFlow + reauth flow (ConfigEntryAuthFailed handling)
    ├── const.py                 # DOMAIN, endpoints, OFFER_SLUG, POLL_INTERVAL, TOKEN_REFRESH_AT
    ├── coordinator.py           # OctopusNeroCoordinator(DataUpdateCoordinator)
    ├── api.py                   # OctopusNeroClient — GraphQL calls, token lifecycle (testable in isolation)
    ├── sensor.py                # OfferStatusSensor(CoordinatorEntity, SensorEntity)
    ├── services.yaml            # Schema for octopus_nero.claim_coffee
    ├── strings.json             # UI labels, config flow steps, error messages
    └── translations/
        └── en.json              # English translations (copy of strings.json values)

tests/
└── test_octopus_nero/
    ├── __init__.py
    ├── conftest.py              # Shared fixtures: mock_aioclient, mock_config_entry
    ├── test_config_flow.py      # User flow, reauth flow, validation errors
    ├── test_api.py              # OctopusNeroClient unit tests (mocked aiohttp)
    ├── test_coordinator.py      # Polling, token refresh, auto-claim trigger, duplicate guard
    ├── test_sensor.py           # State mapping, attributes, unavailable on coordinator error
    └── test_services.py         # claim_coffee service, force flag, notification firing

hacs.json                         # HACS distribution metadata (repo root)
README.md                         # User-facing readme
```

**Structure Decision**: Standard HA custom-component layout under `custom_components/octopus_nero/`. The API client (`api.py`) is separated from the coordinator so it can be unit-tested without HA fixtures — this is a small abstraction that significantly improves testability and matches the philosophy of "Composition over inheritance" from the user's engineering rules. No frontend/backend split; HA owns the UI.

## Complexity Tracking

No constitution violations. One pragmatic choice worth noting:

| Choice | Why Needed | Simpler Alternative Rejected Because |
|--------|------------|--------------------------------------|
| Separate `api.py` from `coordinator.py` | Allows API client unit tests without HA test fixtures; isolates the deprecated `claimOctoplusReward` mutation for easy swap | Putting API calls directly in coordinator would mean every test needs the HA harness, and the August 2026 deprecation swap touches more files |

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| `claimOctoplusReward` removed before integration is updated | High (Aug 2026 deadline) | Critical — claim breaks | Isolate in `api.py`, log warning on startup, monitor Octopus developer comms |
| Octopus adds hCaptcha to `apiKey` auth | Low | Critical — auth breaks | Fall back path documented; user can paste a fresh API key via reauth flow |
| Offer slug changes from `"caffe-nero"` | Low | High — claim silently fails | Define slug as a constant; surface clear error if API returns unknown-offer code |
| HA blocks `cloud_polling` integrations from claiming actions | Very low | Critical | Existing integrations (e.g. `octopus_energy`) perform claim-like actions; precedent exists |
| User's Octoplus membership lapses | Medium (over years) | Medium — claim returns error | Surface clear notification; sensor goes to `unknown` |
| Rate limiting from Octopus | Low at 5-min polls | Low | Coordinator backoff on 429; log and skip cycle |

## Implementation Phases

### Phase 1 — Core Auth + Status Sensor

**Goal**: Integration installs via the HA UI, authenticates with Octopus Energy using a personal API key, and exposes a working `sensor.octopus_nero_offer_status` reflecting the current state.

**Exit criteria**:
- Config flow accepts API key + account number and validates them against the live API
- Sensor entity appears in HA showing `available`, `claimed`, `out_of_stock`, or `unknown`
- Credentials survive HA restart
- Token refresh runs automatically before expiry without user intervention
- All Phase 1 tests pass

**Key files**: `manifest.json`, `const.py`, `api.py` (auth + status query only), `coordinator.py` (poll only, no claim), `config_flow.py` (user step only, no reauth), `sensor.py`, `__init__.py` (no service yet), `strings.json`, `translations/en.json`

**Tests written first**:
- `test_api.py`: `test_obtain_token_with_api_key`, `test_refresh_token_proactive`, `test_refresh_token_falls_back_to_apikey`, `test_get_offer_status_maps_states`
- `test_config_flow.py`: `test_user_step_happy_path`, `test_user_step_invalid_apikey`, `test_user_step_cannot_connect`
- `test_coordinator.py`: `test_first_refresh_authenticates_and_polls`, `test_refresh_failure_marks_update_failed`
- `test_sensor.py`: `test_sensor_state_reflects_coordinator_data`, `test_sensor_unavailable_on_update_failed`

**Status**: pending

---

### Phase 2 — Auto-Claim + Notifications

**Goal**: Coordinator auto-claims when the offer becomes available and notifies the user.

**Exit criteria**:
- Coordinator detects `available` state, claims via API, updates `last_claimed_at`
- Persistent notification fires on success ("Free Cafe Nero claimed — open the Octopus app")
- Persistent notification fires on failure with the specific reason
- Duplicate claim guard prevents claiming twice in one eligibility period
- Claim logic is isolated in one function (`OctopusNeroClient.claim_coffee`) for the August 2026 swap
- All Phase 2 tests pass

**Key files**: `api.py` (add `claim_coffee` adapter), `coordinator.py` (add `_maybe_auto_claim` step in `_async_update_data`), `__init__.py` (no changes needed — notifications fire via `hass.services.async_call`)

**Tests written first**:
- `test_api.py`: `test_claim_coffee_returns_reward_id`, `test_claim_coffee_handles_max_claims_reached`, `test_claim_coffee_handles_out_of_stock`
- `test_coordinator.py`: `test_auto_claim_triggers_on_available`, `test_auto_claim_skipped_within_eligibility_period`, `test_auto_claim_emits_success_notification`, `test_auto_claim_emits_failure_notification`
- `test_coordinator.py`: `test_eligibility_period_resets_after_seven_days`

**Status**: pending

---

### Phase 3 — Manual Service Call + Reauth + HACS Packaging

**Goal**: User can manually trigger a claim via the HA UI or automations; auth failures trigger HA's reauth flow; the integration is HACS-installable.

**Exit criteria**:
- `octopus_nero.claim_coffee` service is registered with optional `force` field
- Calling the service from Developer Tools triggers a claim and fires the correct notification
- `force: true` bypasses the local eligibility guard but the API still enforces server-side
- Auth failures raise `ConfigEntryAuthFailed`; HA shows a reauth dialog where the user can paste a new API key
- `hacs.json` at repo root validates against HACS schema
- README.md documents installation, configuration, and known limitations (incl. Aug 2026 deprecation)
- All Phase 3 tests pass

**Key files**: `services.yaml`, `__init__.py` (register service), `config_flow.py` (add `async_step_reauth`), `coordinator.py` (raise `ConfigEntryAuthFailed` on persistent auth failure), `hacs.json`, `README.md`

**Tests written first**:
- `test_services.py`: `test_claim_service_calls_coordinator`, `test_claim_service_force_bypasses_local_guard`, `test_claim_service_emits_already_claimed_notification`
- `test_config_flow.py`: `test_reauth_flow_with_new_api_key`, `test_reauth_flow_with_invalid_key_shows_error`
- `test_coordinator.py`: `test_persistent_auth_failure_raises_config_entry_auth_failed`

**Status**: pending

---

## Dependencies Between Phases

```
Phase 1 (auth + sensor)
   └─> Phase 2 (auto-claim + notifications)
          └─> Phase 3 (service call + reauth + HACS)
```

Phase 2 depends on Phase 1's `OctopusNeroClient` and coordinator skeleton. Phase 3 depends on Phase 2's claim logic. Each phase is independently deployable — even after Phase 1 alone, the user gets a useful integration (status sensor only); Phase 2 makes it valuable; Phase 3 polishes it.

## Open Questions for `/speckit-tasks`

None blocking. Worth tracking but not gating tasks:
- Should we expose an `OptionsFlow` to let the user tune the poll interval? (Defer to a later iteration unless requested.)
- Should we add a Diagnostics handler for support troubleshooting? (Nice-to-have; not required for v1.)
- Should `force: true` on the service call also reset `last_claimed_at` locally? (Probably not — let the API drive truth.)
