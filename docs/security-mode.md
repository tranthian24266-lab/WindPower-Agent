# Security Mode

## Current Mode

The platform supports a minimal shared-key write-protection mode.

- Header name: `X-API-Key`
- Toggle: `WINDPOWER_AUTH_ENABLED`
- Secret source: `WINDPOWER_API_KEY`

## Behavior

- When disabled, all current write routes behave as before.
- When enabled, write routes require a matching `X-API-Key`.
- Read-only routes remain open.

## Intended Usage

- Trusted local development
- Trusted intranet operation
- Short-term protection before a fuller auth system exists

## Not Included

- User login
- User roles
- Token issuance
- Audit identity per person

Use a stronger auth system before exposing the platform to the public internet.
