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
  /** Honest availability state — never presented as purchasable unless true. */
  status: 'available' | 'coming-soon' | 'request-access' | 'conversation';
  statusLabel: string;
  capabilities: string[];
}

/** Product-tier architecture. No prices, no payment claims, no fake limits. */
export const PLANS: PlanInfo[] = [
  {
    id: 'starter',
    name: 'Starter',
    tagline: 'Entry-level individual FootyEdge access.',
    status: 'available',
    statusLabel: 'Available now',
    capabilities: [
      'Core match intelligence',
      'Team intelligence',
      'Competition intelligence',
      'Basic prediction analytics',
    ],
  },
  {
    id: 'growth',
    name: 'Growth',
    tagline: 'For more serious individual users and analysts.',
    status: 'coming-soon',
    statusLabel: 'Coming soon',
    capabilities: [
      'Everything in Starter',
      'Expanded analysis',
      'Deeper product functionality',
    ],
  },
  {
    id: 'business',
    name: 'Business',
    tagline: 'For teams and commercial users.',
    status: 'request-access',
    statusLabel: 'Request access',
    capabilities: [
      'Everything in Growth',
      'Business and team usage',
      'API-oriented access',
    ],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    tagline: 'For organizations requiring customized access.',
    status: 'conversation',
    statusLabel: 'Start a conversation',
    capabilities: [
      'Custom integrations',
      'Organizational access',
      'Commercial support',
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
