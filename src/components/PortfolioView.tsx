import React, { useState, useEffect } from 'react';
import { Loader2 } from 'lucide-react';
import { supabase } from '../supabase';
import { authHeaders } from '../lib/authFetch';
import {
  SESSION_EXPIRED_MESSAGE,
  messageForStatus,
  messageForFailure,
  BAD_RESPONSE_MESSAGE,
} from '../lib/apiError';
import Portfolio from './Portfolio';

/**
 * Portfolio tab data wrapper (10.2A).
 *
 * Supplies the props App previously omitted: bankroll plus the caller's
 * own bets. Ownership is JWT-bound server-side (10.1A): the user id in
 * the path is route shape only and never authorizes anything. Starter
 * (and any non-entitled) callers receive the backend's 403, surfaced
 * here as a plan message — never a sign-in prompt, never elevated
 * access. DEFAULT_BANKROLL is a local display basis only; no bankroll
 * API exists.
 */

const DEFAULT_BANKROLL = 1000;

const PortfolioView: React.FC = () => {
  const [bets, setBets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const userId = (await supabase?.auth.getUser())?.data.user?.id;
        if (!userId) {
          if (live) {
            setBets([]);
            setError(SESSION_EXPIRED_MESSAGE);
          }
          return;
        }
        const res = await fetch(
          `/api/bets/user/${encodeURIComponent(userId)}`,
          { headers: await authHeaders() }
        );
        if (!res.ok) {
          if (live) {
            setBets([]);
            setError(messageForStatus(res.status));
          }
          return;
        }
        let data: unknown;
        try {
          data = await res.json();
        } catch {
          if (live) {
            setBets([]);
            setError(BAD_RESPONSE_MESSAGE);
          }
          return;
        }
        if (!Array.isArray(data)) {
          if (live) {
            setBets([]);
            setError(BAD_RESPONSE_MESSAGE);
          }
          return;
        }
        if (live) setBets(data);
      } catch (err) {
        if (live) {
          setBets([]);
          setError(messageForFailure(err));
        }
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="w-12 h-12 text-orange-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && <p className="text-red-500 text-sm mt-2 text-center">{error}</p>}
      <Portfolio bankroll={DEFAULT_BANKROLL} userBets={bets} />
    </div>
  );
};

export default PortfolioView;
