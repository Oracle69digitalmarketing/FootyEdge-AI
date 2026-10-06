# FootyEdge owner/admin billing operations (8G)

Operational view over authoritative billing state. Source of truth for
logic: `admin_billing.py` (pure, tested). HTTP boundary: `admin_api.py`
(thin router). Console: `src/components/OwnerConsole.tsx` + `src/lib/ownerBilling.ts`.

## Hierarchy (never reversed)

Paystack → verified webhook → `subscription_events` → `subscriptions`
→ entitlements → Owner Console. The console manufactures no
subscription state and contradicts nothing upstream.

## Owner/admin authorization

- Roles `owner` / `admin` / `user` are administrative authority from
  `profiles.role`; plans are commercial tiers and NEVER authorize.
- Every `/api/admin/billing/*` endpoint independently enforces
  `require_role("owner", "admin")` (8F dependency): JWT →
  authenticated user → server-side role lookup → owner/admin? YES →
  execute, NO → `403 ROLE_REQUIRED`; missing/invalid auth → `401`.
- Role is never accepted from request bodies, query strings, React
  state, URL parameters, or plan selection (`admin_request()` accepts
  body/query and ignores them by construction; tested).
- Owner gets full console access; admin gets administrative read
  access. There are no write operations, so no finer RBAC is invented.
  The console UI gates billing surfaces on the owner||admin predicate
  (`canViewOwnerBilling`, 8.3 §18), matching the API; any lingering
  owner-only labels are UX text, never authorization.
- Frontend console visibility (`canViewOwnerConsole` /
  `canViewOwnerBilling`) is UX only; the backend rejects unauthorized
  callers even on direct API calls.

## Durable-auth assessment (§5): no migration created

- Baseline granted broad `profiles` privileges, but with RLS enabled
  and NO INSERT/DELETE policies, ordinary users cannot insert or
  delete profile rows (denied by default).
- The one concrete gap (row-scoped UPDATE policy with no column
  restriction, allowing self-promotion via `role`/`is_premium`) was
  already closed by 8C, which narrowed the `authenticated` UPDATE grant
  to `(full_name, avatar_url)`.
- `handle_new_user` forces `role='user'` at signup.
- Admin reads use the service-role server client; no RLS change is
  needed for 8G. Hence no new migration (additive-only rule respected).
- `is_premium` is legacy and is never used as an authorization mechanism.

## Operational views (all read-only)

| Endpoint | Returns |
|---|---|
| `GET /api/admin/billing/overview` | `total_users`, `users_with_subscriptions`, `starter_users`, `plan_counts`, `status_counts`, `subscriptions_total` — all from actual records |
| `GET /api/admin/billing/users` | Per-user: id, email, role, effective plan, subscription status, period start/end, provider, created date |
| `GET /api/admin/billing/subscriptions` | Whitelisted subscription columns (ids, plan, status, provider codes, periods, timestamps) |
| `GET /api/admin/billing/events` | Event metadata: provider, event type, processing status, event id, linked subscription, timestamps, error code — NO raw payload |
| `GET /api/admin/billing/usage` | `{"metering_enabled": false, "message": "Usage metering is not yet enabled."}` |

Never exposed: payment secrets, provider authorization codes, raw
webhook payloads, service-role credentials, JWTs, passwords.

## Status semantics & periods

Factual labels only: Active, Trialing, Past Due, Paused, Canceled,
Expired. Canceled rows distinguish "period still active" from "period
ended" using the stored `current_period_end`; no dates are inferred
and no renewal dates calculated. Missing subscription → Starter
display (plan `starter`, status none), mirroring 8F.

## Plan configuration (single sources, not duplicated here)

- Display: `PLANS` in `src/lib/access.ts` (Starter Free, Growth
  ₦5,000/month, Business ₦15,000/month, Enterprise Custom).
- Server pricing: `PAID_PLANS` in `billing.py` (500_000 / 1_500_000 kobo).
- No second pricing source is introduced by 8G.

## Prohibited manual billing operations

No "Activate Business" button, no renewal extensions, no payment
confirmations, no cancellation controls, no balance adjustments exist
in code (verified by test: the admin modules expose zero mutation
surface). The only writer of subscription state remains the verified
8E webhook path. If a manual-override requirement ever appears, it
must be specified separately — not invented here.

## Metrics: IMPLEMENTED vs NOT AVAILABLE

- IMPLEMENTED: user/subscription counts, plan distribution (effective),
  status distribution — all from real rows.
- NOT AVAILABLE: revenue, MRR/ARR, conversion, retention, churn,
  customer LTV, API usage metering. The console shows honest empty
  states ("Not yet available" / "Usage metering is not yet enabled"),
  never estimates. Potential MRR is not computed and nothing is called
  revenue.

## Audit logging

No `activity_log` writes are added: the baseline table grants broad
direct access to anon/authenticated, so client-writable admin audit
entries would be forgeable; a trustworthy audit writer needs its own
service-role boundary and belongs to a later objective. The durable
audit trail for 8G is `subscription_events` itself (append-only,
service-role only, read-only in the console).

## Production prerequisites

- 8C + 8E migrations applied in a non-prod context first; no
  `supabase db push` was run here.
- `SUPABASE_URL` + service-role key configured server-side (admin
  reads and JWT verification depend on them).
- Paystack test mode; webhook URL + secret configured per
  `docs/billing-paystack.md`.
- No production writes, no live provider calls, no commits from 8G.
