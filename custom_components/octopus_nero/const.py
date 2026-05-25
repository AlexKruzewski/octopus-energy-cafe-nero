"""Constants for the Octopus Nero integration."""
from __future__ import annotations

DOMAIN = "octopus_nero"

# GraphQL endpoint (single endpoint for auth + all queries)
API_ENDPOINT = "https://api.octopus.energy/v1/graphql/"

# Octoplus offer
OFFER_SLUG = "caffe-nero"

# Polling + token lifecycle
POLL_INTERVAL_MINUTES = 5
ACCESS_TOKEN_TTL_MINUTES = 60
TOKEN_REFRESH_LEAD_MINUTES = 10
ELIGIBILITY_PERIOD_DAYS = 7

# Config entry keys
CONF_API_KEY = "api_key"
CONF_ACCOUNT_NUMBER = "account_number"

# Service names + fields
SERVICE_CLAIM_COFFEE = "claim_coffee"
SERVICE_FIELD_FORCE = "force"

# Notification messages
NOTIFICATION_TITLE = "Octopus Nero"
NOTIFICATION_ID_PREFIX = "octopus_nero_"

MSG_SUCCESS = (
    "Your free Cafe Nero has been claimed! Open the Octopus Energy app "
    "to find your QR code."
)
MSG_ALREADY_CLAIMED = "Cafe Nero offer already claimed this week."
MSG_OUT_OF_STOCK = (
    "Cafe Nero offer is currently out of stock. Will retry automatically."
)
MSG_AUTH_FAILED = (
    "Octopus Energy authentication failed. Please re-check your API key in "
    "Settings > Devices & Services."
)
MSG_UNKNOWN_ERROR = "Unexpected error claiming Cafe Nero — see Home Assistant logs."

# Deprecation banner
DEPRECATION_WARNING = (
    "Octopus Energy's claimOctoplusReward mutation is scheduled for removal "
    "in August 2026. octopus_nero will need updating when a replacement lands."
)
