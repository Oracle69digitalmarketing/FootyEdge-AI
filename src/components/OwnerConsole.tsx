import { useState } from 'react';
import {
  Activity,
  BarChart3,
  Bell,
  Database,
  HeartPulse,
  Layers,
  ScrollText,
  Settings as SettingsIcon,
  ShieldCheck,
  Users,
} from 'lucide-react';
import AdminMetrics from '../pages/AdminMetrics';
import { PLANS } from '../lib/access';
import {
  formatStatus,
  shortId,
  useOwnerBilling,
  type BillingEvent,
  type BillingOverview,
  type BillingSubscription,
  type BillingUser,
} from '../lib/ownerBilling';
import { cn } from '../lib/utils';

type SectionId =
  | 'overview'
  | 'users'
  | 'subscriptions'
  | 'plans'
  | 'metrics'
  | 'api'
  | 'data'
  | 'health'
  | 'activity'
  | 'settings';

const SECTIONS: { id: SectionId; label: string; icon: React.ReactNode }[] = [
  { id: 'overview', label: 'Overview', icon: <BarChart3 size={18} /> },
  { id: 'users', label: 'Users', icon: <Users size={18} /> },
  { id: 'subscriptions', label: 'Subscriptions', icon: <Layers size={18} /> },
  { id: 'plans', label: 'Plans', icon: <ScrollText size={18} /> },
  { id: 'metrics', label: 'Product Metrics', icon: <Activity size={18} /> },
  { id: 'api', label: 'API Usage', icon: <Database size={18} /> },
  { id: 'data', label: 'Data & Providers', icon: <HeartPulse size={18} /> },
  { id: 'health', label: 'System Health', icon: <ShieldCheck size={18} /> },
  { id: 'activity', label: 'Activity & Audit', icon: <Bell size={18} /> },
  { id: 'settings', label: 'Settings', icon: <SettingsIcon size={18} /> },
];

/**
 * Owner console (platform-level control surface).
 * Composes the existing AdminMetrics view under "Product Metrics" instead of
 * duplicating it. Commercial sections (Overview, Users, Subscriptions,
 * Activity & Audit) render ONLY data returned by the read-only
 * /api/admin/billing/* endpoints; anything unavailable renders an explicit
 * "Not yet available" state — no fabricated users, revenue, usage or health
 * figures anywhere in this file. Visibility here is UX only: every endpoint
 * independently rejects non-owner/admin callers.
 */
export default function OwnerConsole({ ownerEmail }: { ownerEmail: string }) {
  const [section, setSection] = useState<SectionId>('overview');

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-orange-500/10 border border-orange-500/30 flex items-center justify-center">
          <ShieldCheck className="w-5 h-5 text-orange-500" />
        </div>
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Owner Console</h2>
          <p className="text-sm text-zinc-500">Platform control · signed in as {ownerEmail}</p>
        </div>
      </div>

      <nav aria-label="Owner console sections" className="flex flex-wrap gap-2">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            aria-current={section === s.id ? 'page' : undefined}
            className={cn(
              'flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm transition-all focus-visible:ring-2 focus-visible:ring-orange-500/70',
              section === s.id
                ? 'bg-orange-500 text-black font-bold'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-900 border border-zinc-800'
            )}
          >
            {s.icon}
            {s.label}
          </button>
        ))}
      </nav>

      <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 sm:p-8">
        {section === 'overview' && <Overview email={ownerEmail} go={setSection} />}
        {section === 'users' && <UsersSection />}
        {section === 'subscriptions' && <SubscriptionsSection />}
        {section === 'plans' && <PlansSection />}
        {section === 'metrics' && <AdminMetrics />}
        {section === 'api' && (
          <EmptyState
            title="Usage metering is not yet enabled"
            body="Commercial API access is a Business-tier concept. No usage metering exists yet, so there is nothing to report — and nothing here invents usage figures."
          />
        )}
        {section === 'data' && (
          <EmptyState
            title="Provider status is not instrumented yet"
            body="Canonical identity and provenance live in the database (verified read-only in Objectives 6D). A live provider-status surface has not been built."
          />
        )}
        {section === 'health' && (
          <EmptyState
            title="System health checks are not wired yet"
            body="Deployment health is observed in the hosting provider, not in this console. Nothing here restarts or migrates anything."
          />
        )}
        {section === 'activity' && <EventsSection />}
        {section === 'settings' && (
          <EmptyState
            title="Platform settings live outside this console"
            body="Configuration (environment, deployment, database migrations) is managed through reviewed objectives — never from this screen."
          />
        )}
      </div>
    </div>
  );
}

function Overview({ email, go }: { email: string; go: (s: SectionId) => void }) {
  const state = useOwnerBilling<BillingOverview>('/api/admin/billing/overview');

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Signed in</p>
          <p className="mt-1 text-sm text-zinc-100 break-all">{email}</p>
          <p className="mt-1 text-xs text-orange-500 font-semibold">Role: owner/admin (server-verified)</p>
        </div>
        <div className="border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Commercial tiers</p>
          <p className="mt-1 text-sm text-zinc-100">Starter · Growth · Business · Enterprise</p>
          <p className="mt-1 text-xs text-zinc-500">Test-mode billing via Paystack (no live charges)</p>
        </div>
        <div className="border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Authorization basis</p>
          <p className="mt-1 text-sm text-zinc-100">Server role check</p>
          <p className="mt-1 text-xs text-zinc-500">Each admin endpoint verifies owner/admin independently</p>
        </div>
      </div>

      {state.status === 'loading' && <LoadingState label="Loading commercial overview…" />}
      {state.status === 'forbidden' && (
        <EmptyState
          title="Not authorized"
          body="The server did not recognize this session as owner/admin, so no commercial metrics are shown. Visibility in this console never grants access."
        />
      )}
      {state.status === 'unavailable' && (
        <EmptyState
          title="Not yet available"
          body="Commercial overview could not be loaded from the admin API. No figures are shown rather than estimated ones."
        />
      )}
      {state.status === 'ok' && <OverviewMetrics overview={state.data} />}

      <div className="flex flex-wrap gap-2">
        <button onClick={() => go('metrics')} className="px-4 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-sm hover:border-zinc-600 transition-colors focus-visible:ring-2 focus-visible:ring-orange-500/70">
          Open Product Metrics (admin tools)
        </button>
        <button onClick={() => go('plans')} className="px-4 py-2 rounded-xl bg-zinc-900 border border-zinc-800 text-sm hover:border-zinc-600 transition-colors focus-visible:ring-2 focus-visible:ring-orange-500/70">
          Review plan architecture
        </button>
      </div>
    </div>
  );
}

function OverviewMetrics({ overview }: { overview: BillingOverview }) {
  const cards: { label: string; value: number | string }[] = [
    { label: 'Total users', value: overview.total_users },
    { label: 'Users with subscriptions', value: overview.users_with_subscriptions },
    { label: 'Starter users', value: overview.starter_users },
    { label: 'Growth subscriptions', value: overview.plan_counts.growth },
    { label: 'Business subscriptions', value: overview.plan_counts.business },
    { label: 'Enterprise subscriptions', value: overview.plan_counts.enterprise },
    { label: 'Past-due subscriptions', value: overview.status_counts['past_due'] ?? 0 },
    { label: 'Canceled subscriptions', value: overview.status_counts['canceled'] ?? 0 },
  ];
  return (
    <div>
      <h3 className="text-sm font-bold uppercase tracking-widest text-zinc-500">Commercial overview — actual records only</h3>
      <div className="mt-3 grid grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((c) => (
          <div key={c.label} className="border border-zinc-800 rounded-2xl p-5">
            <p className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">{c.label}</p>
            <p className="mt-1 text-2xl font-extrabold tracking-tight">{c.value}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-zinc-600">
        Counts are derived from profiles/subscriptions records. No revenue, MRR, conversion or churn is shown — the database does not support those calculations.
      </p>
    </div>
  );
}

function UsersSection() {
  const state = useOwnerBilling<{ users: BillingUser[]; count: number }>('/api/admin/billing/users');

  if (state.status === 'loading') return <LoadingState label="Loading users…" />;
  if (state.status === 'forbidden') {
    return (
      <EmptyState
        title="Not authorized"
        body="The server did not recognize this session as owner/admin, so no accounts are shown."
      />
    );
  }
  if (state.status === 'unavailable') {
    return (
      <EmptyState
        title="Not yet available"
        body="User records could not be loaded from the admin API. No accounts are shown, and nothing here modifies any user."
      />
    );
  }
  if (state.data.users.length === 0) {
    return (
      <EmptyState
        title="No users found"
        body="The admin API returned zero profiles. Nothing here modifies any user."
      />
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400 leading-relaxed">
        Commercial/account state per user ({state.data.count} shown). Read-only — nothing here modifies any user, role, or subscription.
      </p>
      <div className="overflow-x-auto rounded-2xl border border-zinc-800">
        <table className="w-full min-w-[760px] text-sm bg-[#111]">
          <caption className="sr-only">User commercial state</caption>
          <thead>
            <tr className="border-b border-zinc-800 text-left">
              <Th>User</Th>
              <Th>Role</Th>
              <Th>Plan</Th>
              <Th>Status</Th>
              <Th>Period end</Th>
              <Th>Provider</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/80">
            {state.data.users.map((u, i) => (
              <tr key={u.user_id ?? u.email ?? `row-${i}`}>
                <td className="px-5 py-3 text-zinc-200" title={u.user_id ?? ''}>
                  <span className="block font-semibold">{u.email ?? shortId(u.user_id)}</span>
                  <span className="block text-xs text-zinc-500">{shortId(u.user_id)}</span>
                </td>
                <td className="px-5 py-3 text-zinc-400">{u.role}</td>
                <td className="px-5 py-3 text-zinc-400 capitalize">{u.effective_plan}</td>
                <td className="px-5 py-3 text-zinc-400">{formatStatus(u.subscription_status)}</td>
                <td className="px-5 py-3 text-zinc-400">{u.current_period_end ?? '—'}</td>
                <td className="px-5 py-3 text-zinc-400">{u.provider ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SubscriptionsSection() {
  const state = useOwnerBilling<{ subscriptions: BillingSubscription[]; count: number }>(
    '/api/admin/billing/subscriptions'
  );

  if (state.status === 'loading') return <LoadingState label="Loading subscriptions…" />;
  if (state.status === 'forbidden') {
    return (
      <EmptyState
        title="Not authorized"
        body="The server did not recognize this session as owner/admin, so no subscription records are shown."
      />
    );
  }
  if (state.status === 'unavailable') {
    return (
      <EmptyState
        title="Not yet available"
        body="Subscription records could not be loaded from the admin API. None are created from this console."
      />
    );
  }
  if (state.data.subscriptions.length === 0) {
    return (
      <EmptyState
        title="No subscription records"
        body="There are no subscription rows. Subscription state is written only by verified Paystack webhooks — never from this console."
      />
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400 leading-relaxed">
        Actual subscription records ({state.data.count} shown). Read-only — there are no plan/status controls here.
      </p>
      <div className="overflow-x-auto rounded-2xl border border-zinc-800">
        <table className="w-full min-w-[760px] text-sm bg-[#111]">
          <caption className="sr-only">Subscription records</caption>
          <thead>
            <tr className="border-b border-zinc-800 text-left">
              <Th>User</Th>
              <Th>Plan</Th>
              <Th>Status</Th>
              <Th>Period start</Th>
              <Th>Period end</Th>
              <Th>Provider</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/80">
            {state.data.subscriptions.map((s) => (
              <tr key={s.id}>
                <td className="px-5 py-3 text-zinc-200" title={s.user_id}>{shortId(s.user_id)}</td>
                <td className="px-5 py-3 text-zinc-400 capitalize">{s.plan}</td>
                <td className="px-5 py-3 text-zinc-400">
                  {formatStatus(s.status)}
                  {s.status === 'canceled' && s.current_period_end && Date.parse(s.current_period_end) > Date.now() && (
                    <span className="block text-xs text-zinc-500">period still active</span>
                  )}
                  {s.status === 'canceled' && (!s.current_period_end || Date.parse(s.current_period_end) <= Date.now()) && (
                    <span className="block text-xs text-zinc-500">period ended</span>
                  )}
                </td>
                <td className="px-5 py-3 text-zinc-400">{s.current_period_start ?? '—'}</td>
                <td className="px-5 py-3 text-zinc-400">{s.current_period_end ?? '—'}</td>
                <td className="px-5 py-3 text-zinc-400">{s.provider ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EventsSection() {
  const state = useOwnerBilling<{ events: BillingEvent[]; count: number }>('/api/admin/billing/events');

  if (state.status === 'loading') return <LoadingState label="Loading provider events…" />;
  if (state.status === 'forbidden') {
    return (
      <EmptyState
        title="Not authorized"
        body="The server did not recognize this session as owner/admin, so no provider events are shown."
      />
    );
  }
  if (state.status === 'unavailable') {
    return (
      <EmptyState
        title="Not yet available"
        body="Provider events could not be loaded from the admin API. Raw provider payloads are never displayed here."
      />
    );
  }
  if (state.data.events.length === 0) {
    return (
      <EmptyState
        title="No provider events recorded"
        body="No webhook deliveries have been recorded in subscription_events. This audit trail is append-only and read-only."
      />
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-400 leading-relaxed">
        Provider-event audit trail ({state.data.count} shown). Read-only metadata — raw payloads are never exposed, and events cannot be edited from here.
      </p>
      <div className="overflow-x-auto rounded-2xl border border-zinc-800">
        <table className="w-full min-w-[760px] text-sm bg-[#111]">
          <caption className="sr-only">Provider event history</caption>
          <thead>
            <tr className="border-b border-zinc-800 text-left">
              <Th>Provider</Th>
              <Th>Event</Th>
              <Th>Status</Th>
              <Th>Event ID</Th>
              <Th>Subscription</Th>
              <Th>Recorded</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/80">
            {state.data.events.map((e) => (
              <tr key={`${e.provider}:${e.provider_event_id}`}>
                <td className="px-5 py-3 text-zinc-200">{e.provider}</td>
                <td className="px-5 py-3 text-zinc-400">{e.event_type}</td>
                <td className="px-5 py-3 text-zinc-400">{e.processing_status}</td>
                <td className="px-5 py-3 text-zinc-400" title={e.provider_event_id}>{shortId(e.provider_event_id, 12)}</td>
                <td className="px-5 py-3 text-zinc-400">{e.subscription_id ?? '—'}</td>
                <td className="px-5 py-3 text-zinc-400">{e.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PlansSection() {
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400 leading-relaxed">
        Current commercial configuration (same tiers as the product page). Billing runs in Paystack test mode —
        no live charges. This console cannot change plans or activate subscriptions.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {PLANS.map((p) => (
          <div key={p.id} className="border border-zinc-800 rounded-2xl p-5 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-bold">{p.name}</h3>
              <span className="text-[11px] font-bold uppercase tracking-widest text-orange-500">{p.statusLabel}</span>
            </div>
            <p className="text-2xl font-extrabold tracking-tight">{p.price}</p>
            <p className="text-sm text-zinc-500">{p.tagline}</p>
            <ul className="text-sm text-zinc-300 space-y-1 pt-1">
              {p.capabilities.map((c) => (
                <li key={c} className="flex gap-2"><span aria-hidden="true" className="text-zinc-600">·</span>{c}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return <th scope="col" className="px-5 py-4 font-semibold text-zinc-400">{children}</th>;
}

function LoadingState({ label }: { label: string }) {
  return (
    <div className="py-10 text-center" role="status">
      <p className="text-sm text-zinc-400">{label}</p>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="text-center py-10 space-y-3">
      <p className="text-lg font-bold">{title}</p>
      <p className="text-sm text-zinc-400 max-w-xl mx-auto leading-relaxed">{body}</p>
      <p className="text-xs uppercase tracking-widest text-zinc-600 font-semibold pt-2">No placeholder data shown</p>
    </div>
  );
}
