export interface Team {
  id?: string;
  name: string;
  country?: string;
  logo?: string;
  league?: string;
  elo_rating: number;
  attack_strength: number;
  defense_strength: number;
  home_advantage: number;
  form_rating: number;
  total_matches: number;
  wins: number;
  draws: number;
  losses: number;
  goals_scored: number;
  goals_conceded: number;
  updated_at: string;
  ratings_history?: { rating_date: string; elo_rating: number; attack_strength: number; defense_strength: number; }[];
}

export interface Match {
  id?: string;
  home_team_id: string;
  away_team_id: string;
  match_date: string;
  home_goals: number;
  away_goals: number;
  home_xg: number;
  away_xg: number;
}

export interface Prediction {
  id?: string;
  home_team: string;
  away_team: string;
  home_id?: string | number;
  away_id?: string | number;
  home_prob: number;
  draw_prob: number;
  away_prob: number;
  home_xg: number;
  away_xg: number;
  over_2_5_prob?: number;
  under_2_5_prob?: number;
  btts_prob?: number;
  dc_home_draw_prob?: number;
  dc_away_draw_prob?: number;
  dc_home_away_prob?: number;
  correct_scores?: { score: string; prob: number }[];
  is_premium?: boolean;
  confidence: number;
  best_bet_market?: string;
  best_bet_selection?: string;
  best_bet_odds?: number;
  best_bet_ev?: number;
  kelly_percentage?: number;
  recommended_stake?: string;
  created_at: string;
}

export interface ValueBet {
  id?: string;
  match?: string;
  home_team?: string;
  away_team?: string;
  market: string;
  selection: string;
  odds: number;
  our_probability: number;
  ev: number;
  kelly: number;
  recommended_stake: string;
  status: 'active' | 'won' | 'lost';
  tier: 'Hot 🔥' | 'Solid' | 'Neutral';
  created_at: string;
}

export interface ScoreProbability {
  home_goals: number;
  away_goals: number;
  probability: number;
}
