# Quickstart: Home Assistant Cafe Nero Auto-Claim

**Date**: 2026-05-24

## Prerequisites

- Home Assistant running (any install type: OS, Container, Supervised, or Core)
- An Octopus Energy account with Octoplus membership active
- Your Octopus Energy API key (get it at `account.octopus.energy/personal-details/api-access`)
- Your account number (format `A-XXXXXXXX`, found in your Octopus dashboard)

## Installation

### Option A: Manual (development / local)

1. Copy the `custom_components/octopus_nero/` directory into your Home Assistant config directory:
   ```
   <ha-config>/custom_components/octopus_nero/
   ```
2. Restart Home Assistant.

### Option B: HACS (once published)

1. In Home Assistant, go to **HACS > Integrations > Custom repositories**.
2. Add this repository URL and select **Integration** as the category.
3. Find "Octopus Nero" in HACS and install it.
4. Restart Home Assistant.

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**.
2. Search for **Octopus Nero** and select it.
3. Enter your **API Key** and **Account Number** when prompted.
4. Submit — the integration validates your credentials automatically.

If validation fails, check:
- The API key is copied in full with no extra spaces.
- The account number matches the format `A-XXXXXXXX`.

## What You Get

After setup, the following are created automatically:

| Entity                                 | Type   | Description                              |
|----------------------------------------|--------|------------------------------------------|
| `sensor.octopus_nero_offer_status`     | Sensor | Current offer state (available/claimed/out_of_stock/unknown) |

And the following service is available:

| Service                      | Description                              |
|------------------------------|------------------------------------------|
| `octopus_nero.claim_coffee`  | Manually claim the free Cafe Nero offer  |

## Auto-Claim Behaviour

The integration polls the Octopus Energy API every 5 minutes. When the offer status becomes `available` and no claim has been made in the current week, it claims automatically. You will receive a Home Assistant persistent notification when the claim succeeds.

To check when new stock typically becomes available: batches are released overnight (midnight–2am). The integration will pick it up within 5 minutes of release.

## Manual Claim

To claim manually at any time:

1. Go to **Developer Tools > Services**.
2. Select service `octopus_nero.claim_coffee`.
3. Call the service.

Or trigger it from an automation using the service call action.

## Development Setup

```bash
# Clone the repository
git clone <repo-url>
cd octopus-energy-cafe-nero

# Install dev dependencies
pip install pytest pytest-homeassistant-custom-component

# Run tests
pytest tests/
```
