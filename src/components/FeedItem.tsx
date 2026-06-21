import React from 'react';

interface FeedItemProps {
  title: string;
  time: string;
  detail: string;
}

const FeedItem: React.FC<FeedItemProps> = ({ title, time, detail }) => {
  return (
    <div className="p-4 bg-zinc-900/30 border border-white/5 rounded-2xl space-y-1">
      <div className="flex justify-between items-center">
        <p className="text-xs font-bold text-zinc-300">{title}</p>
        <p className="text-[10px] font-mono text-zinc-600">{time}</p>
      </div>
      <p className="text-[10px] text-zinc-500 leading-relaxed">{detail}</p>
    </div>
  );
};

export default FeedItem;
