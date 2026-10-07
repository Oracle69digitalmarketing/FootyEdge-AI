import React, { useState } from 'react';
import { MessageCircle, Copy, Check, Loader2 } from 'lucide-react';
import { authHeaders } from '../lib/authFetch';

/**
 * Telegram account linking (Objective 9.3D.2).
 *
 * Authenticated users mint a one-time link code via
 * POST /api/telegram/link-token (object response: {code, expires_in_seconds})
 * and send `/link <code>` to the FootyEdge Telegram bot. The actual link
 * happens server-side when Telegram processes that message — generating a
 * code here does NOT link the account.
 *
 * Security: the code lives only in component state for display during this
 * UI session. It is never persisted (no storage, no URL), never logged,
 * and copied only via the manual copy button below.
 */

interface LinkState {
  code: string;
  expiresInSeconds: number;
}

function formatExpiry(totalSeconds: number): string {
  if (totalSeconds >= 60) {
    const minutes = Math.round(totalSeconds / 60);
    return minutes === 1 ? '1 minute' : `${minutes} minutes`;
  }
  return totalSeconds === 1 ? '1 second' : `${totalSeconds} seconds`;
}

/**
 * Diagnostic correlation only (9.3D.4C).
 *
 * Computes the same digest the backend stores (SHA-256 hex, first 12
 * chars) over a client-side value and reports ONLY that non-reversible
 * prefix to the browser console. Plaintext codes, full digests, user
 * identifiers, and credentials are never logged. Failures are silent so
 * diagnostics can never break the UI.
 */
async function clientDigestPrefix(value: string): Promise<string | null> {
  try {
    const subtle = globalThis.crypto?.subtle;
    if (!subtle) return null;
    const bytes = await subtle.digest('SHA-256', new TextEncoder().encode(value));
    const hex = Array.from(new Uint8Array(bytes))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
    return hex.slice(0, 12);
  } catch {
    return null;
  }
}

function logClientDigest(event: string, prefix: string | null): void {
  try {
    console.debug(`${event} digest_prefix=${prefix ?? 'unavailable'}`);
  } catch {
    // Diagnostics must never break the UI.
  }
}

const TelegramLink: React.FC = () => {
  const [link, setLink] = useState<LinkState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => {
    if (loading) return;
    setLoading(true);
    setError(null);
    setCopied(false);
    try {
      const headers = await authHeaders();
      if (!headers.Authorization) {
        setLink(null);
        setError('Please sign in again — generating a link code requires an authenticated session.');
        return;
      }
      const res = await fetch('/api/telegram/link-token', {
        method: 'POST',
        headers,
      });
      if (!res.ok) {
        setLink(null);
        if (res.status === 401) {
          setError('Please sign in again — your session has expired.');
        } else if (res.status === 403) {
          setError('Your current plan does not include Telegram linking.');
        } else if (res.status === 429) {
          setError('Too many requests. Please wait a moment and try again.');
        } else if (res.status >= 500) {
          setError('The linking service is temporarily unavailable. Please try again later.');
        } else {
          setError(`Could not generate a link code (request failed with status ${res.status}).`);
        }
        return;
      }
      const body: unknown = await res.json();
      // The endpoint intentionally returns an OBJECT, never an array.
      // Validate explicitly so a malformed payload can never display a bogus code.
      if (
        !body ||
        typeof body !== 'object' ||
        Array.isArray(body) ||
        typeof (body as { code?: unknown }).code !== 'string' ||
        (body as { code: string }).code.length === 0 ||
        typeof (body as { expires_in_seconds?: unknown }).expires_in_seconds !== 'number' ||
        !Number.isFinite((body as { expires_in_seconds: number }).expires_in_seconds) ||
        (body as { expires_in_seconds: number }).expires_in_seconds <= 0
      ) {
        setLink(null);
        setError('The linking service returned an unexpected response. Please try again.');
        return;
      }
      const valid = body as { code: string; expires_in_seconds: number };
      setLink({ code: valid.code, expiresInSeconds: valid.expires_in_seconds });
      // Diagnostic: prefix of exactly what the API returned.
      void clientDigestPrefix(valid.code).then((prefix) =>
        logClientDigest('telegram_link_client_mint', prefix)
      );
    } catch {
      // Never log the response body here: it may contain the one-time code.
      setLink(null);
      setError('Could not reach the linking service. Please check your connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.code);
      // Diagnostic: prefix of exactly what was handed to the clipboard.
      void clientDigestPrefix(link.code).then((prefix) =>
        logClientDigest('telegram_link_client_copy', prefix)
      );
      // Diagnostic: prefix of what the clipboard actually holds now.
      // Best-effort: permission denial only logs 'unavailable'.
      try {
        const pasted = await navigator.clipboard.readText();
        void clientDigestPrefix(pasted).then((prefix) =>
          logClientDigest('telegram_link_client_clipboard', prefix)
        );
      } catch {
        logClientDigest('telegram_link_client_clipboard', null);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="space-y-8">
      <div className="space-y-2 text-center">
        <MessageCircle className="w-16 h-16 text-orange-500 mx-auto" />
        <h2 className="text-3xl font-bold tracking-tight">Connect Telegram</h2>
        <p className="text-zinc-400 max-w-2xl mx-auto">
          Generate a one-time code, then send <code className="bg-zinc-900 px-2 py-1 rounded mx-1 text-orange-500 font-mono text-sm">/link &lt;code&gt;</code> to the FootyEdge Telegram bot.
        </p>
      </div>

      <div className="max-w-xl mx-auto bg-[#111] border border-zinc-800 rounded-3xl p-8 space-y-6">
        {!link && (
          <div className="space-y-4 text-center">
            <p className="text-sm text-zinc-500">
              The code works once and expires quickly. Do not share it publicly.
            </p>
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="bg-orange-500 text-black font-bold px-8 py-3 rounded-xl hover:bg-orange-400 transition-all disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {loading ? 'Generating…' : 'Generate Telegram Link Code'}
            </button>
          </div>
        )}

        {link && (
          <div className="space-y-4 text-center">
            <p className="text-xs font-mono text-zinc-500 uppercase tracking-widest">Your Telegram link code</p>
            <p className="text-3xl font-black text-orange-500 font-mono break-all">{link.code}</p>
            <p className="text-sm text-zinc-400">Expires in {formatExpiry(link.expiresInSeconds)}.</p>
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
              <p className="text-xs text-zinc-500 mb-1">Open the FootyEdge Telegram bot and send:</p>
              <p className="font-mono text-white break-all">/link {link.code}</p>
            </div>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={handleCopy}
                className="p-2 hover:bg-zinc-800 rounded-lg text-zinc-500 hover:text-white transition-colors inline-flex items-center gap-2 text-sm"
                title="Copy code"
              >
                {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                {copied ? 'Copied' : 'Copy code'}
              </button>
              <button
                onClick={handleGenerate}
                disabled={loading}
                className="text-sm text-zinc-500 hover:text-white transition-colors disabled:opacity-50"
              >
                Generate a new code
              </button>
            </div>
            <p className="text-xs text-zinc-600">
              Code generated — your Telegram account is linked only after the bot successfully processes your <span className="font-mono">/link</span> message.
            </p>
          </div>
        )}

        {error && <p className="text-red-500 text-sm mt-2 text-center">{error}</p>}
      </div>
    </div>
  );
};

export default TelegramLink;
