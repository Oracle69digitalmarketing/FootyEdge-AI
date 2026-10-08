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
import AccaBuilder from './AccaBuilder';

/**
 * Acca Builder tab data wrapper (10.2B).
 *
 * Supplies the props App previously omitted by feeding the presentational
 * AccaBuilder from the established GET /api/acca-builder ticket endpoint:
 * the backend's greedy-combinator selections are adapted to the slip shape
 * (no new prediction math anywhere — odds/markets pass through untouched).
 * Ownership/entitlement stay server-side (10.1A model): non-entitled
 * callers (including Starter and subscription-less owner/admin) receive
 * the backend's 403 as a plan message, never elevated access and never
 * a sign-in prompt. Slip generation is a local summary only; there is no
 * bookmaker booking backend.
 */

interface SlipSelection {
  match: { homeTeam: { name: string }; awayTeam: { name: string } };
  market: string;
  selection: unknown;
  odds: number;
}

function adaptTicketSelections(ticket: unknown): SlipSelection[] | null {
  if (!ticket || typeof ticket !== 'object' || Array.isArray(ticket)) return null;
  const selections = (ticket as { selections?: unknown }).selections;
  if (!Array.isArray(selections)) return null;
  return selections.map((s) => {
    const row = (s !== null && typeof s === 'object' ? s : {}) as Record<string, unknown>;
    const odds = Number(row.odds);
    return {
      match: {
        homeTeam: { name: String(row.home_team ?? 'TBD') },
        awayTeam: { name: String(row.away_team ?? 'TBD') },
      },
      market: String(row.market ?? ''),
      selection: row.selection,
      odds: Number.isFinite(odds) ? odds : 0,
    };
  });
}

const AccaView: React.FC = () => {
  const [selections, setSelections] = useState<SlipSelection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const userId = (await supabase?.auth.getUser())?.data.user?.id;
        if (!userId) {
          if (live) setError(SESSION_EXPIRED_MESSAGE);
          return;
        }
        const res = await fetch('/api/acca-builder', { headers: await authHeaders() });
        if (!res.ok) {
          if (live) setError(messageForStatus(res.status));
          return;
        }
        let body: unknown;
        try {
          body = await res.json();
        } catch {
          if (live) setError(BAD_RESPONSE_MESSAGE);
          return;
        }
        const adapted = adaptTicketSelections(body);
        if (adapted === null) {
          if (live) setError(BAD_RESPONSE_MESSAGE);
          return;
        }
        if (live) setSelections(adapted);
      } catch (err) {
        if (live) setError(messageForFailure(err));
      } finally {
        if (live) setLoading(false);
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const handleRemove = (idx: number) => {
    setSelections((prev) => prev.filter((_, i) => i !== idx));
    setNotice(null);
  };

  const handleGenerateCode = (stake: number, totalOdds: number) => {
    // Local slip summary only: no booking backend exists. Uses the
    // already-displayed slip values, never privileged data.
    const safeStake = Number.isFinite(stake) ? stake : 0;
    const safeOdds = Number.isFinite(totalOdds) ? totalOdds : 0;
    setNotice(
      `Acca slip ready — stake ₦${safeStake.toLocaleString()} at ${safeOdds.toFixed(2)} ` +
        `across ${selections.length} selection${selections.length === 1 ? '' : 's'}. ` +
        `Place it with your bookmaker.`
    );
  };

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
      {notice && (
        <p role="status" className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-900/40 rounded-xl px-4 py-3 text-center">
          {notice}
        </p>
      )}
      <AccaBuilder
        selections={selections}
        onRemove={handleRemove}
        onGenerateCode={handleGenerateCode}
        bankroll={1000}
      />
    </div>
  );
};

export default AccaView;
