# Data Model: Home Assistant Cafe Nero Auto-Claim

**Phase**: 1 | **Date**: 2026-05-24

## Entities

### Config Entry

Persisted by Home Assistant in its config store. Set once during initial setup via Config Flow.

| Field          | Type   | Description                                           |
|----------------|--------|-------------------------------------------------------|
| api_key        | string | Octopus Energy personal API key                       |
| account_number | string | Octopus Energy account number (e.g. A-ABC12345)       |

Validation rules:
- `api_key`: non-empty string, validated against the auth endpoint during Config Flow
- `account_number`: non-empty string matching pattern `[A-Z]-[A-Z0-9]+`

---

### Auth Token (in-memory, coordinator-managed)

Not persisted. Rebuilt from `api_key` on HA restart or after refresh failure.

| Field         | Type     | Description                                     |
|---------------|----------|-------------------------------------------------|
| access_token  | string   | JWT bearer token, 60-minute lifetime            |
| refresh_token | string   | Rotation token, 7-day lifetime                  |
| expires_at    | datetime | Absolute UTC expiry time of the access token    |

State transitions:
- `unauthenticated` → `authenticated` (on successful `ObtainKrakenToken`)
- `authenticated` → `refreshing` (proactively at T-10 minutes before `expires_at`)
- `refreshing` → `authenticated` (on successful token refresh)
- `refreshing` → `unauthenticated` (on refresh failure — triggers full re-auth with `api_key`)

---

### Offer Status

Produced by each coordinator poll cycle. Drives sensor state.

| Field          | Type                                               | Description                                     |
|----------------|----------------------------------------------------|-------------------------------------------------|
| state          | enum: available / claimed / out_of_stock / unknown | Current claimability of the Cafe Nero offer     |
| last_checked   | datetime                                           | UTC timestamp of most recent poll               |
| last_claimed   | datetime \| None                                   | UTC timestamp of last successful claim, or None |
| cannot_claim_reason | string \| None                              | Populated when state is not "available"         |

State transitions:
- `unknown` → `available` (API returns `canClaimOffer: true`)
- `unknown` → `claimed` (API returns `MAX_CLAIMS_PER_PERIOD_REACHED`)
- `unknown` → `out_of_stock` (API returns `OUT_OF_STOCK`)
- Any state → `unknown` (on API error or network failure)
- `available` → `claimed` (after successful `claimOctoplusReward` call)

---

### Claim Result

Produced by each claim attempt. Used to fire notifications and update sensor state.

| Field      | Type            | Description                                         |
|------------|-----------------|-----------------------------------------------------|
| success    | bool            | Whether the claim was accepted by the API           |
| reward_id  | string \| None  | Reward identifier returned on success               |
| error      | string \| None  | Human-readable failure reason, populated on failure |
| claimed_at | datetime \| None | UTC timestamp of the claim attempt                 |

---

## Eligibility Period

The Cafe Nero offer resets weekly. An eligibility period is considered active from when `last_claimed` was set until 7 days later. If `last_claimed` is `None` or more than 7 days old, a new claim is eligible.

This is enforced locally as a guard; the API also enforces it server-side via `MAX_CLAIMS_PER_PERIOD_REACHED`.

---

## Reauth State

When the coordinator detects a persistent authentication failure, it transitions into a reauth state that HA handles through its standard reauth dialog.

| State                   | Trigger                                                    | Resolution                            |
|-------------------------|------------------------------------------------------------|---------------------------------------|
| `authenticated`         | Token + refresh token valid                                | Normal operation                       |
| `needs_reauth`          | Refresh fails AND re-auth with stored API key fails        | Coordinator raises `ConfigEntryAuthFailed`; HA UI prompts user for a new key |
| `authenticated` (after) | User submits a valid new API key via the reauth dialog     | Coordinator resumes polling           |

State transitions:
- `authenticated` → `needs_reauth` (API rejects both refresh and api_key paths)
- `needs_reauth` → `authenticated` (user completes reauth flow with valid key)

The sensor reports `unavailable` while in `needs_reauth`. A persistent notification informs the user that reauth is required.
