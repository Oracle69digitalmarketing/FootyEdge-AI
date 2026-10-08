import { useState, useEffect } from 'react';
import { supabase } from './supabase';
import PortfolioView from './components/PortfolioView';
import AccaBuilder from './components/AccaBuilder';
import ValueBets from './components/ValueBets';
import HowToUse from './components/HowToUse';
import TeamsList from './components/TeamsList';
import PlayersList from './components/PlayersList';
import PredictionsDashboard from './pages/PredictionsDashboard';
import TelegramLink from './components/TelegramLink';
import ProductPage from './components/product/ProductPage';
import OwnerConsole from './components/OwnerConsole';
import { canViewOwnerBilling, planDisplayName, resolveAccess } from './lib/access';
import { authHeaders } from './lib/authFetch';
import { 
  LayoutDashboard, 
  TrendingUp, 
  Crown,
  LogOut, 
  Loader2,
  Database,
  User,
  Layers,
  Send,
  MessageCircle,
  HelpCircle
} from 'lucide-react';
import { cn } from './lib/utils';

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [serverRole, setServerRole] = useState<'owner' | 'admin' | 'user' | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'value' | 'players' | 'portfolio' | 'acca' | 'owner' | 'teams' | 'telegram' | 'how-to-use'>('dashboard');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      setUser(session?.user ?? null);
      setLoading(false);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
    });

    return () => subscription.unsubscribe();
  }, []);

  // Server-authoritative role for display/navigation only. The role comes
  // from GET /api/auth/role (verified JWT -> auth.users.id ->
  // profiles.role); backend enforcement never consults this value.
  // Fail closed for display: unknown until fetched, 'user' on any failure.
  useEffect(() => {
    if (!user) {
      setServerRole(null);
      return;
    }
    let live = true;
    (async () => {
      try {
        const res = await fetch('/api/auth/role', { headers: await authHeaders() });
        if (!res.ok) {
          if (live) setServerRole('user');
          return;
        }
        const body: unknown = await res.json().catch(() => null);
        const role = (body as { role?: unknown } | null)?.role;
        if (live) setServerRole(role === 'owner' || role === 'admin' ? role : 'user');
      } catch {
        if (live) setServerRole('user');
      }
    })();
    return () => {
      live = false;
    };
  }, [user]);

  const handleLogout = async () => {
    if (supabase) {
      await supabase.auth.signOut();
    }
  };

  if (loading) {
    return <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center"><Loader2 className="w-8 h-8 text-orange-500 animate-spin" /></div>;
  }

  if (!supabase) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex flex-col items-center justify-center p-6 text-center">
        <div className="bg-[#111] border border-red-900/30 p-8 rounded-3xl w-full max-w-md space-y-4">
          <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
            <LogOut className="w-8 h-8 text-red-500 rotate-180" />
          </div>
          <h2 className="text-2xl font-bold text-white">Configuration Error</h2>
          <p className="text-zinc-400">
            The Supabase client could not be initialized. Please ensure that 
            <code className="bg-zinc-900 px-2 py-1 rounded mx-1 text-orange-500 font-mono text-sm">VITE_SUPABASE_URL</code> 
            and 
            <code className="bg-zinc-900 px-2 py-1 rounded mx-1 text-orange-500 font-mono text-sm">VITE_SUPABASE_ANON_KEY</code> 
            are correctly set in your environment variables.
          </p>
        </div>
      </div>
    );
  }

  // Signed-out visitors see the commercial product page, which includes
  // the same Supabase email/password sign-in. The authenticated app below
  // is unchanged.
  if (!user) {
    return <ProductPage />;
  }

  // Access model: ROLE (owner/admin/user) and subscription PLAN are
  // independent concepts (see src/lib/access.ts). The role below comes
  // from the server profile lookup. Frontend checks are UX only; every
  // endpoint enforces independently server-side.
  const access = resolveAccess({ email: user?.email ?? null, persistentRole: serverRole });

  return (
    <div className="flex min-h-screen bg-[#0a0a0a] text-white">
      {/* Sidebar */}
      <aside className="w-64 border-r border-zinc-800 p-6 flex flex-col gap-8">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-orange-500 rounded-xl flex items-center justify-center font-black text-black">FE</div>
          <h1 className="text-xl font-bold">FootyEdge AI</h1>
        </div>

        <nav className="flex-1 space-y-2">
          <NavItem active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} icon={<LayoutDashboard size={20} />} label="Dashboard" />
          <NavItem active={activeTab === 'value'} onClick={() => setActiveTab('value')} icon={<TrendingUp size={20} />} label="Value Bets" />
          <NavItem active={activeTab === 'teams'} onClick={() => setActiveTab('teams')} icon={<Database size={20} />} label="Teams" />
          <NavItem active={activeTab === 'players'} onClick={() => setActiveTab('players')} icon={<User size={20} />} label="Players" />
          <NavItem active={activeTab === 'portfolio'} onClick={() => setActiveTab('portfolio')} icon={<Layers size={20} />} label="My Portfolio" />
          <NavItem active={activeTab === 'acca'} onClick={() => setActiveTab('acca')} icon={<Send size={20} />} label="Acca Builder" />
          <NavItem active={activeTab === 'telegram'} onClick={() => setActiveTab('telegram')} icon={<MessageCircle size={20} />} label="Telegram" />
          <NavItem active={activeTab === 'how-to-use'} onClick={() => setActiveTab('how-to-use')} icon={<HelpCircle size={20} />} label="How to Use" />
          {canViewOwnerBilling(access) && (
            <NavItem active={activeTab === 'owner'} onClick={() => setActiveTab('owner')} icon={<Crown size={20} />} label="Owner Console" />
          )}
        </nav>

        <div className="pt-6 border-t border-zinc-800 space-y-3">
          <div className="px-2">
            <p className="text-xs text-zinc-500 truncate" title={user.email}>{user.email}</p>
            <p className="text-xs text-zinc-600" title="Plan labels are display-only; feature access is checked server-side on every request.">
              Plan: {planDisplayName(access)}
              {access.planIsPlaceholder && <span> · server-gated</span>}
              {access.role === 'owner' && <span className="text-orange-500 font-semibold"> · Owner</span>}
            </p>
          </div>
          <button onClick={handleLogout} className="flex items-center gap-3 text-zinc-500 hover:text-red-500 transition-colors w-full p-2">
            <LogOut size={20} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-8">
        {activeTab === 'dashboard' && <PredictionsDashboard />}
        {activeTab === 'value' && <ValueBets />}
        {activeTab === 'teams' && <TeamsList />}
        {activeTab === 'players' && <PlayersList />}
        {activeTab === 'portfolio' && <PortfolioView />}
        {activeTab === 'acca' && <AccaBuilder />}
        {activeTab === 'telegram' && <TelegramLink />}
        {activeTab === 'how-to-use' && <HowToUse />}
        {activeTab === 'owner' && canViewOwnerBilling(access) && <OwnerConsole ownerEmail={user.email} />}
      </main>
    </div>
  );
}

function NavItem({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: any, label: string }) {
  return (
    <button 
      onClick={onClick} 
      className={cn(
        "w-full flex items-center gap-3 p-3 rounded-xl transition-all", 
        active 
          ? "bg-orange-500 text-black font-bold shadow-lg shadow-orange-500/20" 
          : "text-zinc-500 hover:text-white hover:bg-zinc-900"
      )}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}
