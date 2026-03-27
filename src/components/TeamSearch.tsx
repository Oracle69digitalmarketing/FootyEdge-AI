import React, { useState } from 'react';
import { Team } from '../types';
import TeamStats from './TeamStats';

interface TeamSearchProps {
  teams: Team[];
}

const TeamSearch: React.FC<TeamSearchProps> = ({ teams }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);

  const filteredTeams = searchTerm
    ? teams.filter(team =>
        team.name.toLowerCase().includes(searchTerm.toLowerCase())
      )
    : [];

  const handleTeamClick = (team: Team) => {
    setSelectedTeam(team);
    setSearchTerm('');
  };
  
  if (selectedTeam) {
    return <TeamStats team={selectedTeam} onBack={() => setSelectedTeam(null)} />;
  }

  return (
    <div className="p-4 md:p-8">
      <h1 className="text-3xl font-bold mb-6 text-center">Team Search</h1>
      <div className="max-w-xl mx-auto">
        <input
          type="text"
          placeholder="Search for a team..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="w-full bg-zinc-900 border border-zinc-800 rounded-2xl p-4 text-white focus:outline-none focus:border-orange-500 transition-colors"
        />
        {searchTerm && (
          <div className="mt-4 bg-[#1a1a1a] rounded-lg max-h-60 overflow-y-auto">
            {filteredTeams.map(team => (
              <div
                key={team.id}
                onClick={() => handleTeamClick(team)}
                className="p-4 cursor-pointer hover:bg-[#2a2a2a]"
              >
                {team.name}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default TeamSearch;
