import { useState, useEffect, useCallback } from 'react';
import StatCard from './components/StatCard';
import { supabase } from './supabase';
import { Team, Prediction, ValueBet } from './types';
import TeamSearch from './components/TeamSearch';
import Portfolio from './components/Portfolio'; // Import the new Portfolio component
import AccaBuilder from './components/AccaBuilder'; // Import the new AccaBuilder component
import HowToUse from './components/HowToUse'; // Import the new HowToUse component
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
import { cn } from './lib/utils'; // Import cn from utility file


export default function App() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState<Team[]>([]);
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [liveValueBets, setLiveValueBets] = useState<ValueBet[]>([]);
  const [scanning, setScanning] = useState(false);
  const [showLiveBets, setShowLiveBets] = useState(true); // Default to showing live bets
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
  const [bankroll, setBankroll] = useState(10000); // Default 10k NGN
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


  // State for premium data
  const [premiumPerformance, setPremiumPerformance] = useState<any>(null);
  const [premiumTelegramConfig, setPremiumTelegramConfig] = useState<any>(null);
  const [premiumUpcomingMatches, setPremiumUpcomingMatches] = useState<any[]>([]);

  // State for admin data
  const [adminStats, setAdminStats] = useState<any>(null);
  const [adminActivity, setAdminActivity] = useState<any[]>([]);

  const flashMessage = (setter: (msg: string | null) => void, message: string | null) => {
    setter(message);
    setTimeout(() => setter(null), 4000);
  };

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

  const fetchTeams = useCallback(async () => {
    if (!supabase) return;
    try {
      const { data, error } = await supabase.from('teams').select('*').order('league_name').order('name');
      if (error) throw error;
      setTeams(data || []);
    } catch (error: any) {
      flashMessage(setError, `Failed to fetch teams: ${error.message}. Please check your Supabase configuration.`);
    }
  }, []);

  const fetchValueBets = useCallback(async () => {
    try {
      const response = await fetch(`/api/value-bets?status=${betStatusFilter}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setValueBets(data);
    } catch (error: any) {
      flashMessage(setError,`Failed to fetch value bets: ${error.message}`);
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
    fetchValueBets();
    handleScanValueBets(); // Fetch live data on load

    // Set up real-time subscriptions
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

  const handleSyncTeams = async () => {
    setSyncingTeams(true);
    flashMessage(setError, null);
    flashMessage(setSuccess, null);
    try {
      const response = await fetch('/api/admin/sync-teams', { method: 'POST' });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to sync teams.');
      }
      flashMessage(setSuccess, `Successfully synced ${data.synced_count} teams.`);
      await fetchTeams(); // Refresh the teams list
    } catch (err: any) {
      flashMessage(setError, err.message);
    } finally {
      setSyncingTeams(false);
    }
  };

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

  const addToAcca = (match: any, market: string, odds: number, selection: string) => {
    const existingIndex = accaSelections.findIndex(s => s.match.id === match.id);
    if (existingIndex > -1) {
      // If same market, remove it (toggle off)
      if(accaSelections[existingIndex].market === market) {
        setAccaSelections(prev => prev.filter((_, i) => i !== existingIndex));
      } else {
        // If different market for same match, replace it
        setAccaSelections(prev => {
            const newSelections = [...prev];
            newSelections[existingIndex] = { match, market, odds, selection };
            return newSelections;
        });
      }
    } else {
      setAccaSelections(prev => [...prev, { match, market, odds, selection }]);
    }
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-orange-500 animate-spin" />
      </div>
    );
  }

  // ... (Login and No Supabase UI remains the same)
  // ...

  // Main App Return
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white font-sans selection:bg-orange-500 selection:text-black">
      {/* Sidebar / Nav */}
      <div className="fixed left-0 top-0 h-full w-20 md:w-64 bg-[#111] border-r border-zinc-800 flex flex-col z-50">
        {/* ... Nav Header ... */}
        <nav className="flex-1 px-4 space-y-2 mt-8">
            {/* ... Nav Items ... */}
        </nav>
        {/* ... Logout Button ... */}
      </div>

      {/* Main Content */}
      <main className="pl-20 md:pl-64 min-h-screen">
        <header className="h-20 border-b border-zinc-800 flex items-center justify-between px-8 sticky top-0 bg-[#0a0a0a]/80 backdrop-blur-md z-40">
           {/* ... Header Content ... */}
        </header>

        <div className="p-8 max-w-7xl mx-auto space-y-8">
          <AnimatePresence>
            {error && (
              <motion.div 
                initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
                className="bg-red-500/10 border border-red-500/20 p-4 rounded-2xl flex items-center gap-3 text-red-500 fixed top-24 right-8 z-[101]"
              >
                <AlertTriangle className="w-5 h-5" />
                <p className="text-sm font-medium">{error}</p>
              </motion.div>
            )}
            {success && (
              <motion.div 
                initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
                className="bg-green-500/10 border border-green-500/20 p-4 rounded-2xl flex items-center gap-3 text-green-500 fixed top-24 right-8 z-[101]"
              >
                <CheckCircle className="w-5 h-5" />
                <p className="text-sm font-medium">{success}</p>
              </motion.div>
            )}
          </AnimatePresence>


          {activeTab === 'dashboard' && (
            <div className="space-y-12">
              {/* ... Telegram CTA ... */}

              {/* Value Alerts Section */}
              <div className="bg-green-500/5 border border-green-500/20 rounded-[2rem] p-8 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 opacity-10">
                  <TrendingUpIcon className="w-32 h-32 text-green-500" />
                </div>
                <div className="relative z-10 space-y-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-green-500 flex items-center justify-center">
                        <Zap className="w-5 h-5 text-black" />
                      </div>
                      <div>
                        <h2 className="text-2xl font-bold tracking-tight">Live Value Alerts</h2>
                        <p className="text-xs text-zinc-500 font-mono uppercase tracking-widest">Real-time Market Inefficiencies</p>
                      </div>
                    </div>
                    <button onClick={handleScanValueBets} disabled={scanning} className="bg-zinc-900 border border-zinc-800 p-3 rounded-full hover:bg-zinc-800 transition-colors">
                      {scanning ? <Loader2 className="w-4 h-4 animate-spin"/> : <RefreshCw className="w-4 h-4"/>}
                    </button>
                  </div>
                  
                  {liveValueBets.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {liveValueBets.slice(0, 3).map((alert, i) => (
                        <div key={i} className="bg-black/40 border border-white/5 p-4 rounded-2xl hover:border-green-500/30 transition-all cursor-pointer group">
                          <div className="flex justify-between items-start mb-3">
                            <span className="text-[10px] font-mono text-zinc-500">
                                {new Date(alert.match_timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                            <span className="text-[10px] font-mono text-green-500 font-bold">
                                +{(alert.ev * 100).toFixed(1)}% Edge
                            </span>
                          </div>
                          <p className="font-bold text-sm mb-1">{alert.home_team} vs {alert.away_team}</p>
                          <div className="flex justify-between items-center">
                            <span className="text-xs text-zinc-400">{alert.market} - {alert.selection}</span>
                            <span className="text-sm font-bold text-white">@{alert.odds.toFixed(2)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-center py-8 text-zinc-500">
                      {scanning ? 'Scanning for live value...' : 'No live value opportunities found currently.'}
                    </div>
                  )}
                </div>
              </div>

             {/* ... Rest of Dashboard ... */}
            </div>
          )}

          {/* ... Other Tabs ... */}

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
                  <button onClick={handleSyncTeams} disabled={syncingTeams} className="bg-zinc-900 border border-zinc-800 px-6 py-3 rounded-2xl text-sm font-bold hover:bg-zinc-800 transition-colors flex items-center gap-2">
                    {syncingTeams ? <Loader2 className="w-5 h-5 animate-spin" /> : <RefreshCw className="w-5 h-5" />}
                    Sync Teams
                  </button>
                  <button onClick={() => setShowLogsModal(true)} className="bg-zinc-900 border border-zinc-800 px-6 py-3 rounded-2xl text-sm font-bold hover:bg-zinc-800 transition-colors flex items-center gap-2">
                    <Server className="w-5 h-5" />
                    System Logs
                  </button>
                  <button onClick={() => setShowTelegramBroadcastModal(true)} className="bg-blue-500 text-black px-6 py-3 rounded-2xl text-sm font-bold hover:bg-blue-400 transition-colors flex items-center gap-2">
                    <Send className="w-5 h-5" />
                    Global Broadcast
                  </button>
                </div>
              </div>

              {/* ... Admin Stats and Activity ... */}
            </div>
          )}

          {/* ... Acca Builder ... */}
           {activeTab === 'acca' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              <div className="lg:col-span-2 space-y-6">
                {/* ... Acca Header ... */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Mocked matches, replace with real data */}
                  {[
                      { id: 'match1', homeTeam: { name: 'Man U' }, awayTeam: { name: 'Chelsea' }, date: new Date().toISOString() },
                      { id: 'match2', homeTeam: { name: 'Spurs' }, awayTeam: { name: 'West Ham' }, date: new Date().toISOString() },
                  ].map(match => (
                    <MatchCard 
                      key={match.id} 
                      match={match} 
                      onAddToAcca={addToAcca}
                      selectedBookmaker={selectedBookmaker}
                      accaSelections={accaSelections}
                    />
                  ))}
                </div>
              </div>
              <div className="space-y-6">
                 {/* ... AccaBuilder component ... */}
              </div>
            </div>
          )}

          {/* ... Modals ... */}
        </div>
      </main>
    </div>
  );
}

// ... (PremiumModal, NavItem)

function MatchCard({ match, onAddToAcca, selectedBookmaker, accaSelections }: { match: any, onAddToAcca: (match: any, market: string, odds: number, selection: string) => void, selectedBookmaker: string, accaSelections: any[] }) {
  const [multiOdds, setMultiOdds] = useState<any>(null);

  // This is a mock. In a real app, you'd fetch this.
  useEffect(() => {
    setMultiOdds({
      bet9ja: { home_win: 1.80, draw: 3.50, away_win: 4.00, booking_prefix: 'B9' },
      sportybet: { home_win: 1.82, draw: 3.45, away_win: 4.10, booking_prefix: 'SP' },
      '1xbet': { home_win: 1.85, draw: 3.55, away_win: 3.95, booking_prefix: '1X' }
    });
  }, [match.id]);

  const currentOdds = multiOdds ? multiOdds[selectedBookmaker] : null;

  const isSelected = (market: string) => {
    return accaSelections.some(s => s.match.id === match.id && s.market === market);
  };

  return (
    <div className="bg-[#111] border border-zinc-800 rounded-3xl p-6 space-y-6 hover:border-zinc-700 transition-colors group">
        {/* ... MatchCard Header ... */}
      {currentOdds ? (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <button 
              onClick={() => onAddToAcca(match, 'home_win', currentOdds.home_win, match.homeTeam.name)}
              className={cn("bg-zinc-900 border border-zinc-800 p-3 rounded-xl hover:border-green-500/50 transition-all text-center group/btn", isSelected('home_win') && "border-green-500 bg-green-500/10")}
            >
              <p className={cn("text-[10px] font-mono text-zinc-500 uppercase tracking-widest group-hover/btn:text-green-500", isSelected('home_win') && "text-green-500")}>Home</p>
              <p className={cn("text-lg font-bold", isSelected('home_win') && "text-white")}>{currentOdds.home_win.toFixed(2)}</p>
            </button>
            <button 
              onClick={() => onAddToAcca(match, 'draw', currentOdds.draw, 'Draw')}
              className={cn("bg-zinc-900 border border-zinc-800 p-3 rounded-xl hover:border-green-500/50 transition-all text-center group/btn", isSelected('draw') && "border-green-500 bg-green-500/10")}
            >
              <p className={cn("text-[10px] font-mono text-zinc-500 uppercase tracking-widest group-hover/btn:text-green-500", isSelected('draw') && "text-green-500")}>Draw</p>
              <p className={cn("text-lg font-bold", isSelected('draw') && "text-white")}>{currentOdds.draw.toFixed(2)}</p>
            </button>
            <button 
              onClick={() => onAddToAcca(match, 'away_win', currentOdds.away_win, match.awayTeam.name)}
              className={cn("bg-zinc-900 border border-zinc-800 p-3 rounded-xl hover:border-green-500/50 transition-all text-center group/btn", isSelected('away_win') && "border-green-500 bg-green-500/10")}
            >
              <p className={cn("text-[10px] font-mono text-zinc-500 uppercase tracking-widest group-hover/btn:text-green-500", isSelected('away_win') && "text-green-500")}>Away</p>
              <p className={cn("text-lg font-bold", isSelected('away_win') && "text-white")}>{currentOdds.away_win.toFixed(2)}</p>
            </button>
          </div>
        </div>
      ) : (
        <div className="h-20 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-700" />
        </div>
      )}
    </div>
  );
}

// ... (PredictionCard, ProbStat)
