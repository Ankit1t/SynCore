# Authorization

## Purpose

Ensure an authenticated principal may only act within its own tenant and role.

## Model

- **Roles** (`domain.enums.Role`): `USER`, `ADMIN`.
- **Tenant scoping**: every user-owned entity (`ShoppingRequest`, `AgentRun`,
  `Order`, `PaymentIntent`, `UserPreference`) carries `user_id`. Repositories
  filter by it; cross-user reads/writes are rejected.
- **Admin gate**: `/api/v1/admin/*` requires `ADMIN` in production.

Diagram: [`mermaid/20_authorization.mmd`](mermaid/20_authorization.mmd),
multi-tenant view in [`mermaid/21_multi_tenant.mmd`](mermaid/21_multi_tenant.mmd).

## Tool-level authorization

Beyond HTTP authz, the agent's tools are individually authorized: each tool has
a schema, validation, and an audit event. The LLM cannot invoke a tool it isn't
explicitly granted, and it cannot reach shell/network/DB directly
(see [security_architecture](security_architecture.md)).

## Payment authorization

Spending is authorized by the deterministic `PaymentPolicy`, not by role alone:
even a valid user's over-limit or untrusted-vendor payment requires an explicit
human checkpoint.

## MVP state

The slice uses the demo user (role USER). Admin endpoints are exposed read-only
for observability in local mode; production must place them behind the ADMIN
role and an authz dependency.

## Testing

Authorization dependencies get unit tests (allow/deny by role and ownership);
integration tests assert cross-tenant requests return 403/404.
