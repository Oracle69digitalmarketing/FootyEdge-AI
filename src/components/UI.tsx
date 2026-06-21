import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';

export function StatItem({ icon, label, value }: { icon: any, label: string, value: string | number }) {
  return (
    <div className="bg-black/40 border border-white/5 p-6 rounded-3xl space-y-2">
      <div className="flex items-center gap-3">
        {icon}
        <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">{label}</p>
      </div>
      <p className="text-2xl font-bold">{value || '0'}</p>
    </div>
  );
}

export function AdminActionCard({ title, description, onClick, loading, icon }: any) {
  return (
    <button 
      onClick={onClick} 
      disabled={loading} 
      className="w-full text-left bg-[#111] border border-zinc-800 p-8 rounded-[2rem] space-y-4 hover:border-orange-500/40 hover:scale-[1.02] transition-all group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100"
    >
      <div className="w-12 h-12 bg-zinc-900 rounded-2xl flex items-center justify-center border border-white/5 group-hover:bg-zinc-800 transition-colors">
        {loading ? <Loader2 className="animate-spin text-orange-500" /> : icon}
      </div>
      <div className="space-y-1">
        <h3 className="text-xl font-bold group-hover:text-orange-500 transition-colors">{title}</h3>
        <p className="text-sm text-zinc-500">{description}</p>
      </div>
    </button>
  );
}

export function DateToggle({ label, active, onClick }: { label: string, active: boolean, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={cn(
        "px-6 py-2 rounded-xl text-xs font-bold transition-all",
        active ? "bg-orange-500 text-black shadow-lg" : "text-zinc-500 hover:text-white"
      )}
    >
      {label}
    </button>
  );
}

export function NavItem({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: any, label: string }) {
  return (
    <button 
      onClick={onClick} 
      className={cn(
        "w-full flex items-center gap-3 p-4 rounded-2xl transition-all", 
        active ? "bg-orange-500 text-black font-bold shadow-[0_10px_20px_-5px_rgba(249,115,22,0.4)]" : "text-zinc-500 hover:text-white hover:bg-white/5"
      )}
    >
      <span>{icon}</span>
      <span className="">{label}</span>
    </button>
  );
}
