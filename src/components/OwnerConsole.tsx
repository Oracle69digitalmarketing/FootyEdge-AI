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
 * duplicating it. Every section without a real backend shows an explicit
 * empty/coming-soon state — no fabricated users, revenue, usage or health
 * figures anywhere in this file.
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
        {section === 'users' && (
          <EmptyState
            title="User management is not connected yet"
            body="Listing accounts requires the upcoming admin API. No accounts are shown here, and nothing here modifies any user."
          />
        )}
        {section === 'subscriptions' && (
          <EmptyState
            title="No subscription backend yet"
            body="Plans are architecture definitions only. There are no subscription records to display, and none are created from this console."
          />
        )}
        {section === 'plans' && <PlansSection />}
        {section === 'metrics' && <AdminMetrics />}
        {section === 'api' && (
          <EmptyState
            title="API usage is not metered yet"
            body="Commercial API access is a Business-tier concept. Usage metering does not exist yet, so there is nothing to report."
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
        {section === 'activity' && (
          <EmptyState
            title="No audit trail yet"
            body="Administrative actions will be recorded here once the audit log exists. This console currently performs no mutating actions."
          />
        )}
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
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Signed in</p>
          <p className="mt-1 text-sm text-zinc-100 break-all">{email}</p>
          <p className="mt-1 text-xs text-orange-500 font-semibold">Role: owner (bootstrap)</p>
        </div>
        <div className="border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Commercial tiers</p>
          <p className="mt-1 text-sm text-zinc-100">Starter · Growth · Business · Enterprise</p>
          <p className="mt-1 text-xs text-zinc-500">Definitions only — no billing yet</p>
        </div>
        <div className="border border-zinc-800 rounded-2xl p-5">
          <p className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Authorization basis</p>
          <p className="mt-1 text-sm text-zinc-100">Bootstrap mapping</p>
          <p className="mt-1 text-xs text-zinc-500">Durable profiles.role checks pending RLS work</p>
        </div>
      </div>
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

function PlansSection() {
  return (
    <div className="space-y-4">
      <p className="text-sm text-zinc-400 leading-relaxed">
        Commercial tier definitions. No prices, no checkout, no payment processing —
        availability states are honest: only Starter is usable today.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {PLANS.map((p) => (
          <div key={p.id} className="border border-zinc-800 rounded-2xl p-5 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-bold">{p.name}</h3>
              <span className="text-[11px] font-bold uppercase tracking-widest text-orange-500">{p.statusLabel}</span>
            </div>
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

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="text-center py-10 space-y-3">
      <p className="text-lg font-bold">{title}</p>
      <p className="text-sm text-zinc-400 max-w-xl mx-auto leading-relaxed">{body}</p>
      <p className="text-xs uppercase tracking-widest text-zinc-600 font-semibold pt-2">Coming soon — no placeholder data shown</p>
    </div>
  );
}
