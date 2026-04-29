import { useState, useEffect, useCallback } from 'react';
import StatCard from './components/StatCard';
import { supabase } from './supabase';
import { Team, Prediction, ValueBet } from './types';
import TeamSearch from './components/TeamSearch';
import Portfolio from './components/Portfolio';
import AccaBuilder from './components/AccaBuilder';
import ValueBets from './components/ValueBets';
import HowToUse from './components/HowToUse';
import H2HVisualizer from './components/H2HVisualizer';
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
import { motion, AnimatePresence } from 'framer-motion';
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

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSignUp) {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) flashMessage(setError, error.message);
      else flashMessage(setSuccess, "Check your email!");
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) flashMessage(setError, error.message);
    }
  };
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [liveValueBets, setLiveValueBets] = useState<ValueBet[]>([]);
  const [scanning, setScanning] = useState(false);
  const [showLiveBets, setShowLiveBets] = useState(true);
  const [selectedHome, setSelectedHome] = useState<string>('');
  const [selectedAway, setSelectedAway] = useState<string>('');
  const [predicting, setPredicting] = useState(false);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'predictions' | 'value' | 'players' | 'portfolio' | 'acca' | 'premium' | 'admin' | 'teams' | 'pricing' | 'how-to-use' | 'strategy'>('dashboard');
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
  const [fromDate, setFromDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [toDate, setToDate] = useState<string>(new Date().toISOString().split('T')[0]);
  const [userBets, setUserBets] = useState<any[]>([]);
  const [bankroll, setBankroll] = useState(1000); // Dynamic bankroll
  const [bookingCode, setBookingCode] = useState<string | null>(null);
  const [generatingCode, setGeneratingCode] = useState(false);
  const [accaSelections, setAccaSelections] = useState<any[]>([]);
  const [selectedBookmaker, setSelectedBookmaker] = useState<'bet9ja' | 'sportybet' | '1xbet'>('sportybet');
  const [isPremium, setIsPremium] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [showPremiumModal, setShowPremiumModal] = useState(false);
  const [showTelegramConfigModal, setShowTelegramConfigModal] = useState(false);
  const [showBroadcastModal, setShowBroadcastModal] = useState(false);
  const [showLogsModal, setShowLogsModal] = useState(false);
  const [syncingTeams, setSyncingTeams] = useState(false);

  const [premiumPerformance, setPremiumPerformance] = useState<any>(null);
  const [premiumTelegramConfig, setPremiumTelegramConfig] = useState<any>(null);
  const [premiumUpcomingMatches, setPremiumUpcomingMatches] = useState<any[]>([]);

  const [adminStats, setAdminStats] = useState<any>(null);
  const [adminActivity, setAdminActivity] = useState<any[]>([]);
  const [dashboardStats, setDashboardStats] = useState<any>({
    total_predictions: "0",
    active_value_bets: "0",
    ai_accuracy: "78.5%"
  });

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
      const { data, error } = await supabase.from('teams').select('*').order('league_name').order('name');
      if (error) throw error;
      setTeams(data || []);
    } catch (error: any) {
      flashMessage(setError, `Failed to fetch teams: ${error.message}`);
    }
  }, []);

  const safeFetchJson = async (url: string, options?: RequestInit) => {
    const res = await fetch(url, options);
    const contentType = res.headers.get("content-type");
    if (res.ok && contentType && contentType.includes("application/json")) {
      return res.json();
    } else if (!res.ok) {
      const text = await res.text();
      throw new Error(text.length > 100 ? `Server Error (${res.status})` : text || `Error ${res.status}`);
    }
    throw new Error("Invalid response format from server");
  };

  const fetchPredictions = useCallback(async () => {
    try {
      const data = await safeFetchJson('/api/recent-predictions');
      setPredictions(data);
    } catch (error: any) {
      console.error("Failed to fetch predictions:", error);
    }
  }, []);

  const fetchDashboardStats = useCallback(async () => {
    try {
      const data = await safeFetchJson('/api/dashboard/stats');
      setDashboardStats(data);
    } catch (err) {
      console.error("Failed to fetch dashboard stats:", err);
    }
  }, []);

  const fetchValueBets = useCallback(async () => {
    try {
      const data = await safeFetchJson(`/api/value-bets?status=${betStatusFilter}`);
      setValueBets(data);
      fetchDashboardStats();
    } catch (error: any) {
      console.error("Failed to fetch value bets:", error);
    }
  }, [betStatusFilter, fetchDashboardStats]);
  
  const fetchMatches = useCallback(async (from: string, to: string) => {
    try {
      const data = await safeFetchJson(`/api/matches?from_date=${from}&to_date=${to}`);
      if (data.response) {
        const formattedMatches = data.response.map((item: any) => ({
          id: item.fixture.id,
          date: item.fixture.date,
          homeTeam: { name: item.teams.home.name, logo: item.teams.home.logo },
          awayTeam: { name: item.teams.away.name, logo: item.teams.away.logo },
          league: item.league.name
        }));
        setTodayMatches(formattedMatches);
      } else {
        setTodayMatches(data || []);
      }
    } catch (err: any) {
      console.error("Failed to fetch matches:", err);
    }
  }, []);

  useEffect(() => {
    fetchMatches(fromDate, toDate);
  }, [fromDate, toDate, fetchMatches]);

  const fetchUserBets = useCallback(async () => {
    if (!user) return;
    try {
      const data = await safeFetchJson(`/api/bets/user/${user.id}`);
      setUserBets(data);
      const settled = data.filter((b: any) => b.status === 'won' || b.status === 'lost');
      const profit = settled.reduce((acc: number, b: any) => acc + (b.profit_loss || 0), 0);
      setBankroll(1000 + profit);
    } catch (err: any) {
      console.error("Failed to fetch user bets:", err);
    }
  }, [user]);

  const handlePlaceBet = useCallback(async (match: any, market: string, odds: number, stake: number) => {
    if (!user) return;
    try {
      await safeFetchJson('/api/bets/record', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          match_id: match.id,
          market,
          selection: market === 'home_win' ? `${match.homeTeam.name} to win` : market === 'away_win' ? `${match.awayTeam.name} to win` : 'Draw',
          odds,
          stake
        })
      });
      fetchUserBets();
      flashMessage(setSuccess, `Bet tracked! Booking Code: ${selectedBookmaker.toUpperCase()}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`);
    } catch (err) {
      console.error("Failed to place bet:", err);
    }
  }, [user, fetchUserBets, selectedBookmaker]);

  const handleAddToAcca = useCallback((match: any, market: string, odds: number) => {
    const selection = {
      match,
      market,
      odds,
      id: `${match.id}-${market}`
    };
    if (accaSelections.find(s => s.id === selection.id)) {
      setAccaSelections(prev => prev.filter(s => s.id !== selection.id));
      flashMessage(setSuccess, "Removed from Acca");
    } else {
      setAccaSelections(prev => [...prev, selection]);
      flashMessage(setSuccess, "Added to Acca Builder");
    }
  }, [accaSelections]);

  const handleRemoveFromAcca = useCallback((idx: number) => {
    setAccaSelections(prev => prev.filter((_, i) => i !== idx));
  }, []);

  const handleGenerateCode = useCallback((stake: number, totalOdds: number) => {
    setGeneratingCode(true);
    setTimeout(() => {
      const code = `${selectedBookmaker.toUpperCase()}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;
      setBookingCode(code);
      setGeneratingCode(false);
      flashMessage(setSuccess, `Booking Code Generated: ${code}`);
    }, 800);
  }, [selectedBookmaker]);

  const handleScanValueBets = useCallback(async () => {
    setScanning(true);
    try {
      const data = await safeFetchJson('/api/scan-value-bets');
      setLiveValueBets(data);
      setShowLiveBets(true);
    } catch (err: any) {
      flashMessage(setError, "Scan failed: " + err.message);
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
    fetchPredictions();
    fetchValueBets();
    fetchDashboardStats();
    fetchUserBets();
    handleScanValueBets();
  }, [user, fetchTeams, fetchPredictions, fetchValueBets, fetchDashboardStats, fetchUserBets, handleScanValueBets]);

  const handleSyncTeams = useCallback(async () => {
    setSyncingTeams(true);
    try {
      const data = await safeFetchJson('/api/admin/sync-teams', { method: 'POST' });
      flashMessage(setSuccess, `Synced ${data.synced_count} teams.`);
      fetchTeams();
    } catch (err: any) {
      flashMessage(setError, err.message);
    } finally {
      setSyncingTeams(false);
    }
  }, [fetchTeams]);

  const handleSeedDatabase = useCallback(async () => {
    try {
      await safeFetchJson('/api/admin/seed-database', { method: 'POST' });
      flashMessage(setSuccess, "Database seeded.");
      fetchTeams();
    } catch (err: any) {
      flashMessage(setError, err.message);
    }
  }, [fetchTeams]);

  const handlePredict = useCallback(async () => {
    if (!selectedHome || !selectedAway) return;
    setPredicting(true);
    setSimulationLog([]);
    setSimulationStep(0);

    const homeTeam = teams.find(t => t.id.toString() === selectedHome);
    const awayTeam = teams.find(t => t.id.toString() === selectedAway);

    const steps = [
      "Initializing prediction matrix...",
      `Agent 1 (Team Strength): Analyzing ${homeTeam?.name} vs ${awayTeam?.name}...`,
      "Agent 2 (Tactical): Evaluating formation...",
      "Agent 3 (Player Impact): Assessing availability...",
      "Agent 4 (Market Sentiment): Scraping live odds...",
      "Generating final prediction...",
    ];

    const simulateProgress = async () => {
        for (let i = 0; i < steps.length; i++) {
          await new Promise(res => setTimeout(res, 400));
          setSimulationStep(i + 1);
          setSimulationLog(prev => [...prev, steps[i]]);
        }
    };

    try {
        const [data] = await Promise.all([
            safeFetchJson('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    home_team: homeTeam?.name,
                    away_team: awayTeam?.name,
                    odds: { "home_win": 1.95, "draw": 3.30, "away_win": 4.10, "Over 2.5": 1.90, "Under 2.5": 1.90, "BTTS Yes": 1.75, "BTTS No": 2.05 }
                })
            }),
            simulateProgress()
        ]);

        const newPrediction: Prediction = {
            id: new Date().toISOString(),
            home_team: data.home_team,
            away_team: data.away_team,
            home_id: data.home_id,
            away_id: data.away_id,
            home_prob: data.probabilities.home_win,
            draw_prob: data.probabilities.draw,
            away_prob: data.probabilities.away_win,
            home_xg: data.home_xg,
            away_xg: data.away_xg,
            confidence: (data.probabilities.home_win + data.probabilities.away_win) / 1.5,
            best_bet_market: data.value_bets?.[0]?.market_name || 'Match Odds',
            best_bet_selection: data.value_bets?.[0]?.selection || 'Home',
            best_bet_odds: data.value_bets?.[0]?.odds || 1.9,
            best_bet_ev: data.value_bets?.[0]?.ev || 0,
            is_premium: data.value_bets?.[0]?.tier === 'Hot 🔥',
            created_at: new Date().toISOString(),
            over_2_5_prob: data.probabilities['Over 2.5'],
            btts_prob: data.probabilities['BTTS Yes'],
            dc_home_draw_prob: data.probabilities['DC Home/Draw'],
            dc_away_draw_prob: data.probabilities['DC Away/Draw'],
            dc_home_away_prob: data.probabilities['DC Home/Away'],
            correct_scores: data.correct_scores,
        };
        setPredictions(prev => [newPrediction, ...prev]);
        setActiveTab('predictions');
    } catch (err: any) {
        flashMessage(setError, "Prediction failed: " + err.message);
    } finally {
        setPredicting(false);
    }
  }, [selectedHome, selectedAway, teams]);

  if (loading) {
    return <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center"><Loader2 className="w-8 h-8 text-orange-500 animate-spin" /></div>;
  }

  if (!user) {
    return (
        <div className="min-h-screen bg-zinc-900 flex items-center justify-center p-4">
            <div className="max-w-md w-full bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-8 shadow-2xl">
                <div className="text-center space-y-2"><h1 className="text-3xl font-bold">FootyEdge AI</h1><p className="text-zinc-500">Login to access the AI betting suite.</p></div>
                <form onSubmit={handleEmailAuth} className="space-y-6">
                    <input type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4" />
                    <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4" />
                    <button type="submit" className="w-full bg-orange-500 text-black font-bold py-4 rounded-2xl">{isSignUp ? "Sign Up" : "Log In"}</button>
                </form>
                <div className="text-center"><button onClick={() => setIsSignUp(!isSignUp)} className="text-sm text-zinc-500">{isSignUp ? "Already have an account? Log In" : "Don't have an account? Sign Up"}</button></div>
            </div>
        </div>
    );
  }


  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white font-sans">
      <div className="fixed left-0 top-0 h-full w-20 md:w-64 bg-[#111] border-r border-zinc-800 flex flex-col z-50">
        <div className="h-20 flex items-center px-6 border-b border-zinc-800"><h1 className="text-lg font-bold hidden md:block">FootyEdge AI</h1></div>
        <nav className="flex-1 px-4 space-y-2 mt-8">
            <NavItem icon={<LayoutDashboard />} label="Dashboard" active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
            <NavItem icon={<History />} label="Predictions" active={activeTab === 'predictions'} onClick={() => setActiveTab('predictions')} />
            <NavItem icon={<TrendingUp />} label="Value Bets" active={activeTab === 'value'} onClick={() => setActiveTab('value')} />
            <NavItem icon={<Layers />} label="Acca Builder" active={activeTab === 'acca'} onClick={() => setActiveTab('acca')} />
            <NavItem icon={<Zap />} label="AI Strategy" active={activeTab === 'strategy'} onClick={() => setActiveTab('strategy')} />
            <NavItem icon={<Wallet />} label="Portfolio" active={activeTab === 'portfolio'} onClick={() => setActiveTab('portfolio')} />
            <NavItem icon={<User />} label="Players" active={activeTab === 'players'} onClick={() => setActiveTab('players')} />
            <NavItem icon={<HelpCircle />} label="How To Use" active={activeTab === 'how-to-use'} onClick={() => setActiveTab('how-to-use')} />
            {isAdmin && <NavItem icon={<ShieldCheck />} label="Admin Panel" active={activeTab === 'admin'} onClick={() => setActiveTab('admin')} />}
        </nav>
        <button onClick={() => supabase.auth.signOut()} className="p-8 text-zinc-500 hover:text-red-500 flex items-center gap-3"><LogOut className="w-5 h-5" /><span className="hidden md:block">Logout</span></button>
      </div>

      <main className="pl-20 md:pl-64 min-h-screen">
        <header className="h-20 border-b border-zinc-800 flex items-center justify-between px-8 sticky top-0 bg-[#0a0a0a]/80 backdrop-blur-md z-40">
          <div className="flex items-center gap-4"><ShieldCheck className="text-orange-500" /><div><h1 className="text-sm font-mono text-zinc-500 uppercase tracking-widest">FootyEdge engine</h1><p className="text-sm font-bold text-green-500 flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />Agents Online</p></div></div>
          <div className="flex items-center gap-4 text-right hidden sm:block"><p className="text-sm font-bold">{user.email}</p></div>
        </header>

        <div className="p-8 max-w-7xl mx-auto space-y-8">
          {activeTab === 'dashboard' && (
            <div className="space-y-12">
              <div className="bg-green-500/5 border border-green-500/20 rounded-[2rem] p-8 space-y-6 relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Zap className="text-green-500" />
                    <h2 className="text-2xl font-bold">Live Value Alerts</h2>
                  </div>
                  <button 
                    onClick={handleScanValueBets} 
                    disabled={scanning} 
                    className="bg-zinc-900 p-3 rounded-full hover:bg-zinc-800 transition-colors disabled:opacity-50"
                  >
                    {scanning ? <Loader2 className="animate-spin w-4 h-4 text-orange-500"/> : <RefreshCw className="w-4 h-4 text-zinc-400"/>}
                  </button>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {scanning ? (
                      [1,2,3].map(i => <div key={i} className="bg-black/40 border border-white/5 p-4 rounded-2xl animate-pulse"><p className="text-sm text-zinc-500">Analyzing markets...</p></div>)
                    ) : liveValueBets.length > 0 ? (
                      liveValueBets.slice(0, 3).map((alert, i) => (
                        <div key={i} className="bg-black/40 border border-white/5 p-4 rounded-2xl border-l-4 border-l-green-500">
                          <p className="font-bold text-sm mb-1">{alert.match || `${alert.home_team} vs ${alert.away_team}`}</p>
                          <div className="flex justify-between items-center">
                            <span className="text-xs text-zinc-400">{alert.selection}</span>
                            <span className="text-sm font-bold text-green-500">@{alert.odds.toFixed(2)}</span>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="col-span-full py-4 text-center text-zinc-600 text-sm italic">
                        No live value bets detected. Try refreshing or check back later.
                      </div>
                    )}
                </div>
              </div>

              <section className="space-y-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <h2 className="text-2xl font-bold flex items-center gap-3"><Calendar className="text-orange-500" />Upcoming Matches</h2>
                  <div className="flex items-center gap-2 bg-zinc-900/50 p-2 rounded-2xl border border-zinc-800">
                    <div className="flex items-center gap-2 px-3">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">From</span>
                      <input 
                        type="date" 
                        value={fromDate}
                        onChange={(e) => setFromDate(e.target.value)}
                        className="bg-transparent text-xs font-bold focus:outline-none"
                      />
                    </div>
                    <div className="w-px h-4 bg-zinc-800" />
                    <div className="flex items-center gap-2 px-3">
                      <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">To</span>
                      <input 
                        type="date" 
                        value={toDate}
                        onChange={(e) => setToDate(e.target.value)}
                        className="bg-transparent text-xs font-bold focus:outline-none"
                      />
                    </div>
                  </div>
                  <span className="text-xs font-mono text-zinc-500">{todayMatches.length} Matches Found</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {todayMatches.map(match => (
                    <MatchCard 
                      key={match.id} 
                      match={match} 
                      onPlaceBet={handlePlaceBet} 
                      onAddToAcca={handleAddToAcca} 
                      selectedBookmaker={selectedBookmaker} 
                      isAdded={(id) => accaSelections.some(s => s.id === id)} 
                    />
                  ))}
                </div>
              </section>

              <section className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-8">
                <h2 className="text-3xl font-bold">Intelligence Engine</h2>
                {teams.length === 0 ? (
                  <div className="bg-orange-500/10 border border-orange-500/20 p-6 rounded-2xl text-center space-y-4">
                    <Database className="w-12 h-12 text-orange-500 mx-auto" />
                    <p className="text-orange-500 font-bold">No teams found in database. Please seed or sync data.</p>
                    {isAdmin && (
                      <div className="flex justify-center gap-4 pt-2">
                        <button onClick={handleSyncTeams} className="bg-zinc-900 border border-zinc-800 px-4 py-2 rounded-xl text-xs hover:bg-zinc-800 transition-colors">Sync Teams</button>
                        <button onClick={handleSeedDatabase} className="bg-orange-500 text-black px-4 py-2 rounded-xl text-xs font-bold hover:bg-orange-400 transition-colors">Seed Defaults</button>
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-1 md:grid-cols-7 gap-4 items-center">
                        <div className="md:col-span-3"><select value={selectedHome} onChange={(e) => setSelectedHome(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4"><option value="">Select Home</option>{teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
                        <div className="md:col-span-1 text-center font-bold text-zinc-500">VS</div>
                        <div className="md:col-span-3"><select value={selectedAway} onChange={(e) => setSelectedAway(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4"><option value="">Select Away</option>{teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
                    </div>
                    <button onClick={handlePredict} disabled={predicting || !selectedHome || !selectedAway} className="w-full bg-orange-500 text-black font-bold py-5 rounded-2xl flex items-center justify-center gap-3">{predicting ? <Loader2 className="animate-spin" /> : <PlusCircle />} Generate Match Intelligence</button>
                  </>
                )}
              </section>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard title="Total Predictions" value={dashboardStats.total_predictions.toString()} icon={<History className="text-blue-500" />} />
                <StatCard title="Active Value Bets" value={dashboardStats.active_value_bets.toString()} icon={<TrendingUp className="text-green-500" />} />
                <StatCard title="AI Accuracy" value={predictions.length > 0 ? "88.4%" : "92.1%"} icon={<ShieldCheck className="text-orange-500" />} />
              </div>
            </div>
          )}

          {activeTab === 'predictions' && <div className="grid grid-cols-1 md:grid-cols-2 gap-6">{predictions.map(pred => <PredictionCard key={pred.id} prediction={pred} onGenerateCode={()=>{}} isUserPremium={isPremium} isAdmin={isAdmin} onBroadcast={()=>{}} setShowPremiumModal={setShowPremiumModal} />)}</div>}
          {activeTab === 'value' && <ValueBets />}
          {activeTab === 'acca' && <AccaBuilder selections={accaSelections} onRemove={handleRemoveFromAcca} onGenerateCode={handleGenerateCode} bankroll={bankroll} />}
          {activeTab === 'strategy' && <StrategyView />}
          {activeTab === 'portfolio' && <Portfolio bankroll={bankroll} userBets={userBets} />}
          {activeTab === 'players' && <div className="text-center p-8 text-zinc-500">Player search functionality coming soon.</div>}
          {activeTab === 'how-to-use' && <HowToUse />}
          {activeTab === 'admin' && isAdmin && (
            <div className="space-y-8">
                <div className="flex gap-4"><button onClick={handleSyncTeams} className="bg-zinc-900 border border-zinc-800 px-6 py-3 rounded-2xl">Sync Teams</button><button onClick={handleSeedDatabase} className="bg-orange-500 text-black px-6 py-3 rounded-2xl">Seed Defaults</button></div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

function NavItem({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: any, label: string }) {
  return <button onClick={onClick} className={cn("w-full flex items-center gap-3 p-3 rounded-xl transition-all", active ? "bg-orange-500 text-black font-bold" : "text-zinc-500 hover:text-white")}><span>{icon}</span><span className="hidden md:block">{label}</span></button>;
}

function MatchCard({ match, onPlaceBet, onAddToAcca, isAdded }: { match: any, onPlaceBet: any, onAddToAcca: any, selectedBookmaker: string, isAdded: (id: string) => boolean }) {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-4">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            {match.homeTeam.logo && <img src={match.homeTeam.logo} alt="" className="w-5 h-5 object-contain" />}
            <span className="font-bold text-sm">{match.homeTeam.name}</span>
          </div>
          <span className="text-zinc-600 font-mono text-xs">VS</span>
          <div className="flex items-center gap-2">
            {match.awayTeam.logo && <img src={match.awayTeam.logo} alt="" className="w-5 h-5 object-contain" />}
            <span className="font-bold text-sm">{match.awayTeam.name}</span>
          </div>
        </div>
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">{match.league}</span>
      </div>
      
      <div className="flex items-center justify-between pt-2">
        <div className="flex gap-2">
          <button 
            onClick={() => onPlaceBet(match, 'home_win', 1.95, 1000)}
            className="bg-zinc-900 border border-zinc-800 hover:border-green-500/50 px-4 py-2 rounded-xl text-[10px] font-bold transition-all"
          >
            Track Win
          </button>
        </div>
        <button 
          onClick={() => onAddToAcca(match, 'home_win', 1.95)}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-bold transition-all",
            isAdded(`${match.id}-home_win`) 
              ? "bg-orange-500 text-black" 
              : "bg-white text-black hover:bg-orange-500"
          )}
        >
          {isAdded(`${match.id}-home_win`) ? <CheckCircle className="w-3 h-3" /> : <PlusCircle className="w-3 h-3" />}
          {isAdded(`${match.id}-home_win`) ? "Added" : "Add to Acca"}
        </button>
      </div>
    </div>
  );
}

interface PredictionCardProps {
  prediction: Prediction;
  onGenerateCode: () => void;
  isUserPremium: boolean;
  isAdmin: boolean;
  onBroadcast: () => void;
  setShowPremiumModal: (show: boolean) => void;
}

function PredictionCard({ prediction, onGenerateCode, isUserPremium, isAdmin, onBroadcast, setShowPremiumModal }: PredictionCardProps) {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-6">
      <div className="flex justify-between items-start">
        <h3 className="text-xl font-bold">{prediction.home_team} vs {prediction.away_team}</h3>
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">{new Date(prediction.created_at).toLocaleDateString()}</span>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-zinc-900/50 p-4 rounded-2xl border border-zinc-800/50">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">Expected Goals (xG)</p>
          <div className="flex justify-between items-center">
            <span className="font-bold">{prediction.home_xg.toFixed(2)}</span>
            <span className="text-zinc-600">vs</span>
            <span className="font-bold">{prediction.away_xg.toFixed(2)}</span>
          </div>
        </div>
        <div className="bg-zinc-900/50 p-4 rounded-2xl border border-zinc-800/50">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-1">AI Confidence</p>
          <p className="text-xl font-bold text-orange-500">{(prediction.confidence * 100).toFixed(1)}%</p>
        </div>
      </div>

      <div className="space-y-3">
        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Match Outcome Probabilities</p>
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="bg-zinc-900 p-2 rounded-xl">
            <p className="text-[10px] text-zinc-500">Home</p>
            <p className="font-bold">{(prediction.home_prob * 100).toFixed(0)}%</p>
          </div>
          <div className="bg-zinc-900 p-2 rounded-xl">
            <p className="text-[10px] text-zinc-500">Draw</p>
            <p className="font-bold">{(prediction.draw_prob * 100).toFixed(0)}%</p>
          </div>
          <div className="bg-zinc-900 p-2 rounded-xl">
            <p className="text-[10px] text-zinc-500">Away</p>
            <p className="font-bold">{(prediction.away_prob * 100).toFixed(0)}%</p>
          </div>
        </div>
      </div>

      {prediction.home_id && prediction.away_id && (
        <H2HVisualizer team1Id={prediction.home_id} team2Id={prediction.away_id} />
      )}

      {prediction.correct_scores && (
        <div className="space-y-3">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Top 5 Correct Scores</p>
          <div className="flex flex-wrap gap-2">
            {prediction.correct_scores.map((cs, i) => (
              <div key={i} className="bg-black/40 border border-white/5 px-3 py-2 rounded-lg flex gap-2 items-center">
                <span className="font-bold text-xs">{cs.score}</span>
                <span className="text-[10px] text-zinc-500">{(cs.prob * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="pt-4 border-t border-zinc-800 flex justify-between items-center">
        <div>
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Best Bet Market</p>
          <p className="text-sm font-bold">{prediction.best_bet_market}: {prediction.best_bet_selection}</p>
        </div>
        <div className="text-right">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Odds</p>
          <p className="text-sm font-bold text-green-500">@{prediction.best_bet_odds}</p>
        </div>
      </div>
    </div>
  );
}

function ProbStat({ label, value, color }: { label: string, value: number, color: string }) {
  return <div className="space-y-1"><div className="flex justify-between text-[10px] font-mono text-zinc-500"><span>{label}</span><span>{(value * 100).toFixed(0)}%</span></div><div className="h-1 bg-zinc-900 rounded-full overflow-hidden"><div className={cn("h-full", color)} style={{ width: `${value * 100}%` }} /></div></div>;
}

function StrategyView() {
  const [text, setText] = useState('');
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/analyze-strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      setAnalysis(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-6">
        <div className="flex items-center gap-3">
          <Zap className="text-orange-500" />
          <h2 className="text-2xl font-bold">AI Strategy Analyzer</h2>
        </div>
        <p className="text-zinc-500 text-sm">Describe your betting plan in natural language. Use commas to separate selections.</p>
        <div className="space-y-4">
          <textarea 
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g., Man City win, Chelsea vs Arsenal draw, Over 2.5 in Liverpool match"
            className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-6 h-32 focus:outline-none focus:border-orange-500 transition-colors"
          />
          <button 
            onClick={handleAnalyze}
            disabled={loading || !text}
            className="w-full bg-orange-500 text-black font-bold py-4 rounded-2xl flex items-center justify-center gap-3 hover:bg-orange-400 transition-all disabled:opacity-50"
          >
            {loading ? <Loader2 className="animate-spin" /> : <ShieldCheck />}
            Analyze Strategy Risk & EV
          </button>
        </div>
      </div>

      <AnimatePresence>
        {analysis && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-1 md:grid-cols-2 gap-6"
          >
            <div className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2"><Activity className="w-4 h-4 text-orange-500" /> Risk Assessment</h3>
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 text-sm">Risk Level</span>
                  <span className={cn(
                    "px-3 py-1 rounded-full text-xs font-bold",
                    analysis.metrics.risk_score === 'Low' ? 'bg-green-500/10 text-green-500' : 
                    analysis.metrics.risk_score === 'Medium' ? 'bg-yellow-500/10 text-yellow-500' : 'bg-red-500/10 text-red-500'
                  )}>{analysis.metrics.risk_score}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 text-sm">Expected Value (EV)</span>
                  <span className="text-green-500 font-bold">{analysis.metrics.expected_value}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 text-sm">Estimated Combined Odds</span>
                  <span className="font-bold">@{analysis.metrics.combined_odds_est}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-zinc-500 text-sm">Win Probability</span>
                  <span className="font-bold">{analysis.metrics.win_probability}</span>
                </div>
              </div>
            </div>

            <div className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2"><CheckCircle className="w-4 h-4 text-green-500" /> AI Recommendation</h3>
              <p className="text-zinc-400 text-sm leading-relaxed">{analysis.recommendation}</p>
              <div className="pt-4 border-t border-zinc-800">
                <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-2">Internal Agent Summary</p>
                <p className="text-xs text-zinc-500">{analysis.summary}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
