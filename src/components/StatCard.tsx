import React from 'react';

const StatCard: React.FC<{ title: string; value: string; icon?: React.ReactNode }> = ({ title, value, icon }) => (
    <div className="bg-[#1a1a1a] p-4 rounded-lg text-center flex flex-col items-center justify-center">
        {icon && <div className="mb-2">{icon}</div>}
        <p className="text-sm text-zinc-400">{title}</p>
        <p className="text-2xl font-bold">{value}</p>
    </div>
);

export default StatCard;
