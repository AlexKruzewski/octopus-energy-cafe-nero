# Feature Specification: Home Assistant Cafe Nero Auto-Claim

**Feature Branch**: `001-ha-nero-claim`

**Created**: 2026-05-24

**Status**: Draft

**Input**: User description: "Create a custom Home Assistant integration that calls the Octopus Energy API to claim my daily free Cafe Nero"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Claim Free Coffee (Priority: P1)

As an Octopus Energy customer with Octoplus benefits, I want to claim my free Cafe Nero through Home Assistant so that I never miss a free coffee.

**Why this priority**: Core value of the feature — without the ability to claim, nothing else works.

**Independent Test**: Can be fully tested by triggering the claim action in Home Assistant and verifying a successful claim appears in the Octopus Energy app within 30 seconds.

**Acceptance Scenarios**:

1. **Given** a free Cafe Nero is available to claim, **When** I trigger the claim action in Home Assistant, **Then** the claim is registered and a QR code becomes available in the Octopus Energy app.
2. **Given** the offer has already been claimed this period, **When** I trigger the claim action, **Then** Home Assistant reports the offer has already been claimed and no duplicate claim is attempted.
3. **Given** the Cafe Nero offer is out of stock, **When** I trigger the claim action, **Then** Home Assistant reports the offer is out of stock and no claim is attempted.

---

### User Story 2 - Monitor Offer Availability (Priority: P2)

As a Home Assistant user, I want a sensor that shows the current Cafe Nero offer status so that I can see at a glance whether a free coffee is waiting to be claimed.

**Why this priority**: Provides visibility into offer state and enables users to build their own automations on top of the integration.

**Independent Test**: Can be fully tested by viewing the sensor state in Home Assistant and confirming it matches the current offer status in the Octopus Energy app.

**Acceptance Scenarios**:

1. **Given** the Cafe Nero offer is available, **When** the integration polls for status, **Then** the Home Assistant sensor shows "available".
2. **Given** the offer has been claimed this period, **When** the integration polls for status, **Then** the sensor shows "claimed".
3. **Given** the offer is out of stock, **When** the integration polls for status, **Then** the sensor shows "out_of_stock".

---

### User Story 3 - Receive Claim Notifications (Priority: P3)

As a Home Assistant user, I want to receive a notification when my free Cafe Nero is successfully claimed so that I know to open the Octopus app and use the QR code before it expires.

**Why this priority**: Keeps the user informed, especially when the claim is triggered automatically rather than by the user directly.

**Independent Test**: Can be fully tested by configuring a Home Assistant notification target, triggering a claim, and confirming a notification is received within 30 seconds.

**Acceptance Scenarios**:

1. **Given** a successful claim, **When** the claim completes, **Then** a notification is sent via the configured Home Assistant notification service within 30 seconds.
2. **Given** a failed claim attempt, **When** the claim fails, **Then** a notification is sent indicating the reason (e.g., out of stock, already claimed, authentication failure).

---

### Edge Cases

- What happens when the Octopus Energy session expires mid-claim?
- How does the system handle a network timeout during a claim request?
- What happens if the Cafe Nero offer is discontinued or the offer identifier changes?
- How does the system behave if the user's Octoplus membership lapses?
- What happens if the integration is triggered multiple times in rapid succession?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Integration MUST authenticate with Octopus Energy using credentials stored during initial setup, without requiring repeated manual login.
- **FR-002**: Integration MUST check whether the Cafe Nero offer is currently available, distinguishing between "available", "already claimed this period", and "out of stock" states.
- **FR-003**: Integration MUST expose a service call in Home Assistant that triggers a claim of the free Cafe Nero offer.
- **FR-004**: Integration MUST expose a sensor in Home Assistant reflecting the current offer availability status.
- **FR-005**: Integration MUST refresh authentication credentials automatically before they expire.
- **FR-006**: Integration MUST prevent duplicate claims within the same eligibility period.
- **FR-007**: Integration MUST surface authentication and claim errors clearly within Home Assistant.
- **FR-008**: Integration MUST be configurable with the user's Octopus Energy account credentials and account number via the Home Assistant UI.
- **FR-009**: Integration MUST include a built-in scheduler that automatically polls for offer availability and claims the free Cafe Nero when stock becomes available, without requiring the user to configure a separate automation.

### Key Entities

- **Offer Status**: The current availability state of the Cafe Nero reward — available, claimed, or out of stock.
- **Reward Claim**: A single successful claim event, capturing the timestamp and outcome.
- **Account Credentials**: The Octopus Energy account details used to authenticate and identify the claimable account.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A free coffee can be claimed through Home Assistant in under 30 seconds from the moment the action is triggered.
- **SC-002**: The offer status sensor updates within 2 minutes of a change in availability.
- **SC-003**: The integration correctly identifies and prevents duplicate claims 100% of the time within a single eligibility period.
- **SC-004**: Authentication continues without user intervention for at least 7 days after initial setup.
- **SC-005**: The integration can be fully configured via the Home Assistant UI in under 5 minutes.

## Assumptions

- User has an active Octopus Energy account with Octoplus membership enabled.
- User has Home Assistant installed and is comfortable adding custom integrations.
- The Cafe Nero offer resets on a weekly basis (once per week per account).
- The integration is for a single Octopus Energy account.
- Home Assistant's native notification system is used for claim alerts.
- Initial credentials are entered once through the Home Assistant UI; all subsequent authentication is handled automatically.
