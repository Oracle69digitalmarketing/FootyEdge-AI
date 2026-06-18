import React, { useState } from 'react';
import { Zap, Loader2, ShieldCheck, Activity, CheckCircle } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '../lib/utils';

const StrategyView: React.FC = () => {
  const [text, setText] = useState('');
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/analyze-strategy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      const data = await res.json();
      setAnalysis(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-8 md:p-12 space-y-8">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 bg-orange-500/10 rounded-2xl flex items-center justify-center border border-orange-500/20">
            <Zap className="text-orange-500" />
          </div>
          <div className="space-y-1">
            <h2 className="text-3xl font-bold">AI Strategy Analyzer</h2>
            <p className="text-zinc-500 text-sm">Describe your betting plan in natural language. Use commas to separate selections.</p>
          </div>
        </div>

        <div className="space-y-6">
          <textarea 
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="e.g., Man City win, Chelsea vs Arsenal draw, Over 2.5 in Liverpool match"
            className="w-full bg-zinc-900/50 border border-zinc-800 rounded-[2rem] p-8 h-48 focus:outline-none focus:border-orange-500 transition-colors resize-none leading-relaxed"
          />
          <button 
            onClick={handleAnalyze}
            disabled={loading || !text}
            className="w-full bg-orange-500 text-black font-black py-6 rounded-[2rem] flex items-center justify-center gap-4 hover:scale-[1.01] transition-all shadow-[0_20px_40px_-10px_rgba(249,115,22,0.3)] disabled:opacity-50 disabled:scale-100 uppercase tracking-widest"
          >
            {loading ? <Loader2 className="animate-spin w-6 h-6" /> : <ShieldCheck className="w-6 h-6" />}
            Analyze Strategy Risk & EV
          </button>
        </div>
      </div>

      <AnimatePresence>
        {analysis && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid grid-cols-1 md:grid-cols-2 gap-8"
          >
            <div className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-10 space-y-8">
              <h3 className="text-xl font-bold flex items-center gap-3"><Activity className="w-5 h-5 text-orange-500" /> Risk Assessment</h3>
              <div className="space-y-6">
                <div className="flex justify-between items-center p-4 bg-zinc-900/50 rounded-2xl border border-white/5">
                  <span className="text-zinc-500 text-sm">Risk Level</span>
                  <span className={cn(
                    "px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-widest",
                    analysis.metrics?.risk_score === 'Low' ? 'bg-green-500/10 text-green-500 border border-green-500/20' : 
                    analysis.metrics?.risk_score === 'Medium' ? 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20' : 'bg-red-500/10 text-red-500 border border-red-500/20'
                  )}>{analysis.metrics?.risk_score || 'Calculating...'}</span>
                </div>
                <div className="flex justify-between items-center p-4 bg-zinc-900/50 rounded-2xl border border-white/5">
                  <span className="text-zinc-500 text-sm">Expected Value (EV)</span>
                  <span className="text-green-500 font-black text-lg">{analysis.metrics?.expected_value || 'N/A'}</span>
                </div>
                <div className="flex justify-between items-center p-4 bg-zinc-900/50 rounded-2xl border border-white/5">
                  <span className="text-zinc-500 text-sm">Combined Odds</span>
                  <span className="font-black text-lg">@{analysis.metrics?.combined_odds_est || '0.00'}</span>
                </div>
                <div className="flex justify-between items-center p-4 bg-zinc-900/50 rounded-2xl border border-white/5">
                  <span className="text-zinc-500 text-sm">Win Probability</span>
                  <span className="font-black text-lg text-orange-500">{analysis.metrics?.win_probability || '0%'}</span>
                </div>
              </div>
            </div>

            <div className="bg-[#111] border border-zinc-800 rounded-[2.5rem] p-10 space-y-8">
              <h3 className="text-xl font-bold flex items-center gap-3"><CheckCircle className="w-5 h-5 text-green-500" /> AI Recommendation</h3>
              <div className="bg-zinc-900/50 p-6 rounded-2xl border-l-4 border-l-orange-500">
                <p className="text-white text-sm leading-relaxed font-medium italic">"{analysis.recommendation}"</p>
              </div>
              <div className="pt-6 border-t border-zinc-800">
                <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest mb-4">Internal Agent Summary</p>
                <p className="text-xs text-zinc-400 leading-relaxed">{analysis.summary}</p>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default StrategyView;
