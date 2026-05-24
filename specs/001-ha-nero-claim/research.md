# Research: Home Assistant Cafe Nero Auto-Claim

**Phase**: 0 | **Date**: 2026-05-24 | **Status**: Complete

## Authentication

**Decision**: Use Octopus Energy API key (`apiKey`) in the `ObtainKrakenToken` mutation rather than email/password.

**Rationale**: Direct email/password login has been protected by hCaptcha since April 2026, making programmatic login unreliable. Octopus Energy provides personal API keys at `account.octopus.energy/personal-details/api-access`. The Kraken GraphQL API accepts an `APIKey` field in the token mutation input, bypassing hCaptcha entirely. This is the stable, supported path for programmatic access.

**Alternatives considered**:
- Email/password: Blocked by hCaptcha since April 2026 — rejected.
- Refresh token harvested from browser: Fragile, requires manual intervention on expiry — rejected.

---

## GraphQL API Endpoints

**Decision**: Use two separate endpoints — public for authentication, internal for rewards.

- Auth (token acquisition): `https://api.octopus.energy/v1/graphql/`
- Rewards (offer status + claim): `https://api.backend.octopus.energy/v1/graphql/`

**Rationale**: These endpoints serve different concerns and are documented as separate surfaces. The internal backend endpoint hosts the Octoplus reward operations.

---

## Token Lifecycle

**Decision**: Cache tokens in memory within the coordinator, refresh proactively every 50 minutes (tokens expire after 60 minutes), fall back to full re-authentication with the API key if refresh fails.

**Rationale**: Access tokens have a 60-minute lifetime; refresh tokens have a 7-day lifetime. Proactive refresh (before expiry) prevents mid-operation failures. If the refresh token itself expires, re-authenticating with the stored API key is seamless — no user intervention needed.

---

## Claim Mutation Deprecation Risk

**Decision**: Proceed with `claimOctoplusReward` mutation for now; log a warning on startup noting the August 2026 deprecation date.

**Rationale**: The mutation is currently functional (confirmed May 2026). Removal is scheduled for August 2026. The integration should be built with the claim logic isolated in a single function so the replacement can be dropped in with minimal changes. A logged warning on startup ensures visibility.

**Offer slug**: `"caffe-nero"`

**Risk**: If Octopus removes or replaces the mutation before the integration is updated, claiming will break. Mitigation: isolate claim logic, monitor Octopus developer communications.

---

## Polling Strategy

**Decision**: Use Home Assistant's `DataUpdateCoordinator` with a 5-minute polling interval. When the coordinator observes `canClaimOffer: true` and no claim has been made in the current eligibility period, it automatically triggers a claim.

**Rationale**: This approach uses HA's standard update pattern, provides a status sensor automatically, and handles the auto-claim behaviour without a separate scheduler. The 5-minute interval means the integration responds to midnight stock releases within 5 minutes — well within the 2-minute sensor-update requirement gap. (The spec requires status updates within 2 minutes; this can be tightened to a 90-second poll if needed.)

**Alternatives considered**:
- Dedicated midnight cron: More complex, duplicates HA's scheduling infrastructure — rejected.
- Webhook/push from Octopus: No push API available — not possible.

---

## Duplicate Claim Prevention

**Decision**: Track `last_claimed_at` timestamp in the coordinator. Before any claim attempt, check whether a claim has been made in the current eligibility period (weekly). If yes, skip and log.

**Rationale**: The Octopus API returns `MAX_CLAIMS_PER_PERIOD_REACHED` if you try to double-claim, but we should guard against this locally to avoid unnecessary API calls and to give the sensor a clear "claimed" state.

---

## Home Assistant Integration Pattern

**Decision**: Standard HA custom integration with `DataUpdateCoordinator`, `ConfigFlow`, and a `sensor` platform.

- `ConfigFlow`: collects API key + account number, validates them on submit.
- `DataUpdateCoordinator`: owns all API calls, token lifecycle, and auto-claim logic.
- `sensor` platform: registers `OfferStatusSensor` derived from `CoordinatorEntity`.
- Service `octopus_nero.claim_coffee`: registered in `__init__.py`, delegates to coordinator.
- Notifications: fired via `hass.services.async_call("notify", ...)` using HA's built-in notify integration.

**Rationale**: This is the canonical HA pattern for polling integrations. It centralises all network I/O, supports multiple entities from one coordinator, and integrates cleanly with HA's config flow UI.

---

## HACS Compatibility

**Decision**: Structure the component to be HACS-compatible from the start.

Requirements met by:
- `custom_components/octopus_nero/manifest.json` with correct fields
- `hacs.json` at repo root (if distributing via HACS)
- Version field in manifest

**Rationale**: HACS is the standard distribution mechanism for HA custom integrations. Building for it from the start costs nothing and enables easy installation.
