# Authentication

## Purpose

Establish who the caller is before any user-scoped action.

## MVP state

The vertical slice runs with a seeded **demo user** (`demo@syncore.local`) so the
end-to-end flow is demonstrable without an auth UI. All persistence is already
`user_id`-scoped, so enabling real auth is additive, not structural.

Diagram: [`mermaid/19_authentication.mmd`](mermaid/19_authentication.mmd).

## Production design

- **Token-based sessions** (JWT or opaque session id) issued after login;
  short-lived access + rotating refresh.
- **Secure cookies**: `HttpOnly`, `Secure`, `SameSite=Lax/Strict`; CSRF token
  for cookie-based state-changing requests.
- **Password storage**: Argon2/bcrypt; never plaintext. Prefer OIDC/social where
  possible to avoid handling passwords.
- **MFA** supported at the identity provider; Syncore never bypasses it.
- FastAPI dependency (`get_current_user`) resolves the principal and injects it;
  routes use it instead of the demo user.

## What Syncore never does

Store or transmit auth secrets to the LLM; bypass MFA/OTP/CAPTCHA; reuse one
user's session for another. Legitimate verification pauses for the human.

## Testing

Auth middleware gets unit tests for token validation, expiry, and tenant
binding; integration tests assert 401/403 on missing/insufficient credentials.
