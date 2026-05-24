# Octopus Nero

A Home Assistant custom integration that automatically claims your free weekly Cafe Nero from Octopus Energy's Octoplus rewards.

## What it does

- Polls the Octopus Energy Octoplus rewards API every 5 minutes.
- Exposes the Cafe Nero offer status as a Home Assistant sensor (`available` / `claimed` / `out_of_stock` / `unknown`).
- Automatically claims the free coffee when stock becomes available.
- Provides an `octopus_nero.claim_coffee` service for manual triggering from Developer Tools or automations.
- Fires a Home Assistant persistent notification when a claim succeeds or fails.

## Requirements

- Home Assistant 2026.1.0 or later
- An active Octopus Energy account with [Octoplus](https://octopus.energy/octoplus/) enabled
- A personal API key from [Octopus Energy account settings](https://octopus.energy/dashboard/new/accounts/personal-details/api-access)
- Your account number (`A-XXXXXXXX` format)

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant sidebar.
2. Go to **Integrations** and click the three-dot menu in the top right.
3. Select **Custom repositories**.
4. Enter this repository URL and select **Integration** as the category.
5. Click **Add**, then find **Octopus Nero** in the HACS integrations list and install it.
6. Restart Home Assistant.

### Manual

1. Download or clone this repository.
2. Copy the `custom_components/octopus_nero/` directory into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**.
2. Search for **Octopus Nero**.
3. Enter your **Octopus Energy API Key** (find it at `octopus.energy/dashboard/new/accounts/personal-details/api-access`).
4. Enter your **Account Number** in the format `A-XXXXXXXX`.
5. Click **Submit**. The integration authenticates against the Octopus Energy API and begins polling immediately.

### Re-authentication

If your API key is revoked or expires, Home Assistant will prompt you to re-authenticate. Go to **Settings > Devices & Services**, find the Octopus Nero entry, and follow the re-auth flow to enter a new API key.

## Sensor

After setup, a `sensor.octopus_nero_offer_status` entity appears in Home Assistant.

| State | Description |
|---|---|
| `available` | A free coffee is ready to claim |
| `claimed` | Already claimed this eligibility period |
| `out_of_stock` | Offer allocation exhausted; no codes available |
| `unknown` | Status could not be determined (network/auth error) |

**Attributes**:
- `last_checked` — ISO 8601 UTC timestamp of the most recent status poll
- `last_claimed` — ISO 8601 UTC timestamp of the last successful claim (or `null`)
- `cannot_claim_reason` — API reason when not claimable (or `null`)

## Service: `octopus_nero.claim_coffee`

Manually triggers a claim attempt. Safe to call at any time.

| Field | Type | Default | Description |
|---|---|---|---|
| `force` | boolean | `false` | Bypass the local 7-day eligibility guard. The API still enforces server-side limits. |

**Example automation** — claim every Monday at 08:00:

```yaml
automation:
  - alias: "Claim Cafe Nero on Monday"
    trigger:
      - platform: time
        at: "08:00:00"
    condition:
      - condition: time
        weekday: [mon]
    action:
      - service: octopus_nero.claim_coffee
```

## Notifications

A persistent notification appears in the Home Assistant notification panel after each claim attempt:

- **Success**: "Your free Cafe Nero has been claimed! Open the Octopus Energy app to find your QR code."
- **Already claimed**: "Cafe Nero offer already claimed this week."
- **Out of stock**: "Cafe Nero offer is currently out of stock. Will retry automatically."
- **Auth error**: "Octopus Energy authentication failed. Please re-check your API key in Settings > Devices & Services."

## Known Limitations

- The underlying `claimOctoplusReward` GraphQL mutation is deprecated by Octopus Energy and scheduled for removal in **August 2026**. When Octopus publishes a replacement API, this integration will need updating. A warning is logged on each HA restart as a reminder.
- Only the Cafe Nero offer is supported (slug `caffe-nero`). Other Octoplus offers (e.g. Greggs) are not currently exposed.
- If `sensor.octopus_nero_offer_status` shows `unknown` and `cannot_claim_reason` is `offer_not_found`, the offer slug may have been renamed by Octopus. Check the `OFFER_SLUG` constant in `const.py`.

## Development

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
# or: source .venv/bin/activate  # Linux/macOS
pip install -r requirements-test.txt
pytest tests/ -v
```

See [specs/001-ha-nero-claim/quickstart.md](specs/001-ha-nero-claim/quickstart.md) for end-to-end testing against a real Octopus Energy account.

## License

MIT
