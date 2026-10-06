# FootyEdge entitlements — server-authoritative access (8F)

Source of truth: `entitlements.py`. Frontend checks are UX only.

## Role vs plan (independent dimensions)

- **Role** (`profiles.role`): `owner` | `admin` | `user` — administrative
  authority. Read from the `profiles` table. Missing, unknown, or
  unreadable role fails closed to `user`. A role NEVER grants a plan.
- **Plan** (`subscriptions` row): `starter` | `growth` | `business` |
  `enterprise` — commercial tier. No row means Starter. Unknown plan
  fails closed to Starter. A plan NEVER grants a role.

## Plan -> capability matrix

| Capability | Starter | Growth | Business | Enterprise |
|---|---|---|---|---|
| `dashboard` | Included | Included | Included | Included |
| `match_intelligence` | Included | Included | Included | Included |
| `predictions` | Included | Included | Included | Included |
| `teams` | Included | Included | Included | Included |
| `players` | Included | Included | Included | Included |
| `value_bets` | — | Included | Included | Included |
| `acca_builder` | — | Included | Included | Included |
| `portfolio` | — | Included | Included | Included |
| `ai_strategy_analysis` | — | Included | Included | Included |
| `api_access` | — | — | Planned | Planned |
| `data_export` | — | — | Planned | Planned |
| `multiple_seats` | — | — | Planned | Planned |
| `organization_controls` | — | — | Planned | Planned |

"Planned" means designed but not enforced yet: `ALL_CAPABILITIES`
lists every known capability while `IMPLEMENTED_CAPABILITIES` lists
only what the backend actually gates today. Business/Enterprise
resolve to Growth for implemented caps.

## Subscription status semantics

Only `active` and `trialing` confer paid-plan capabilities.
`past_due` is conservative (no paid entitlements; grace is a webhook
concern, see `docs/billing-paystack.md`). `paused` / `expired` confer
nothing. `canceled` keeps the declared plan **only while**
`current_period_end` is in the future; once the paid period ends (or
when no period is stored) it falls back to Starter. Unknown statuses
fail closed to Starter.

## Backend enforcement (`api.py`)

Paid product routes carry `Depends(require_capability(...))`:

- predictions (`/api/daily-picks`, `/api/predict`, `/api/recent-predictions`)
  require `predictions`
- `/api/teams*` require `teams`; `/api/players*` require `players`
- `/api/value-bets` requires `value_bets`
- `/api/acca-builder` requires `acca_builder`
- `/api/bets/*` require `portfolio`
- `/api/analyze-strategy` requires `ai_strategy_analysis`
- `/api/dashboard/stats` requires `dashboard`
- `/api/matches` requires `match_intelligence`
- `/api/admin/metrics` requires role `owner`/`admin` via
  `require_role(...)` — roles and capabilities are separate checks

Denials are `403` with `FEATURE_NOT_ENTITLED` (capability) or
`ROLE_REQUIRED` (role). Missing/invalid auth is `401`. Identity comes
from the Supabase JWT via the Auth API; browser-supplied user identity
is never trusted.

## Frontend (`src/lib/access.ts`, `ProductPage.tsx`)

Display only. Plan prices/statuses shown on the product page are the
proposed commercial structure; online billing is not enabled and the
page states this. No frontend value gates features or implies checkout
exists.

## Tests

`tests/test_entitlements.py` (offline, stub Supabase): plan matrix,
all-status sweep, canceled period-end boundary, unknown plan/status
fail-closed, role independence and fail-closed defaults, end-to-end
`resolve_entitlements`, result helpers, and factory validation.
