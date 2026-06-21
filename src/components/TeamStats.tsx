import React from 'react';
import { Team } from '../types';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

import StatCard from './StatCard';

interface TeamStatsProps {
  team: Team;
  onBack: () => void;
}

const TeamStats: React.FC<TeamStatsProps> = ({ team, onBack }) => {
  const chartData = {
    labels: team.ratings_history?.map(h => new Date(h.rating_date).toLocaleDateString()).reverse() || [],
    datasets: [
      {
        label: 'Elo Rating',
        data: team.ratings_history?.map(h => h.elo_rating).reverse() || [],
        borderColor: 'rgb(255, 99, 132)',
        backgroundColor: 'rgba(255, 99, 132, 0.5)',
      },
    ],
  };

  const chartOptions = {
    responsive: true,
    plugins: {
      legend: {
        position: 'top' as const,
      },
      title: {
        display: true,
        text: 'Elo Rating Over Time',
      },
    },
  };

  return (
    <div className="p-4 md:p-8">
      <button onClick={onBack} className="text-orange-500 mb-4">&larr; Back to search</button>
      <h1 className="text-3xl font-bold mb-2 text-center">{team.name}</h1>
      <p className="text-center text-zinc-500 mb-6">{team.league}</p>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard title="Elo Rating" value={team.elo_rating.toFixed(0)} />
        <StatCard title="Attack Strength" value={team.attack_strength.toFixed(2)} />
        <StatCard title="Defense Strength" value={team.defense_strength.toFixed(2)} />
        <StatCard title="Form" value={`${(team.form_rating * 100).toFixed(0)}%`} />
      </div>

      <div className="bg-[#1a1a1a] p-6 rounded-lg">
        <h2 className="text-xl font-bold mb-4">Rating History</h2>
        {team.ratings_history && team.ratings_history.length > 0 ? (
          <Line options={chartOptions} data={chartData} />
        ) : (
          <div className="h-64 flex items-center justify-center text-zinc-500">
            No rating history available.
          </div>
        )}
      </div>
    </div>
  );
};



export default TeamStats;
