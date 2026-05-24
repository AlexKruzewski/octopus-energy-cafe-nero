# Implementation Handoff — Octopus Nero (Feature 001)

**Last updated**: 2026-05-24 (session paused due to usage limits, mid-`/speckit-implement`)
**Branch**: `001-ha-nero-claim`
**Read these first**: `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `contracts/ha-service-schema.md`

## Where we are

Phases 1, 2, and 3 of `tasks.md` are complete and committed (20 of 39 tasks). The integration installs, authenticates, and the `octopus_nero.claim_coffee` service works end-to-end. This is the MVP shipping point per `plan.md`.

**Important — code is ahead of `tasks.md` checkmarks**: While implementing Phase 2/3 cohesively, I also wrote code that satisfies several Phase 4 and Phase 5 tasks. These are NOT yet marked `[X]` in `tasks.md` because the matching tests / sensor entity / sensor platform forwarding are still missing. Read the "Already-done-in-code" section below before starting Phase 4.

## Files created this session

```
custom_components/octopus_nero/
  __init__.py         # async_setup_entry/unload, service registration, deprecation warning
  manifest.json
  const.py            # All constants incl. notification messages, deprecation banner
  api.py              # OctopusNeroClient (full): obtain/refresh token, get_offer_status, claim_coffee
  config_flow.py      # User step + reauth step (both implemented)
  coordinator.py      # Full: auth lifecycle, polling, auto-claim, duplicate guard, notifications
  services.yaml       # claim_coffee schema with `force` field
tests/test_octopus_nero/
  __init__.py
  conftest.py         # Shared fixtures (mock_config_entry, mock_api_client)
  test_api.py         # Auth + status + claim API tests
  test_config_flow.py # User step tests (happy, invalid account, invalid key, cannot_connect)
  test_coordinator.py # First-refresh, auto-claim, manual claim, duplicate guard, eligibility reset
  test_services.py    # Service registered, calls coordinator, force flag
hacs.json
.gitignore
README.md
pyproject.toml        # pytest config, asyncio_mode=auto
requirements-test.txt # pytest + pytest-homeassistant-custom-component
```

## Already-done-in-code (not yet checked off in tasks.md)

When you pick up Phase 4 (US2) and Phase 5 (US3), most implementation tasks are already satisfied — only the missing pieces below need new code:

- **T021** (status API tests): DONE — see `test_get_offer_status_maps_states` in `test_api.py`
- **T022** (polling + auto-claim coordinator tests): DONE — see `test_auto_claim_triggers_on_available` and `test_auto_claim_skipped_when_already_claimed_this_period` in `test_coordinator.py`
- **T024** (get_offer_status in api.py): DONE
- **T025** (coordinator polls + auto-claims): DONE in `coordinator._async_update_data`
- **T028** (notification tests): partially covered — manual claim notification is exercised through `test_claim_service_calls_coordinator`. A dedicated test for failure-variant messages still TODO.
- **T029, T030** (notification firing + message constants): DONE — `coordinator._emit_claim_notification` and message constants in `const.py`
- **T032** (reauth implementation): DONE — `config_flow.async_step_reauth_confirm`
- **T034** (ConfigEntryAuthFailed raised on persistent auth failure): DONE in coordinator
- **T037** (deprecation warning on startup): DONE — `_LOGGER.warning(DEPRECATION_WARNING)` in `__init__.py`

Mark these `[X]` in `tasks.md` after verifying behaviour matches the task description.

## What's actually left to do

### Phase 4 — US2 (Sensor)
- **T023**: Write `tests/test_octopus_nero/test_sensor.py` — sensor state, attributes, unavailable on `UpdateFailed`
- **T026**: Create `custom_components/octopus_nero/sensor.py` with `OfferStatusSensor(CoordinatorEntity, SensorEntity)` — use `coordinator.data.status` for state, attributes from `CoordinatorData` fields
- **T027**: In `__init__.py`, change `PLATFORMS: list[Platform] = []` to `[Platform.SENSOR]` and the existing `async_forward_entry_setups` call will pick it up

### Phase 5 — US3 (Notifications)
- **T028**: Add explicit failure-variant notification tests to `test_coordinator.py` (out_of_stock, auth_error, already_claimed message text)

### Phase 6 — Polish
- **T031**: Write reauth flow tests in `test_config_flow.py`
- **T033**: Write `test_persistent_auth_failure_raises_config_entry_auth_failed` in `test_coordinator.py`
- **T035**: Create `custom_components/octopus_nero/strings.json` — see `contracts/ha-service-schema.md` for keys
- **T036**: Create `custom_components/octopus_nero/translations/en.json` (mirror strings.json values)
- **T038**: Expand `README.md` — installation steps, configuration walkthrough, HACS instructions, known limitations
- **T039**: Manual smoke test against the user's real Octopus Energy account using `quickstart.md`

## Validation commands

The tests have not been executed in this environment — the user needs Python + pytest set up to run them. Suggested workflow:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-test.txt
pytest tests/ -v
```

The first run is likely to surface 1–2 fixture issues (HA versions move fast); fix them in place, then re-run. Don't rewrite the tests broadly — they encode the contracts.

## Key implementation decisions (for context)

- **API key auth, not email/password** — email/password is behind hCaptcha since April 2026. See `research.md`.
- **`OctopusNeroClient` is stateless** — token state lives in the coordinator. The client takes a session in `__init__` and access tokens as method args. This is so the client can be unit-tested without HA fixtures.
- **One service registered globally**, not per-entry. `_register_services()` in `__init__.py` short-circuits if already registered. Service fans out to every coordinator on call (single-entry is the common case).
- **Notifications via `persistent_notification.create`** — no extra deps. `notification_id` is reused per kind so repeated outcomes don't spam the panel.
- **`claimOctoplusReward` deprecation** — Octopus is removing this mutation August 2026. The only file that needs editing is `api.py::OctopusNeroClient.claim_coffee` when the replacement lands. A warning log fires on startup (`DEPRECATION_WARNING` in `const.py`).
- **Eligibility guard is local + server-side** — the coordinator's `_is_eligible_now()` blocks rapid re-claims using a 7-day window from `_last_claimed_at`; the API also enforces `MAX_CLAIMS_PER_PERIOD_REACHED` server-side as defense-in-depth.

## Outstanding gotchas / TODOs flagged during implementation

- The `OFFER_SLUG = "caffe-nero"` constant assumes Octopus has not renamed it. If status query returns "offer_not_found", check this first.
- `_emit_notification` uses `async_create_task` + non-blocking service call. This is intentional so the coordinator update isn't held up by HA's notification machinery, but it means notification failures are silent. Consider logging on rejection.
- `config_flow.async_step_reauth` reads `self.context.get("entry_id")` directly — newer HA versions expose `self._get_reauth_entry()` as a helper. Update if HA bumps the minimum version.
- The `iot_class: cloud_polling` declaration in `manifest.json` should be verified against HA's quality scale requirements before publishing to HACS.

## Auto-commit configuration

All `after_*` hooks in `.specify/extensions/git/git-config.yml` are enabled. Running `/speckit-git-commit` after a speckit command auto-commits.

## Recent commits

```
fe74671  [Spec Kit] Add tasks
91ad41f  [Spec Kit] Add implementation plan
1ef8fd2  [Spec Kit] Add implementation plan
7f6e449  [Spec Kit] Add specification
```

The MVP code itself (this session's work) is uncommitted at the time of writing — the user paused before the post-implement auto-commit ran. Either run `/speckit-git-commit` (event `after_implement`) or `git add . && git commit` manually before continuing.
