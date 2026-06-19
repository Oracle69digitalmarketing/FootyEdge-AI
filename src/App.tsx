import React, { useState, useEffect, useCallback } from 'react';
import { supabase } from './supabase';
import StatCard from './components/StatCard';
import ValueBets from './components/ValueBets';
import TeamsList from './components/TeamsList';
import PlayersList from './components/PlayersList';
import Pricing from './components/Pricing';
import AccaBuilder from './components/AccaBuilder';
import Portfolio from './components/Portfolio';
import HowToUse from './components/HowToUse';
import H2HVisualizer from './components/H2HVisualizer';
import PredictionCard from './components/PredictionCard';
import StrategyView from './components/StrategyView';
import FeedItem from './components/FeedItem';
import MatchCard from './components/MatchCard';
import { StatItem, AdminActionCard, DateToggle, NavItem } from './components/UI';
import { Activity, Terminal, TrendingUp, History, ShieldCheck, LogOut, LogIn, PlusCircle, AlertTriangle, Loader2, ChevronRight, Database, Search, User, CheckCircle, XCircle, Mail, Lock, Calendar, Wallet, Clock, DollarSign, Zap, Layers, Send, ExternalLink, Crown, Bell, HelpCircle, RefreshCw, Server, Menu, X, CreditCard, BookOpen, BrainCircuit, Shield, Cpu, BarChart3 } from 'lucide-react';
import PredictionsDashboard from './pages/PredictionsDashboard';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from './lib/utils';

// ... (rest of imports/types)

interface Team {
  id: string;
  name: string;
  logo_url?: string;
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
  best_bet_ev: number;
  is_premium: boolean;
  created_at: string;
  over_2_5_prob?: number;
  btts_prob?: number;
  dc_home_draw_prob?: number;
  dc_away_draw_prob?: number;
  dc_home_away_prob?: number;
  correct_scores?: any;
}

interface ValueBet {
  id: string;
  home_team: string;
  away_team: string;
  market: string;
  selection: string;
  odds: number;
  ev: number;
  status: 'active' | 'won' | 'lost';
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
  const [activeTab, setActiveTab] = useState<'dashboard' | 'predictions' | 'value' | 'players' | 'portfolio' | 'acca' | 'premium' | 'teams' | 'pricing' | 'how-to-use' | 'strategy'>('dashboard');
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
  const [showNotifications, setShowNotifications] = useState(false);
  const [notifications, setNotifications] = useState<any[]>([
    { id: 1, title: 'Neural Model Online', message: 'The AI prediction engine is fully operational.', time: 'Just now', type: 'system' },
    { id: 2, title: 'Market Opportunity', message: 'High EV detections available in Value Scanner.', time: '2 mins ago', type: 'alert' }
  ]);
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

  const [dashboardStats, setTerminalStats] = useState<any>({
    total_predictions: "0",
    active_value_bets: "0",
    ai_accuracy: "0%"
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
      const data = await safeFetchJson('/api/admin/metrics');
      setTerminalStats(data);
    } catch (err) {
      console.error("Failed to fetch admin metrics:", err);
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
      setUserBets(data || []);
      const settled = (data || []).filter((b: any) => b.status === 'won' || b.status === 'lost');
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

  const handlePredict = useCallback(async () => {
    if (!selectedHome || !selectedAway) return;
    setPredicting(true);
    setSimulationLog([]);
    setSimulationStep(0);

    const homeTeam = teams.find(t => t?.id?.toString() === selectedHome);
    const awayTeam = teams.find(t => t?.id?.toString() === selectedAway);

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
        // Search for this match in upcoming fixtures to get real odds
        const matchesRes = await safeFetchJson(`/api/matches?from_date=${new Date().toISOString().split('T')[0]}&to_date=${(new Date(Date.now() + 7 * 86400000)).toISOString().split('T')[0]}`);
        const foundMatch = matchesRes.response?.find((m: any) => 
            (m.teams.home.name.toLowerCase().includes(homeTeam?.name?.toLowerCase() || '') || homeTeam?.name?.toLowerCase().includes(m.teams.home.name.toLowerCase())) &&
            (m.teams.away.name.toLowerCase().includes(awayTeam?.name?.toLowerCase() || '') || awayTeam?.name?.toLowerCase().includes(m.teams.away.name.toLowerCase()))
        );

        let liveOdds = { "home_win": 1.95, "draw": 3.30, "away_win": 4.10, "Over 2.5": 1.90, "Under 2.5": 1.90, "BTTS Yes": 1.75, "BTTS No": 2.05 };
        
        if (foundMatch) {
            try {
                const oddsRes = await safeFetchJson(`/api/odds/${foundMatch.fixture.id}`);
                if (oddsRes.default) {
                    liveOdds = oddsRes.default;
                    setSimulationLog(prev => [...prev, "Found live market odds for this fixture."]);
                }
            } catch (e) {
                console.warn("Could not fetch live odds, using market estimates.");
            }
        }

        const [data] = await Promise.all([
            safeFetchJson('/api/predict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    home_team: homeTeam?.name,
                    away_team: awayTeam?.name,
                    odds: liveOdds
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
            home_prob: data.home_prob ?? data.probabilities?.home_win ?? 0.33,
            draw_prob: data.draw_prob ?? data.probabilities?.draw ?? 0.34,
            away_prob: data.away_prob ?? data.probabilities?.away_win ?? 0.33,
            home_xg: data.home_xg ?? 0,
            away_xg: data.away_xg ?? 0,
            confidence: data.confidence ?? (( (data.home_prob ?? data.probabilities?.home_win ?? 0) + (data.away_prob ?? data.probabilities?.away_win ?? 0) ) / 1.5),
            best_bet_market: data.value_bets?.[0]?.market_name ?? 'Match Odds',
            best_bet_selection: data.value_bets?.[0]?.selection ?? 'Home',
            best_bet_odds: data.value_bets?.[0]?.odds ?? 1.9,
            best_bet_ev: data.value_bets?.[0]?.ev ?? 0,
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
                  AI Models Operational ({dashboardStats.system_mode || 'Live'} Mode)
                </p>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="relative">
              <button 
                onClick={() => setShowNotifications(!showNotifications)}
                className="relative w-10 h-10 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center justify-center hover:bg-zinc-800 transition-colors"
              >
                <Bell className="w-5 h-5 text-zinc-400" />
                <span className="absolute top-0 right-0 w-2.5 h-2.5 bg-orange-500 border-2 border-[#0a0a0a] rounded-full" />
              </button>

              <AnimatePresence>
                {showNotifications && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                    className="absolute right-0 mt-4 w-80 bg-[#111] border border-zinc-800 rounded-2xl shadow-2xl z-[100] overflow-hidden"
                  >
                    <div className="p-4 border-b border-zinc-800 flex justify-between items-center bg-zinc-900/50">
                      <h3 className="font-bold text-sm">Notifications</h3>
                      <button onClick={() => setShowNotifications(false)}><X className="w-4 h-4 text-zinc-500" /></button>
                    </div>
                    <div className="max-h-96 overflow-y-auto">
                      {notifications.length > 0 ? notifications.map(n => (
                        <div key={n.id} className="p-4 border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors cursor-default">
                          <div className="flex justify-between items-start mb-1">
                            <p className="text-xs font-bold text-zinc-200">{n.title}</p>
                            <span className="text-[10px] text-zinc-600 font-mono">{n.time}</span>
                          </div>
                          <p className="text-[11px] text-zinc-500 leading-relaxed">{n.message}</p>
                        </div>
                      )) : (
                        <div className="p-8 text-center text-zinc-600 text-xs italic">No new notifications</div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
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
                        <StatItem icon={<History className="text-blue-500" />} label="Total Predictions" value={`${dashboardStats.total_predictions ?? 0} matches`} />
                        <StatItem icon={<Activity className="text-purple-500" />} label="Platform Win Rate" value={dashboardStats.win_rate ?? "0%"} />
                        <StatItem icon={<TrendingUp className="text-green-500" />} label="Active Value Bets" value={dashboardStats.active_value_bets ?? 0} />
                        <StatItem icon={<Zap className="text-yellow-500" />} label="Portfolio ROI" value={dashboardStats.portfolio_roi ?? "0%"} />
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
                      {(liveValueBets || []).length > 0 ? ((liveValueBets || []).slice(0, 4)).map((bet, i) => (
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
                      <p className="text-sm text-zinc-500">Select any two teams or choose a live fixture below to generate a report.</p>
                    </div>
                    <div className="flex p-1 bg-zinc-900 border border-zinc-800 rounded-xl">
                      <button onClick={() => { setFromDate(new Date().toISOString().split('T')[0]); setToDate(new Date().toISOString().split('T')[0]); }} className={cn("px-4 py-1.5 rounded-lg text-[10px] font-bold transition-all", fromDate === new Date().toISOString().split('T')[0] ? "bg-orange-500 text-black" : "text-zinc-500 hover:text-white")}>Today</button>
                      <button onClick={() => { 
                        const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1);
                        setFromDate(tomorrow.toISOString().split('T')[0]); 
                        setToDate(tomorrow.toISOString().split('T')[0]); 
                      }} className={cn("px-4 py-1.5 rounded-lg text-[10px] font-bold transition-all", fromDate !== new Date().toISOString().split('T')[0] ? "bg-orange-500 text-black" : "text-zinc-500 hover:text-white")}>Tomorrow</button>
                    </div>
                  </div>

                  {todayMatches.length > 0 && (
                    <div className="space-y-4">
                      <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest ml-4">Quick Select: Upcoming Fixtures</p>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {todayMatches.slice(0, 6).map((match: any) => (
                          <button 
                            key={match.id}
                            onClick={() => {
                              // Find if these teams exist in our local DB to get their IDs
                              const hTeam = teams.find(t => t.name.toLowerCase().includes(match.homeTeam.name.toLowerCase()) || match.homeTeam.name.toLowerCase().includes(t.name.toLowerCase()));
                              const aTeam = teams.find(t => t.name.toLowerCase().includes(match.awayTeam.name.toLowerCase()) || match.awayTeam.name.toLowerCase().includes(t.name.toLowerCase()));
                              
                              if (hTeam) setSelectedHome(hTeam.id);
                              if (aTeam) setSelectedAway(aTeam.id);
                              
                              if (!hTeam || !aTeam) {
                                flashMessage(setError, "One or both teams not found in Database. Using API data only.");
                              }
                            }}
                            className="bg-zinc-900/50 border border-zinc-800 p-4 rounded-2xl text-left hover:border-orange-500/50 transition-all group"
                          >
                            <div className="flex justify-between items-center mb-2">
                               <span className="text-[9px] font-mono text-zinc-600 uppercase">{match.league}</span>
                               <span className="text-[9px] text-zinc-500">{new Date(match.date).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                            </div>
                            <div className="flex items-center gap-3">
                               <div className="flex-1 space-y-1">
                                  <div className="flex items-center gap-2">
                                     <img src={match.homeTeam.logo} alt="" className="w-4 h-4 object-contain opacity-50 group-hover:opacity-100" />
                                     <p className="text-xs font-bold truncate">{match.homeTeam.name}</p>
                                  </div>
                                  <div className="flex items-center gap-2">
                                     <img src={match.awayTeam.logo} alt="" className="w-4 h-4 object-contain opacity-50 group-hover:opacity-100" />
                                     <p className="text-xs font-bold truncate">{match.awayTeam.name}</p>
                                  </div>
                               </div>
                               <PlusCircle className="w-4 h-4 text-zinc-800 group-hover:text-orange-500" />
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {teams.length === 0 ? (
                    <div className="bg-orange-500/5 border border-orange-500/10 p-12 rounded-[2rem] text-center space-y-6">
                      <Database className="w-16 h-16 text-orange-500 mx-auto" />
                      <div className="space-y-2">
                        <p className="text-xl font-bold">Team Database Not Initialized</p>
                        <p className="text-sm text-zinc-500 max-w-md mx-auto">Please wait for the automated pipeline to seed the database, or check the system health.</p>
                        </div>
                      {isAdmin && (
                        <div className="flex justify-center gap-4">
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
                              {(teams || []).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                            </select>
                          </div>
                          <div className="md:col-span-1 text-center">
                            <div className="w-12 h-12 bg-zinc-800 rounded-full flex items-center justify-center mx-auto border-4 border-[#111] font-black text-zinc-500 italic">VS</div>
                          </div>
                          <div className="md:col-span-3 space-y-2">
                            <label className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest ml-4">Away Side</label>
                            <select value={selectedAway} onChange={(e) => setSelectedAway(e.target.value)} className="w-full bg-zinc-900/50 border border-zinc-800 rounded-[2rem] p-6 focus:border-orange-500 transition-colors appearance-none cursor-pointer">
                              <option value="">Select Away Team</option>
                              {(teams || []).map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
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
                ) : (dailyPicks || []).length > 0 ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {(dailyPicks || []).map(pred => <PredictionCard key={pred.id} prediction={pred} onGenerateCode={()=>{}} isUserPremium={isPremium} isAdmin={isAdmin} onBroadcast={()=>{}} setShowPremiumModal={()=>{}} />)}
                  </div>
                ) : (
                  <div className="col-span-full py-32 text-center bg-zinc-900/30 border border-dashed border-zinc-800 rounded-[2.5rem]">
                    <BrainCircuit className="w-16 h-16 text-zinc-800 mx-auto mb-4" />
                    <p className="text-zinc-500 text-xl font-bold">No fixtures found for this period.</p>
                    <p className="text-sm text-zinc-600 mt-2">Try checking another date or use the **Admin** tools to sync live fixtures from the cloud.</p>
                  </div>
                )}
                
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <StatCard title="Total Predictions" value={dashboardStats?.total_predictions?.toString() || "0"} icon={<History className="text-blue-500" />} />
                  <StatCard title="Active Value Bets" value={dashboardStats?.active_value_bets?.toString() || "0"} icon={<TrendingUp className="text-green-500" />} />
                  <StatCard title="AI Accuracy" value={dashboardStats?.ai_accuracy || "0%"} icon={<ShieldCheck className="text-orange-500" />} />
                </div>
                
                <div className="pt-12 border-t border-zinc-800/50">
                  <h3 className="text-xl font-bold mb-8">Generated History</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8 opacity-60 grayscale hover:opacity-100 hover:grayscale-0 transition-all">
                    {(predictions || []).map(pred => <PredictionCard key={pred.id} prediction={pred} onGenerateCode={()=>{}} isUserPremium={isPremium} isAdmin={isAdmin} onBroadcast={()=>{}} setShowPremiumModal={()=>{}} />)}
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
            {activeTab === 'predictions' && <PredictionsDashboard />}
            
          </motion.div>
        </div>
      </main>

    </div>
  );
}

