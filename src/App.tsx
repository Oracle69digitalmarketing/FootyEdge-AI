import { useState, useEffect } from 'react';
import { supabase } from './supabase';
import { Team, Prediction, ValueBet } from './types';
import TeamSearch from './components/TeamSearch';
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
  TrendingUp as TrendingUpIcon
} from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { motion, AnimatePresence } from 'motion/react';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState<Team[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [liveValueBets, setLiveValueBets] = useState<ValueBet[]>([]);
  const [scanning, setScanning] = useState(false);
  const [showLiveBets, setShowLiveBets] = useState(false);
  const [selectedHome, setSelectedHome] = useState<string>('');
  const [selectedAway, setSelectedAway] = useState<string>('');
  const [predicting, setPredicting] = useState(false);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'predictions' | 'value' | 'players' | 'portfolio' | 'acca' | 'premium' | 'admin' | 'teams'>('dashboard');
  const [error, setError] = useState<string | null>(null);
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
  const [bankroll, setBankroll] = useState(10000); // Default 10k NGN
  const [bookingCode, setBookingCode] = useState<string | null>(null);
  const [generatingCode, setGeneratingCode] = useState(false);
  const [accaSelections, setAccaSelections] = useState<any[]>([]);
  const [selectedBookmaker, setSelectedBookmaker] = useState<'bet9ja' | 'sportybet' | '1xbet'>('bet9ja');
  const [isPremium, setIsPremium] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [showPremiumModal, setShowPremiumModal] = useState(false);

  useEffect(() => {
    if (!user || !supabase) return;
    // Check if user is premium and admin from profile
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

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }

    // Check auth session
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

    // Fetch initial data
    fetchTeams();
    fetchPredictions();
    fetchValueBets();
    fetchTodayMatches();
    fetchUserBets();

    // Set up real-time subscriptions
    const predictionsSub = supabase
      .channel('predictions-changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'predictions' }, (payload) => {
        setPredictions(prev => [payload.new as Prediction, ...prev].slice(0, 10));
      })
      .subscribe();

    const valueBetsSub = supabase
      .channel('value-bets-changes')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'value_bets' }, (payload) => {
        setValueBets(prev => [payload.new as ValueBet, ...prev].slice(0, 10));
      })
      .subscribe();

    return () => {
      predictionsSub.unsubscribe();
      valueBetsSub.unsubscribe();
    };
  }, [user]);

  const fetchTeams = async () => {
    if (!supabase) return;
    const { data, error } = await supabase.from('teams').select('*').order('name');
    if (error) setError(error.message);
    else setTeams(data || []);
  };

  const fetchPredictions = async () => {
    const response = await fetch('/api/predictions');
    if (response.ok) {
      const data = await response.json();
      setPredictions(data);
    }
  };

  const fetchValueBets = async () => {
    const response = await fetch(`/api/value-bets?status=${betStatusFilter}`);
    if (response.ok) {
      const data = await response.json();
      setValueBets(data);
    }
  };

  const fetchTodayMatches = async () => {
    try {
      const response = await fetch('/api/matches/today');
      if (response.ok) {
        const data = await response.json();
        setTodayMatches(data);
      }
    } catch (err) {
      console.error("Failed to fetch matches:", err);
    }
  };

  const fetchUserBets = async () => {
    if (!user) return;
    try {
      const response = await fetch(`/api/bets/user/${user.id}`);
      if (response.ok) {
        const data = await response.json();
        setUserBets(data);
        
        // Calculate bankroll based on settled bets
        const settled = data.filter((b: any) => b.status === 'won' || b.status === 'lost');
        const profit = settled.reduce((acc: number, b: any) => acc + (b.profit_loss || 0), 0);
        setBankroll(1000 + profit);
      }
    } catch (err) {
      console.error("Failed to fetch user bets:", err);
    }
  };

  const handlePlaceBet = async (match: any, market: string, odds: number, stake: number) => {
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
        // Show a simulated Bet9ja success
        alert(`Bet tracked in FootyEdge! Use Booking Code: B9JA-${Math.random().toString(36).substring(2, 8).toUpperCase()} on Bet9ja.`);
      }
    } catch (err) {
      console.error("Failed to place bet:", err);
    }
  };

  const generateBookingCode = async (predictionId: string) => {
    setGeneratingCode(true);
    // Simulate AI mapping to Bet9ja markets
    await new Promise(r => setTimeout(r, 1500));
    setBookingCode(`B9-${Math.random().toString(36).substring(2, 9).toUpperCase()}`);
    setGeneratingCode(false);
  };

  useEffect(() => {
    if (user) {
      fetchValueBets();
    }
  }, [betStatusFilter]);

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!supabase) return;
    setError(null);
    
    if (isSignUp) {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) setError(error.message);
      else setError("Check your email for the confirmation link!");
    } else {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) setError(error.message);
    }
  };

  const handleSeedDatabase = async () => {
    try {
      setError(null);
      const initialTeams = [
        { name: 'Manchester City', elo_rating: 1950, attack_strength: 2.4, defense_strength: 0.8, form_rating: 0.8, league: 'Premier League' },
        { name: 'Liverpool', elo_rating: 1900, attack_strength: 2.2, defense_strength: 0.9, form_rating: 0.7, league: 'Premier League' },
        { name: 'Arsenal', elo_rating: 1880, attack_strength: 2.1, defense_strength: 0.7, form_rating: 0.9, league: 'Premier League' },
        { name: 'Real Madrid', elo_rating: 1920, attack_strength: 2.3, defense_strength: 1.0, form_rating: 0.6, league: 'La Liga' },
        { name: 'Bayern Munich', elo_rating: 1850, attack_strength: 2.5, defense_strength: 1.1, form_rating: 0.5, league: 'Bundesliga' },
        { name: 'Inter Milan', elo_rating: 1870, attack_strength: 1.9, defense_strength: 0.6, form_rating: 0.8, league: 'Serie A' },
        { name: 'Barcelona', elo_rating: 1820, attack_strength: 2.0, defense_strength: 1.2, form_rating: 0.4, league: 'La Liga' },
        { name: 'PSG', elo_rating: 1800, attack_strength: 2.4, defense_strength: 1.3, form_rating: 0.3, league: 'Ligue 1' }
      ];

      const { error: seedError } = await supabase.from('teams').upsert(initialTeams, { onConflict: 'name' });
      if (seedError) {
        if (seedError.message.includes('relation "public.teams" does not exist')) {
          throw new Error('Database table "teams" not found. Please run the SQL schema in your Supabase SQL Editor first (see supabase_schema.sql in the file explorer).');
        }
        throw seedError;
      }
      
      const { data: teamsData } = await supabase.from('teams').select('*').order('name');
      if (teamsData) setTeams(teamsData);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
  };

  const handlePredict = async () => {
    if (!selectedHome || !selectedAway || selectedHome === selectedAway) return;
    
    setPredicting(true);
    setError(null);
    setSimulationStep(0);
    setSimulationLog([]);

    const agents = [
      { name: "Athena", task: "Ingesting and normalizing team data..." },
      { name: "Ares", task: "Calculating Bayesian Elo and strength ratings..." },
      { name: "Apollo", task: "Executing goal distribution models (xG)..." },
      { name: "Hermes", task: "Detecting value in betting markets..." },
      { name: "Nike", task: "Optimizing stakes via Kelly Criterion..." },
      { name: "Zeus", task: "Synthesizing final match intelligence..." }
    ];

    try {
      // Orchestrate agent work for UI feedback
      for (let i = 0; i < agents.length; i++) {
        setSimulationStep(i + 1);
        setSimulationLog(prev => [...prev, `[${agents[i].name}] ${agents[i].task}`]);
        await new Promise(r => setTimeout(r, 600));
      }

      const response = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ home_team_id: selectedHome, away_team_id: selectedAway })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || 'Prediction failed');
      }

      const result = await response.json();
      
      // Broadcast to Telegram if there's a value bet
      if (result.value_bets && result.value_bets.length > 0) {
        try {
          await fetch('/api/telegram/broadcast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
              prediction: result.prediction, 
              valueBet: result.value_bets[0],
              isPremium: result.prediction.is_premium
            })
          });
        } catch (tgErr) {
          console.error("Telegram broadcast failed:", tgErr);
        }
      }

      await new Promise(r => setTimeout(r, 400));
      setActiveTab('predictions');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setPredicting(false);
      setSimulationStep(0);
    }
  };

  const handlePlayerSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!playerQuery.trim()) return;

    setSearchingPlayers(true);
    setError(null);
    try {
      const response = await fetch(`/api/players/search?query=${encodeURIComponent(playerQuery)}`);
      if (!response.ok) throw new Error('Failed to search players');
      const data = await response.json();
      // Based on typical RapidAPI responses, it might be data.data or data.results
      setPlayers(data.data || data.results || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSearchingPlayers(false);
    }
  };

  const handleScanValueBets = async () => {
    setScanning(true);
    setError(null);
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
      setError(err.message);
    } finally {
      setScanning(false);
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
      
      // Refresh value bets
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
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4 text-white">
        <div className="bg-zinc-900 border border-orange-500/50 p-8 rounded-3xl max-w-lg w-full space-y-6 text-center">
          <div className="w-16 h-16 bg-orange-500/10 rounded-2xl flex items-center justify-center mx-auto">
            <AlertTriangle className="w-8 h-8 text-orange-500" />
          </div>
          <div className="space-y-2">
            <h2 className="text-2xl font-bold">Configuration Required</h2>
            <p className="text-zinc-400">
              Please set up your Supabase environment variables in the <strong>Settings</strong> menu to start using FootyEdge AI.
            </p>
          </div>
          <div className="bg-black/50 p-4 rounded-xl text-left font-mono text-xs space-y-2">
            <p className="text-zinc-500">Required variables:</p>
            <ul className="list-disc list-inside text-zinc-300">
              <li>VITE_SUPABASE_URL</li>
              <li>VITE_SUPABASE_ANON_KEY</li>
            </ul>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="w-full bg-white text-black font-bold py-3 rounded-xl hover:bg-zinc-200 transition-colors"
          >
            Check Again
          </button>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex flex-col items-center justify-center p-4">
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="max-w-md w-full text-center space-y-8"
        >
          <div className="space-y-2">
            <h1 className="text-5xl font-bold tracking-tighter text-white uppercase italic">
              Footy<span className="text-orange-500">Edge</span> AI
            </h1>
            <p className="text-zinc-400 font-mono text-xs uppercase tracking-widest">
              Professional Football Analytics & Value Betting
            </p>
          </div>

          {error && (
            <div className={cn(
              "p-4 rounded-2xl text-sm text-left flex gap-3 border",
              error.includes("confirmation") 
                ? "bg-green-500/10 border-green-500/20 text-green-500" 
                : "bg-red-500/10 border-red-500/20 text-red-500"
            )}>
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <p>{error}</p>
            </div>
          )}

          <form onSubmit={handleEmailAuth} className="space-y-4 text-left">
            <div className="space-y-2">
              <label className="text-xs font-mono text-zinc-500 uppercase tracking-widest ml-1">Email Address</label>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                <input 
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl py-4 pl-12 pr-4 text-white focus:outline-none focus:border-orange-500 transition-colors"
                  required
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-mono text-zinc-500 uppercase tracking-widest ml-1">Password</label>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                <input 
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl py-4 pl-12 pr-4 text-white focus:outline-none focus:border-orange-500 transition-colors"
                  required
                />
              </div>
            </div>

            <button 
              type="submit"
              className="w-full bg-white text-black font-bold py-4 px-8 rounded-full flex items-center justify-center gap-3 hover:bg-orange-500 hover:text-white transition-all duration-300 transform hover:scale-[1.02]"
            >
              <LogIn className="w-5 h-5" />
              {isSignUp ? 'Create Account' : 'Sign In'}
            </button>
          </form>

          <div className="pt-4 space-y-4">
            <button 
              onClick={() => setIsSignUp(!isSignUp)}
              className="text-zinc-500 text-xs font-mono hover:text-orange-500 transition-colors"
            >
              {isSignUp ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
            </button>
            <div className="border-t border-zinc-900 pt-4">
              <p className="text-zinc-500 text-[10px] font-mono leading-relaxed uppercase tracking-tighter">
                Powered by Oracle69 Systems
              </p>
              <p className="text-zinc-600 text-[9px] font-mono leading-relaxed uppercase tracking-tighter">
                Enterprise AI Engine | Multi-Agent Architecture | PostgreSQL
              </p>
            </div>
          </div>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white font-sans selection:bg-orange-500 selection:text-black">
      {/* Sidebar / Nav */}
      <div className="fixed left-0 top-0 h-full w-20 md:w-64 bg-[#111] border-r border-zinc-800 flex flex-col z-50">
        <div className="p-6">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-purple-600 via-blue-500 to-green-400 rounded-full flex items-center justify-center shadow-lg shadow-purple-500/20">
              <Activity className="w-6 h-6 text-white" />
            </div>
            <h2 className="text-xl font-bold tracking-tighter uppercase italic hidden md:block">
              Footy<span className="text-orange-500">Edge</span> <span className="text-zinc-500 text-xs">AI</span>
            </h2>
          </div>
          <div className="md:hidden text-orange-500 font-bold text-2xl mt-2">FE</div>
        </div>
        
        <nav className="flex-1 px-4 space-y-2 mt-8">
          <NavItem 
            active={activeTab === 'dashboard'} 
            onClick={() => setActiveTab('dashboard')}
            icon={<LayoutDashboard />}
            label="Dashboard"
          />
          <NavItem 
            active={activeTab === 'predictions'} 
            onClick={() => setActiveTab('predictions')}
            icon={<History />}
            label="Predictions"
          />
          <NavItem 
            active={activeTab === 'value'} 
            onClick={() => setActiveTab('value')}
            icon={<TrendingUp />}
            label="Value Bets"
          />
           <NavItem 
            active={activeTab === 'teams'} 
            onClick={() => setActiveTab('teams')}
            icon={<Database />}
            label="Teams"
          />
          <NavItem 
            active={activeTab === 'players'} 
            onClick={() => setActiveTab('players')}
            icon={<Search />}
            label="Player Search"
          />
          <NavItem 
            active={activeTab === 'acca'} 
            onClick={() => setActiveTab('acca')}
            icon={<Layers />}
            label="Acca Builder"
          />
          <NavItem 
            active={activeTab === 'portfolio'} 
            onClick={() => setActiveTab('portfolio')}
            icon={<Wallet />}
            label="Portfolio"
          />
          {isPremium && (
            <NavItem 
              active={activeTab === 'premium'} 
              onClick={() => setActiveTab('premium')}
              icon={<Zap className="text-orange-500" />}
              label="Premium Hub"
            />
          )}
          {isAdmin && (
            <NavItem 
              active={activeTab === 'admin'} 
              onClick={() => setActiveTab('admin')}
              icon={<ShieldCheck className="text-blue-500" />}
              label="Admin Panel"
            />
          )}
          <div className="pt-4 mt-4 border-t border-zinc-800">
            <button 
              onClick={() => setShowPremiumModal(true)}
              className={cn(
                "w-full flex items-center gap-3 p-3 rounded-xl transition-all duration-300 group relative overflow-hidden",
                isPremium ? "bg-zinc-900 text-orange-500 border border-orange-500/20" : "bg-orange-500 text-black font-bold shadow-lg shadow-orange-500/20"
              )}
            >
              <Zap className={cn("w-5 h-5", isPremium ? "text-orange-500" : "text-black")} />
              <span className="hidden md:block">{isPremium ? 'Premium Active' : 'Go Premium'}</span>
              {!isPremium && <span className="absolute -right-4 top-0 w-12 h-12 bg-white/20 rotate-45 transform translate-x-4 -translate-y-4" />}
            </button>
          </div>
        </nav>

        <div className="p-4 border-t border-zinc-800">
          <button 
            onClick={handleLogout}
            className="w-full flex items-center gap-3 p-3 text-zinc-400 hover:text-white hover:bg-zinc-800 rounded-xl transition-colors"
          >
            <LogOut className="w-5 h-5" />
            <span className="hidden md:block font-medium">Logout</span>
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
              <h1 className="text-sm font-mono text-zinc-500 uppercase tracking-widest">Oracle69 AI Engine</h1>
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
            <img src={user.user_metadata?.avatar_url || ''} className="w-10 h-10 rounded-full border border-zinc-700" referrerPolicy="no-referrer" />
          </div>
        </header>

        <div className="p-8 max-w-6xl mx-auto space-y-8">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 p-4 rounded-2xl flex items-center gap-3 text-red-500">
              <AlertTriangle className="w-5 h-5" />
              <p className="text-sm font-medium">{error}</p>
            </div>
          )}

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
                  <p className="text-blue-100 max-w-md">Get instant value alerts, daily booking codes, and expert analysis directly on your phone. Join 5,000+ Oracle69 members.</p>
                  <button className="bg-white text-blue-600 px-8 py-3 rounded-xl font-bold hover:bg-blue-50 transition-all flex items-center gap-2">
                    Join Channel <ExternalLink className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex -space-x-4 relative z-10">
                  {[1,2,3,4].map(i => (
                    <div key={i} className="w-12 h-12 rounded-full border-4 border-blue-600 bg-zinc-800 flex items-center justify-center overflow-hidden">
                      <img src={`https://picsum.photos/seed/user${i}/100/100`} alt="user" referrerPolicy="no-referrer" />
                    </div>
                  ))}
                  <div className="w-12 h-12 rounded-full border-4 border-blue-600 bg-blue-500 flex items-center justify-center text-[10px] font-bold text-white">
                    +5k
                  </div>
                </div>
              </div>

              {/* Value Alerts Section */}
              <div className="bg-green-500/5 border border-green-500/20 rounded-[2rem] p-8 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-10">
                  <TrendingUpIcon className="w-32 h-32 text-green-500" />
                </div>
                <div className="relative z-10 space-y-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center">
                      <Zap className="w-5 h-5 text-black" />
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold tracking-tight">Live Value Alerts</h2>
                      <p className="text-xs text-zinc-500 font-mono uppercase tracking-widest">Real-time Bet9ja Inefficiencies</p>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {[
                      { match: "Arsenal vs Man City", market: "Over 2.5", odds: "1.95", edge: "+12.4%", time: "2m ago" },
                      { match: "Real Madrid vs Barca", market: "Home Win", odds: "2.10", edge: "+8.1%", time: "5m ago" },
                      { match: "Luton vs Everton", market: "BTTS - Yes", odds: "1.85", edge: "+15.2%", time: "12m ago" }
                    ].map((alert, i) => (
                      <div key={i} className="bg-black/40 border border-white/5 p-4 rounded-2xl hover:border-green-500/30 transition-all cursor-pointer group">
                        <div className="flex justify-between items-start mb-3">
                          <span className="text-[10px] font-mono text-zinc-500">{alert.time}</span>
                          <span className="text-[10px] font-mono text-green-500 font-bold">{alert.edge} Edge</span>
                        </div>
                        <p className="font-bold text-sm mb-1">{alert.match}</p>
                        <div className="flex justify-between items-center">
                          <span className="text-xs text-zinc-400">{alert.market}</span>
                          <span className="text-sm font-bold text-white">@{alert.odds}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Today's Matches */}
              <section className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-2xl font-bold tracking-tight flex items-center gap-3">
                    <Calendar className="w-6 h-6 text-orange-500" />
                    Today's Matches
                  </h2>
                  <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">{todayMatches.length} Found</span>
                </div>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {todayMatches.map(match => (
                    <MatchCard 
                      key={match.id} 
                      match={match} 
                      onPlaceBet={handlePlaceBet} 
                      onAddToAcca={(match, market, odds) => setAccaSelections(prev => [...prev, { match, market, odds }])}
                      selectedBookmaker={selectedBookmaker}
                    />
                  ))}
                </div>
              </section>

              {/* Intelligence Engine */}
              <section className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-8">
                <div className="space-y-2">
                  <h2 className="text-3xl font-bold tracking-tight">Intelligence Engine</h2>
                  <p className="text-zinc-400">Select teams to generate deep match intelligence via Supabase.</p>
                </div>

                {teams.length === 0 ? (
                  <div className="p-12 text-center space-y-6 bg-zinc-900/50 rounded-2xl border border-dashed border-zinc-800">
                    <Database className="w-12 h-12 text-zinc-700 mx-auto" />
                    <div className="space-y-2">
                      <p className="text-zinc-500">No teams found in database. Please run the schema and seed data.</p>
                      <button 
                        onClick={handleSeedDatabase}
                        className="bg-orange-500/10 text-orange-500 border border-orange-500/20 px-6 py-2 rounded-full text-xs font-bold hover:bg-orange-500/20 transition-all"
                      >
                        Seed Database
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-7 gap-4 items-center">
                    <div className="md:col-span-3 space-y-2">
                      <label className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Home Team</label>
                      <select 
                        value={selectedHome}
                        onChange={(e) => setSelectedHome(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 focus:outline-none focus:border-orange-500 transition-colors appearance-none"
                      >
                        <option value="">Select Home Team</option>
                        {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                    </div>

                    <div className="md:col-span-1 flex justify-center">
                      <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center font-bold text-zinc-500">VS</div>
                    </div>

                    <div className="md:col-span-3 space-y-2">
                      <label className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Away Team</label>
                      <select 
                        value={selectedAway}
                        onChange={(e) => setSelectedAway(e.target.value)}
                        className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 focus:outline-none focus:border-orange-500 transition-colors appearance-none"
                      >
                        <option value="">Select Away Team</option>
                        {teams.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                      </select>
                    </div>
                  </div>
                )}

                <button 
                  onClick={handlePredict}
                  disabled={predicting || !selectedHome || !selectedAway || selectedHome === selectedAway}
                  className="w-full bg-orange-500 text-black font-bold py-5 rounded-2xl flex items-center justify-center gap-3 hover:bg-orange-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {predicting ? <Loader2 className="w-6 h-6 animate-spin" /> : <PlusCircle className="w-6 h-6" />}
                  {predicting ? 'Orchestrating Agents...' : 'Generate Match Intelligence'}
                </button>

                <AnimatePresence>
                  {predicting && (
                    <motion.div 
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="space-y-3 pt-4"
                    >
                      <div className="flex justify-between items-center px-1">
                        <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Agent Progress</span>
                        <span className="text-[10px] font-mono text-orange-500 uppercase tracking-widest">{Math.round((simulationStep / 6) * 100)}%</span>
                      </div>
                      <div className="h-1 w-full bg-zinc-900 rounded-full overflow-hidden">
                        <motion.div 
                          className="h-full bg-orange-500"
                          initial={{ width: 0 }}
                          animate={{ width: `${(simulationStep / 6) * 100}%` }}
                        />
                      </div>
                      <div className="space-y-1.5">
                        {simulationLog.map((log, idx) => (
                          <motion.p 
                            key={idx}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            className="text-[10px] font-mono text-zinc-400 flex items-center gap-2"
                          >
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
                <StatCard 
                  title="Total Predictions" 
                  value={predictions.length.toString()} 
                  icon={<History className="text-blue-500" />} 
                />
                <StatCard 
                  title="Active Value Bets" 
                  value={valueBets.length.toString()} 
                  icon={<TrendingUp className="text-green-500" />} 
                />
                <StatCard 
                  title="AI Accuracy" 
                  value="92.1%" 
                  icon={<ShieldCheck className="text-orange-500" />} 
                />
              </div>
            </div>
          )}

          {activeTab === 'predictions' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Recent Predictions</h2>
                <div className="flex items-center gap-2 text-xs font-mono text-zinc-500">
                  <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  Live Bet9ja Sync
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {predictions.map(pred => (
                  <PredictionCard 
                    key={pred.id} 
                    prediction={pred} 
                    onGenerateCode={generateBookingCode} 
                    isUserPremium={isPremium}
                    isAdmin={isAdmin}
                    onBroadcast={async (prediction, valueBet) => {
                      try {
                        const res = await fetch('/api/telegram/broadcast', {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ 
                            prediction, 
                            valueBet,
                            isPremium: prediction.is_premium
                          })
                        });
                        const data = await res.json();
                        if (data.success) alert("Broadcast successful!");
                        else alert("Broadcast failed: " + data.error);
                      } catch (err) {
                        alert("Broadcast error: " + err);
                      }
                    }}
                  />
                ))}
              </div>
            </div>
          )}

          {activeTab === 'value' && (
            <div className="space-y-6">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h2 className="text-3xl font-bold tracking-tight">Value Bets</h2>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleScanValueBets}
                    disabled={scanning}
                    className="bg-orange-500 text-black font-bold px-6 py-2 rounded-xl hover:bg-orange-400 transition-all disabled:opacity-50 flex items-center gap-2"
                  >
                    {scanning ? <Loader2 className="w-5 h-5 animate-spin" /> : <Zap className="w-5 h-5" />}
                    Live Scan
                  </button>
                  <div className="flex bg-zinc-900 p-1 rounded-xl border border-zinc-800">
                  {(['active', 'won', 'lost', 'all'] as const).map((status) => (
                    <button
                      key={status}
                      onClick={() => {
                        setBetStatusFilter(status);
                        setShowLiveBets(false);
                      }}
                      className={cn(
                        "px-4 py-2 rounded-lg text-sm font-medium transition-all capitalize",
                        !showLiveBets && betStatusFilter === status 
                          ? "bg-zinc-800 text-white shadow-lg" 
                          : "text-zinc-500 hover:text-zinc-300"
                      )}
                    >
                      {status}
                    </button>
                  ))}
                  </div>
                </div>
              </div>

              <div className="bg-[#111] border border-zinc-800 rounded-3xl overflow-hidden">
                <table className="w-full text-left">
                  <thead className="bg-zinc-900/50 border-b border-zinc-800">
                    <tr>
                      <th className="p-6 text-xs font-mono text-zinc-500 uppercase tracking-widest">Match</th>
                      <th className="p-6 text-xs font-mono text-zinc-500 uppercase tracking-widest">Selection</th>
                      <th className="p-6 text-xs font-mono text-zinc-500 uppercase tracking-widest">Status</th>
                      <th className="p-6 text-xs font-mono text-zinc-500 uppercase tracking-widest">Odds</th>
                      <th className="p-6 text-xs font-mono text-zinc-500 uppercase tracking-widest">EV</th>
                      <th className="p-6 text-xs font-mono text-zinc-500 uppercase tracking-widest">Stake</th>
                      <th className="p-6 text-xs font-mono text-zinc-500 uppercase tracking-widest">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800">
                    {(showLiveBets ? liveValueBets : valueBets).map(bet => (
                      <tr key={bet.id} className="hover:bg-zinc-800/30 transition-colors">
                        <td className="p-6 font-bold">{showLiveBets ? `${bet.home_team} vs ${bet.away_team}`: bet.match}</td>
                        <td className="p-6 text-zinc-400">{bet.selection}</td>
                        <td className="p-6">
                          <span className={cn(
                            "px-2 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider",
                            bet.status === 'active' ? "bg-blue-500/10 text-blue-500 border border-blue-500/20" :
                            bet.status === 'won' ? "bg-green-500/10 text-green-500 border border-green-500/20" :
                            "bg-red-500/10 text-red-500 border border-red-500/20"
                          )}>
                            {bet.status}
                          </span>
                        </td>
                        <td className="p-6 font-mono text-orange-500">{bet.odds.toFixed(2)}</td>
                        <td className="p-6 font-mono text-green-500">+{(bet.ev * 100).toFixed(1)}%</td>
                        <td className="p-6">
                          <span className="bg-zinc-800 px-3 py-1 rounded-full text-xs font-bold text-zinc-300">
                            {bet.recommended_stake}
                          </span>
                        </td>
                        <td className="p-6">
                          {bet.status === 'active' && !showLiveBets &&(
                            <div className="flex gap-2">
                              <button 
                                onClick={() => updateBetStatus(bet.id, 'won')}
                                className="p-2 hover:bg-green-500/20 rounded-lg transition-colors group"
                                title="Mark as Won"
                              >
                                <CheckCircle className="w-5 h-5 text-zinc-500 group-hover:text-green-500" />
                              </button>
                              <button 
                                onClick={() => updateBetStatus(bet.id, 'lost')}
                                className="p-2 hover:bg-red-500/20 rounded-lg transition-colors group"
                                title="Mark as Lost"
                              >
                                <XCircle className="w-5 h-5 text-zinc-500 group-hover:text-red-500" />
                              </button>
                            </div>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab === 'teams' && (
            <TeamSearch teams={teams} />
          )}

          {activeTab === 'players' && (
            <div className="space-y-8">
              <div className="space-y-2">
                <h2 className="text-3xl font-bold tracking-tight">Player Search</h2>
                <p className="text-zinc-400">Search for football players globally using RapidAPI.</p>
              </div>

              <form onSubmit={handlePlayerSearch} className="flex gap-4">
                <div className="relative flex-1">
                  <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-zinc-500" />
                  <input 
                    type="text" 
                    value={playerQuery}
                    onChange={(e) => setPlayerQuery(e.target.value)}
                    placeholder="Search players (e.g. Messi, Ronaldo...)"
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 pl-12 focus:outline-none focus:border-orange-500 transition-colors"
                  />
                </div>
                <button 
                  type="submit"
                  disabled={searchingPlayers || !playerQuery.trim()}
                  className="bg-orange-500 text-black font-bold px-8 rounded-2xl hover:bg-orange-400 transition-all disabled:opacity-50"
                >
                  {searchingPlayers ? <Loader2 className="w-6 h-6 animate-spin" /> : 'Search'}
                </button>
              </form>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {players.map((player, idx) => (
                  <div key={idx} className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-4 hover:border-zinc-700 transition-colors">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-full bg-zinc-800 flex items-center justify-center">
                        <User className="w-6 h-6 text-zinc-500" />
                      </div>
                      <div>
                        <h3 className="font-bold text-lg">{player.name || player.player_name}</h3>
                        <p className="text-xs text-zinc-500 font-mono uppercase tracking-widest">{player.position || 'Player'}</p>
                      </div>
                    </div>
                    <div className="pt-4 border-t border-zinc-800 flex justify-between items-center">
                      <div className="text-xs text-zinc-500 font-mono">
                        {player.team_name || player.team || 'Unknown Team'}
                      </div>
                      <div className="text-orange-500 text-xs font-bold">
                        {player.nationality || player.country}
                      </div>
                    </div>
                  </div>
                ))}
                {players.length === 0 && !searchingPlayers && playerQuery && (
                  <div className="col-span-full py-12 text-center text-zinc-500">
                    No players found for "{playerQuery}"
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'acca' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2 space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-3xl font-bold tracking-tight">Acca Builder</h2>
                    <p className="text-zinc-500 mt-1">Select high-confidence matches to build your winning slip.</p>
                  </div>
                  <div className="flex bg-zinc-900 p-1 rounded-xl border border-zinc-800">
                    {(['bet9ja', 'sportybet', '1xbet'] as const).map((bookie) => (
                      <button
                        key={bookie}
                        onClick={() => setSelectedBookmaker(bookie)}
                        className={cn(
                          "px-4 py-2 rounded-lg text-xs font-bold transition-all",
                          selectedBookmaker === bookie ? "bg-zinc-800 text-white shadow-lg" : "text-zinc-500 hover:text-zinc-300"
                        )}
                      >
                        {bookie.toUpperCase()}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {todayMatches.map(match => (
                    <MatchCard 
                      key={match.id} 
                      match={match} 
                      onPlaceBet={handlePlaceBet} 
                      onAddToAcca={(match, market, odds) => setAccaSelections(prev => [...prev, { match, market, odds }])}
                      selectedBookmaker={selectedBookmaker}
                    />
                  ))}
                </div>
              </div>

              <div className="space-y-6">
                <AccaBuilder 
                  selections={accaSelections} 
                  onRemove={(idx) => setAccaSelections(prev => prev.filter((_, i) => i !== idx))}
                  onGenerateCode={() => {
                    if (accaSelections.length < 2) return alert("Select at least 2 matches for an accumulator.");
                    alert(`${selectedBookmaker.toUpperCase()} Acca Generated! Code: ${selectedBookmaker === 'bet9ja' ? 'B9JA-' : selectedBookmaker === 'sportybet' ? 'SB-' : '1X-'}${Math.random().toString(36).substring(2, 10).toUpperCase()}`);
                  }}
                  bankroll={bankroll}
                />
                
                <div className="bg-orange-500/5 border border-orange-500/20 rounded-3xl p-6 space-y-4">
                  <div className="flex items-center gap-3">
                    <ShieldCheck className="w-5 h-5 text-orange-500" />
                    <h4 className="font-bold text-sm">Safe Acca Strategy</h4>
                  </div>
                  <p className="text-xs text-zinc-400 leading-relaxed">Oracle69 AI recommends combining 3-5 selections with confidence {'>'} 75% for the optimal balance of risk and reward.</p>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'premium' && isPremium && (
            <div className="space-y-8">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                    <Zap className="text-orange-500" />
                    Premium Hub
                  </h2>
                  <p className="text-zinc-500 mt-1">Exclusive insights and advanced AI metrics for elite bettors.</p>
                </div>
                <div className="bg-orange-500/10 border border-orange-500/20 px-6 py-3 rounded-2xl flex items-center gap-3">
                  <Crown className="w-5 h-5 text-orange-500" />
                  <span className="text-sm font-bold text-orange-500 uppercase tracking-widest">Elite Member</span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                <div className="md:col-span-2 space-y-6">
                  <div className="bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-6 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-8 opacity-10">
                      <TrendingUp className="w-32 h-32 text-orange-500" />
                    </div>
                    <h3 className="text-xl font-bold">Premium Signal Performance</h3>
                    <div className="grid grid-cols-3 gap-4">
                      <div className="p-4 bg-zinc-900 rounded-2xl border border-zinc-800">
                        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Avg. Confidence</p>
                        <p className="text-2xl font-bold text-orange-500">87.4%</p>
                      </div>
                      <div className="p-4 bg-zinc-900 rounded-2xl border border-zinc-800">
                        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">ROI (30d)</p>
                        <p className="text-2xl font-bold text-green-500">+14.2%</p>
                      </div>
                      <div className="p-4 bg-zinc-900 rounded-2xl border border-zinc-800">
                        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Win Rate</p>
                        <p className="text-2xl font-bold text-blue-500">72.1%</p>
                      </div>
                    </div>
                    <p className="text-sm text-zinc-400 leading-relaxed">
                      Your premium access includes the **Oracle69 Deep Analysis Agent**, which processes over 10,000 data points per match, including real-time lineup changes and market sentiment.
                    </p>
                  </div>

                  <div className="bg-zinc-900/50 border border-zinc-800 rounded-3xl p-8 space-y-4">
                    <h3 className="font-bold flex items-center gap-2">
                      <Bell className="w-5 h-5 text-orange-500" />
                      Premium Telegram Alerts
                    </h3>
                    <p className="text-sm text-zinc-400">
                      You are currently receiving **Elite Signals** on Telegram. These include full EV breakdowns and direct booking codes for Bet9ja and SportyBet.
                    </p>
                    <button className="text-orange-500 text-sm font-bold hover:underline">Configure Alert Settings →</button>
                  </div>
                </div>

                <div className="space-y-6">
                  <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-4">
                    <h4 className="font-bold text-sm uppercase tracking-widest text-zinc-500">Upcoming High-Value Matches</h4>
                    <div className="space-y-3">
                      {[1, 2, 3].map(i => (
                        <div key={i} className="p-3 bg-zinc-900 rounded-xl border border-zinc-800 flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className="w-2 h-2 rounded-full bg-orange-500 animate-pulse" />
                            <span className="text-xs font-medium">Match Analysis Pending...</span>
                          </div>
                          <Lock className="w-3 h-3 text-zinc-600" />
                        </div>
                      ))}
                    </div>
                    <p className="text-[10px] text-zinc-500 italic">Next deep-scan in 14 minutes.</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'admin' && isAdmin && (
            <div className="space-y-8">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-3xl font-bold tracking-tight flex items-center gap-3">
                    <ShieldCheck className="text-blue-500" />
                    Admin Control Panel
                  </h2>
                  <p className="text-zinc-500 mt-1">Manage system parameters, broadcast signals, and monitor performance.</p>
                </div>
                <div className="flex gap-4">
                  <button className="bg-zinc-900 border border-zinc-800 px-6 py-3 rounded-2xl text-sm font-bold hover:bg-zinc-800 transition-colors">
                    System Logs
                  </button>
                  <button className="bg-blue-500 text-black px-6 py-3 rounded-2xl text-sm font-bold hover:bg-blue-400 transition-colors">
                    Global Broadcast
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-2">
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Total Users</p>
                  <p className="text-3xl font-bold">1,284</p>
                  <p className="text-xs text-green-500">+12% this week</p>
                </div>
                <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-2">
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Premium Subs</p>
                  <p className="text-3xl font-bold">412</p>
                  <p className="text-xs text-orange-500">32% conversion</p>
                </div>
                <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-2">
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Daily Revenue</p>
                  <p className="text-3xl font-bold">₦84.2k</p>
                  <p className="text-xs text-green-500">Target: ₦100k</p>
                </div>
                <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-2">
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Bot Health</p>
                  <p className="text-3xl font-bold text-green-500">100%</p>
                  <p className="text-xs text-zinc-500">Latency: 42ms</p>
                </div>
              </div>

              <div className="bg-[#111] border border-zinc-800 rounded-3xl overflow-hidden">
                <div className="p-6 border-b border-zinc-800 flex items-center justify-between">
                  <h3 className="font-bold">Recent System Activity</h3>
                  <div className="flex gap-2">
                    <span className="px-3 py-1 bg-zinc-900 rounded-full text-[10px] font-mono text-zinc-500 uppercase">All Events</span>
                  </div>
                </div>
                <div className="p-6 space-y-4">
                  {[
                    { time: '14:22', event: 'Premium Signal Broadcasted', status: 'success' },
                    { time: '14:15', event: 'New Subscription: Weekly Plan', status: 'success' },
                    { time: '13:58', event: 'AI Engine: Deep Scan Completed', status: 'info' },
                    { time: '13:42', event: 'Telegram Webhook: Message Delivered', status: 'success' }
                  ].map((log, i) => (
                    <div key={i} className="flex items-center gap-4 text-sm">
                      <span className="font-mono text-zinc-500">{log.time}</span>
                      <span className="w-2 h-2 rounded-full bg-zinc-700" />
                      <span className="flex-1 text-zinc-300">{log.event}</span>
                      <span className={cn(
                        "text-[10px] font-bold uppercase tracking-widest",
                        log.status === 'success' ? "text-green-500" : "text-blue-500"
                      )}>{log.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'portfolio' && (
            <div className="space-y-8">
              <div className="flex items-center justify-between">
                <h2 className="text-3xl font-bold tracking-tight">Your Portfolio</h2>
                <div className="bg-zinc-900 border border-zinc-800 px-6 py-3 rounded-2xl">
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Available Bankroll</p>
                  <p className="text-2xl font-bold text-green-500">₦{bankroll.toLocaleString()}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <StatCard title="Active Bets" value={userBets.filter(b => b.status === 'pending').length.toString()} icon={<Clock className="text-blue-500" />} />
                <StatCard title="Total Stake" value={`₦${userBets.reduce((acc, b) => acc + b.stake, 0).toFixed(2)}`} icon={<DollarSign className="text-green-500" />} />
                <StatCard title="Win Rate" value={`${((userBets.filter(b => b.status === 'won').length / (userBets.filter(b => b.status !== 'pending').length || 1)) * 100).toFixed(1)}%`} icon={<TrendingUpIcon className="text-orange-500" />} />
                <StatCard title="Net Profit" value={`₦${(bankroll - 10000).toFixed(2)}`} icon={<Wallet className="text-purple-500" />} />
              </div>

              <div className="bg-[#111] border border-zinc-800 rounded-3xl overflow-hidden">
                <div className="p-6 border-b border-zinc-800">
                  <h3 className="font-bold">Betting History</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left">
                    <thead className="bg-zinc-900/50 text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
                      <tr>
                        <th className="px-6 py-4">Match</th>
                        <th className="px-6 py-4">Selection</th>
                        <th className="px-6 py-4">Odds</th>
                        <th className="px-6 py-4">Stake</th>
                        <th className="px-6 py-4">Potential</th>
                        <th className="px-6 py-4">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800">
                      {userBets.map(bet => (
                        <tr key={bet.id} className="hover:bg-zinc-900/30 transition-colors">
                          <td className="px-6 py-4 font-medium">{bet.selection.split(' to ')[0]}</td>
                          <td className="px-6 py-4">
                            <span className="text-xs bg-zinc-800 px-2 py-1 rounded-md">{bet.market}</span>
                          </td>
                          <td className="px-6 py-4 font-mono">{bet.odds}</td>
                          <td className="px-6 py-4 font-mono">₦{bet.stake}</td>
                          <td className="px-6 py-4 font-mono text-green-500">₦{bet.potential_win.toFixed(2)}</td>
                          <td className="px-6 py-4">
                            <span className={cn(
                              "text-[10px] font-bold uppercase px-2 py-1 rounded-full",
                              bet.status === 'won' ? "bg-green-500/10 text-green-500" :
                              bet.status === 'lost' ? "bg-red-500/10 text-red-500" :
                              "bg-blue-500/10 text-blue-500"
                            )}>
                              {bet.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          <AnimatePresence>
            {showPremiumModal && (
              <PremiumModal 
                onClose={() => setShowPremiumModal(false)} 
                onSubscribe={async (plan) => {
                  if (!user) return;
                  const res = await fetch('/api/premium/subscribe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ userId: user.id, plan })
                  });
                  const data = await res.json();
                  if (data.success) {
                    setIsPremium(true);
                    setShowPremiumModal(false);
                    alert(data.message);
                  }
                }}
              />
            )}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

function PremiumModal({ onClose, onSubscribe }: { onClose: () => void, onSubscribe: (plan: string) => void }) {
  const plans = [
    { name: 'Daily Pass', price: '₦2,000', period: '24 Hours', features: ['All Premium Signals', 'Telegram Access', 'Acca Builder'] },
    { name: 'Weekly Pro', price: '₦10,000', period: '7 Days', features: ['All Premium Signals', 'Priority Support', 'Bankroll Strategy', 'Telegram Access'], popular: true },
    { name: 'Monthly Oracle', price: '₦35,000', period: '30 Days', features: ['VIP Telegram Group', '1-on-1 Strategy', 'All Premium Signals', 'Custom Accas'] },
  ];

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md"
    >
      <motion.div 
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.9, y: 20 }}
        className="bg-[#111] border border-zinc-800 w-full max-w-4xl rounded-[2.5rem] overflow-hidden shadow-2xl"
      >
        <div className="p-8 md:p-12 space-y-8">
          <div className="flex justify-between items-start">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-orange-500 font-bold text-sm uppercase tracking-widest">
                <Zap className="w-4 h-4 fill-current" />
                FootyEdge AI Premium
              </div>
              <h2 className="text-4xl font-bold tracking-tight">Unlock the Edge</h2>
              <p className="text-zinc-500 max-w-md">Get access to high-confidence signals with 85%+ historical accuracy and professional bankroll management.</p>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-zinc-800 rounded-full transition-colors">
              <XCircle className="w-8 h-8 text-zinc-500" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {plans.map((plan) => (
              <div 
                key={plan.name}
                className={cn(
                  "p-8 rounded-3xl border transition-all space-y-6 relative",
                  plan.popular ? "bg-zinc-900 border-orange-500/50 shadow-lg shadow-orange-500/5" : "bg-zinc-900/50 border-zinc-800"
                )}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-orange-500 text-black text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest">
                    Most Popular
                  </div>
                )}
                <div className="space-y-1">
                  <h3 className="font-bold text-xl">{plan.name}</h3>
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold">{plan.price}</span>
                    <span className="text-xs text-zinc-500">/ {plan.period}</span>
                  </div>
                </div>
                <ul className="space-y-3">
                  {plan.features.map(f => (
                    <li key={f} className="flex items-center gap-2 text-xs text-zinc-400">
                      <CheckCircle className="w-3 h-3 text-green-500" />
                      {f}
                    </li>
                  ))}
                </ul>
                <button 
                  onClick={() => onSubscribe(plan.name)}
                  className={cn(
                    "w-full py-4 rounded-2xl font-bold text-sm transition-all",
                    plan.popular ? "bg-orange-500 text-black hover:bg-orange-400" : "bg-zinc-800 text-white hover:bg-zinc-700"
                  )}
                >
                  Get Started
                </button>
              </div>
            ))}
          </div>

          <p className="text-center text-[10px] text-zinc-600 font-mono uppercase tracking-widest">
            Secure payment via Paystack & Flutterwave • Instant Activation
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}

function NavItem({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: any, label: string }) {
  return (
    <button 
      onClick={onClick}
      className={cn(
        "w-full flex items-center gap-3 p-3 rounded-xl transition-all duration-300 group",
        active ? "bg-orange-500 text-black font-bold shadow-lg shadow-orange-500/20" : "text-zinc-500 hover:text-white hover:bg-zinc-800"
      )}
    >
      <span className={cn("w-5 h-5", active ? "text-black" : "group-hover:scale-110 transition-transform")}>{icon}</span>
      <span className="hidden md:block">{label}</span>
    </button>
  );
}

function MatchCard({ match, onPlaceBet, onAddToAcca, selectedBookmaker }: { match: any, onPlaceBet: (match: any, market: string, odds: number, stake: number) => void, onAddToAcca: (match: any, market: string, odds: number) => void, selectedBookmaker: string }) {
  const [stake, setStake] = useState(1000); // 1000 NGN default
  const [multiOdds, setMultiOdds] = useState<any>(null);

  useEffect(() => {
    fetch(`/api/matches/${match.id}/odds`)
      .then(res => res.json())
      .then(data => setMultiOdds(data));
  }, [match.id]);

  const currentOdds = multiOdds ? multiOdds[selectedBookmaker] : null;

  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-6 hover:border-zinc-700 transition-colors group">
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">{new Date(match.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} GMT</span>
            <span className="w-1 h-1 rounded-full bg-zinc-700" />
            <span className="text-xs font-mono text-green-500 uppercase tracking-widest">{selectedBookmaker.toUpperCase()} Market Open</span>
          </div>
          <h3 className="text-xl font-bold">{match.homeTeam.name} vs {match.awayTeam.name}</h3>
        </div>
        <div className="w-10 h-10 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center">
          <Calendar className="w-5 h-5 text-zinc-500" />
        </div>
      </div>

      {currentOdds ? (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <button 
              onClick={() => onAddToAcca(match, 'home_win', currentOdds.home_win)}
              className="bg-zinc-900 border border-zinc-800 p-3 rounded-xl hover:border-green-500/50 transition-all text-center group/btn"
            >
              <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest group-hover/btn:text-green-500">Home</p>
              <p className="text-lg font-bold">{currentOdds.home_win}</p>
            </button>
            <button 
              onClick={() => onAddToAcca(match, 'draw', currentOdds.draw)}
              className="bg-zinc-900 border border-zinc-800 p-3 rounded-xl hover:border-green-500/50 transition-all text-center group/btn"
            >
              <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest group-hover/btn:text-green-500">Draw</p>
              <p className="text-lg font-bold">{currentOdds.draw}</p>
            </button>
            <button 
              onClick={() => onAddToAcca(match, 'away_win', currentOdds.away_win)}
              className="bg-zinc-900 border border-zinc-800 p-3 rounded-xl hover:border-green-500/50 transition-all text-center group/btn"
            >
              <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest group-hover/btn:text-green-500">Away</p>
              <p className="text-lg font-bold">{currentOdds.away_win}</p>
            </button>
          </div>

          <div className="flex items-center gap-2 pt-2">
            <div className="flex-1 relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 font-bold text-xs">₦</span>
              <input 
                type="number" 
                value={stake}
                onChange={(e) => setStake(Number(e.target.value))}
                className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-2 pl-8 pr-4 text-sm focus:outline-none focus:border-green-500"
                placeholder="Stake"
              />
            </div>
            <button 
              onClick={() => onPlaceBet(match, 'home_win', currentOdds.home_win, stake)}
              className="bg-green-600 text-white text-xs font-bold px-4 py-2.5 rounded-xl hover:bg-green-500 transition-all shadow-lg shadow-green-900/20"
            >
              Bet
            </button>
            <button 
              onClick={() => alert(`${selectedBookmaker.toUpperCase()} Booking Code: ${currentOdds.booking_prefix}${Math.random().toString(36).substring(2, 8).toUpperCase()}`)}
              className="bg-zinc-800 text-zinc-400 text-[10px] font-bold px-3 py-2.5 rounded-xl hover:bg-zinc-700 transition-all"
            >
              Code
            </button>
          </div>
        </div>
      ) : (
        <div className="h-32 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-700" />
        </div>
      )}
    </div>
  );
}

function AccaBuilder({ selections, onRemove, onGenerateCode, bankroll }: { selections: any[], onRemove: (idx: number) => void, onGenerateCode: () => void, bankroll: number }) {
  const totalOdds = selections.reduce((acc, s) => acc * s.odds, 1).toFixed(2);
  const [stake, setStake] = useState(1000);

  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl overflow-hidden">
      <div className="p-6 border-b border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Layers className="w-5 h-5 text-orange-500" />
          <h3 className="font-bold">Acca Builder</h3>
        </div>
        <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">{selections.length} Selections</span>
      </div>
      
      <div className="p-6 space-y-4">
        {selections.length === 0 ? (
          <div className="py-12 text-center space-y-4">
            <PlusCircle className="w-12 h-12 text-zinc-800 mx-auto" />
            <p className="text-zinc-500 text-sm">Add selections from matches to build your accumulator.</p>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {selections.map((s, idx) => (
                <div key={idx} className="flex items-center justify-between bg-zinc-900/50 p-4 rounded-2xl border border-zinc-800 group">
                  <div>
                    <p className="text-xs font-bold">{s.match.homeTeam.name} vs {s.match.awayTeam.name}</p>
                    <p className="text-[10px] text-zinc-500 uppercase tracking-widest">{s.market.replace('_', ' ')} @ {s.odds}</p>
                  </div>
                  <button 
                    onClick={() => onRemove(idx)}
                    className="text-zinc-600 hover:text-red-500 transition-colors"
                  >
                    <XCircle className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>

            <div className="pt-4 border-t border-zinc-800 space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Total Odds</span>
                <span className="text-2xl font-bold text-orange-500">{totalOdds}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Potential Return</span>
                <span className="text-xl font-bold text-green-500">₦{(totalOdds * stake).toLocaleString()}</span>
              </div>

              <div className="flex items-center gap-4">
                <div className="flex-1 relative">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500 font-bold text-xs">₦</span>
                  <input 
                    type="number" 
                    value={stake}
                    onChange={(e) => setStake(Number(e.target.value))}
                    className="w-full bg-zinc-900 border border-zinc-800 rounded-xl py-3 pl-8 pr-4 text-sm focus:outline-none focus:border-orange-500"
                    placeholder="Stake"
                  />
                </div>
                <button 
                  onClick={onGenerateCode}
                  className="bg-white text-black font-bold px-8 py-3 rounded-xl hover:bg-orange-500 hover:text-white transition-all shadow-lg shadow-orange-500/20"
                >
                  Generate Code
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function StatCard({ title, value, icon }: { title: string, value: string, icon: any }) {
  return (
    <div className="bg-[#111] border border-zinc-800 p-6 rounded-3xl space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">{title}</span>
        {icon}
      </div>
      <p className="text-4xl font-bold tracking-tighter">{value}</p>
    </div>
  );
}

function PredictionCard({ 
  prediction, 
  onGenerateCode, 
  isUserPremium, 
  isAdmin, 
  onBroadcast 
}: { 
  prediction: Prediction, 
  onGenerateCode: (id: string) => void, 
  isUserPremium: boolean,
  isAdmin: boolean,
  onBroadcast: (prediction: Prediction, valueBet: any) => void
}) {
  const [localCode, setLocalCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [broadcasting, setBroadcasting] = useState(false);

  const isLocked = prediction.is_premium && !isUserPremium;

  const handleBroadcast = async () => {
    setBroadcasting(true);
    await onBroadcast(prediction, {
      market: prediction.best_bet_market,
      selection: prediction.best_bet_selection,
      odds: prediction.best_bet_odds,
      ev: prediction.best_bet_ev,
      match: `${prediction.home_team} vs ${prediction.away_team}`
    });
    setBroadcasting(false);
  };

  const handleGenerate = async () => {
    if (isLocked) {
      alert("This is a Premium Signal. Upgrade to unlock!");
      return;
    }
    setLoading(true);
    await new Promise(r => setTimeout(r, 1200));
    setLocalCode(`B9JA-${Math.random().toString(36).substring(2, 8).toUpperCase()}`);
    setLoading(false);
  };

  return (
    <div className={cn(
      "bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-6 hover:border-zinc-700 transition-colors group relative overflow-hidden",
      isLocked && "opacity-80"
    )}>
      {prediction.is_premium && (
        <div className="absolute top-0 right-0 bg-gradient-to-l from-orange-500 to-orange-600 text-black text-[10px] font-bold px-4 py-1 rounded-bl-2xl flex items-center gap-1 shadow-lg">
          <Zap className="w-3 h-3 fill-current" />
          PREMIUM
        </div>
      )}

      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <h3 className="text-xl font-bold">{prediction.home_team} vs {prediction.away_team}</h3>
          <p className="text-xs text-zinc-500 font-mono">{new Date(prediction.created_at).toLocaleString()}</p>
        </div>
        <div className="flex flex-col items-end gap-2 pr-12">
          <div className="bg-green-500/10 text-green-500 px-3 py-1 rounded-full text-xs font-bold border border-green-500/20">
            {(prediction.confidence * 100).toFixed(0)}% Confidence
          </div>
          <div className="flex items-center gap-1 text-[8px] font-mono text-zinc-600 uppercase tracking-tighter">
            <ShieldCheck className="w-2 h-2" />
            Oracle69 AI Verified
          </div>
        </div>
      </div>

      <div className={cn("grid grid-cols-3 gap-4 transition-all", isLocked && "blur-md select-none")}>
        <ProbStat label="Home" value={prediction.home_prob} color="bg-green-500" />
        <ProbStat label="Draw" value={prediction.draw_prob} color="bg-zinc-500" />
        <ProbStat label="Away" value={prediction.away_prob} color="bg-red-500" />
      </div>

      {isLocked ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/40 backdrop-blur-sm z-10 p-6 text-center space-y-4">
          <Lock className="w-8 h-8 text-orange-500" />
          <div className="space-y-1">
            <p className="font-bold text-lg">Premium Signal Locked</p>
            <p className="text-xs text-zinc-400">This high-confidence prediction is reserved for Oracle69 Premium members.</p>
          </div>
          <button className="bg-orange-500 text-black font-bold px-6 py-2 rounded-full text-sm hover:bg-orange-400 transition-all">
            Unlock Now
          </button>
        </div>
      ) : (
        <>
          {(prediction.over_2_5_prob || prediction.btts_prob) && (
            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-zinc-800/50">
              <div className="space-y-1">
                <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Over 2.5 Goals</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 bg-zinc-900 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-orange-500" 
                      style={{ width: `${(prediction.over_2_5_prob || 0) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-bold text-zinc-300">{((prediction.over_2_5_prob || 0) * 100).toFixed(0)}%</span>
                </div>
              </div>
              <div className="space-y-1">
                <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">BTTS Yes</p>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-1 bg-zinc-900 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-blue-500" 
                      style={{ width: `${(prediction.btts_prob || 0) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-bold text-zinc-300">{((prediction.btts_prob || 0) * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          )}

          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between p-4 bg-zinc-900/50 rounded-2xl border border-zinc-800">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-green-500/10 flex items-center justify-center">
                  <TrendingUpIcon className="w-4 h-4 text-green-500" />
                </div>
                <div>
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">{prediction.best_bet_market || 'Best Bet'}</p>
                  <p className="text-sm font-bold">{prediction.best_bet_selection || 'No Value Found'} {prediction.best_bet_odds && `@ ${prediction.best_bet_odds}`}</p>
                </div>
              </div>
              {prediction.best_bet_ev && (
                <div className="text-right">
                  <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">EV</p>
                  <p className="text-sm font-bold text-green-500">+{(prediction.best_bet_ev * 100).toFixed(1)}%</p>
                </div>
              )}
            </div>

            {localCode ? (
              <div className="flex items-center justify-between p-4 bg-green-500/10 rounded-2xl border border-green-500/20 animate-in fade-in slide-in-from-bottom-2">
                <div>
                  <p className="text-[10px] font-mono text-green-500 uppercase tracking-widest">Bet9ja Booking Code</p>
                  <p className="text-lg font-bold text-white tracking-widest">{localCode}</p>
                </div>
                <button 
                  onClick={() => {
                    navigator.clipboard.writeText(localCode);
                    alert("Code copied to clipboard!");
                  }}
                  className="bg-green-500 text-black text-[10px] font-bold px-3 py-1 rounded-md hover:bg-green-400 transition-colors"
                >
                  Copy Code
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <button 
                  onClick={handleGenerate}
                  disabled={loading}
                  className="flex-1 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-2xl text-xs font-bold transition-all flex items-center justify-center gap-2"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlusCircle className="w-4 h-4" />}
                  Generate Booking Code
                </button>
                {isAdmin && (
                  <button 
                    onClick={handleBroadcast}
                    disabled={broadcasting}
                    className="px-4 bg-blue-500/10 text-blue-500 border border-blue-500/20 rounded-2xl hover:bg-blue-500/20 transition-all flex items-center justify-center"
                    title="Broadcast to Telegram"
                  >
                    {broadcasting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  </button>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function ProbStat({ label, value, color }: { label: string, value: number, color: string }) {
  return (
    <div className="space-y-2">
      <div className="flex justify-between text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
        <span>{label}</span>
        <span>{(value * 100).toFixed(0)}%</span>
      </div>
      <div className="h-1.5 w-full bg-zinc-800 rounded-full overflow-hidden">
        <div 
          className={cn("h-full transition-all duration-1000", color)} 
          style={{ width: `${value * 100}%` }} 
        />
      </div>
    </div>
  );
}
