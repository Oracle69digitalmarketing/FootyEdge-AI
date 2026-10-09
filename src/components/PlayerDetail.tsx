import React, { useState, useEffect } from 'react';
import { X, User, Shield, Globe, Award, Calendar, Activity, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';
import { authHeaders } from '../lib/authFetch';
import { messageForStatus, messageForFailure, BAD_RESPONSE_MESSAGE } from '../lib/apiError';

interface PlayerDetailProps {
  playerId: string | number;
  onClose: () => void;
}

const PlayerDetail: React.FC<PlayerDetailProps> = ({ playerId, onClose }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const fetchDetail = async () => {
      try {
        setLoading(true);
        setError(null);
        setData(null);
        const res = await fetch(`/api/players/${playerId}`, { headers: await authHeaders() });
        // Non-2xx responses carry a JSON error object, not a player record.
        // 401 and 403 intentionally produce different messages here.
        if (!res.ok) {
          if (live) {
            setData(null);
            setError(res.status === 404 ? 'Player not found.' : messageForStatus(res.status));
          }
          return;
        }
        let json: unknown;
        try {
          json = await res.json();
        } catch {
          if (live) {
            setData(null);
            setError(BAD_RESPONSE_MESSAGE);
          }
          return;
        }
        // Validate the record shape before rendering: an object with a
        // valid id and name, and the returned id must match the request.
        // Anything else is treated as a bad response, never rendered.
        if (
          typeof json !== 'object' || json === null || Array.isArray(json) ||
          (typeof (json as any).id !== 'number' && typeof (json as any).id !== 'string') ||
          typeof (json as any).name !== 'string' || (json as any).name.trim() === '' ||
          String((json as any).id) !== String(playerId)
        ) {
          if (live) {
            setData(null);
            setError(BAD_RESPONSE_MESSAGE);
          }
          return;
        }
        if (live) setData(json);
      } catch (err) {
        if (live) {
          setData(null);
          setError(messageForFailure(err));
        }
      } finally {
        if (live) setLoading(false);
      }
    };
    fetchDetail();
    return () => {
      live = false;
    };
  }, [playerId]);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-6">
        <Loader2 className="w-12 h-12 text-orange-500 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-6">
        <div className="bg-[#111] border border-zinc-800 w-full max-w-md rounded-[2rem] p-10 text-center space-y-6 relative">
          <button onClick={onClose} className="absolute top-6 right-6 w-10 h-10 bg-zinc-900 border border-zinc-800 rounded-full flex items-center justify-center hover:bg-zinc-800 transition-all" aria-label="Close">
            <X className="w-5 h-5 text-zinc-500" />
          </button>
          <p className="text-zinc-300 font-bold">{error}</p>
          <button onClick={onClose} className="px-6 py-2 bg-zinc-900 border border-zinc-800 rounded-full text-zinc-300 text-sm font-bold hover:bg-zinc-800 transition-all">
            Close
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const team = data.teams;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-6 overflow-y-auto">
      <div className="bg-[#111] border border-zinc-800 w-full max-w-2xl rounded-[3rem] overflow-hidden relative shadow-2xl p-10">
        <button onClick={onClose} className="absolute top-8 right-8 w-12 h-12 bg-zinc-900 border border-zinc-800 rounded-full flex items-center justify-center hover:bg-zinc-800 transition-all z-10">
          <X className="w-6 h-6 text-zinc-500" />
        </button>

        <div className="space-y-10">
          <div className="flex flex-col items-center text-center space-y-6">
            <div className="w-40 h-40 bg-zinc-900 rounded-[2.5rem] border border-white/5 overflow-hidden relative shadow-2xl">
              {data.photo_url ? (
                <img src={data.photo_url} alt={data.name} className="w-full h-full object-cover" />
              ) : (
                <User className="w-20 h-20 text-zinc-800 absolute inset-0 m-auto" />
              )}
            </div>
            <div className="space-y-2">
               <h2 className="text-4xl font-black">{data.name}</h2>
               <div className="flex items-center justify-center gap-3">
                  <span className="px-4 py-1 bg-orange-500/10 border border-orange-500/20 rounded-full text-orange-500 text-xs font-bold uppercase tracking-widest">{data.position}</span>
                  <span className="text-zinc-500">•</span>
                  <span className="text-zinc-500 font-mono text-sm">#{data.number || '??'}</span>
               </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6 pt-10 border-t border-zinc-800/50">
             <div className="space-y-6">
                <DetailRow icon={<Globe className="text-blue-500" />} label="Nationality" value={data.nationality || 'Unknown'} />
                <DetailRow icon={<Calendar className="text-green-500" />} label="Age" value={`${data.age || '??'} years`} />
             </div>
             <div className="space-y-6">
                <DetailRow icon={<Award className="text-yellow-500" />} label="Club" value={team?.name || 'Free Agent'} />
                <DetailRow icon={<Activity className="text-red-500" />} label="Status" value={data.is_injured ? 'Injured' : 'Available'} color={data.is_injured ? 'text-red-500' : 'text-green-500'} />
             </div>
          </div>

          <div className="bg-zinc-900/50 p-8 rounded-[2rem] border border-white/5 space-y-6">
             <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-[0.2em] text-center">Season Overview</p>
             <div className="grid grid-cols-3 gap-4">
                <div className="text-center space-y-1">
                   <p className="text-xs text-zinc-500">Apps</p>
                   <p className="text-xl font-bold">--</p>
                </div>
                <div className="text-center space-y-1 border-x border-zinc-800">
                   <p className="text-xs text-zinc-500">Goals</p>
                   <p className="text-xl font-bold">--</p>
                </div>
                <div className="text-center space-y-1">
                   <p className="text-xs text-zinc-500">Assists</p>
                   <p className="text-xl font-bold">--</p>
                </div>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

function DetailRow({ icon, label, value, color }: any) {
  return (
    <div className="flex items-center gap-4">
      <div className="w-10 h-10 rounded-xl bg-zinc-900/50 flex items-center justify-center border border-white/5">{icon}</div>
      <div>
        <p className="text-[10px] text-zinc-600 uppercase font-mono tracking-widest">{label}</p>
        <p className={cn("font-bold", color || "text-zinc-300")}>{value}</p>
      </div>
    </div>
  );
}

export default PlayerDetail;
