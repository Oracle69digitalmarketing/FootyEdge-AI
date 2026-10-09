import {
  ArrowDown,
  ArrowRight,
  BadgeCheck,
  BarChart3,
  Blocks,
  BookOpenText,
  CalendarDays,
  FlaskConical,
  Fingerprint,
  Landmark,
  Layers,
  ListChecks,
  Network,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Trophy,
  Users,
} from 'lucide-react';
import SignInCard from './SignInCard';
import { PLANS } from '../../lib/access';

/**
 * Commercial product page for FootyEdge AI.
 * Shown to signed-out visitors. The authenticated application is untouched:
 * signing in opens the existing app (dashboard, value bets, teams, players,
 * portfolio, acca builder, guides).
 */
export default function ProductPage() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white antialiased">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:bg-orange-500 focus:text-black focus:px-4 focus:py-2 focus:rounded-lg focus:font-bold"
      >
        Skip to content
      </a>

      {/* ---------- Header ---------- */}
      <header className="sticky top-0 z-40 border-b border-zinc-800/80 bg-[#0a0a0a]/90 backdrop-blur">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 flex items-center justify-between h-16">
          <a href="#top" className="flex items-center gap-3 rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" aria-label="FootyEdge AI home">
            <span className="w-9 h-9 bg-orange-500 rounded-xl flex items-center justify-center font-black text-black text-sm" aria-hidden="true">FE</span>
            <span className="text-lg font-bold tracking-tight">FootyEdge AI</span>
          </a>
          <nav aria-label="Product sections" className="hidden md:flex items-center gap-6 text-sm text-zinc-400">
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#product">Product</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#how-it-works">How it works</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#trust">Trust</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#plans">Plans</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#preview">Preview</a>
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            <a
              href="#preview"
              className="text-sm font-semibold px-3 sm:px-4 py-2 rounded-xl border border-zinc-700 text-zinc-200 hover:border-zinc-500 hover:text-white transition-colors focus-visible:ring-2 focus-visible:ring-orange-500/70"
            >
              Explore FootyEdge
            </a>
            <a
              href="#access"
              className="text-sm font-bold px-3 sm:px-4 py-2 rounded-xl bg-orange-500 text-black hover:bg-orange-400 transition-colors focus-visible:ring-2 focus-visible:ring-orange-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0a]"
            >
              Request Access
            </a>
          </div>
        </div>
      </header>

      <main id="main">
        {/* ---------- 3.1 Hero ---------- */}
        <section id="top" aria-labelledby="hero-heading" className="border-b border-zinc-800/80">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-24 text-center">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500 mb-5">FootyEdge AI</p>
            <h1 id="hero-heading" className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-tight max-w-4xl mx-auto">
              Football intelligence built on verified match data.
            </h1>
            <p className="mt-6 text-base sm:text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed">
              FootyEdge turns structured football data into useful match, team, competition
              and AI-assisted insights — starting from identities and fixtures you can trace,
              not guesswork you cannot check.
            </p>
            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
              <a
                href="#preview"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 bg-orange-500 text-black font-bold px-7 py-3.5 rounded-2xl hover:bg-orange-400 transition-colors focus-visible:ring-2 focus-visible:ring-orange-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0a]"
              >
                Explore FootyEdge <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </a>
              <a
                href="#access"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 border border-zinc-700 text-zinc-100 font-semibold px-7 py-3.5 rounded-2xl hover:border-zinc-500 hover:text-white transition-colors focus-visible:ring-2 focus-visible:ring-orange-500/70"
              >
                Request Access
              </a>
            </div>
            <dl className="mt-12 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-3xl mx-auto text-left">
              <div className="bg-[#111] border border-zinc-800 rounded-2xl px-5 py-4">
                <dt className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Traceable fixtures</dt>
                <dd className="mt-1 text-sm text-zinc-200">Every fixture keeps its provider provenance.</dd>
              </div>
              <div className="bg-[#111] border border-zinc-800 rounded-2xl px-5 py-4">
                <dt className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Canonical entities</dt>
                <dd className="mt-1 text-sm text-zinc-200">Teams, competitions and seasons with stable identity.</dd>
              </div>
              <div className="bg-[#111] border border-zinc-800 rounded-2xl px-5 py-4">
                <dt className="text-xs uppercase tracking-widest text-zinc-500 font-semibold">Fail-closed identity</dt>
                <dd className="mt-1 text-sm text-zinc-200">Ambiguous identities are flagged, never silently merged.</dd>
              </div>
            </dl>
          </div>
        </section>

        {/* ---------- 3.2 Product value ---------- */}
        <section id="product" aria-labelledby="product-heading" className="scroll-mt-20 border-b border-zinc-800/80">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-20">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Product</p>
            <h2 id="product-heading" className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight">What FootyEdge does</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl leading-relaxed">
              Five connected capabilities, all reading from the same verified football data —
              available today inside the FootyEdge app.
            </p>
            <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
              <ValueCard
                icon={<CalendarDays className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                title="Match Intelligence"
                body="Structured match information and analysis: fixtures, daily and weekly picks, head-to-head views and expected-goals context."
              />
              <ValueCard
                icon={<ShieldCheck className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                title="Team Intelligence"
                body="Organized team-level football information and context: ratings, attack and defensive strength, form and historical performance."
              />
              <ValueCard
                icon={<Trophy className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                title="Competition & Season Intelligence"
                body="Canonical competitions, seasons and competition-season relationships — so every match sits in the right competition at the right time."
              />
              <ValueCard
                icon={<Sparkles className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                title="AI-Assisted Analysis"
                body="Models that transform structured football information into useful analysis: win probabilities, expected goals and strategy breakdowns."
              />
              <ValueCard
                icon={<BarChart3 className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                title="Prediction Analytics"
                body="Prediction-related tooling the app supports today: value bets with expected value, accumulator building with booking codes, and portfolio tracking of your settled results."
              />
              <ValueCard
                icon={<BookOpenText className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                title="Guided & Transparent"
                body="Built-in guides explain each surface, and a public ledger keeps selections reviewable. You always know what the app can and cannot do."
              />
            </div>
          </div>
        </section>

        {/* ---------- 3.3 How FootyEdge works ---------- */}
        <section id="how-it-works" aria-labelledby="how-heading" className="scroll-mt-20 border-b border-zinc-800/80 bg-[#0d0d0d]">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-20">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Architecture</p>
            <h2 id="how-heading" className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight">How FootyEdge works</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl leading-relaxed">
              FootyEdge is designed around reliable identity resolution and traceable football
              data — rather than silently guessing when provider identities are ambiguous.
            </p>
            <ol className="mt-10 grid grid-cols-1 md:grid-cols-5 gap-4">
              <FlowStep icon={<Network className="w-5 h-5 text-orange-500" aria-hidden="true" />} step="1" title="Data Providers" body="Fixtures, teams and odds arrive from external football data providers." last={false} />
              <FlowStep icon={<Fingerprint className="w-5 h-5 text-orange-500" aria-hidden="true" />} step="2" title="Identity & Provenance" body="Provider identities are resolved by exact match and their provenance is recorded." last={false} />
              <FlowStep icon={<Blocks className="w-5 h-5 text-orange-500" aria-hidden="true" />} step="3" title="Canonical Football Entities" body="Verified teams, competitions, seasons and fixtures with stable identity." last={false} />
              <FlowStep icon={<ScanSearch className="w-5 h-5 text-orange-500" aria-hidden="true" />} step="4" title="Match Intelligence" body="Structured match context: ratings, expected goals, value and accumulators." last={false} />
              <FlowStep icon={<Sparkles className="w-5 h-5 text-orange-500" aria-hidden="true" />} step="5" title="AI Insights" body="AI transforms verified structures into readable, useful analysis." last={true} />
            </ol>
            <p className="mt-8 text-sm text-zinc-500 max-w-3xl leading-relaxed">
              When a provider identity is ambiguous, FootyEdge stops and flags it instead of
              quietly merging two different teams or fixtures. That fail-closed behavior is a
              deliberate trust feature — it keeps every downstream insight traceable.
            </p>
          </div>
        </section>

        {/* ---------- 3.4 Trust / data integrity ---------- */}
        <section id="trust" aria-labelledby="trust-heading" className="scroll-mt-20 border-b border-zinc-800/80">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-20">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Trust</p>
            <h2 id="trust-heading" className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight">Data you can check</h2>
            <ul className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
              <TrustItem icon={<BadgeCheck aria-hidden="true" />} title="Exact-match identity" body="Teams and fixtures are matched exactly — spelling variants never silently become the same entity." />
              <TrustItem icon={<ListChecks aria-hidden="true" />} title="Provider provenance" body="Every record keeps where it came from, so analysis can always be traced back to its source." />
              <TrustItem icon={<Layers aria-hidden="true" />} title="Canonical entities" body="One stable identity per team, competition, season and fixture across all providers." />
              <TrustItem icon={<Landmark aria-hidden="true" />} title="Structured competitions" body="Competitions and seasons are modeled explicitly, keeping matches in their correct context." />
              <TrustItem icon={<FlaskConical aria-hidden="true" />} title="Fail-closed on ambiguity" body="Unclear identities raise a flag for review instead of producing a confident-sounding wrong answer." />
              <TrustItem icon={<ShieldCheck aria-hidden="true" />} title="No silent remapping" body="Fixtures and teams are never quietly rewritten from one identity to another." />
            </ul>
          </div>
        </section>

        {/* ---------- 3.5 Who it is for ---------- */}
        <section id="audiences" aria-labelledby="audiences-heading" className="scroll-mt-20 border-b border-zinc-800/80 bg-[#0d0d0d]">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-20">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Audiences</p>
            <h2 id="audiences-heading" className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight">Who FootyEdge is for</h2>
            <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
              <AudienceCard icon={<BarChart3 className="w-5 h-5 text-orange-500" aria-hidden="true" />} title="Football analysts" body="Structured ratings, expected goals and head-to-head context for pre-match work." />
              <AudienceCard icon={<Users className="w-5 h-5 text-orange-500" aria-hidden="true" />} title="Fans & researchers" body="Browse teams, players and competitions with context that stays consistent." />
              <AudienceCard icon={<Layers className="w-5 h-5 text-orange-500" aria-hidden="true" />} title="Sports-content platforms" body="Canonical football entities that keep coverage and archives aligned." />
              <AudienceCard icon={<Blocks className="w-5 h-5 text-orange-500" aria-hidden="true" />} title="Developers & API consumers" body="Account-backed access to the same structured endpoints that power the app." />
              <AudienceCard icon={<Trophy className="w-5 h-5 text-orange-500" aria-hidden="true" />} title="Football businesses" body="Traceable match intelligence for products where wrong identity means wrong output." />
            </div>
          </div>
        </section>

        {/* ---------- Plans (architecture only: no prices, no checkout) ---------- */}
        <section id="plans" aria-labelledby="plans-heading" className="scroll-mt-20 border-b border-zinc-800/80">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-20">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Plans</p>
            <h2 id="plans-heading" className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight">Commercial tiers</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl leading-relaxed">
              Four tiers describe where FootyEdge is going. Only Starter is usable today;
              the rest are honest statuses — not things you can buy yet.
            </p>
            <p role="note" className="mt-4 text-sm text-zinc-300 bg-[#111] border border-zinc-800 rounded-2xl px-5 py-4 max-w-3xl leading-relaxed">
              Pricing shown here reflects the current proposed FootyEdge AI commercial
              structure. Online billing and checkout are not yet enabled.
            </p>
            <div className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-5">
              {PLANS.map((p) => (
                <div key={p.id} className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-3 flex flex-col">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-lg font-bold">{p.name}</h3>
                    <span className="text-[11px] font-bold uppercase tracking-widest text-orange-500">{p.statusLabel}</span>
                  </div>
                  <p className="text-2xl font-extrabold tracking-tight">{p.price}</p>
                  <p className="text-sm text-zinc-500">{p.tagline}</p>
                  <ul className="text-sm text-zinc-300 space-y-1.5 pt-1 flex-1">
                    {p.capabilities.map((c) => (
                      <li key={c} className="flex gap-2"><span aria-hidden="true" className="text-zinc-600">·</span>{c}</li>
                    ))}
                  </ul>
                  <a
                    href="#access"
                    className="inline-flex items-center justify-center gap-2 mt-2 border border-zinc-700 text-zinc-100 text-sm font-semibold px-4 py-2.5 rounded-xl hover:border-zinc-500 hover:text-white transition-colors focus-visible:ring-2 focus-visible:ring-orange-500/70"
                  >
                    {planCtaLabel(p.id)} <ArrowRight className="w-4 h-4" aria-hidden="true" />
                  </a>
                </div>
              ))}
            </div>
            <PlanComparison />
          </div>
        </section>

        {/* ---------- 3.6 Product preview ---------- */}
        <section id="preview" aria-labelledby="preview-heading" className="scroll-mt-20 border-b border-zinc-800/80">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-20">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Preview</p>
            <h2 id="preview-heading" className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight">Inside the FootyEdge app</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl leading-relaxed">
              The working application is one sign-in away. These are the real surfaces you get:
            </p>
            <ul className="mt-10 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-5">
              <PreviewItem title="Dashboard" body="Daily and weekly picks, accumulator suggestions and a reviewable public ledger." />
              <PreviewItem title="Value Bets" body="Expected-value opportunities you can scan, filter and settle." />
              <PreviewItem title="Teams & Players" body="Searchable directory with ratings, strengths, form, positions and nationalities." />
              <PreviewItem title="Acca Builder" body="Multi-match accumulator slips with totals and bookmaker booking codes." />
              <PreviewItem title="Portfolio" body="Track stakes, win rate and profit across your settled history." />
              <PreviewItem title="Guides" body="In-app walkthroughs plus premium and strategy documentation." />
            </ul>
            <div className="mt-10 text-center">
              <a
                href="#access"
                className="inline-flex items-center justify-center gap-2 bg-orange-500 text-black font-bold px-8 py-3.5 rounded-2xl hover:bg-orange-400 transition-colors focus-visible:ring-2 focus-visible:ring-orange-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#0a0a0a]"
              >
                Explore FootyEdge <ArrowRight className="w-4 h-4" aria-hidden="true" />
              </a>
            </div>
          </div>
        </section>

        {/* ---------- 3.7 Commercial access ---------- */}
        <section id="access" aria-labelledby="access-heading" className="scroll-mt-20 border-b border-zinc-800/80 bg-[#0d0d0d]">
          <div className="mx-auto max-w-6xl px-4 sm:px-6 py-16 sm:py-20">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-orange-500">Access</p>
            <h2 id="access-heading" className="mt-3 text-3xl sm:text-4xl font-bold tracking-tight">Get access</h2>
            <p className="mt-4 text-zinc-400 max-w-2xl leading-relaxed">
              Access to FootyEdge is account-based. Create an account to open the app —
              API and partnership conversations start from there.
            </p>
            <div className="mt-10 grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10 items-start">
              <div className="flex justify-center lg:justify-end">
                <SignInCard />
              </div>
              <div className="space-y-4">
                <AccessCard
                  icon={<ArrowRight className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                  title="Try FootyEdge"
                  body="Create a free account and open the live app right away: dashboard picks, value bets, teams, players and the acca builder."
                />
                <AccessCard
                  icon={<Blocks className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                  title="Request API Access"
                  body="The app is backed by structured REST endpoints. API access is provisioned for account holders — create an account to start that conversation."
                />
                <AccessCard
                  icon={<Users className="w-5 h-5 text-orange-500" aria-hidden="true" />}
                  title="Partner With FootyEdge"
                  body="For content platforms, developers and football businesses building on verified match data. Partnerships begin with an account and a conversation about your use case."
                />
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ---------- 3.8 Footer ---------- */}
      <footer className="mx-auto max-w-6xl px-4 sm:px-6 py-12">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <span className="w-9 h-9 bg-orange-500 rounded-xl flex items-center justify-center font-black text-black text-sm" aria-hidden="true">FE</span>
            <div>
              <p className="font-bold">FootyEdge AI</p>
              <p className="text-xs text-zinc-500">Football intelligence built on verified match data.</p>
            </div>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-zinc-400">
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#product">Product</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#how-it-works">How it works</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#trust">Trust</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#plans">Plans</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#preview">Preview</a>
            <a className="hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/70" href="#access">Request access</a>
          </nav>
        </div>
        <p className="mt-8 pt-6 border-t border-zinc-800/80 text-xs text-zinc-600">
          © 2026 FootyEdge AI. Football data is provided for informational purposes and carries no guarantee of outcome.
        </p>
      </footer>
    </div>
  );
}

/* ---------- building blocks (same design tokens as the app) ---------- */

function planCtaLabel(planId: string): string {
  // Honest non-payment CTAs: every tier leads to the existing
  // account/sign-in flow. No checkout exists.
  switch (planId) {
    case 'starter': return 'Get Started';
    case 'growth': return 'Coming soon';
    case 'business': return 'Request Access';
    case 'enterprise': return 'Talk to FootyEdge';
    default: return 'Learn more';
  }
}

const COMPARISON_ROWS: { capability: string; starter: string; growth: string; business: string; enterprise: string }[] = [
  { capability: 'Match intelligence', starter: 'Included', growth: 'Included', business: 'Included', enterprise: 'Custom' },
  { capability: 'Team analysis', starter: 'Included', growth: 'Included', business: 'Included', enterprise: 'Custom' },
  { capability: 'Player analysis', starter: 'Included', growth: 'Included', business: 'Included', enterprise: 'Custom' },
  { capability: 'Prediction analytics', starter: 'Included', growth: 'Expanded', business: 'Included', enterprise: 'Custom' },
  { capability: 'Value bets', starter: '—', growth: 'Expanded', business: 'Included', enterprise: 'Custom' },
  { capability: 'Portfolio', starter: '—', growth: 'Expanded', business: 'Included', enterprise: 'Custom' },
  { capability: 'Acca Builder', starter: '—', growth: 'Expanded', business: 'Included', enterprise: 'Custom' },
  { capability: 'Advanced analytics', starter: '—', growth: 'Included', business: 'Included', enterprise: 'Custom' },
  { capability: 'Extended AI capacity', starter: '—', growth: 'Included', business: 'Included', enterprise: 'Custom' },
  { capability: 'Higher usage limits', starter: '—', growth: 'Included', business: 'Included', enterprise: 'Custom' },
  { capability: 'Commercial usage', starter: '—', growth: '—', business: 'Planned', enterprise: 'Negotiated' },
  { capability: 'API access', starter: '—', growth: '—', business: 'Planned', enterprise: 'Negotiated' },
  { capability: 'Data export', starter: '—', growth: '—', business: 'Planned', enterprise: 'Negotiated' },
  { capability: 'Multiple seats', starter: '—', growth: '—', business: 'Planned', enterprise: 'Custom' },
  { capability: 'Organization controls', starter: '—', growth: '—', business: 'Planned', enterprise: 'Custom' },
];

function PlanComparison() {
  return (
    <div className="mt-10">
      <h3 className="text-xl font-bold">Compare plans</h3>
      <p className="mt-2 text-sm text-zinc-500 max-w-3xl leading-relaxed">
        “Planned” means designed but not yet available. Nothing on this page can be
        purchased yet — online billing is not enabled.
      </p>
      <div className="mt-4 overflow-x-auto rounded-3xl border border-zinc-800">
        <table className="w-full min-w-[640px] text-sm bg-[#111]">
          <caption className="sr-only">Feature comparison across Starter, Growth, Business and Enterprise plans</caption>
          <thead>
            <tr className="border-b border-zinc-800 text-left">
              <th scope="col" className="px-5 py-4 font-semibold text-zinc-400">Capability</th>
              <th scope="col" className="px-5 py-4 font-bold">Starter <span className="block text-xs font-semibold text-zinc-500">Free</span></th>
              <th scope="col" className="px-5 py-4 font-bold">Growth <span className="block text-xs font-semibold text-zinc-500">₦5,000/mo</span></th>
              <th scope="col" className="px-5 py-4 font-bold">Business <span className="block text-xs font-semibold text-zinc-500">₦15,000/mo</span></th>
              <th scope="col" className="px-5 py-4 font-bold">Enterprise <span className="block text-xs font-semibold text-zinc-500">Custom</span></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/80">
            {COMPARISON_ROWS.map((r) => (
              <tr key={r.capability}>
                <th scope="row" className="px-5 py-3 font-semibold text-left text-zinc-200">{r.capability}</th>
                <td className="px-5 py-3 text-zinc-400">{r.starter}</td>
                <td className="px-5 py-3 text-zinc-400">{r.growth}</td>
                <td className="px-5 py-3 text-zinc-400">{r.business}</td>
                <td className="px-5 py-3 text-zinc-400">{r.enterprise}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ValueCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 sm:p-7 space-y-3">
      <div className="w-10 h-10 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">{icon}</div>
      <h3 className="text-lg font-bold">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
    </div>
  );
}

function FlowStep({ icon, step, title, body, last }: { icon: React.ReactNode; step: string; title: string; body: string; last: boolean }) {
  return (
    <li className="relative bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-3">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">{icon}</div>
        <span className="text-xs font-bold text-zinc-500">STEP {step}</span>
      </div>
      <h3 className="text-base font-bold">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
      {!last && (
        <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 md:hidden text-zinc-600" aria-hidden="true">
          <ArrowDown className="w-4 h-4" />
        </span>
      )}
    </li>
  );
}

function TrustItem({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-3">
      <div className="text-green-500 [&>svg]:w-5 [&>svg]:h-5">{icon}</div>
      <h3 className="text-base font-bold">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
    </div>
  );
}

function AudienceCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-3">
      <div className="w-10 h-10 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">{icon}</div>
      <h3 className="text-base font-bold">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
    </div>
  );
}

function PreviewItem({ title, body }: { title: string; body: string }) {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-2">
      <h3 className="text-base font-bold">{title}</h3>
      <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
    </div>
  );
}

function AccessCard({ icon, title, body }: { icon: React.ReactNode; title: string; body: string }) {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 flex gap-4">
      <div className="w-10 h-10 shrink-0 rounded-xl bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">{icon}</div>
      <div className="space-y-1.5">
        <h3 className="text-base font-bold">{title}</h3>
        <p className="text-sm text-zinc-400 leading-relaxed">{body}</p>
      </div>
    </div>
  );
}
