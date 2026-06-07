import React from 'react';
import { Check, Crown, Zap, Shield, Star } from 'lucide-react';
import { cn } from '../lib/utils';

const Pricing: React.FC = () => {
  return (
    <div className="space-y-12 py-8">
      <div className="text-center space-y-4">
        <h2 className="text-4xl font-bold">Choose Your Edge</h2>
        <p className="text-zinc-500 max-w-2xl mx-auto">Get access to professional-grade AI betting tools, advanced xG models, and real-time value alerts.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <PriceCard 
          tier="Basic"
          price="Free"
          description="Essential AI tools for casual bettors."
          features={[
            "Standard Poisson Predictions",
            "Recent Match History",
            "Basic Value Scanner (3 Leagues)",
            "Acca Builder Access",
            "Community Telegram Channel"
          ]}
        />
        
        <PriceCard 
          tier="Pro"
          price="₦15,000"
          period="/month"
          highlight
          description="Advanced intelligence for serious traders."
          features={[
            "Hybrid AI Model (70% Stats / 30% xG)",
            "Live Value Alerts (All Major Leagues)",
            "Full Team & Player Database",
            "AI Strategy Analyzer",
            "Detailed H2H Visualizer",
            "365Scores Stats Integration",
            "Priority Support"
          ]}
          icon={<Zap className="w-5 h-5 text-orange-500" />}
        />

        <PriceCard 
          tier="Premium"
          price="₦35,000"
          period="/month"
          description="The ultimate betting engine for professionals."
          features={[
            "Everything in Pro",
            "Exclusive Premium Signals Channel",
            "Unlimited Live Market Scanning",
            "Custom Strategy Backtesting",
            "Early Access to New Models",
            "Personalized Portfolio Management",
            "1-on-1 Betting Consultation"
          ]}
          icon={<Crown className="w-5 h-5 text-yellow-500" />}
        />
      </div>
    </div>
  );
};

function PriceCard({ tier, price, period, description, features, highlight, icon }: any) {
  return (
    <div className={cn(
      "bg-[#111] border rounded-[2.5rem] p-8 space-y-8 relative overflow-hidden transition-all hover:scale-[1.02]",
      highlight ? "border-orange-500/50 shadow-[0_0_40px_-15px_rgba(249,115,22,0.3)]" : "border-zinc-800"
    )}>
      {highlight && (
        <div className="absolute top-0 right-0 bg-orange-500 text-black text-[10px] font-bold px-4 py-1 rounded-bl-xl uppercase tracking-widest">
          Most Popular
        </div>
      )}
      
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          {icon || <Shield className="w-5 h-5 text-zinc-500" />}
          <h3 className="text-xl font-bold">{tier}</h3>
        </div>
        <div className="flex items-baseline gap-1">
          <span className="text-4xl font-bold">{price}</span>
          {period && <span className="text-zinc-500 text-sm">{period}</span>}
        </div>
        <p className="text-sm text-zinc-500">{description}</p>
      </div>

      <div className="space-y-4">
        {features.map((f: string, i: number) => (
          <div key={i} className="flex items-start gap-3">
            <Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
            <span className="text-sm text-zinc-300">{f}</span>
          </div>
        ))}
      </div>

      <button className={cn(
        "w-full py-4 rounded-2xl font-bold transition-all",
        highlight ? "bg-orange-500 text-black hover:bg-orange-400" : "bg-zinc-900 border border-zinc-800 text-white hover:bg-zinc-800"
      )}>
        Upgrade to {tier}
      </button>
    </div>
  );
}

export default Pricing;
