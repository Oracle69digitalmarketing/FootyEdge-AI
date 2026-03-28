import React from 'react';
import { Clock, DollarSign, Wallet, TrendingUp as TrendingUpIcon } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

// Helper function (assuming it's reusable or defined elsewhere)
function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// StatCard component (assuming it's reusable or defined elsewhere)
function StatCard({ title, value, icon }: { title: string, value: string, icon: any }) {
    return (
      <div className="bg-[#111] border border-zinc-800 p-6 rounded-3xl space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">{title}</span>
          {icon}
        </div>
        <p className="text-4xl font-bold tracking-tighter">{value}</p>
      </div>
    );
  }

interface PortfolioProps {
  bankroll: number;
  userBets: any[]; // Define a more specific type if available
}

const Portfolio: React.FC<PortfolioProps> = ({ bankroll, userBets }) => {
  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Your Portfolio</h2>
        <div className="bg-zinc-900 border border-zinc-800 px-6 py-3 rounded-2xl">
          <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">Available Bankroll</p>
          <p className="text-2xl font-bold text-green-500">₦{bankroll.toLocaleString()}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <StatCard title="Active Bets" value={userBets.filter(b => b.status === 'pending').length.toString()} icon={<Clock className="text-blue-500" />} />
        <StatCard title="Total Stake" value={`₦${userBets.reduce((acc, b) => acc + b.stake, 0).toFixed(2)}`} icon={<DollarSign className="text-green-500" />} />
        <StatCard title="Win Rate" value={`${((userBets.filter(b => b.status === 'won').length / (userBets.filter(b => b.status !== 'pending').length || 1)) * 100).toFixed(1)}%`} icon={<TrendingUpIcon className="text-orange-500" />} />
        <StatCard title="Net Profit" value={`₦${(bankroll - 10000).toFixed(2)}`} icon={<Wallet className="text-purple-500" />} />
      </div>

      <div className="bg-[#111] border border-zinc-800 rounded-3xl overflow-hidden">
        <div className="p-6 border-b border-zinc-800">
          <h3 className="font-bold">Betting History</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-zinc-900/50 text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
              <tr>
                <th className="px-6 py-4">Match</th>
                <th className="px-6 py-4">Selection</th>
                <th className="px-6 py-4">Odds</th>
                <th className="px-6 py-4">Stake</th>
                <th className="px-6 py-4">Potential</th>
                <th className="px-6 py-4">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {userBets.map(bet => (
                <tr key={bet.id} className="hover:bg-zinc-900/30 transition-colors">
                  <td className="px-6 py-4 font-medium">{bet.selection.split(' to ')[0]}</td>
                  <td className="px-6 py-4">
                    <span className="text-xs bg-zinc-800 px-2 py-1 rounded-md">{bet.market}</span>
                  </td>
                  <td className="px-6 py-4 font-mono">{bet.odds}</td>
                  <td className="px-6 py-4 font-mono">₦{bet.stake}</td>
                  <td className="px-6 py-4 font-mono text-green-500">₦{bet.potential_win.toFixed(2)}</td>
                  <td className="px-6 py-4">
                    <span className={cn(
                      "text-[10px] font-bold uppercase px-2 py-1 rounded-full",
                      bet.status === 'won' ? "bg-green-500/10 text-green-500" :
                      bet.status === 'lost' ? "bg-red-500/10 text-red-500" :
                      "bg-blue-500/10 text-blue-500"
                    )}>
                      {bet.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default Portfolio;
