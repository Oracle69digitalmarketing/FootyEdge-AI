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
 * 1. The ONLY persistent role store available today is the
 *    `profiles.role` column (default 'user'). It is NOT yet read here
 *    because the current production RLS ("Users can update own profile",
 *    FOR UPDATE with no column restriction) would let any user promote
 *    themselves — so `profiles.role` must NOT be trusted until the RLS
 *    hardening migration lands (see final report, Objective 7C Step 10).
 *
 * 2. Until then, owner recognition uses OWNER_BOOTSTRAP_EMAILS below —
 *    the same single address the app previously hardcoded
 *    ('admin@footyedge.ai'), now isolated in ONE place with this warning.
 *    This is a BOOTSTRAP mechanism, not durable authorization, and must be
 *    replaced by persistent `profiles.role` checks before rollout.
 *
 * 3. There is NO subscription backend yet, so resolvePlan() returns the
 *    development default ('starter') explicitly flagged as a placeholder.
 *    It is displayed only with a "default" label and MUST NOT be treated
 *    as authorization (see canAdministrate()).
 *
 * 4. Frontend role checks are UX controls ONLY. Real enforcement must
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

/**
 * Bootstrap owner mapping. TEMPORARY — see header.
 * Same address the app previously compared inline; centralized here so the
 * future `profiles.role` migration has exactly one call site to replace.
 */
export const OWNER_BOOTSTRAP_EMAILS: readonly string[] = ['admin@footyedge.ai'];

export interface AccessContext {
  role: Role;
  /** True when the role came from the temporary bootstrap mapping. */
  roleIsBootstrap: boolean;
  plan: Plan;
  /** True while no subscription backend exists. */
  planIsPlaceholder: boolean;
}

export function resolveAccess(arg: {
  email?: string | null;
  /** Persistent role — accepted ONLY from a trusted source (see header). */
  persistentRole?: Role | null;
}): AccessContext {
  const email = (arg.email ?? '').trim().toLowerCase();

  if (arg.persistentRole === 'owner' || arg.persistentRole === 'admin') {
    return { role: arg.persistentRole, roleIsBootstrap: false, plan: 'starter', planIsPlaceholder: true };
  }
  if (email && (OWNER_BOOTSTRAP_EMAILS as readonly string[]).includes(email)) {
    return { role: 'owner', roleIsBootstrap: true, plan: 'starter', planIsPlaceholder: true };
  }
  return { role: 'user', roleIsBootstrap: false, plan: 'starter', planIsPlaceholder: true };
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

/** Display helper: never imply a real subscription while placeholder is set. */
export function planDisplayName(ctx: AccessContext): string {
  const name = ctx.plan.charAt(0).toUpperCase() + ctx.plan.slice(1);
  return ctx.planIsPlaceholder ? `${name} (default)` : name;
}
