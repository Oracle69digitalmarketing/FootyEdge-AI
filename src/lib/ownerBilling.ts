import { useEffect, useState } from 'react';
import { supabase } from '../supabase';

/**
 * Owner-console data access (8G).
 *
 * UX fetching only — never authorization. Every /api/admin/billing/*
 * endpoint independently enforces owner/admin via the caller's Supabase
 * JWT (server-side profiles.role lookup). A 401/403 here means the
 * backend rejected the caller; the console only renders that fact.
 */

export type BillingFetchState<T> =
  | { status: 'loading' }
  | { status: 'ok'; data: T }
  | { status: 'forbidden' }
  | { status: 'unavailable' };

export interface BillingOverview {
  total_users: number;
  users_with_subscriptions: number;
  starter_users: number;
  plan_counts: { starter: number; growth: number; business: number; enterprise: number };
  status_counts: Record<string, number>;
  subscriptions_total: number;
}

export interface BillingUser {
  user_id: string | null;
  email: string | null;
  role: string;
  effective_plan: string;
  subscription_status: string | null;
  provider: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string | null;
}

export interface BillingSubscription {
  id: number;
  user_id: string;
  plan: string;
  status: string;
  provider: string | null;
  provider_customer_id: string | null;
  provider_subscription_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BillingEvent {
  id: number;
  subscription_id: number | null;
  provider: string;
  provider_event_id: string;
  event_type: string;
  processing_status: string;
  error_code: string | null;
  created_at: string;
  processed_at: string | null;
}

async function fetchAdmin<T>(path: string): Promise<BillingFetchState<T>> {
  try {
    const session = (await supabase?.auth.getSession())?.data.session;
    const token = session?.access_token;
    if (!token) return { status: 'forbidden' };
    const res = await fetch(path, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401 || res.status === 403) return { status: 'forbidden' };
    if (!res.ok) return { status: 'unavailable' };
    return { status: 'ok', data: (await res.json()) as T };
  } catch {
    return { status: 'unavailable' };
  }
}

export function useOwnerBilling<T>(path: string | null): BillingFetchState<T> {
  const [state, setState] = useState<BillingFetchState<T>>({ status: 'loading' });
  useEffect(() => {
    if (!path) {
      setState({ status: 'unavailable' });
      return;
    }
    let live = true;
    setState({ status: 'loading' });
    fetchAdmin<T>(path).then((s) => {
      if (live) setState(s);
    });
    return () => {
      live = false;
    };
  }, [path]);
  return state;
}

/** Factual subscription-status labels. No vague health judgments. */
export function formatStatus(status: string | null | undefined): string {
  switch ((status ?? '').toLowerCase()) {
    case 'active': return 'Active';
    case 'trialing': return 'Trialing';
    case 'past_due': return 'Past Due';
    case 'paused': return 'Paused';
    case 'canceled': return 'Canceled';
    case 'expired': return 'Expired';
    case '': return '—';
    default: return String(status);
  }
}

/** Shorten long identifiers for table display (full value in title). */
export function shortId(value: string | null | undefined, head = 8): string {
  if (!value) return '—';
  return value.length > head + 4 ? `${value.slice(0, head)}…` : value;
}
