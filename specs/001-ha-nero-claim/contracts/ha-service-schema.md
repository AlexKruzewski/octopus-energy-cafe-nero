# Home Assistant Service Contracts

**Integration domain**: `octopus_nero`

---

## Service: `octopus_nero.claim_coffee`

Manually triggers a claim of the free Cafe Nero offer for the configured Octopus Energy account. Safe to call even if a claim has already been made — the integration will respond with the current state rather than erroring.

### Fields

| Field   | Type    | Required | Default | Description                                                                 |
|---------|---------|----------|---------|-----------------------------------------------------------------------------|
| force   | boolean | No       | false   | If true, bypass the local eligibility period guard and attempt the API call regardless. The API will still reject duplicate claims server-side. |

### Response (fired as a persistent notification)

On success:
```
Your free Cafe Nero has been claimed! Open the Octopus Energy app to find your QR code.
```

On failure (already claimed):
```
Cafe Nero offer already claimed this week.
```

On failure (out of stock):
```
Cafe Nero offer is currently out of stock. Will retry automatically.
```

On failure (auth error):
```
Octopus Energy authentication failed. Please re-check your API key in Settings > Integrations.
```

---

## Sensor: `sensor.octopus_nero_offer_status`

Exposes the current claimability state of the Cafe Nero offer as a Home Assistant sensor.

### States

| State       | Description                                              |
|-------------|----------------------------------------------------------|
| available   | A free coffee is ready to claim                          |
| claimed     | Already claimed this eligibility period                  |
| out_of_stock | Offer allocation exhausted; no codes available          |
| unknown     | Status could not be determined (network/auth error)      |

### Attributes

| Attribute      | Type            | Description                                     |
|----------------|-----------------|-------------------------------------------------|
| last_checked   | ISO 8601 string | UTC timestamp of most recent status poll        |
| last_claimed   | ISO 8601 string \| null | UTC timestamp of last successful claim  |
| cannot_claim_reason | string \| null | API reason when not claimable              |

---

## Config Flow Schema

Presented to the user during initial integration setup in the HA UI.

| Field          | Label                   | Type     | Validation                              |
|----------------|-------------------------|----------|-----------------------------------------|
| api_key        | Octopus Energy API Key  | password | Non-empty; validated against auth API   |
| account_number | Account Number          | string   | Matches pattern A-XXXXXXXX              |

Error messages shown in UI:

| Error key             | Message shown to user                                       |
|-----------------------|-------------------------------------------------------------|
| invalid_api_key       | Could not authenticate with that API key. Please check it. |
| invalid_account       | Account number not found for this API key.                  |
| cannot_connect        | Could not reach Octopus Energy. Check your connection.      |
| unknown               | An unexpected error occurred. Please try again.             |
