---

description: "Task list for Home Assistant Cafe Nero Auto-Claim integration"
---

# Tasks: Home Assistant Cafe Nero Auto-Claim

**Input**: Design documents from `specs/001-ha-nero-claim/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ha-service-schema.md, quickstart.md

**Tests**: Test tasks are included — the project's global engineering philosophy (`~/.claude/CLAUDE.md`) mandates a test-first approach, and the plan explicitly lists tests-written-first per phase.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and shipped independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Different file, no dependency on an incomplete task → can run in parallel
- **[Story]**: User story tag (US1, US2, US3) — Setup, Foundational, and Polish phases have no tag

## Path Conventions

- Source: `custom_components/octopus_nero/`
- Tests: `tests/test_octopus_nero/`
- Distribution metadata + docs at repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the directory layout and distribution metadata.

- [ ] T001 Create directories `custom_components/octopus_nero/` and `tests/test_octopus_nero/`
- [ ] T002 [P] Create `custom_components/octopus_nero/manifest.json` with domain `octopus_nero`, name, version `0.1.0`, `iot_class: cloud_polling`, `integration_type: service`, `config_flow: true`, codeowners, documentation URL
- [ ] T003 [P] Create `hacs.json` at repo root with name, content_in_root false, and minimum HA version
- [ ] T004 [P] Create `tests/test_octopus_nero/__init__.py` and `tests/test_octopus_nero/conftest.py` with shared fixtures (`mock_config_entry`, `mock_aioclient`, `enable_custom_integrations`)
- [ ] T005 [P] Create skeleton `README.md` at repo root with project description, link to spec, and "work in progress" notice

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Constants, auth/token client, config flow, and the coordinator skeleton — everything every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T006 Create `custom_components/octopus_nero/const.py` with `DOMAIN`, `AUTH_ENDPOINT`, `BACKEND_ENDPOINT`, `OFFER_SLUG = "caffe-nero"`, `POLL_INTERVAL_MINUTES = 5`, `TOKEN_REFRESH_LEAD_MINUTES = 10`, `ELIGIBILITY_PERIOD_DAYS = 7`
- [ ] T007 [P] Write token-lifecycle tests in `tests/test_octopus_nero/test_api.py`: `test_obtain_token_with_api_key`, `test_refresh_token_proactive_at_lead_time`, `test_refresh_token_falls_back_to_apikey_on_failure`
- [ ] T008 Implement `OctopusNeroClient` with `obtain_token(api_key)` and `refresh_token(refresh_token)` in `custom_components/octopus_nero/api.py` (depends on T006, T007 tests must fail first)
- [ ] T009 [P] Write config-flow tests in `tests/test_octopus_nero/test_config_flow.py`: `test_user_step_happy_path`, `test_user_step_invalid_apikey`, `test_user_step_cannot_connect`
- [ ] T010 Implement `OctopusNeroConfigFlow.async_step_user` in `custom_components/octopus_nero/config_flow.py` — collect `api_key` and `account_number`, validate against live API (depends on T008, T009)
- [ ] T011 [P] Write coordinator-skeleton tests in `tests/test_octopus_nero/test_coordinator.py`: `test_first_refresh_authenticates`, `test_refresh_failure_marks_update_failed`
- [ ] T012 Implement `OctopusNeroCoordinator(DataUpdateCoordinator)` skeleton with `_async_setup` (initial auth) and `_async_update_data` stub in `custom_components/octopus_nero/coordinator.py` (depends on T008, T011)
- [ ] T013 Implement `async_setup_entry` in `custom_components/octopus_nero/__init__.py` — create coordinator, call `async_config_entry_first_refresh`, store on `hass.data[DOMAIN][entry_id]` (depends on T010, T012)

**Checkpoint**: Foundation ready — integration can be installed and authenticates; no entities or services yet.

---

## Phase 3: User Story 1 - Claim Free Coffee (Priority: P1) 🎯 MVP

**Goal**: User can claim their free Cafe Nero through Home Assistant via the `octopus_nero.claim_coffee` service.

**Independent Test**: Install integration → Developer Tools > Services > call `octopus_nero.claim_coffee` → verify a QR code appears in the Octopus Energy app within 30 seconds.

### Tests for User Story 1

- [ ] T014 [P] [US1] Write claim API tests in `tests/test_octopus_nero/test_api.py`: `test_claim_coffee_returns_reward_id`, `test_claim_coffee_handles_max_claims_reached`, `test_claim_coffee_handles_out_of_stock`
- [ ] T015 [P] [US1] Write coordinator claim tests in `tests/test_octopus_nero/test_coordinator.py`: `test_coordinator_claim_returns_success`, `test_duplicate_claim_guard_blocks_within_period`, `test_eligibility_period_resets_after_seven_days`
- [ ] T016 [P] [US1] Write service tests in `tests/test_octopus_nero/test_services.py`: `test_claim_service_calls_coordinator`, `test_claim_service_force_bypasses_local_guard`, `test_claim_service_handles_already_claimed`

### Implementation for User Story 1

- [ ] T017 [US1] Implement `OctopusNeroClient.claim_coffee(account_number)` in `custom_components/octopus_nero/api.py` — isolate `claimOctoplusReward` mutation here for the August 2026 swap (depends on T014)
- [ ] T018 [US1] Add `async_claim_coffee(force: bool = False)` method and `_last_claimed_at` guard to coordinator in `custom_components/octopus_nero/coordinator.py` (depends on T015, T017)
- [ ] T019 [P] [US1] Create `custom_components/octopus_nero/services.yaml` with `claim_coffee` schema including optional `force` boolean field
- [ ] T020 [US1] Register `octopus_nero.claim_coffee` service handler in `custom_components/octopus_nero/__init__.py` — delegates to coordinator's `async_claim_coffee` (depends on T016, T018, T019)

**Checkpoint**: User Story 1 fully functional — manual claim via service call works end-to-end.

---

## Phase 4: User Story 2 - Monitor Offer Availability (Priority: P2)

**Goal**: A `sensor.octopus_nero_offer_status` entity reflects the current offer state, and the coordinator auto-claims when the state becomes `available` (FR-009).

**Independent Test**: Install integration → check Developer Tools > States for `sensor.octopus_nero_offer_status` → verify state matches the Octopus Energy app within 5 minutes. Confirm auto-claim fires when state transitions to `available`.

### Tests for User Story 2

- [ ] T021 [P] [US2] Write status-query API tests in `tests/test_octopus_nero/test_api.py`: `test_get_offer_status_maps_available`, `test_get_offer_status_maps_claimed`, `test_get_offer_status_maps_out_of_stock`
- [ ] T022 [P] [US2] Write polling + auto-claim tests in `tests/test_octopus_nero/test_coordinator.py`: `test_coordinator_polls_status_at_interval`, `test_auto_claim_triggers_on_available`, `test_auto_claim_skipped_when_already_claimed_this_period`
- [ ] T023 [P] [US2] Write sensor tests in `tests/test_octopus_nero/test_sensor.py`: `test_sensor_state_reflects_coordinator_data`, `test_sensor_attributes_include_last_checked_and_last_claimed`, `test_sensor_unavailable_on_update_failed`

### Implementation for User Story 2

- [ ] T024 [US2] Implement `OctopusNeroClient.get_offer_status(account_number)` in `custom_components/octopus_nero/api.py` — parse `octoplusOfferGroups` response into the `OfferStatus` enum (depends on T021)
- [ ] T025 [US2] Implement coordinator `_async_update_data` to call `get_offer_status` every 5 minutes and invoke `async_claim_coffee` automatically when state is `available` and within-period guard allows it (depends on T018, T022, T024)
- [ ] T026 [US2] Create `OfferStatusSensor(CoordinatorEntity, SensorEntity)` in `custom_components/octopus_nero/sensor.py` with `state`, `extra_state_attributes`, and `unique_id` derived from entry ID (depends on T023, T025)
- [ ] T027 [US2] Forward sensor platform in `async_setup_entry` (`await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])`) in `custom_components/octopus_nero/__init__.py` (depends on T026)

**Checkpoint**: User Story 2 fully functional — sensor reflects state, auto-claim fires on availability transitions.

---

## Phase 5: User Story 3 - Receive Claim Notifications (Priority: P3)

**Goal**: HA persistent notifications fire on every claim attempt — success or failure — with a clear message.

**Independent Test**: Trigger a claim (manual or auto) → confirm a notification appears in HA's notification panel within 30 seconds with the correct message variant.

### Tests for User Story 3

- [ ] T028 [P] [US3] Write notification tests in `tests/test_octopus_nero/test_coordinator.py`: `test_success_notification_fires_on_claim`, `test_failure_notification_fires_on_out_of_stock`, `test_failure_notification_fires_on_auth_error`, `test_already_claimed_notification_message`

### Implementation for User Story 3

- [ ] T029 [US3] Add `_emit_claim_notification(result: ClaimResult)` helper to coordinator and call it from both the auto-claim and manual-claim paths in `custom_components/octopus_nero/coordinator.py` (depends on T020, T025, T028)
- [ ] T030 [US3] Define notification message constants in `custom_components/octopus_nero/const.py` covering: success, already-claimed, out-of-stock, auth-failed, unknown-error

**Checkpoint**: All three user stories complete and independently testable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Reauth flow, translations, deprecation warning, packaging, and final validation.

- [ ] T031 [P] Write reauth tests in `tests/test_octopus_nero/test_config_flow.py`: `test_reauth_flow_with_new_api_key`, `test_reauth_flow_with_invalid_key_shows_error`
- [ ] T032 Implement `async_step_reauth` in `custom_components/octopus_nero/config_flow.py` (depends on T031)
- [ ] T033 [P] Write reauth-trigger test in `tests/test_octopus_nero/test_coordinator.py`: `test_persistent_auth_failure_raises_config_entry_auth_failed`
- [ ] T034 Raise `ConfigEntryAuthFailed` in coordinator when both `refresh_token` and `obtain_token(api_key)` fail in `custom_components/octopus_nero/coordinator.py` (depends on T033)
- [ ] T035 [P] Create `custom_components/octopus_nero/strings.json` with config flow labels, error keys, and notification messages
- [ ] T036 [P] Create `custom_components/octopus_nero/translations/en.json` mirroring `strings.json` values
- [ ] T037 [P] Add startup warning log in `custom_components/octopus_nero/__init__.py` noting `claimOctoplusReward` deprecation (scheduled August 2026)
- [ ] T038 [P] Expand `README.md` with installation steps, configuration walkthrough, known limitations, and HACS instructions
- [ ] T039 Run manual smoke test against the live Octopus Energy account following `specs/001-ha-nero-claim/quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No deps — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. Blocks ALL user stories.
- **US1 (Phase 3)**: Depends on Foundational. Independent of US2 and US3.
- **US2 (Phase 4)**: Depends on Foundational; reuses US1's `async_claim_coffee` for auto-claim (so US2 ideally runs after US1).
- **US3 (Phase 5)**: Depends on US1 and US2 (notifications wrap both manual and auto-claim paths).
- **Polish (Phase 6)**: Depends on US1–US3 complete.

### User Story Dependencies

- **US1 (P1)**: Independent. MVP candidate — can ship with only manual claim service.
- **US2 (P2)**: Depends on US1's claim function being available for auto-claim (FR-009).
- **US3 (P3)**: Depends on US1 and US2 to have something to notify about.

### Within Each User Story

- Tests written first (T0xx test tasks) — must fail before implementation
- API client methods before coordinator methods
- Coordinator methods before service handlers
- Service handlers before sensor platform forwarding

### Parallel Opportunities

- **Phase 1**: T002, T003, T004, T005 — all different files, all parallel.
- **Phase 2**: Test files (T007, T009, T011) parallel with each other; implementations sequential since they share `api.py` evolution.
- **Phase 3 (US1)**: T014, T015, T016, T019 all parallel (different files); T017–T020 implementations sequential per their dependencies.
- **Phase 4 (US2)**: T021, T022, T023 parallel; implementations sequential.
- **Phase 5 (US3)**: T028 sole test; T029 and T030 sequential (same file / same const).
- **Phase 6**: T031, T033, T035, T036, T037, T038 all parallel (different files); T032 depends on T031; T034 depends on T033.

---

## Parallel Example: User Story 1 Test Authoring

```bash
# Launch all US1 tests in parallel (each touches a different file):
Task: "Write tests in tests/test_octopus_nero/test_api.py for claim_coffee (T014)"
Task: "Write tests in tests/test_octopus_nero/test_coordinator.py for claim + guard (T015)"
Task: "Write tests in tests/test_octopus_nero/test_services.py for claim_coffee service (T016)"
Task: "Create custom_components/octopus_nero/services.yaml (T019)"
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Complete Phase 1 (Setup) — 5 tasks
2. Complete Phase 2 (Foundational) — 8 tasks
3. Complete Phase 3 (US1) — 7 tasks
4. **STOP and validate**: install integration, call `octopus_nero.claim_coffee`, confirm claim works
5. Ship as v0.1.0 — users can wire their own automations using the service call

### Incremental Delivery

1. Foundational complete → install + authenticate
2. + US1 → manual claim works (MVP, v0.1.0)
3. + US2 → status sensor + auto-claim (v0.2.0)
4. + US3 → notifications (v0.3.0)
5. + Polish → reauth, translations, HACS-ready (v1.0.0)

### Suggested MVP Scope

User Story 1 alone. After Phase 3, the user can install the integration, configure it, and call the claim service from Developer Tools or any HA automation. The sensor, auto-claim, and notifications are valuable but not required for the integration to deliver its core value.

---

## Task Counts

- **Setup**: 5 tasks (T001–T005)
- **Foundational**: 8 tasks (T006–T013)
- **US1 (P1, MVP)**: 7 tasks (T014–T020)
- **US2 (P2)**: 7 tasks (T021–T027)
- **US3 (P3)**: 3 tasks (T028–T030)
- **Polish**: 9 tasks (T031–T039)
- **Total**: 39 tasks

## Notes

- Tests in `test_api.py` cover the deprecated `claimOctoplusReward` mutation in T014; when the replacement lands (target August 2026), swap the implementation in T017 and update T014 — no other tests should need to change.
- The `force: true` field on `claim_coffee` only bypasses the local eligibility guard; the API still enforces server-side limits.
- Notifications use HA's `persistent_notification` service — no extra dependency. Users wanting push notifications can build an automation on top.
