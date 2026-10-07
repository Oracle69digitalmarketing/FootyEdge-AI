import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { supabase } from '../../supabase';

/**
 * Account access card used on the commercial product page.
 * Same authentication mechanism as the in-app sign-in screen:
 * Supabase email/password auth (sign in or create an account).
 */
export default function SignInCard() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isSignUp, setIsSignUp] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const submit = async () => {
    if (busy) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      if (isSignUp) {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) throw error;
        if (data.session) {
          // Session established: the app-level auth listener transitions
          // into the authenticated shell. Never sign in a second time here.
          setNotice('Signed in — opening FootyEdge…');
        } else if (data.user) {
          // No session: the account exists but confirmation is required
          // before signing in. Say so explicitly instead of going silent.
          setNotice('Account created. Check your email to confirm your account, then sign in.');
        } else {
          setNotice('Account created. Check your email to confirm your account, then sign in.');
        }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
    } catch (e: any) {
      setError(e?.message ?? 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-[#111] border border-zinc-800 p-8 rounded-3xl w-full max-w-sm space-y-6">
      <div className="space-y-2 text-center">
        <h3 className="text-2xl font-bold text-white">{isSignUp ? 'Create your account' : 'Sign in'}</h3>
        <p className="text-sm text-zinc-400">
          {isSignUp
            ? 'Create an account to open FootyEdge and request access.'
            : 'Welcome back. Sign in to open FootyEdge.'}
        </p>
      </div>
      <div className="space-y-4">
        <label className="block">
          <span className="sr-only">Email address</span>
          <input
            type="email"
            autoComplete="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-800 p-4 rounded-xl text-white outline-none focus:border-orange-500 focus-visible:ring-2 focus-visible:ring-orange-500/60"
          />
        </label>
        <label className="block">
          <span className="sr-only">Password</span>
          <input
            type="password"
            autoComplete={isSignUp ? 'new-password' : 'current-password'}
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
            className="w-full bg-zinc-900 border border-zinc-800 p-4 rounded-xl text-white outline-none focus:border-orange-500 focus-visible:ring-2 focus-visible:ring-orange-500/60"
          />
        </label>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-400 bg-red-500/10 border border-red-900/40 rounded-xl px-4 py-3">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-900/40 rounded-xl px-4 py-3">
          {notice}
        </p>
      )}
      <button
        onClick={submit}
        disabled={busy || !email || !password}
        className="w-full bg-orange-500 text-black font-bold py-3 rounded-xl hover:bg-orange-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 focus-visible:ring-2 focus-visible:ring-orange-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#111]"
      >
        {busy && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}
        {isSignUp ? 'Create account' : 'Sign in'}
      </button>
      <button
        onClick={() => { setIsSignUp(!isSignUp); setError(null); setNotice(null); }}
        className="w-full text-zinc-500 text-sm hover:text-white transition-colors rounded focus-visible:ring-2 focus-visible:ring-orange-500/60"
      >
        {isSignUp ? 'Already have an account? Sign in' : 'Need an account? Create one'}
      </button>
    </div>
  );
}
