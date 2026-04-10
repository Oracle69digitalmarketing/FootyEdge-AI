import React, { useState, useEffect } from 'react';

interface ValueBet {
  id?: string;
  home_team: string;
  away_team: string;
  market: string;
  selection: string;
  odds: number;
  our_probability: number;
  ev: number;
  kelly_percentage: number;
  recommended_stake_percentage: number;
  created_at: string;
}

const ValueBets: React.FC = () => {
  const [valueBets, setValueBets] = useState<ValueBet[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchValueBets = async () => {
      try {
        setLoading(true);
        const response = await fetch('/api/value-bets');
        if (!response.ok) {
          throw new Error('Failed to fetch value bets');
        }
        const data = await response.json();
        setValueBets(data);
      } catch (err) {
        if (err instanceof Error) {
            setError(err.message);
        } else {
            setError('An unknown error occurred');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchValueBets();
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchValueBets, 30000);
    
    return () => clearInterval(interval);
  }, []);

  if (loading && valueBets.length === 0) {
    return <div className="text-center p-8">Loading value bets...</div>;
  }

  if (error) {
    return <div className="text-center p-8 text-red-500">Error: {error}</div>;
  }

  return (
    <div className="p-4 md:p-8">
      <h1 className="text-3xl font-bold mb-6 text-center">Real-Time Value Bets</h1>
      {valueBets.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-full bg-[#1a1a1a] rounded-lg">
            <thead className="bg-[#2a2a2a]">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Match</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Market</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-300 uppercase tracking-wider">Selection</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-300 uppercase tracking-wider">Odds</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-300 uppercase tracking-wider">Our Prob.</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-300 uppercase tracking-wider">EV</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-300 uppercase tracking-wider">Stake %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {valueBets.map((bet) => (
                <tr key={bet.id} className="hover:bg-[#2a2a2a]">
                  <td className="px-6 py-4 whitespace-nowrap">{bet.home_team} vs {bet.away_team}</td>
                  <td className="px-6 py-4 whitespace-nowrap">{bet.market}</td>
                  <td className="px-6 py-4 whitespace-nowrap">{bet.selection}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right font-mono">{bet.odds.toFixed(2)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right font-mono">{(bet.our_probability * 100).toFixed(1)}%</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right font-mono text-green-400">{bet.ev.toFixed(3)}</td>
                  <td className="px-6 py-4 whitespace-nowrap text-right font-mono">{bet.recommended_stake_percentage.toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center p-8">No value bets found at the moment.</div>
      )}
    </div>
  );
};

export default ValueBets;
