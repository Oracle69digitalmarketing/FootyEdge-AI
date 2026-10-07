import { supabase } from '../supabase';

/**
 * Authenticated request headers for protected FootyEdge API calls.
 *
 * Reuses the project's existing Supabase client/session mechanism (same as
 * src/lib/ownerBilling.ts): the current session's access token is attached
 * as `Authorization: Bearer <access_token>`. Returns an empty object when
 * there is no session or no client, so callers degrade to a controlled
 * 401/empty state instead of crashing. The token is never logged,
 * persisted, or printed.
 */
export async function authHeaders(): Promise<Record<string, string>> {
  try {
    const session = (await supabase?.auth.getSession())?.data.session;
    const token = session?.access_token;
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  } catch {
    return {};
  }
}
