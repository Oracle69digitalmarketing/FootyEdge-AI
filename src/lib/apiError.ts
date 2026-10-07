/**
 * Shared HTTP/API error classification (9.3D.7).
 *
 * The backend distinguishes 401 (unauthenticated/invalid session) from
 * 403 (authenticated but not entitled). These must NEVER be conflated in
 * the UI: telling an entitled-but-unsubscribed user to "sign in again"
 * sends them in circles. Every component fetching protected APIs must
 * map failures through messageForStatus() instead of inventing its own
 * wording, so messaging stays consistent across the application.
 */

export const SESSION_EXPIRED_MESSAGE =
  'Your session has expired. Please sign in again.';

export const PLAN_FORBIDDEN_MESSAGE =
  'Your current plan does not include this feature.';

export const RATE_LIMITED_MESSAGE =
  'Too many requests. Please wait a moment and try again.';

export const SERVICE_UNAVAILABLE_MESSAGE =
  'The service is temporarily unavailable. Please try again later.';

export const CONNECTION_ERROR_MESSAGE =
  'Could not reach the server. Please check your connection and try again.';

export const BAD_RESPONSE_MESSAGE =
  'The server returned an unexpected response. Please try again later.';

/**
 * Map an HTTP status to the user-facing message. 401 and 403 intentionally
 * produce different strings; nothing here exposes backend internals.
 */
export function messageForStatus(status: number): string {
  if (status === 401) return SESSION_EXPIRED_MESSAGE;
  if (status === 403) return PLAN_FORBIDDEN_MESSAGE;
  if (status === 429) return RATE_LIMITED_MESSAGE;
  if (status >= 500) return SERVICE_UNAVAILABLE_MESSAGE;
  return `Request failed (status ${status}). Please try again later.`;
}

/** True for fetch-level network failures (the request never completed). */
export function isNetworkFailure(err: unknown): boolean {
  return err instanceof TypeError;
}

/**
 * Message for a caught fetch failure that is not an HTTP status:
 * connectivity problems get the connection message, anything else a
 * generic service message. Raw backend bodies are never surfaced here.
 */
export function messageForFailure(err: unknown): string {
  if (isNetworkFailure(err)) return CONNECTION_ERROR_MESSAGE;
  return SERVICE_UNAVAILABLE_MESSAGE;
}
