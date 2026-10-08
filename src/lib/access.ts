/**
 * FootyEdge access model: ROLE vs SUBSCRIPTION PLAN.
 *
 * ROLE answers "what may this account administer?"
 *   'owner' — platform-level control (owner console).
 *   'admin' — operational administration (admin tools).
 *   'user'  — product consumer.
 *
 * PLAN answers "which commercial tier does this account use?"
 *   'starter' | 'growth' | 'business' | 'enterprise'
 *
 * The two concepts are INDEPENDENT. A role is never derived from a plan
 * and a plan is never derived from a role:
 *   owner + no plan, admin + no plan,
 *   user + starter/growth/business/enterprise.
 *
 * AUTHORIZATION STATUS (read carefully before production rollout):
 *
 * 1. Roles are server-authoritative: the backend resolves
 *    authenticated user -> auth.users.id -> profiles.role on every
 *    request (see entitlements.require_role). The frontend MUST NOT
 *    decide authority from email addresses. A previous email-allowlist
 *    mechanism has been removed; there is no allowlist anywhere in this
 *    file. Frontend role state below is display/navigation only and is
 *    populated from GET /api/auth/role (the caller's own server-resolved
 *    role), never from local email matching.
 *
 * 2. There is NO subscription backend yet, so resolvePlan() returns the
 *    development default ('starter') explicitly flagged as a placeholder.
 *    It is displayed only with a server-gated qualifier and MUST NOT be
 *    treated as authorization (see canAdministrate()).
 *
 * 3. Frontend role checks are UX controls ONLY. Real enforcement must
 *    happen server-side / in RLS (documented limitation, not security).
 */

export type Role = 'owner' | 'admin' | 'user';
export type Plan = 'starter' | 'growth' | 'business' | 'enterprise';

export interface PlanInfo {
  id: Plan;
  name: string;
  tagline: string;
  /**
   * Proposed commercial price (8A model, presented in 8B).
   * Display-only: billing is NOT implemented, and this value must never
   * gate features or imply checkout exists.
   */
  price: string;
  /** Honest availability state — never presented as purchasable unless true. */
  status: 'available' | 'coming-soon' | 'request-access' | 'conversation';
  statusLabel: string;
  capabilities: string[];
}

/** Product-tier architecture. Prices are proposed only; no billing exists. */
export const PLANS: PlanInfo[] = [
  {
    id: 'starter',
    name: 'Starter',
    tagline: 'Explore FootyEdge AI\u2019s football intelligence and core analysis workflows.',
    price: 'Free',
    status: 'available',
    statusLabel: 'Available now',
    capabilities: [
      'Match intelligence',
      'Team analysis',
      'Player analysis',
      'Core prediction analytics',
      'Value-bet access at controlled usage',
      'Portfolio workflows',
      'Acca Builder',
      'Public prediction ledger',
    ],
  },
  {
    id: 'growth',
    name: 'Growth',
    tagline: 'For serious individual football analysts who need deeper analysis and higher personal usage.',
    price: '\u20A65,000 / month',
    status: 'coming-soon',
    statusLabel: 'Coming soon',
    capabilities: [
      'Everything in Starter',
      'Advanced analytics',
      'Higher usage limits',
      'Expanded portfolio capacity',
      'Extended AI analysis capacity',
      'Deeper historical analysis',
    ],
  },
  {
    id: 'business',
    name: 'Business',
    tagline: 'For analysts, football media, research teams and commercial football workflows.',
    price: '\u20A615,000 / month',
    status: 'request-access',
    statusLabel: 'Request access',
    capabilities: [
      'Everything in Growth',
      'Higher organizational usage',
      'Commercial usage',
      'Multiple seats \u2014 planned',
      'Organization controls \u2014 planned',
      'API access \u2014 planned',
      'Data export \u2014 planned',
    ],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: 'For organizations requiring custom limits, integrations, API/data arrangements and organizational requirements.',
    price: 'Custom',
    status: 'conversation',
    statusLabel: 'Talk to FootyEdge',
    capabilities: [
      'Custom usage requirements',
      'Custom integrations',
      'API/data arrangements',
      'Organization requirements',
      'Negotiated commercial terms',
    ],
  },
];

export interface AccessContext {
  role: Role;
  /** Always false: no bootstrap/allowlist mechanism exists anymore. */
  roleIsBootstrap: boolean;
  plan: Plan;
  /** True while no subscription backend exists. */
  planIsPlaceholder: boolean;
  /** Where the role came from: server profile lookup or local fallback. */
  roleSource: 'server' | 'local-fallback';
}

export function resolveAccess(arg: {
  email?: string | null;
  /**
   * Server-authoritative role for this session (from GET /api/auth/role,
   * i.e. verified JWT -> auth.users.id -> profiles.role). The email is
   * accepted for potential display use only and NEVER authorizes.
   */
  persistentRole?: Role | null;
}): AccessContext {
  const fromServer =
    arg.persistentRole === 'owner' ||
    arg.persistentRole === 'admin' ||
    arg.persistentRole === 'user';
  return {
    role: fromServer && arg.persistentRole ? arg.persistentRole : 'user',
    roleIsBootstrap: false,
    plan: 'starter',
    planIsPlaceholder: true,
    roleSource: fromServer ? 'server' : 'local-fallback',
  };
}

/** Owner console visibility. UX gate only — not authorization. */
export function canViewOwnerConsole(ctx: AccessContext): boolean {
  return ctx.role === 'owner';
}

/**
 * Owner/admin billing-console visibility (8.3 §18).
 * Mirrors the API contract where owner == admin on all
 * /api/admin/billing/* reads. UX gate only — every endpoint enforces
 * owner/admin independently via the caller's JWT. Prefer this over
 * canViewOwnerConsole for billing surfaces.
 */
export function canViewOwnerBilling(ctx: AccessContext): boolean {
  return canViewAdminTools(ctx);
}

/** Admin tools visibility (owner includes admin tools via console composition). */
export function canViewAdminTools(ctx: AccessContext): boolean {
  return ctx.role === 'owner' || ctx.role === 'admin';
}

/**
 * The ONLY predicate that may gate administrative affordances.
 * Deliberately ignores `plan`: a subscription tier NEVER authorizes.
 */
export function canAdministrate(ctx: AccessContext): boolean {
  return canViewAdminTools(ctx);
}

/** Display helper: placeholder tiers are display-only and must never
 *  imply a confirmed subscription record. The backend remains authoritative:
 *  every protected feature is gated server-side per request. */
export function planDisplayName(ctx: AccessContext): string {
  const name = ctx.plan.charAt(0).toUpperCase() + ctx.plan.slice(1);
  return name;
}
