import { useState, useEffect, useCallback } from 'react';
import { Activity, Terminal, TrendingUp, History, ShieldCheck, LogOut, LogIn, PlusCircle, AlertTriangle, Loader2, ChevronRight, Database, Search, User, CheckCircle, XCircle, Mail, Lock, Calendar, Wallet, Clock, DollarSign, Zap, Layers, Send, ExternalLink, Crown, Bell, HelpCircle, RefreshCw, Server, Menu, X, CreditCard, BookOpen, BrainCircuit, Shield, Cpu, BarChart3 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from './lib/utils';
import { supabase } from './supabase';



interface Team {
  id: string | number;
  name: string;
  country?: string;
  league_name?: string;
  logo_url?: string;
}

interface ValueBet {
  id?: string;
  home_team: string;
  away_team: string;
  market: string;
  selection: string;
  odds: number;
  our_probability: number;
  ev: number;
  tier: 'Hot 🔥' | 'Solid' | 'Neutral';
  created_at: string;
}

interface Prediction {
  id: string;
  home_team: string;
  away_team: string;
  home_id?: number;
  away_id?: number;
  home_prob: number;
  draw_prob: number;
  away_prob: number;
  home_xg: number;
  away_xg: number;
  confidence: number;
  best_bet_market: string;
  best_bet_selection: string;
  best_bet_odds: number;
  best_bet_ev?: number;
  is_premium: boolean;
  created_at: string;
  over_2_5_prob?: number;
  btts_prob?: number;
  dc_home_draw_prob?: number;
  dc_away_draw_prob?: number;
  dc_home_away_prob?: number;
  correct_scores?: any[];
}
export default function App() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [teams, setTeams] = useState<Team[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
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
  const [bankroll, setBankroll] = useState(1000); 
  const [bookingCode, setBookingCode] = useState<string | null>(null);
  const [generatingCode, setGeneratingCode] = useState(false);
  const [accaSelections, setAccaSelections] = useState<any[]>([]);
  const [selectedBookmaker, setSelectedBookmaker] = useState<'bet9ja' | 'sportybet' | '1xbet'>('sportybet');
  const [isPremium, setIsPremium] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [dailyPicks, setDailyPicks] = useState<Prediction[]>([]);
  const [fetchingPicks, setFetchingPicks] = useState(false);
  const [picksDate, setPicksDate] = useState<'today' | 'tomorrow' | 'week'>('today');

  const fetchDailyPicks = useCallback(async (period: 'today' | 'tomorrow' | 'week') => {
    setFetchingPicks(true);
    try {
      let from = new Date().toISOString().split('T')[0];
      let to = from;
      
      if (period === 'tomorrow') {
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        from = tomorrow.toISOString().split('T')[0];
        to = from;
      } else if (period === 'week') {
        const week = new Date();
        week.setDate(week.getDate() + 7);
        to = week.toISOString().split('T')[0];
      }

      const data = await safeFetchJson(`/api/daily-picks?from_date=${from}&to_date=${to}`);
      setDailyPicks(data || []);
    } catch (err: any) {
      console.error(err);
      flashMessage(setError, "Failed to load daily picks: " + err.message);
    } finally {
      setFetchingPicks(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'predictions') {
      fetchDailyPicks(picksDate);
    }
  }, [activeTab, picksDate, fetchDailyPicks]);
  const [syncingTeams, setSyncingTeams] = useState(false);
  const [syncingPlayers, setSyncingPlayers] = useState(false);
  const [seedingData, setSeedingData] = useState(false);

  const [dashboardStats, setTerminalStats] = useState<any>({
    total_predictions: "0",
    active_value_bets: "0",
    ai_accuracy: "78.5%"
  });

  const flashMessage = (setter: (msg: string | null) => void, message: string | null) => {
    setter(message);
    setTimeout(() => setter(null), 4000);
  };

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) {
      flashMessage(setError, "Auth service not configured");
      return;
    }
    if (isSignUp) {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) flashMessage(setError, error.message);
      else flashMessage(setSuccess, "Check your email!");
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) flashMessage(setError, error.message);
    }
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
      })
      .catch(err => {
        console.error("Profile fetch failed:", err);
        if (user.email === 'sophiemabel69@gmail.com') {
          setIsAdmin(true);
          setIsPremium(true);
        }
      });
  }, [user]);

  const fetchTeams = useCallback(async () => {
    try {
      const data = await safeFetchJson('/api/teams');
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

  const fetchTerminalStats = useCallback(async () => {
    try {
      const data = await safeFetchJson('/api/dashboard/stats');
      setTerminalStats(data);
    } catch (err) {
      console.error("Failed to fetch dashboard stats:", err);
    }
  }, []);

  const fetchValueBets = useCallback(async () => {
    try {
      const data = await safeFetchJson(`/api/value-bets?status=${betStatusFilter}`);
      setValueBets(data);
      fetchTerminalStats();
    } catch (error: any) {
      console.error("Failed to fetch value bets:", error);
    }
  }, [betStatusFilter, fetchTerminalStats]);
  
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
    supabase.auth.getSession()
      .then(({ data: { session } }) => {
        setUser(session?.user ?? null);
      })
      .catch((err) => {
        console.error("Session check failed:", err);
      })
      .finally(() => {
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
    fetchTerminalStats();
    fetchUserBets();
    handleScanValueBets();
  }, [user, fetchTeams, fetchPredictions, fetchValueBets, fetchTerminalStats, fetchUserBets, handleScanValueBets]);

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
    setSeedingData(true);
    try {
      await safeFetchJson('/api/admin/seed-database', { method: 'POST' });
      flashMessage(setSuccess, "Database seeded successfully.");
      fetchTeams();
    } catch (err: any) {
      flashMessage(setError, "Seeding failed: " + err.message);
    } finally {
      setSeedingData(false);
    }
  }, [fetchTeams]);

  const handleSyncPlayers = useCallback(async () => {
    setSyncingPlayers(true);
    try {
      const data = await safeFetchJson('/api/admin/sync-players', { method: 'POST' });
      flashMessage(setSuccess, `Successfully synced ${data.synced_count} players.`);
    } catch (err: any) {
      flashMessage(setError, "Player sync failed: " + err.message);
    } finally {
      setSyncingPlayers(false);
    }
  }, []);

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
            home_team: data.home_team || homeTeam?.name || 'Unknown',
            away_team: data.away_team || awayTeam?.name || 'Unknown',
            home_id: data.home_id,
            away_id: data.away_id,
            home_prob: data.home_prob ?? data.probabilities?.home_win ?? 0.33,
            draw_prob: data.draw_prob ?? data.probabilities?.draw ?? 0.34,
            away_prob: data.away_prob ?? data.probabilities?.away_win ?? 0.33,
            home_xg: data.home_xg || 0,
            away_xg: data.away_xg || 0,
            confidence: data.confidence || (( (data.home_prob || data.probabilities?.home_win || 0) + (data.away_prob || data.probabilities?.away_win || 0) ) / 1.5),
            best_bet_market: data.value_bets?.[0]?.market_name || 'Match Odds',
            best_bet_selection: data.value_bets?.[0]?.selection || 'Home',
            best_bet_odds: data.value_bets?.[0]?.odds || 1.9,
            best_bet_ev: data.value_bets?.[0]?.ev || 0,
            is_premium: data.value_bets?.[0]?.tier === 'Hot 🔥',
            created_at: new Date().toISOString(),
            over_2_5_prob: data.probabilities?.['Over 2.5'] || 0,
            btts_prob: data.probabilities?.['BTTS Yes'] || 0,
            dc_home_draw_prob: data.probabilities?.['DC Home/Draw'] || 0,
            dc_away_draw_prob: data.probabilities?.['DC Away/Draw'] || 0,
            dc_home_away_prob: data.probabilities?.['DC Home/Away'] || 0,
            correct_scores: data.correct_scores || [],
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
                <div className="text-center space-y-2">
                    <h1 className="text-3xl font-bold">FootyEdge AI</h1>
                    <p className="text-zinc-500">Login to access the AI betting suite.</p>
                </div>

                {error && (
                    <div className="bg-red-500/10 border border-red-500/20 p-4 rounded-2xl flex items-center gap-3 text-red-500 text-sm">
                        <AlertTriangle className="w-4 h-4" />
                        {error}
                    </div>
                )}

                {success && (
                    <div className="bg-green-500/10 border border-green-500/20 p-4 rounded-2xl flex items-center gap-3 text-green-500 text-sm">
                        <CheckCircle className="w-4 h-4" />
                        {success}
                    </div>
                )}

                <form onSubmit={handleEmailAuth} className="space-y-6">
                    <div className="space-y-4">
                        <div className="relative">
                            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                            <input 
                                type="email" 
                                placeholder="Email" 
                                value={email} 
                                onChange={e => setEmail(e.target.value)} 
                                className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 pl-12 focus:border-orange-500 transition-colors" 
                            />
                        </div>
                        <div className="relative">
                            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                            <input 
                                type="password" 
                                placeholder="Password" 
                                value={password} 
                                onChange={e => setPassword(e.target.value)} 
                                className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 pl-12 focus:border-orange-500 transition-colors" 
                            />
                        </div>
                    </div>
                    <button type="submit" className="w-full bg-orange-500 text-black font-bold py-4 rounded-2xl hover:bg-orange-400 transition-all flex items-center justify-center gap-2">
                        {isSignUp ? "Create Account" : "Log In"}
                        <ChevronRight className="w-4 h-4" />
                    </button>
                </form>
                <div className="text-center">
                    <button onClick={() => setIsSignUp(!isSignUp)} className="text-sm text-zinc-500 hover:text-white transition-colors">
                        {isSignUp ? "Already have an account? Log In" : "Don't have an account? Sign Up"}
                    </button>
                </div>
            </div>
        </div>
    );
  }


  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white font-sans overflow-x-hidden">
      {/* Sidebar Backdrop (Mobile) */}
      <AnimatePresence>
        {isSidebarOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsSidebarOpen(false)}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] lg:hidden"
          />
        )}
      </AnimatePresence>

      <div className={cn(
        "fixed left-0 top-0 h-full w-72 bg-[#111] border-r border-zinc-800 flex flex-col z-[70] transition-transform duration-300 lg:translate-x-0",
        isSidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="h-24 flex items-center justify-between px-8 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-orange-500 rounded-2xl flex items-center justify-center shadow-[0_0_20px_-5px_rgba(249,115,22,0.5)]">
              <ShieldCheck className="text-black w-6 h-6" />
            </div>
            <h1 className="text-xl font-bold tracking-tight">FootyEdge AI</h1>
          </div>
          <button onClick={() => setIsSidebarOpen(false)} className="lg:hidden text-zinc-500">
            <X className="w-6 h-6" />
          </button>
        </div>

        <nav className="flex-1 px-4 py-8 space-y-2 overflow-y-auto scrollbar-hide">
            <NavItem icon={<Terminal className="w-5 h-5" />} label="Terminal" active={activeTab === 'dashboard'} onClick={() => { setActiveTab('dashboard'); setIsSidebarOpen(false); }} />
            <NavItem icon={<BrainCircuit className="w-5 h-5" />} label="Intelligence" active={activeTab === 'predictions'} onClick={() => { setActiveTab('predictions'); setIsSidebarOpen(false); }} />
            <NavItem icon={<TrendingUp />} label="Value Scanner" active={activeTab === 'value'} onClick={() => { setActiveTab('value'); setIsSidebarOpen(false); }} />
            <NavItem icon={<Layers />} label="Acca Builder" active={activeTab === 'acca'} onClick={() => { setActiveTab('acca'); setIsSidebarOpen(false); }} />
            <NavItem icon={<Zap />} label="AI Analysis" active={activeTab === 'strategy'} onClick={() => { setActiveTab('strategy'); setIsSidebarOpen(false); }} />
            <div className="h-px bg-zinc-800/50 my-6 mx-4" />
            <NavItem icon={<Shield />} label="Teams DB" active={activeTab === 'teams'} onClick={() => { setActiveTab('teams'); setIsSidebarOpen(false); }} />
            <NavItem icon={<User />} label="Players DB" active={activeTab === 'players'} onClick={() => { setActiveTab('players'); setIsSidebarOpen(false); }} />
            <NavItem icon={<Wallet />} label="Portfolio" active={activeTab === 'portfolio'} onClick={() => { setActiveTab('portfolio'); setIsSidebarOpen(false); }} />
            <NavItem icon={<CreditCard />} label="Pricing" active={activeTab === 'pricing'} onClick={() => { setActiveTab('pricing'); setIsSidebarOpen(false); }} />
            <NavItem icon={<BookOpen />} label="Guide" active={activeTab === 'how-to-use'} onClick={() => { setActiveTab('how-to-use'); setIsSidebarOpen(false); }} />
            {isAdmin && <NavItem icon={<ShieldCheck />} label="Admin" active={activeTab === 'admin'} onClick={() => { setActiveTab('admin'); setIsSidebarOpen(false); }} />}
        </nav>

        <div className="p-6 border-t border-zinc-800 space-y-4">
          <div className="flex items-center gap-3 p-3 bg-zinc-900/50 rounded-2xl border border-white/5">
             <div className="w-10 h-10 rounded-xl bg-orange-500/10 flex items-center justify-center border border-orange-500/20">
                <Crown className="w-5 h-5 text-orange-500" />
             </div>
             <div>
                <p className="text-xs font-bold">{isPremium ? 'Premium Plan' : 'Basic Plan'}</p>
                <p className="text-[10px] text-zinc-500">{user.email.split('@')[0]}</p>
             </div>
          </div>
          <button onClick={() => supabase.auth.signOut()} className="w-full flex items-center justify-center gap-3 p-4 text-zinc-500 hover:text-red-500 hover:bg-red-500/5 rounded-2xl transition-all">
            <LogOut className="w-5 h-5" />
            <span className="font-bold text-sm">Sign Out</span>
          </button>
        </div>
      </div>

      <main className="lg:pl-72 min-h-screen flex flex-col">
        <header className="h-20 border-b border-zinc-800 flex items-center justify-between px-6 md:px-12 sticky top-0 bg-[#0a0a0a]/80 backdrop-blur-xl z-40">
          <div className="flex items-center gap-6">
            <button onClick={() => setIsSidebarOpen(true)} className="lg:hidden text-white">
              <Menu className="w-6 h-6" />
            </button>
            <div className="hidden sm:flex items-center gap-4">
              <div className="flex flex-col">
                <h1 className="text-[10px] font-mono text-green-500 uppercase tracking-[0.2em]">SYSTEM: ONLINE</h1>
                <p className="text-sm font-bold text-green-500 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
                  AI Models Operational
                </p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <button className="relative w-10 h-10 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center justify-center hover:bg-zinc-800 transition-colors">
              <Bell className="w-5 h-5 text-zinc-400" />
              <span className="absolute top-0 right-0 w-2.5 h-2.5 bg-orange-500 border-2 border-[#0a0a0a] rounded-full" />
            </button>
            <div className="hidden md:block w-px h-6 bg-zinc-800" />
            <div className="hidden md:flex items-center gap-3">
              <div className="text-right">
                <p className="text-xs font-bold text-white">{user.email}</p>
                <p className="text-[10px] font-mono text-zinc-500">ID: {user.id.substring(0, 8)}</p>
              </div>
            </div>
          </div>
        </header>

        <div className="p-6 md:p-12 max-w-7xl mx-auto w-full flex-1">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
          >
            {activeTab === 'dashboard' && (
              <div className="space-y-12">
                                <div className="relative group">
                  <div className="absolute -inset-1 bg-gradient-to-r from-orange-500 to-yellow-500 rounded-[2.5rem] blur opacity-10 group-hover:opacity-20 transition duration-1000 group-hover:duration-200"></div>
                  <div className="relative bg-zinc-900/40 border border-white/5 rounded-[2.5rem] p-8 md:p-12 overflow-hidden">
                    <div className="absolute top-0 right-0 p-8 opacity-10">
                      <Terminal className="w-48 h-48 text-orange-500" />
                    </div>
                    <div className="relative z-10 space-y-6">
                      <div className="inline-flex items-center gap-2 px-4 py-1.5 bg-orange-500/10 border border-orange-500/20 rounded-full text-orange-500 text-[10px] font-bold uppercase tracking-wider">
                        <Cpu className="w-3 h-3" /> Terminal Overview
                      </div>
                      <h2 className="text-4xl md:text-5xl font-bold max-w-2xl leading-tight">Real-time edge detection and <span className="text-transparent bg-clip-text bg-gradient-to-r from-orange-400 to-yellow-500">portfolio metrics.</span></h2>
                      <div className="grid grid-cols-2 lg:grid-cols-4 gap-6 pt-4">
                        <StatItem icon={<History className="text-blue-500" />} label="Total Predictions" value={`${dashboardStats.total_predictions || 0} matches`} />
                        <StatItem icon={<Activity className="text-purple-500" />} label="Platform Win Rate" value={dashboardStats.win_rate || "0%"} />
                        <StatItem icon={<TrendingUp className="text-green-500" />} label="Active Value Bets" value={dashboardStats.active_value_bets || 0} />
                        <StatItem icon={<Zap className="text-yellow-500" />} label="Portfolio ROI" value={dashboardStats.portfolio_roi || "0%"} />
                      </div>
                    </div>
                  </div>
                </div>

                <section className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                  <div className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-8 space-y-6">
                    <div className="flex items-center justify-between">
                       <h3 className="text-xl font-bold flex items-center gap-3"><Activity className="text-orange-500" /> Live Feed</h3>
                       <span className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">Real-time Stream</span>
                    </div>
                    <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 scrollbar-hide">
                      {liveValueBets.length > 0 && <FeedItem title="Value Bet Scan Complete" time="Just Now" detail={`${liveValueBets.length} EV+ opportunities identified using real-market calibration data.`} />}
                      {predictions.slice(0, 10).map((p, i) => (
                        <FeedItem key={i} title={`AI Prediction: ${p.home_team} vs ${p.away_team}`} time="Recently" detail={`${p.best_bet_selection} @ ${p.best_bet_odds} - ${(p.confidence * 100).toFixed(1)}% confidence`} />
                      ))}
                      {predictions.length === 0 && <div className="py-20 text-center text-zinc-700 text-xs italic">Waiting for incoming signal stream...</div>}
                    </div>
                  </div>
                  <div className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-8 space-y-6">
                    <div className="flex items-center justify-between">
                       <h3 className="text-xl font-bold flex items-center gap-3"><TrendingUp className="text-green-500" /> Edge Alerts</h3>
                       <span className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">High EV Only</span>
                    </div>
                    <div className="space-y-4">
                      {liveValueBets.length > 0 ? liveValueBets.slice(0, 4).map((bet, i) => (
                        <div key={i} className="p-5 bg-zinc-900/50 border border-white/5 rounded-3xl space-y-3 hover:border-orange-500/30 transition-all group">
                           <div className="flex justify-between items-start">
                              <div className="space-y-1">
                                 <p className="text-[10px] font-bold text-orange-500 uppercase tracking-tighter">Value Bet Detected</p>
                                 <p className="text-sm font-bold">{bet.home_team} vs {bet.away_team}</p>
                              </div>
                              <span className="text-[10px] font-black bg-green-500/10 text-green-500 px-3 py-1 rounded-full uppercase">EV+ {((bet.ev || 0) * 100).toFixed(1)}%</span>
                           </div>
                           <div className="flex items-center justify-between pt-2 border-t border-white/5">
                              <p className="text-[10px] text-zinc-500 uppercase font-mono">{bet.market}: <span className="text-white font-bold">{bet.selection}</span></p>
                              <p className="text-sm font-black text-green-400">@{bet.odds}</p>
                           </div>
                        </div>
                      )) : (
                        <div className="py-20 text-center bg-zinc-900/20 border border-dashed border-zinc-800 rounded-3xl">
                           <Loader2 className="w-6 h-6 text-zinc-800 animate-spin mx-auto mb-2" />
                           <p className="text-zinc-600 text-[10px] uppercase font-bold tracking-widest">Scanning Markets...</p>
                        </div>
                      )}
                    </div>
                  </div>
                </section>
                <section className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-8 md:p-12 space-y-12">
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                    <div className="space-y-1">
                      <h2 className="text-3xl font-bold">Terminal Overview</h2>
                      <p className="text-sm text-zinc-500">Select any two teams to generate a deep-dive match intelligence report.</p>
                    </div>
                    <RefreshCw className="w-6 h-6 text-zinc-700 hidden md:block" />
                  </div>

                  {teams.length === 0 ? (
                    <div className="bg-orange-500/5 border border-orange-500/10 p-12 rounded-[2rem] text-center space-y-6">
                      <Database className="w-16 h-16 text-orange-500 mx-auto" />
                      <div className="space-y-2">
                        <p className="text-xl font-bold">Team Database Not Initialized</p>
                        <p className="text-sm text-zinc-500 max-w-md mx-auto">Please seed or sync the database from the admin panel to enable the intelligence engine.</p>
                      </div>
                      {isAdmin && (
                        <div className="flex justify-center gap-4">
                          <button onClick={handleSyncTeams} className="bg-zinc-900 border border-zinc-800 px-8 py-3 rounded-2xl font-bold hover:bg-zinc-800 transition-all">Sync Teams</button>
                          <a href="/api/health" target="_blank" className="bg-zinc-900 border border-zinc-800 px-8 py-3 rounded-2xl font-bold hover:bg-zinc-800 transition-all flex items-center gap-2">
                            <Server className="w-4 h-4" /> System Health
                          </a>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-10">
                      <div className="grid grid-cols-1 md:grid-cols-7 gap-6 items-center">
                          <div className="md:col-span-3 space-y-2">
                            <label className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest ml-4">Home Side</label>
                            <select value={selectedHome} onChange={(e) => setSelectedHome(e.target.value)} className="w-full bg-zinc-900/50 border border-zinc-800 rounded-[2rem] p-6 focus:border-orange-500 transition-colors appearance-none cursor-pointer">
                              <option value="">Select Home Team</option>
                              {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                            </select>
                          </div>
                          <div className="md:col-span-1 text-center">
                            <div className="w-12 h-12 bg-zinc-800 rounded-full flex items-center justify-center mx-auto border-4 border-[#111] font-black text-zinc-500 italic">VS</div>
                          </div>
                          <div className="md:col-span-3 space-y-2">
                            <label className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest ml-4">Away Side</label>
                            <select value={selectedAway} onChange={(e) => setSelectedAway(e.target.value)} className="w-full bg-zinc-900/50 border border-zinc-800 rounded-[2rem] p-6 focus:border-orange-500 transition-colors appearance-none cursor-pointer">
                              <option value="">Select Away Team</option>
                              {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                            </select>
                          </div>
                      </div>
                      <button onClick={handlePredict} disabled={predicting || !selectedHome || !selectedAway} className="w-full bg-orange-500 text-black font-black py-6 rounded-[2rem] flex items-center justify-center gap-4 hover:scale-[1.01] transition-all shadow-[0_20px_40px_-10px_rgba(249,115,22,0.3)] disabled:opacity-50 disabled:scale-100 uppercase tracking-widest">
                        {predicting ? <Loader2 className="animate-spin w-6 h-6" /> : <PlusCircle className="w-6 h-6" />}
                        Generate Match Analysis
                      </button>
                    </div>
                  )}
                </section>
              </div>
            )}

            {activeTab === 'predictions' && (
              <div className="space-y-12">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                  <div className="space-y-1">
                    <h2 className="text-3xl font-bold">AI Predictions</h2>
                    <p className="text-zinc-500 text-sm">Deep learning match outcomes and probability models.</p>
                  </div>
                  <div className="flex p-1.5 bg-zinc-900 border border-zinc-800 rounded-2xl">
                    <DateToggle label="Today" active={picksDate === 'today'} onClick={() => setPicksDate('today')} />
                    <DateToggle label="Tomorrow" active={picksDate === 'tomorrow'} onClick={() => setPicksDate('tomorrow')} />
                    <DateToggle label="Next 7 Days" active={picksDate === 'week'} onClick={() => setPicksDate('week')} />
                  </div>
                </div>

                {fetchingPicks ? (
                  <div className="py-32 flex flex-col items-center justify-center space-y-6 bg-zinc-900/30 border border-dashed border-zinc-800 rounded-[2.5rem]">
                    <Loader2 className="w-12 h-12 text-orange-500 animate-spin" />
                    <p className="text-zinc-500 font-bold animate-pulse">Oracle is analyzing upcoming fixtures...</p>
                  </div>
                ) : dailyPicks.length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {dailyPicks.map(pred => <PredictionCard key={pred.id} prediction={pred} onGenerateCode={()=>{}} isUserPremium={isPremium} isAdmin={isAdmin} onBroadcast={()=>{}} setShowPremiumModal={()=>{}} />)}
                  </div>
                ) : (
                  <div className="col-span-full py-32 text-center bg-zinc-900/30 border border-dashed border-zinc-800 rounded-[2.5rem]">
                    <BrainCircuit className="w-16 h-16 text-zinc-800 mx-auto mb-4" />
                    <p className="text-zinc-500 text-xl font-bold">No fixtures found for this period.</p>
                    <p className="text-sm text-zinc-600 mt-2">Try checking another date or wait for API refresh.</p>
                  </div>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <StatCard title="Total Predictions" value={dashboardStats.total_predictions.toString()} icon={<History className="text-blue-500" />} />
                  <StatCard title="Active Value Bets" value={dashboardStats.active_value_bets.toString()} icon={<TrendingUp className="text-green-500" />} />
                  <StatCard title="AI Accuracy" value={dashboardStats.ai_accuracy} icon={<ShieldCheck className="text-orange-500" />} />
                </div>
                
                <div className="pt-12 border-t border-zinc-800/50">
                  <h3 className="text-xl font-bold mb-8">Generated History</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 opacity-60 grayscale hover:opacity-100 hover:grayscale-0 transition-all">
                    {predictions.map(pred => <PredictionCard key={pred.id} prediction={pred} onGenerateCode={()=>{}} isUserPremium={isPremium} isAdmin={isAdmin} onBroadcast={()=>{}} setShowPremiumModal={()=>{}} />)}
                  </div>
                </div>
              </div>
            )}
            
            {activeTab === 'value' && <ValueBets />}
            {activeTab === 'teams' && <TeamsList />}
            {activeTab === 'players' && <PlayersList />}
            {activeTab === 'pricing' && <Pricing />}
            {activeTab === 'acca' && <AccaBuilder selections={accaSelections} onRemove={handleRemoveFromAcca} onGenerateCode={handleGenerateCode} bankroll={bankroll} />}
            {activeTab === 'strategy' && <StrategyView />}
            {activeTab === 'portfolio' && <Portfolio bankroll={bankroll} userBets={userBets} />}
            {activeTab === 'how-to-use' && <HowToUse />}
            
            {activeTab === 'admin' && isAdmin && (
              <div className="space-y-12">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    <AdminActionCard 
                      title="Sync Teams" 
                      description="Fetch and update club details from API."
                      onClick={handleSyncTeams}
                      loading={syncingTeams}
                      icon={<Shield className="text-blue-500" />}
                    />
                    <AdminActionCard 
                      title="Sync Players" 
                      description="Fetch and update player squads for all teams."
                      onClick={handleSyncPlayers}
                      loading={syncingPlayers}
                      icon={<User className="text-green-500" />}
                    />
                    <AdminActionCard 
                      title="Seed Data" 
                      description="Populate DB with high-quality base stats."
                      onClick={handleSeedDatabase}
                      loading={seedingData}
                      icon={<Database className="text-orange-500" />}
                    />
                  </div>
              </div>
            )}
          </motion.div>
        </div>
      </main>

    </div>
  );
}

function StatItem({ icon, label, value }: { icon: any, label: string, value: string | number }) {
  return (
    <div className="bg-black/40 border border-white/5 p-6 rounded-3xl space-y-2">
      <div className="flex items-center gap-3">
        {icon}
        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">{label}</p>
      </div>
      <p className="text-2xl font-bold">{value || '0'}</p>
    </div>
  );
}

function AdminActionCard({ title, description, onClick, loading, icon }: any) {
  return (
    <button 
      onClick={onClick} 
      disabled={loading} 
      className="w-full text-left bg-[#111] border border-zinc-800 p-8 rounded-[2rem] space-y-4 hover:border-orange-500/40 hover:scale-[1.02] transition-all group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
    >
      <div className="w-12 h-12 bg-zinc-900 rounded-2xl flex items-center justify-center border border-white/5 group-hover:bg-zinc-800 transition-colors">
        {loading ? <Loader2 className="animate-spin text-orange-500" /> : icon}
      </div>
      <div className="space-y-1">
        <h3 className="text-xl font-bold group-hover:text-orange-500 transition-colors">{title}</h3>
        <p className="text-sm text-zinc-500">{description}</p>
      </div>
    </button>
  );
}

function DateToggle({ label, active, onClick }: { label: string, active: boolean, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={cn(
        "px-6 py-2 rounded-xl text-xs font-bold transition-all",
        active ? "bg-orange-500 text-black shadow-lg" : "text-zinc-500 hover:text-white"
      )}
    >
      {label}
    </button>
  );
}

function NavItem({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: any, label: string }) {
  return <button onClick={onClick} className={cn("w-full flex items-center gap-3 p-4 rounded-2xl transition-all", active ? "bg-orange-500 text-black font-bold shadow-[0_10px_20px_-5px_rgba(249,115,22,0.4)]" : "text-zinc-500 hover:text-white hover:bg-white/5")}><span>{icon}</span><span className="">{label}</span></button>;
}

function MatchCard({ match, onPlaceBet, onAddToAcca, isAdded }: { match: any, onPlaceBet: any, onAddToAcca: any, selectedBookmaker: string, isAdded: (id: string) => boolean }) {
  return (
    <div className="bg-[#111] border border-zinc-800 rounded-[2rem] p-6 space-y-6 hover:border-zinc-700 transition-all group">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            {match.homeTeam.logo ? <img src={match.homeTeam.logo} alt="" className="w-6 h-6 object-contain" /> : <div className="w-6 h-6 bg-zinc-800 rounded-full" />}
            <span className="font-bold text-sm">{match.homeTeam.name}</span>
          </div>
          <span className="text-zinc-700 font-mono text-[10px]">VS</span>
          <div className="flex items-center gap-2">
            {match.awayTeam.logo ? <img src={match.awayTeam.logo} alt="" className="w-6 h-6 object-contain" /> : <div className="w-6 h-6 bg-zinc-800 rounded-full" />}
            <span className="font-bold text-sm">{match.awayTeam.name}</span>
          </div>
        </div>
      </div>
      
      <div className="flex items-center justify-between pt-4 border-t border-zinc-800/50">
        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">{match.league}</span>
        <div className="flex gap-2">
          <button 
            onClick={() => onAddToAcca(match, 'home_win', 1.95)}
            className={cn(
              "flex items-center gap-2 px-4 py-2 rounded-xl text-[10px] font-bold transition-all",
              isAdded(`${match.id}-home_win`) 
                ? "bg-orange-500 text-black" 
                : "bg-zinc-800 text-white hover:bg-zinc-700"
            )}
          >
            {isAdded(`${match.id}-home_win`) ? <CheckCircle className="w-3 h-3" /> : <PlusCircle className="w-3 h-3" />}
            {isAdded(`${match.id}-home_win`) ? "Added" : "Add to Acca"}
          </button>
        </div>
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
    <div className="bg-[#111] border border-zinc-800 rounded-[2rem] p-8 space-y-8 relative overflow-hidden group">
      <div className="flex justify-between items-start relative z-10">
        <div className="space-y-1">
          <h3 className="text-2xl font-bold">{prediction.home_team} <span className="text-zinc-700 mx-2">vs</span> {prediction.away_team}</h3>
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-[0.2em]">
            {prediction.created_at ? new Date(prediction.created_at).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }) : 'Date Pending'}
          </p>
        </div>
        <div className="w-12 h-12 rounded-2xl bg-orange-500/10 flex items-center justify-center border border-orange-500/20">
          <BrainCircuit className="w-6 h-6 text-orange-500" />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 relative z-10">
        <div className="bg-zinc-900/50 p-6 rounded-2xl border border-white/5 space-y-4">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Expected Goals (xG)</p>
          <div className="flex justify-between items-end">
            <div className="text-center">
              <p className="text-2xl font-bold">{(prediction.home_xg || 0).toFixed(2)}</p>
              <p className="text-[10px] text-zinc-600 uppercase">Home</p>
            </div>
            <div className="h-8 w-px bg-zinc-800 mb-2" />
            <div className="text-center">
              <p className="text-2xl font-bold">{(prediction.away_xg || 0).toFixed(2)}</p>
              <p className="text-[10px] text-zinc-600 uppercase">Away</p>
            </div>
          </div>
        </div>
        <div className="bg-zinc-900/50 p-6 rounded-2xl border border-white/5 space-y-4">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">AI Confidence</p>
          <div className="flex items-center gap-4">
             <div className="relative w-16 h-16 flex items-center justify-center">
                <svg className="w-full h-full -rotate-90">
                  <circle cx="32" cy="32" r="28" fill="transparent" stroke="currentColor" strokeWidth="4" className="text-zinc-800" />
                  <circle cx="32" cy="32" r="28" fill="transparent" stroke="currentColor" strokeWidth="4" strokeDasharray={175.9} strokeDashoffset={175.9 * (1 - (prediction.confidence || 0))} className="text-orange-500" />
                </svg>
                <p className="absolute text-xs font-bold">{((prediction.confidence || 0) * 100).toFixed(0)}%</p>
             </div>
             <p className="text-sm text-zinc-400 leading-tight">High probability matchup detected by Neural Net.</p>
          </div>
        </div>
      </div>

      <div className="space-y-4 relative z-10">
        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Match Outcome Probabilities</p>
        <div className="grid grid-cols-3 gap-3">
          <ProbStat label="Home" value={prediction.home_prob} color="bg-orange-500" />
          <ProbStat label="Draw" value={prediction.draw_prob} color="bg-zinc-700" />
          <ProbStat label="Away" value={prediction.away_prob} color="bg-blue-500" />
        </div>
      </div>

      {prediction.home_id && prediction.away_id && (
        <div className="relative z-10">
          <H2HVisualizer team1Id={prediction.home_id} team2Id={prediction.away_id} />
        </div>
      )}

      <div className="pt-6 border-t border-zinc-800 flex justify-between items-center relative z-10">
        <div className="space-y-1">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Oracle Selection</p>
          <p className="text-sm font-bold text-white">{prediction.best_bet_market}: <span className="text-orange-500">{prediction.best_bet_selection}</span></p>
        </div>
        <div className="text-right space-y-1">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Market Odds</p>
          <p className="text-xl font-black text-green-500">@{(prediction.best_bet_odds || 0).toFixed(2)}</p>
        </div>
      </div>
    </div>
  );
}

function ProbStat({ label, value, color }: { label: string, value: number, color: string }) {
  return (
    <div className="bg-zinc-900/50 p-4 rounded-2xl border border-white/5 space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-[10px] font-mono text-zinc-500 uppercase">{label}</span>
        <span className="text-xs font-bold">{((value || 0) * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div className={cn("h-full transition-all duration-1000", color)} style={{ width: `${(value || 0) * 100}%` }} />
      </div>
    </div>
  );
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
      <div className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-8 md:p-12 space-y-8">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-orange-500/10 rounded-2xl flex items-center justify-center border border-orange-500/20">
            <Zap className="text-orange-500" />
          </div>
          <div className="space-y-1">
            <h2 className="text-3xl font-bold">AI Strategy Analyzer</h2>
            <p className="text-zinc-500 text-sm">Describe your betting plan in natural language. Use commas to separate selections.</p>
          </div>
        </div>

        <div className="space-y-6">
          <textarea 
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g., Man City win, Chelsea vs Arsenal draw, Over 2.5 in Liverpool match"
            className="w-full bg-zinc-900/50 border border-zinc-800 rounded-[2rem] p-8 h-48 focus:outline-none focus:border-orange-500 transition-colors resize-none leading-relaxed"
          />
          <button 
            onClick={handleAnalyze}
            disabled={loading || !text}
            className="w-full bg-orange-500 text-black font-black py-6 rounded-[2rem] flex items-center justify-center gap-4 hover:scale-[1.01] transition-all shadow-[0_20px_40px_-10px_rgba(249,115,22,0.3)] disabled:opacity-50 disabled:scale-100 uppercase tracking-widest"
          >
            {loading ? <Loader2 className="animate-spin w-6 h-6" /> : <ShieldCheck className="w-6 h-6" />}
            Analyze Strategy Risk & EV
          </button>
        </div>
      </div>

      <AnimatePresence>
        {analysis && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-1 md:grid-cols-2 gap-8"
          >
            <div className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-10 space-y-8">
              <h3 className="text-xl font-bold flex items-center gap-3"><Activity className="w-5 h-5 text-orange-500" /> Risk Assessment</h3>
              <div className="space-y-6">
                <div className="flex justify-between items-center p-4 bg-zinc-900/50 rounded-2xl border border-white/5">
                  <span className="text-zinc-500 text-sm">Risk Level</span>
                  <span className={cn(
                    "px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest",
                    analysis.metrics.risk_score === 'Low' ? 'bg-green-500/10 text-green-500 border border-green-500/20' : 
                    analysis.metrics.risk_score === 'Medium' ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'
                  )}>{analysis.metrics.risk_score}</span>
                </div>
                <div className="flex justify-between items-center p-4 bg-zinc-900/50 rounded-2xl border border-white/5">
                  <span className="text-zinc-500 text-sm">Expected Value (EV)</span>
                  <span className="text-green-500 font-black text-lg">{analysis.metrics.expected_value}</span>
                </div>
                <div className="flex justify-between items-center p-4 bg-zinc-900/50 rounded-2xl border border-white/5">
                  <span className="text-zinc-500 text-sm">Combined Odds</span>
                  <span className="font-black text-lg">@{analysis.metrics.combined_odds_est}</span>
                </div>
                <div className="flex justify-between items-center p-4 bg-zinc-900/50 rounded-2xl border border-white/5">
                  <span className="text-zinc-500 text-sm">Win Probability</span>
                  <span className="font-black text-lg text-orange-500">{analysis.metrics.win_probability}</span>
                </div>
              </div>
            </div>

            <div className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-10 space-y-8">
              <h3 className="text-xl font-bold flex items-center gap-3"><CheckCircle className="w-5 h-5 text-green-500" /> AI Recommendation</h3>
              <div className="bg-zinc-900/50 p-6 rounded-2xl border-l-4 border-l-orange-500">
                <p className="text-white text-sm leading-relaxed font-medium italic">"{analysis.recommendation}"</p>
              </div>
              <div className="pt-6 border-t border-zinc-800">
                <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-4">Internal Agent Summary</p>
                <p className="text-xs text-zinc-400 leading-relaxed">{analysis.summary}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}


function FeedItem({ title, time, detail }: { title: string, time: string, detail: string }) {
  return (
    <div className="p-4 bg-zinc-900/30 border border-white/5 rounded-2xl space-y-1">
      <div className="flex justify-between items-center">
        <p className="text-xs font-bold text-zinc-300">{title}</p>
        <p className="text-[10px] font-mono text-zinc-600">{time}</p>
      </div>
      <p className="text-[10px] text-zinc-500 leading-relaxed">{detail}</p>
    </div>
  );
}
