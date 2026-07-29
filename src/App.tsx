import { useState, useEffect } from 'react';
import { supabase } from './supabase';
import Portfolio from './components/Portfolio';
import AccaBuilder from './components/AccaBuilder';
import ValueBets from './components/ValueBets';
import HowToUse from './components/HowToUse';
import TeamsList from './components/TeamsList';
import PlayersList from './components/PlayersList';
import PredictionsDashboard from './pages/PredictionsDashboard';
import AdminMetrics from './pages/AdminMetrics';
import { 
  LayoutDashboard, 
  TrendingUp, 
  ShieldCheck, 
  LogOut, 
  Loader2,
  Database,
  User,
  Layers,
  Send,
  HelpCircle
} from 'lucide-react';
import { cn } from './lib/utils';

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'value' | 'players' | 'portfolio' | 'acca' | 'admin' | 'teams' | 'how-to-use'>('dashboard');
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);

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

  if (!user) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-6">
        <div className="bg-[#111] border border-zinc-800 p-8 rounded-3xl w-full max-w-sm space-y-6">
          <h2 className="text-2xl font-bold text-white text-center">{isSignUp ? "Sign Up" : "Sign In"}</h2>
          <div className="space-y-4">
            <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 p-4 rounded-xl text-white outline-none focus:border-orange-500" />
            <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 p-4 rounded-xl text-white outline-none focus:border-orange-500" />
          </div>
          <button 
            onClick={async () => {
              if (isSignUp) await supabase.auth.signUp({ email, password });
              else await supabase.auth.signInWithPassword({ email, password });
            }}
            className="w-full bg-orange-500 text-black font-bold py-3 rounded-xl hover:bg-orange-400 transition-colors"
          >
            {isSignUp ? "Sign Up" : "Sign In"}
          </button>
          <button onClick={() => setIsSignUp(!isSignUp)} className="w-full text-zinc-500 text-sm hover:text-white transition-colors">
            {isSignUp ? "Already have an account? Sign In" : "Need an account? Sign Up"}
          </button>
        </div>
      </div>
    );
  }

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
          <NavItem active={activeTab === 'how-to-use'} onClick={() => setActiveTab('how-to-use')} icon={<HelpCircle size={20} />} label="How to Use" />
          {user.email === 'admin@footyedge.ai' && (
            <NavItem active={activeTab === 'admin'} onClick={() => setActiveTab('admin')} icon={<ShieldCheck size={20} />} label="Admin Panel" />
          )}
        </nav>

        <div className="pt-6 border-t border-zinc-800">
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
        {activeTab === 'portfolio' && <Portfolio />}
        {activeTab === 'acca' && <AccaBuilder />}
        {activeTab === 'how-to-use' && <HowToUse />}
        {activeTab === 'admin' && <AdminMetrics />}
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
