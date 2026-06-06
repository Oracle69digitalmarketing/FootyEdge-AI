import React, { useState, useEffect } from 'react';
import { X, Shield, Globe, Trophy, Users, Calendar, MapPin, Activity, History, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';

interface TeamDetailProps {
  teamId: string | number;
  onClose: () => void;
}

const TeamDetail: React.FC<TeamDetailProps> = ({ teamId, onClose }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        setLoading(true);
        const res = await fetch(`/api/teams/${teamId}`);
        const json = await res.json();
        setData(json);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [teamId]);

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-6">
        <Loader2 className="w-12 h-12 text-orange-500 animate-spin" />
      </div>
    );
  }

  if (!data) return null;

  const { team, players } = data;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-[100] flex items-center justify-center p-6 overflow-y-auto">
      <div className="bg-[#111] border border-zinc-800 w-full max-w-5xl rounded-[3rem] overflow-hidden relative shadow-2xl">
        <button onClick={onClose} className="absolute top-8 right-8 w-12 h-12 bg-zinc-900 border border-zinc-800 rounded-full flex items-center justify-center hover:bg-zinc-800 transition-all z-10">
          <X className="w-6 h-6 text-zinc-500" />
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-3">
          {/* Sidebar / Info */}
          <div className="lg:col-span-1 bg-zinc-900/50 p-10 border-r border-zinc-800 space-y-10">
            <div className="text-center space-y-6">
              <div className="w-32 h-32 bg-black/40 rounded-[2rem] flex items-center justify-center mx-auto border border-white/5 p-4 shadow-xl">
                {team.logo_url ? <img src={team.logo_url} alt="" className="w-full h-full object-contain" /> : <Shield className="w-16 h-16 text-zinc-800" />}
              </div>
              <div className="space-y-2">
                <h2 className="text-3xl font-black">{team.name}</h2>
                <p className="text-orange-500 font-mono text-sm uppercase tracking-widest">{team.league_name}</p>
              </div>
            </div>

            <div className="space-y-6">
              <InfoItem icon={<Globe className="text-blue-500" />} label="Country" value={team.country || 'International'} />
              <InfoItem icon={<MapPin className="text-red-500" />} label="Stadium" value={team.stadium || 'N/A'} />
              <InfoItem icon={<Calendar className="text-green-500" />} label="Founded" value={team.founded || 'Unknown'} />
            </div>

            <div className="pt-8 border-t border-zinc-800 space-y-4">
              <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-[0.2em]">Live Performance</p>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-black/40 p-4 rounded-2xl border border-white/5">
                  <p className="text-[10px] text-zinc-500 uppercase">ELO</p>
                  <p className="text-xl font-bold">{team.elo_rating || '1500'}</p>
                </div>
                <div className="bg-black/40 p-4 rounded-2xl border border-white/5">
                  <p className="text-[10px] text-zinc-500 uppercase">Form</p>
                  <p className="text-xl font-bold text-green-500">{((team.form_rating || 0.5) * 100).toFixed(0)}%</p>
                </div>
              </div>
            </div>
          </div>

          {/* Main Content */}
          <div className="lg:col-span-2 p-10 space-y-12">
            <section className="space-y-6">
              <div className="flex items-center justify-between">
                <h3 className="text-2xl font-bold flex items-center gap-3"><Users className="text-orange-500" /> First Team Squad</h3>
                <span className="text-xs font-mono text-zinc-500">{players.length} Players Active</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {players.slice(0, 12).map((p: any) => (
                  <div key={p.id} className="flex items-center gap-4 p-4 bg-zinc-900/30 border border-white/5 rounded-2xl hover:border-orange-500/20 transition-all group cursor-pointer">
                    <div className="w-10 h-10 rounded-xl bg-zinc-900 overflow-hidden">
                      {p.photo_url ? <img src={p.photo_url} alt="" className="w-full h-full object-cover" /> : <div className="w-full h-full flex items-center justify-center"><Activity className="w-4 h-4 text-zinc-700" /></div>}
                    </div>
                    <div>
                      <p className="font-bold text-sm group-hover:text-orange-500 transition-colors">{p.name}</p>
                      <p className="text-[10px] text-zinc-500 uppercase tracking-widest">{p.position}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-6">
               <h3 className="text-2xl font-bold flex items-center gap-3"><History className="text-orange-500" /> Performance History</h3>
               <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <StatCard label="Played" value={team.total_matches} />
                  <StatCard label="Wins" value={team.wins} color="text-green-500" />
                  <StatCard label="Draws" value={team.draws} color="text-zinc-500" />
                  <StatCard label="Losses" value={team.losses} color="text-red-500" />
               </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  );
};

function InfoItem({ icon, label, value }: any) {
  return (
    <div className="flex items-center gap-4">
      <div className="w-10 h-10 rounded-xl bg-black/40 flex items-center justify-center border border-white/5">{icon}</div>
      <div>
        <p className="text-[10px] text-zinc-600 uppercase font-mono tracking-widest">{label}</p>
        <p className="font-bold text-zinc-300">{value}</p>
      </div>
    </div>
  );
}

function StatCard({ label, value, color }: any) {
  return (
    <div className="bg-zinc-900/30 border border-white/5 p-6 rounded-2xl text-center space-y-1">
      <p className="text-[10px] text-zinc-600 uppercase font-mono tracking-widest">{label}</p>
      <p className={cn("text-2xl font-black", color || "text-white")}>{value || '0'}</p>
    </div>
  );
}

export default TeamDetail;
