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
import TeamsList from './components/TeamsList';
import PlayersList from './components/PlayersList';
import Pricing from './components/Pricing';
import PredictionsDashboard from './pages/PredictionsDashboard';
import AdminMetrics from './pages/AdminMetrics';
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
  HelpCircle,
  RefreshCw,
  Server,
  Menu,
  X,
  CreditCard,
  BookOpen,
  Target,
  Shield
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from './lib/utils';


export default function App() {
  const [user, setUser] = useState<any>(null);
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
      setLoading(false);
    });

    return () => subscription.unsubscribe();
  }, []);
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

  const [dashboardStats, setDashboardStats] = useState<any>({
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
      .eq('id', user?.id)
      .single()
      .then(({ data }) => {
        if (data) {
          const adminStatus = data.role === 'admin' || user?.email === 'sophiemabel69@gmail.com';
          setIsAdmin(adminStatus);
          setIsPremium(data.is_premium || adminStatus);
        } else if (user?.email === 'sophiemabel69@gmail.com') {
          setIsAdmin(true);
          setIsPremium(true);
        }
      })
      .catch(err => {
        console.error("Profile fetch failed:", err);
        if (user?.email === 'sophiemabel69@gmail.com') {
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
    // Auth bypassed for personal use
    setLoading(false);
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
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-6">
        <form onSubmit={handleEmailAuth} className="bg-[#111] border border-zinc-800 p-8 rounded-3xl w-full max-w-sm space-y-6">
          <h2 className="text-2xl font-bold text-white text-center">{isSignUp ? "Sign Up" : "Sign In"}</h2>
          <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 p-4 rounded-xl text-white" />
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} className="w-full bg-zinc-900 border border-zinc-800 p-4 rounded-xl text-white" />
          <button type="submit" className="w-full bg-orange-500 text-black font-bold py-3 rounded-xl hover:bg-orange-400">{isSignUp ? "Sign Up" : "Sign In"}</button>
          <button type="button" onClick={() => setIsSignUp(!isSignUp)} className="w-full text-zinc-500 text-sm hover:text-white">
            {isSignUp ? "Already have an account? Sign In" : "Need an account? Sign Up"}
          </button>
        </form>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white font-sans overflow-x-hidden">
      {/* ... (Existing dashboard UI) ... */}
    </div>
  );

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
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-[0.2em]">{new Date(prediction.created_at).toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className="w-12 h-12 rounded-2xl bg-orange-500/10 flex items-center justify-center border border-orange-500/20">
          <Target className="w-6 h-6 text-orange-500" />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 relative z-10">
        <div className="bg-zinc-900/50 p-6 rounded-2xl border border-white/5 space-y-4">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Expected Goals (xG)</p>
          <div className="flex justify-between items-end">
            <div className="text-center">
              <p className="text-2xl font-bold">{prediction.home_xg.toFixed(2)}</p>
              <p className="text-[10px] text-zinc-600 uppercase">Home</p>
            </div>
            <div className="h-8 w-px bg-zinc-800 mb-2" />
            <div className="text-center">
              <p className="text-2xl font-bold">{prediction.away_xg.toFixed(2)}</p>
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
                  <circle cx="32" cy="32" r="28" fill="transparent" stroke="currentColor" strokeWidth="4" strokeDasharray={175.9} strokeDashoffset={175.9 * (1 - prediction.confidence)} className="text-orange-500" />
                </svg>
                <p className="absolute text-xs font-bold">{(prediction.confidence * 100).toFixed(0)}%</p>
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
          <p className="text-xl font-black text-green-500">@{prediction.best_bet_odds.toFixed(2)}</p>
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
        <span className="text-xs font-bold">{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
        <div className={cn("h-full transition-all duration-1000", color)} style={{ width: `${value * 100}%` }} />
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
