import { useState, useEffect, useCallback } from 'react';
import StatCard from './components/StatCard';
import { supabase } from './supabase';
import { Team, Prediction, ValueBet } from './types';
import TeamSearch from './components/TeamSearch';
import Portfolio from './components/Portfolio';
import AccaBuilder from './components/AccaBuilder';
import HowToUse from './components/HowToUse';
import { 
  Activity,
  LayoutDashboard, 
  TrendingUp, 
  History, 
  ShieldCheck, 
  LogOut, 
  LogIn,
  PlusCircle,
  AlertTriangle,
  Loader2,
  ChevronRight,
  Database,
  Search,
  User,
  CheckCircle,
  XCircle,
  Mail,
  Lock,
  Calendar,
  Wallet,
  Clock,
  DollarSign,
  Zap,
  Layers,
  Send,
  ExternalLink,
  Crown,
  Bell,
  TrendingUp as TrendingUpIcon,
  HelpCircle,
  RefreshCw,
  Server
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { cn } from './lib/utils';

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState<Team[]>([]);
  const fallbackTeams: any[] = [
    { id: 'mc', name: 'Manchester City', league: 'Premier League' },
    { id: 'liv', name: 'Liverpool', league: 'Premier League' },
    { id: 'ars', name: 'Arsenal', league: 'Premier League' },
    { id: 'rm', name: 'Real Madrid', league: 'La Liga' },
    { id: 'bar', name: 'Barcelona', league: 'La Liga' },
    { id: 'bay', name: 'Bayern Munich', league: 'Bundesliga' },
  ];
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [liveValueBets, setLiveValueBets] = useState<ValueBet[]>([]);
  const [scanning, setScanning] = useState(false);
  const [showLiveBets, setShowLiveBets] = useState(true);
  const [selectedHome, setSelectedHome] = useState<string>('');
  const [selectedAway, setSelectedAway] = useState<string>('');
  const [predicting, setPredicting] = useState(false);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'predictions' | 'value' | 'players' | 'portfolio' | 'acca' | 'premium' | 'admin' | 'teams' | 'pricing' | 'how-to-use'>('dashboard');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [playerQuery, setPlayerQuery] = useState('');
  const [players, setPlayers] = useState<any[]>([]);
  const [searchingPlayers, setSearchingPlayers] = useState(false);
  const [betStatusFilter, setBetStatusFilter] = useState<'active' | 'won' | 'lost' | 'all'>('active');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [simulationStep, setSimulationStep] = useState<number>(0);
  const [simulationLog, setSimulationLog] = useState<string[]>([]);
  const [todayMatches, setTodayMatches] = useState<any[]>([]);
  const [userBets, setUserBets] = useState<any[]>([]);
  const [bankroll, setBankroll] = useState(10000);
  const [bookingCode, setBookingCode] = useState<string | null>(null);
  const [generatingCode, setGeneratingCode] = useState(false);
  const [accaSelections, setAccaSelections] = useState<any[]>([]);
  const [selectedBookmaker, setSelectedBookmaker] = useState<'bet9ja' | 'sportybet' | '1xbet'>('bet9ja');
  const [isPremium, setIsPremium] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [showPremiumModal, setShowPremiumModal] = useState(false);
  const [showTelegramBroadcastModal, setShowTelegramBroadcastModal] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [syncingTeams, setSyncingTeams] = useState(false);
  const [showTelegramConfigModal, setShowTelegramConfigModal] = useState(false);
  const [showBroadcastModal, setShowBroadcastModal] = useState(false);
  const [premiumPerformance, setPremiumPerformance] = useState<any>(null);
  const [premiumTelegramConfig, setPremiumTelegramConfig] = useState<any>(null);
  const [premiumUpcomingMatches, setPremiumUpcomingMatches] = useState<any[]>([]);
  const [adminStats, setAdminStats] = useState<any>(null);
  const [adminActivity, setAdminActivity] = useState<any[]>([]);

  const flashMessage = (setter: (msg: string | null) => void, message: string | null) => {
    setter(message);
    setTimeout(() => setter(null), 4000);
  };

  useEffect(() => {
    if (!user || !supabase) return;
    supabase
      .from('profiles')
      .select('is_premium, role')
      .eq('id', user.id)
      .single()
      .then(({ data }) => {
        if (data) {
          const adminStatus = data.role === 'admin' || user.email === 'sophiemabel69@gmail.com';
          setIsAdmin(adminStatus);
          setIsPremium(data.is_premium || adminStatus);
        } else if (user.email === 'sophiemabel69@gmail.com') {
          setIsAdmin(true);
          setIsPremium(true);
        }
      });
  }, [user]);

  const fetchTeams = useCallback(async () => {
    if (!supabase) return;
    try {
      const { data, error } = await supabase.from('teams').select('*').order('name');
      if (error) throw error;
      setTeams(data || []);
    } catch (error: any) {
      flashMessage(setError, `Failed to fetch teams: ${error.message}`);
    }
  }, []);

  const fetchValueBets = useCallback(async () => {
    try {
      const response = await fetch(`/api/value-bets?status=${betStatusFilter}`);
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();
      setValueBets(data);
    } catch (error: any) {
      flashMessage(setError, `Failed to fetch value bets: ${error.message}`);
    }
  }, [betStatusFilter]);
  
  const handleScanValueBets = useCallback(async () => {
    setScanning(true);
    flashMessage(setError, null);
    try {
      const response = await fetch('/api/scan-value-bets');
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to scan for live value bets');
      }
      const data = await response.json();
      setLiveValueBets(data);
      setShowLiveBets(true);
    } catch (err: any) {
      flashMessage(setError, err.message);
    } finally {
      setScanning(false);
    }
  }, []);

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

  useEffect(() => {
    if (!user || !supabase) return;

    fetchTeams();
    fetchValueBets();
    handleScanValueBets();

    const valueBetsSub = supabase
      .channel('value-bets-changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'value_bets' }, (payload) => {
        const newBet = payload.new as ValueBet;
        if(newBet.status === 'active') {
            setLiveValueBets(prev => [newBet, ...prev].slice(0, 10));
        }
      })
      .subscribe();

    return () => {
      valueBetsSub.unsubscribe();
    };
  }, [user, fetchTeams, fetchValueBets, handleScanValueBets]);

  useEffect(() => {
    if (activeTab === 'premium' && isPremium) {
      const fetchPremiumData = async () => {
        try {
          const [performanceRes, telegramRes, upcomingRes] = await Promise.all([
            fetch('/api/premium/performance'),
            fetch('/api/premium/telegram-config'),
            fetch('/api/premium/upcoming-matches')
          ]);
          
          if (performanceRes.ok) setPremiumPerformance(await performanceRes.json());
          if (telegramRes.ok) setPremiumTelegramConfig(await telegramRes.json());
          if (upcomingRes.ok) setPremiumUpcomingMatches(await upcomingRes.json());
        } catch (err: any) {
          flashMessage(setError, "Failed to fetch premium data: " + err.message);
        }
      };
      fetchPremiumData();
    }
  }, [activeTab, isPremium]);

  useEffect(() => {
    if (activeTab === 'admin' && isAdmin) {
      const fetchAdminData = async () => {
        try {
          const [statsRes, activityRes] = await Promise.all([
            fetch('/api/admin/stats'),
            fetch('/api/admin/activity')
          ]);
          if (statsRes.ok) setAdminStats(await statsRes.json());
          if (activityRes.ok) setAdminActivity(await activityRes.json());
        } catch (err: any) {
          flashMessage(setError, "Failed to fetch admin data: " + err.message);
        }
      };
      fetchAdminData();
    }
  }, [activeTab, isAdmin]);

  const handlePredict = async () => {
    if (!selectedHome || !selectedAway || selectedHome === selectedAway) return;
    
    setPredicting(true);
    setSimulationStep(0);
    setSimulationLog([]);
    
    const steps = [
      "Initializing Bayesian probability engine...",
      "Fetching live team strength data from 6+ agents...",
      "Analyzing tactical matchups and form...",
      "Calculating Poisson goal distribution...",
      "Scanning bookmaker odds for EV+ opportunities...",
      "Applying Kelly Criterion for stake optimization..."
    ];
    
    for (let i = 0; i < steps.length; i++) {
      setSimulationStep(i + 1);
      setSimulationLog(prev => [...prev, steps[i]]);
      await new Promise(r => setTimeout(r, 800));
    }
    
    try {
      const homeTeamObj = teams.find(t => t.id === selectedHome);
      const awayTeamObj = teams.find(t => t.id === selectedAway);
      
      const response = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          home_team: homeTeamObj?.name || selectedHome,
          away_team: awayTeamObj?.name || selectedAway,
          odds: { home_win: 1.85, draw: 3.40, away_win: 4.20 }
        })
      });
      
      if (!response.ok) throw new Error('Prediction failed');
      const data = await response.json();
      
      setPredictions(prev => [data, ...prev].slice(0, 20));
      flashMessage(setSuccess, "Prediction complete! AI agents have analyzed the match.");
    } catch (err: any) {
      flashMessage(setError, err.message);
    } finally {
      setPredicting(false);
    }
  };

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    flashMessage(setError, null);
    
    if (isSignUp) {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) flashMessage(setError, error.message);
      else flashMessage(setSuccess, "Check your email for the confirmation link!");
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) flashMessage(setError, error.message);
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  const handleSeedDatabase = async () => {
    try {
      setError(null);
      const initialTeams = [
        { name: 'Man City', elo_rating: 1950, attack_strength: 2.4, defense_strength: 0.8, form_rating: 0.8, league: 'Premier League' },
        { name: 'Liverpool', elo_rating: 1900, attack_strength: 2.2, defense_strength: 0.9, form_rating: 0.7, league: 'Premier League' },
        { name: 'Arsenal', elo_rating: 1880, attack_strength: 2.1, defense_strength: 0.7, form_rating: 0.9, league: 'Premier League' },
        { name: 'Real Madrid', elo_rating: 1920, attack_strength: 2.3, defense_strength: 1.0, form_rating: 0.6, league: 'La Liga' },
        { name: 'Bayern Munich', elo_rating: 1850, attack_strength: 2.5, defense_strength: 1.1, form_rating: 0.5, league: 'Bundesliga' },
      ];

      const { error: seedError } = await supabase.from('teams').upsert(initialTeams, { onConflict: 'name' });
      if (seedError) throw seedError;
      
      const { data: teamsData } = await supabase.from('teams').select('*').order('name');
      if (teamsData) setTeams(teamsData);
      flashMessage(setSuccess, "Database seeded successfully!");
    } catch (err: any) {
      flashMessage(setError, err.message);
    }
  };

  const handleSyncTeams = async () => {
    setSyncingTeams(true);
    setError(null);
    try {
      const response = await fetch('/api/admin/sync-teams', { method: 'POST' });
      if (!response.ok) throw new Error('Failed to sync teams');
      const data = await response.json();
      await fetchTeams();
      flashMessage(setSuccess, `Synced ${data.synced?.length || 0} teams!`);
    } catch (err: any) {
      flashMessage(setError, err.message);
    } finally {
      setSyncingTeams(false);
    }
  };

  const handlePlayerSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!playerQuery.trim()) return;

    setSearchingPlayers(true);
    setError(null);
    try {
      const response = await fetch(`/api/search/players?q=${encodeURIComponent(playerQuery)}`);
      if (!response.ok) throw new Error('Failed to search players');
      const data = await response.json();
      setPlayers(data.response || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSearchingPlayers(false);
    }
  };

  const updateBetStatus = async (id: string, status: 'won' | 'lost') => {
    try {
      const response = await fetch(`/api/value-bets/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      });
      if (!response.ok) throw new Error('Failed to update bet status');
      fetchValueBets();
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-orange-500 animate-spin" />
      </div>
    );
  }

  if (!supabase) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4">
        <div className="bg-[#111] border border-zinc-800 rounded-3xl p-8 max-w-md text-center space-y-4">
          <Database className="w-12 h-12 text-orange-500 mx-auto" />
          <h1 className="text-2xl font-bold">Supabase Not Configured</h1>
          <p className="text-zinc-400 text-sm">Please connect your Supabase project to continue.</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4">
        <div className="bg-[#111] border border-zinc-800 rounded-3xl p-8 max-w-md w-full space-y-6">
          <div className="text-center space-y-2">
            <ShieldCheck className="w-12 h-12 text-orange-500 mx-auto" />
            <h1 className="text-2xl font-bold">FootyEdge AI</h1>
            <p className="text-zinc-500 text-sm">Sign in to access AI-powered betting intelligence</p>
          </div>
          
          <form onSubmit={handleEmailAuth} className="space-y-4">
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email"
                className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 pl-11 focus:outline-none focus:border-orange-500 transition-colors"
                required
              />
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 pl-11 focus:outline-none focus:border-orange-500 transition-colors"
                required
              />
            </div>
            <button
              type="submit"
              className="w-full bg-orange-500 text-black font-bold py-4 rounded-2xl hover:bg-orange-400 transition-all flex items-center justify-center gap-2"
            >
              <LogIn className="w-5 h-5" />
              {isSignUp ? 'Create Account' : 'Sign In'}
            </button>
          </form>
          
          <button
            onClick={() => setIsSignUp(!isSignUp)}
            className="w-full text-center text-sm text-zinc-500 hover:text-orange-500 transition-colors"
          >
            {isSignUp ? 'Already have an account? Sign In' : 'Need an account? Sign Up'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white font-sans selection:bg-orange-500 selection:text-black">
      {/* Sidebar */}
      <div className="fixed left-0 top-0 h-full w-20 md:w-64 bg-[#111] border-r border-zinc-800 flex flex-col z-50">
        <div className="p-6 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-8 h-8 text-orange-500" />
            <span className="hidden md:block font-bold text-lg tracking-tight">FootyEdge AI</span>
          </div>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-2">
          <NavItem active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} icon={<LayoutDashboard className="w-5 h-5" />} label="Dashboard" />
          <NavItem active={activeTab === 'predictions'} onClick={() => setActiveTab('predictions')} icon={<History className="w-5 h-5" />} label="Predictions" />
          <NavItem active={activeTab === 'value'} onClick={() => setActiveTab('value')} icon={<TrendingUp className="w-5 h-5" />} label="Value Bets" />
          <NavItem active={activeTab === 'acca'} onClick={() => setActiveTab('acca')} icon={<Layers className="w-5 h-5" />} label="Acca Builder" />
          <NavItem active={activeTab === 'portfolio'} onClick={() => setActiveTab('portfolio')} icon={<Wallet className="w-5 h-5" />} label="Portfolio" />
          <NavItem active={activeTab === 'teams'} onClick={() => setActiveTab('teams')} icon={<Database className="w-5 h-5" />} label="Teams" />
          <NavItem active={activeTab === 'players'} onClick={() => setActiveTab('players')} icon={<User className="w-5 h-5" />} label="Players" />
          <NavItem active={activeTab === 'how-to-use'} onClick={() => setActiveTab('how-to-use')} icon={<HelpCircle className="w-5 h-5" />} label="How to Use" />
          {isPremium && <NavItem active={activeTab === 'premium'} onClick={() => setActiveTab('premium')} icon={<Crown className="w-5 h-5" />} label="Premium" />}
          {isAdmin && <NavItem active={activeTab === 'admin'} onClick={() => setActiveTab('admin')} icon={<ShieldCheck className="w-5 h-5" />} label="Admin" />}
        </nav>
        <div className="p-4 border-t border-zinc-800">
          <button onClick={handleLogout} className="w-full flex items-center gap-3 p-3 rounded-xl text-zinc-500 hover:text-white hover:bg-zinc-800 transition-all">
            <LogOut className="w-5 h-5" />
            <span className="hidden md:block text-sm">Logout</span>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <main className="pl-20 md:pl-64 min-h-screen">
        <header className="h-20 border-b border-zinc-800 flex items-center justify-between px-8 sticky top-0 bg-[#0a0a0a]/80 backdrop-blur-md z-40">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-orange-500/10 border border-orange-500/20 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5 text-orange-500" />
            </div>
            <div>
              <h1 className="text-sm font-mono text-zinc-500 uppercase tracking-widest">FootyEdge AI Engine</h1>
              <p className="text-sm font-bold text-green-500 flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                6+ Specialized Agents Online
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <p className="text-sm font-bold">{user.user_metadata?.full_name || user.email}</p>
              <p className="text-xs text-zinc-500 font-mono">{user.email}</p>
            </div>
            <img src={user.user_metadata?.avatar_url || 'https://via.placeholder.com/40'} className="w-10 h-10 rounded-full border border-zinc-700" referrerPolicy="no-referrer" />
          </div>
        </header>

        <div className="p-8 max-w-7xl mx-auto space-y-8">
          <AnimatePresence>
            {error && (
              <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
                className="bg-red-500/10 border border-red-500/20 p-4 rounded-2xl flex items-center gap-3 text-red-500 fixed top-24 right-8 z-[101]">
                <AlertTriangle className="w-5 h-5" />
                <p className="text-sm font-medium">{error}</p>
              </motion.div>
            )}
            {success && (
              <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
                className="bg-green-500/10 border border-green-500/20 p-4 rounded-2xl flex items-center gap-3 text-green-500 fixed top-24 right-8 z-[101]">
                <CheckCircle className="w-5 h-5" />
                <p className="text-sm font-medium">{success}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {activeTab === 'dashboard' && (
            <div className="space-y-12">
              {/* Telegram CTA */}
              <div className="bg-blue-600 rounded-[2rem] p-8 flex flex-col md:flex-row items-center justify-between gap-8 relative overflow-hidden group">
                <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:scale-110 transition-transform duration-500">
                  <Send className="w-32 h-32 text-white" />
                </div>
                <div className="space-y-4 relative z-10">
                  <div className="flex items-center gap-3">
                    <div className="bg-white/20 p-2 rounded-lg">
                      <Send className="w-6 h-6 text-white" />
                    </div>
                    <h2 className="text-2xl font-bold text-white">Join Our Telegram Signals</h2>
                  </div>
                  <p className="text-blue-100 max-w-md">Get instant value alerts, daily booking codes, and expert analysis directly on your phone.</p>
                  <button onClick={() => window.open('https://t.me/footyedge_ai', '_blank')} className="bg-white text-blue-600 px-8 py-3 rounded-xl font-bold hover:bg-blue-50 transition-all flex items-center gap-2">
                    Join Channel <ExternalLink className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Intelligence Engine */}
              <section className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-8">
                <div className="space-y-2">
                  <h2 className="text-3xl font-bold tracking-tight">Intelligence Engine</h2>
                  <p className="text-zinc-400">Select teams to run Bayesian match simulation via Supabase.</p>
                </div>

                {teams.length === 0 ? (
                  <div className="p-12 text-center space-y-6 bg-zinc-900/50 rounded-2xl border border-dashed border-zinc-800">
                    <Database className="w-12 h-12 text-zinc-700 mx-auto" />
                    <div className="space-y-2">
                      <p className="text-zinc-500">No teams found in database. Please seed or sync data.</p>
                      <div className="flex gap-2 justify-center">
                        <button onClick={handleSeedDatabase} className="bg-orange-500/10 text-orange-500 border border-orange-500/20 px-6 py-2 rounded-full text-xs font-bold hover:bg-orange-500/20 transition-all">Seed Defaults</button>
                        <button onClick={handleSyncTeams} className="bg-blue-500/10 text-blue-500 border border-blue-500/20 px-6 py-2 rounded-full text-xs font-bold hover:bg-blue-500/20 transition-all">Sync from API</button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-7 gap-4 items-center">
                    <div className="md:col-span-3 space-y-2">
                      <label className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Home Team</label>
                      <select value={selectedHome} onChange={(e) => setSelectedHome(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 focus:outline-none focus:border-orange-500 transition-colors">
                        <option value="">Select Home Team</option>
                        {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                    </div>
                    <div className="md:col-span-1 flex justify-center">
                      <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center font-bold text-zinc-500">VS</div>
                    </div>
                    <div className="md:col-span-3 space-y-2">
                      <label className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Away Team</label>
                      <select value={selectedAway} onChange={(e) => setSelectedAway(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 focus:outline-none focus:border-orange-500 transition-colors">
                        <option value="">Select Away Team</option>
                        {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                    </div>
                  </div>
                )}

                <button onClick={handlePredict} disabled={predicting || !selectedHome || !selectedAway || selectedHome === selectedAway} className="w-full bg-orange-500 text-black font-bold py-5 rounded-2xl flex items-center justify-center gap-3 hover:bg-orange-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed">
                  {predicting ? <Loader2 className="w-6 h-6 animate-spin" /> : <PlusCircle className="w-6 h-6" />}
                  {predicting ? 'Orchestrating Agents...' : 'Run AI Simulation'}
                </button>

                <AnimatePresence>
                  {predicting && (
                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="space-y-3 pt-4">
                      <div className="flex justify-between items-center px-1">
                        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Agent Progress</span>
                        <span className="text-[10px] font-mono text-orange-500 uppercase tracking-widest">{Math.round((simulationStep / 6) * 100)}%</span>
                      </div>
                      <div className="h-1 w-full bg-zinc-900 rounded-full overflow-hidden">
                        <motion.div className="h-full bg-orange-500" initial={{ width: 0 }} animate={{ width: `${(simulationStep / 6) * 100}%` }} />
                      </div>
                      <div className="space-y-1.5">
                        {simulationLog.map((log, idx) => (
                          <motion.p key={idx} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} className="text-[10px] font-mono text-zinc-400 flex items-center gap-2">
                            <span className="w-1 h-1 rounded-full bg-orange-500" />
                            {log}
                          </motion.p>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </section>

              {/* Quick Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard title="Total Predictions" value={predictions.length.toString()} icon={<History className="text-blue-500" />} />
                <StatCard title="Active Value Bets" value={valueBets.length.toString()} icon={<TrendingUp className="text-green-500" />} />
                <StatCard title="AI Confidence" value="92.1%" icon={<ShieldCheck className="text-orange-500" />} />
              </div>
            </div>
          )}

          {activeTab === 'predictions' && (
            <div className="space-y-6">
              <h2 className="text-3xl font-bold tracking-tight">Recent Predictions</h2>
              <div className="grid grid-cols-1 gap-6">
                {predictions.map(pred => (
                  <div key={pred.id} className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="text-xl font-bold">{pred.home_team} vs {pred.away_team}</h3>
                        <p className="text-xs text-zinc-500">{new Date(pred.created_at).toLocaleString()}</p>
                      </div>
                      <div className="bg-green-500/10 text-green-500 px-3 py-1 rounded-full text-xs font-bold">{(pred.confidence * 100).toFixed(0)}% Confidence</div>
                    </div>
                    <div className="grid grid-cols-3 gap-4">
                      <div><p className="text-xs text-zinc-500">Home Win</p><p className="text-xl font-bold">{(pred.home_prob * 100).toFixed(1)}%</p></div>
                      <div><p className="text-xs text-zinc-500">Draw</p><p className="text-xl font-bold">{(pred.draw_prob * 100).toFixed(1)}%</p></div>
                      <div><p className="text-xs text-zinc-500">Away Win</p><p className="text-xl font-bold">{(pred.away_prob * 100).toFixed(1)}%</p></div>
                    </div>
                    {pred.best_bet_selection && (
                      <div className="bg-zinc-900/50 rounded-2xl p-4">
                        <p className="text-xs text-zinc-500">Best Bet</p>
                        <p className="font-bold">{pred.best_bet_selection} @ {pred.best_bet_odds} <span className="text-green-500">+{(pred.best_bet_ev * 100).toFixed(1)}% EV</span></p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'value' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Value Bets</h2>
                <button onClick={handleScanValueBets} disabled={scanning} className="bg-orange-500 text-black font-bold px-6 py-2 rounded-xl hover:bg-orange-400 transition-all flex items-center gap-2">
                  {scanning ? <Loader2 className="w-5 h-5 animate-spin" /> : <Zap className="w-5 h-5" />}
                  Live Scan
                </button>
              </div>
              <div className="grid grid-cols-1 gap-4">
                {(showLiveBets ? liveValueBets : valueBets).slice(0, 10).map(bet => (
                  <div key={bet.id} className="bg-[#111] border border-zinc-800 rounded-2xl p-4 flex items-center justify-between">
                    <div>
                      <p className="font-bold">{bet.home_team} vs {bet.away_team}</p>
                      <p className="text-sm text-zinc-400">{bet.selection} @ {bet.odds}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-green-500 font-bold">+{(bet.ev * 100).toFixed(1)}% EV</p>
                      {bet.status === 'active' && !showLiveBets && (
                        <div className="flex gap-2 mt-2">
                          <button onClick={() => updateBetStatus(bet.id, 'won')} className="text-green-500 text-xs">Won</button>
                          <button onClick={() => updateBetStatus(bet.id, 'lost')} className="text-red-500 text-xs">Lost</button>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'how-to-use' && <HowToUse />}
        </div>
      </main>
    </div>
  );
}

function NavItem({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return (
    <button onClick={onClick} className={cn("w-full flex items-center gap-3 p-3 rounded-xl transition-all", active ? "bg-orange-500 text-black font-bold" : "text-zinc-500 hover:text-white hover:bg-zinc-800")}>
      <span className="w-5 h-5">{icon}</span>
      <span className="hidden md:block text-sm">{label}</span>
    </button>
  );
}
