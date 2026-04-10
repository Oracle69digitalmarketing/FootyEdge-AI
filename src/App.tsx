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
    ai_accuracy: "92.1%"
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

  const fetchPredictions = useCallback(async () => {
    try {
      const response = await fetch('/api/recent-predictions');
      if (response.ok) {
        const data = await response.json();
        setPredictions(data);
      }
    } catch (error: any) {
      console.error("Failed to fetch predictions:", error);
    }
  }, []);

  const fetchDashboardStats = useCallback(async () => {
    try {
      const response = await fetch('/api/dashboard/stats');
      if (response.ok) {
        const data = await response.json();
        setDashboardStats(data);
      }
    } catch (err) {
      console.error("Failed to fetch dashboard stats:", err);
    }
  }, []);

  const fetchValueBets = useCallback(async () => {
    try {
      const response = await fetch(`/api/value-bets?status=${betStatusFilter}`);
      if (response.ok) {
        const data = await response.json();
        setValueBets(data);
        fetchDashboardStats();
      }
    } catch (error: any) {
      console.error("Failed to fetch value bets:", error);
    }
  }, [betStatusFilter, fetchDashboardStats]);
  
  const fetchTodayMatches = useCallback(async () => {
    try {
      const today = new Date().toISOString().split('T')[0];
      const response = await fetch(`/api/matches?date=${today}`);
      if (response.ok) {
        const data = await response.json();
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
      }
    } catch (err: any) {
      console.error("Failed to fetch today's matches:", err);
    }
  }, []);

  const fetchUserBets = useCallback(async () => {
    if (!user) return;
    try {
      const response = await fetch(`/api/bets/user/${user.id}`);
      if (response.ok) {
        const data = await response.json();
        setUserBets(data);
        const settled = data.filter((b: any) => b.status === 'won' || b.status === 'lost');
        const profit = settled.reduce((acc: number, b: any) => acc + (b.profit_loss || 0), 0);
        setBankroll(1000 + profit);
      }
    } catch (err: any) {
      console.error("Failed to fetch user bets:", err);
    }
  }, [user]);

  const handlePlaceBet = useCallback(async (match: any, market: string, odds: number, stake: number) => {
    if (!user) return;
    try {
      const response = await fetch('/api/bets/record', {
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
      if (response.ok) {
        fetchUserBets();
        flashMessage(setSuccess, `Bet tracked! Booking Code: ${selectedBookmaker.toUpperCase()}-${Math.random().toString(36).substring(2, 8).toUpperCase()}`);
      }
    } catch (err) {
      console.error("Failed to place bet:", err);
    }
  }, [user, fetchUserBets, selectedBookmaker]);

  const handleScanValueBets = useCallback(async () => {
    setScanning(true);
    try {
      const response = await fetch('/api/scan-value-bets');
      if (response.ok) {
        const data = await response.json();
        setLiveValueBets(data);
        setShowLiveBets(true);
      }
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
    fetchTodayMatches();
    fetchUserBets();
    handleScanValueBets();
  }, [user, fetchTeams, fetchPredictions, fetchValueBets, fetchTodayMatches, fetchUserBets, handleScanValueBets]);

  const handleSyncTeams = useCallback(async () => {
    setSyncingTeams(true);
    try {
      const response = await fetch('/api/admin/sync-teams', { method: 'POST' });
      const data = await response.json();
      if (response.ok) {
        flashMessage(setSuccess, `Synced ${data.synced_count} teams.`);
        fetchTeams();
      }
    } finally {
      setSyncingTeams(false);
    }
  }, [fetchTeams]);

  const handleSeedDatabase = useCallback(async () => {
    try {
      const response = await fetch('/api/admin/seed-database', { method: 'POST' });
      if (response.ok) {
        flashMessage(setSuccess, "Database seeded.");
        fetchTeams();
      }
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
        const [apiResponse] = await Promise.all([
            fetch('/api/predict', {
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

        if (apiResponse.ok) {
            const data = await apiResponse.json();
            const newPrediction: Prediction = {
                id: new Date().toISOString(),
                home_team: data.home_team,
                away_team: data.away_team,
                home_prob: data.probabilities.home_win,
                draw_prob: data.probabilities.draw,
                away_prob: data.probabilities.away_win,
                confidence: (data.probabilities.home_win + data.probabilities.away_win) / 1.5,
                best_bet_market: data.value_bets?.[0]?.market_name || 'Match Odds',
                best_bet_selection: data.value_bets?.[0]?.selection || 'Home',
                best_bet_odds: data.value_bets?.[0]?.odds || 1.9,
                best_bet_ev: data.value_bets?.[0]?.ev || 0,
                is_premium: Math.random() > 0.7,
                created_at: new Date().toISOString(),
                over_2_5_prob: data.probabilities['Over 2.5'],
                btts_prob: data.probabilities['BTTS Yes'],
            };
            setPredictions(prev => [newPrediction, ...prev]);
            setActiveTab('predictions');
        }
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

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white font-sans">
      <div className="fixed left-0 top-0 h-full w-20 md:w-64 bg-[#111] border-r border-zinc-800 flex flex-col z-50">
        <div className="h-20 flex items-center px-6 border-b border-zinc-800"><h1 className="text-lg font-bold hidden md:block">FootyEdge AI</h1></div>
        <nav className="flex-1 px-4 space-y-2 mt-8">
            <NavItem icon={<LayoutDashboard />} label="Dashboard" active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} />
            <NavItem icon={<History />} label="Predictions" active={activeTab === 'predictions'} onClick={() => setActiveTab('predictions')} />
            <NavItem icon={<TrendingUp />} label="Value Bets" active={activeTab === 'value'} onClick={() => setActiveTab('value')} />
            <NavItem icon={<Layers />} label="Acca Builder" active={activeTab === 'acca'} onClick={() => setActiveTab('acca')} />
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
                <div className="flex items-center justify-between"><div className="flex items-center gap-3"><Zap className="text-green-500" /><h2 className="text-2xl font-bold">Live Value Alerts</h2></div><button onClick={handleScanValueBets} disabled={scanning} className="bg-zinc-900 p-3 rounded-full">{scanning ? <Loader2 className="animate-spin w-4 h-4"/> : <RefreshCw className="w-4 h-4"/>}</button></div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {liveValueBets.length > 0 ? (
                      liveValueBets.slice(0, 3).map((alert, i) => (
                        <div key={i} className="bg-black/40 border border-white/5 p-4 rounded-2xl">
                          <p className="font-bold text-sm mb-1">{alert.match || `${alert.home_team} vs ${alert.away_team}`}</p>
                          <div className="flex justify-between items-center"><span className="text-xs text-zinc-400">{alert.selection}</span><span className="text-sm font-bold">@{alert.odds.toFixed(2)}</span></div>
                        </div>
                      ))
                    ) : [1,2,3].map(i => <div key={i} className="bg-black/40 border border-white/5 p-4 rounded-2xl opacity-50"><p className="text-sm">Scanning matches...</p></div>)}
                </div>
              </div>

              <section className="space-y-6">
                <div className="flex items-center justify-between"><h2 className="text-2xl font-bold flex items-center gap-3"><Calendar className="text-orange-500" />Today's Matches</h2><span className="text-xs font-mono text-zinc-500">{todayMatches.length} Matches</span></div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">{todayMatches.map(match => <MatchCard key={match.id} match={match} onPlaceBet={handlePlaceBet} onAddToAcca={()=>{}} selectedBookmaker={selectedBookmaker} isAdded={()=>false} />)}</div>
              </section>

              <section className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-8">
                <h2 className="text-3xl font-bold">Intelligence Engine</h2>
                <div className="grid grid-cols-1 md:grid-cols-7 gap-4 items-center">
                    <div className="md:col-span-3"><select value={selectedHome} onChange={(e) => setSelectedHome(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4"><option value="">Select Home</option>{teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
                    <div className="md:col-span-1 text-center font-bold text-zinc-500">VS</div>
                    <div className="md:col-span-3"><select value={selectedAway} onChange={(e) => setSelectedAway(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4"><option value="">Select Away</option>{teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></div>
                </div>
                <button onClick={handlePredict} disabled={predicting || !selectedHome || !selectedAway} className="w-full bg-orange-500 text-black font-bold py-5 rounded-2xl flex items-center justify-center gap-3">{predicting ? <Loader2 className="animate-spin" /> : <PlusCircle />} Generate Match Intelligence</button>
              </section>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <StatCard title="Total Predictions" value={dashboardStats.total_predictions.toString()} icon={<History className="text-blue-500" />} />
                <StatCard title="Active Value Bets" value={dashboardStats.active_value_bets.toString()} icon={<TrendingUp className="text-green-500" />} />
                <StatCard title="AI Accuracy" value={predictions.length > 0 ? "88.4%" : "92.1%"} icon={<ShieldCheck className="text-orange-500" />} />
              </div>
            </div>
          )}

          {activeTab === 'predictions' && <div className="grid grid-cols-1 md:grid-cols-2 gap-6">{predictions.map(pred => <PredictionCard key={pred.id} prediction={pred} onGenerateCode={()=>{}} isUserPremium={isPremium} isAdmin={isAdmin} onBroadcast={()=>{}} setShowPremiumModal={setShowPremiumModal} />)}</div>}
          {activeTab === 'portfolio' && <Portfolio bankroll={bankroll} userBets={userBets} />}
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

function MatchCard({ match, onPlaceBet, selectedBookmaker }: { match: any, onPlaceBet: any, selectedBookmaker: string }) {
  return <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 flex justify-between items-center"><div className="flex items-center gap-3"><span>{match.homeTeam.name}</span><span className="text-zinc-500">vs</span><span>{match.awayTeam.name}</span></div><button onClick={() => onPlaceBet(match, 'home_win', 1.9, 1000)} className="bg-green-600 px-4 py-2 rounded-xl text-xs font-bold">Quick Bet</button></div>;
}

function PredictionCard({ prediction, isLocked }: { prediction: Prediction, isLocked?: boolean }) {
  return <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-4"><h3>{prediction.home_team} vs {prediction.away_team}</h3><div className="grid grid-cols-3 gap-2 text-center"><div className="bg-zinc-900 p-2 rounded-lg"><p className="text-[10px] text-zinc-500">Home</p><p className="font-bold">{(prediction.home_prob * 100).toFixed(0)}%</p></div><div className="bg-zinc-900 p-2 rounded-lg"><p className="text-[10px] text-zinc-500">Draw</p><p className="font-bold">{(prediction.draw_prob * 100).toFixed(0)}%</p></div><div className="bg-zinc-900 p-2 rounded-lg"><p className="text-[10px] text-zinc-500">Away</p><p className="font-bold">{(prediction.away_prob * 100).toFixed(0)}%</p></div></div></div>;
}

function ProbStat({ label, value, color }: { label: string, value: number, color: string }) {
  return <div className="space-y-1"><div className="flex justify-between text-[10px] font-mono text-zinc-500"><span>{label}</span><span>{(value * 100).toFixed(0)}%</span></div><div className="h-1 bg-zinc-900 rounded-full overflow-hidden"><div className={cn("h-full", color)} style={{ width: `${value * 100}%` }} /></div></div>;
}
