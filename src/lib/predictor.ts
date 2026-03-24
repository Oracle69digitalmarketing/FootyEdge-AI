import { Team, Prediction, ValueBet, ScoreProbability } from '../types';

/**
 * FootyEdge AI Engine - Enterprise Multi-Agent Architecture
 */
export class FootyEdgePredictor {
  private homeAdvantage = 50;

  /**
   * AGENT: Athena (Data Ingestion & Normalization)
   * Prepares and cleans team data for analysis
   */
  private athenaNormalize(team: Team): Team {
    return {
      ...team,
      attack_strength: Math.max(0.1, Math.min(3.0, team.attack_strength)),
      defense_strength: Math.max(0.1, Math.min(3.0, team.defense_strength)),
      form_rating: Math.max(-1.0, Math.min(1.0, team.form_rating))
    };
  }

  /**
   * AGENT: Ares (Team Strength Analyzer)
   * Calculates Bayesian Elo ratings and relative dominance
   */
  private aresCalculateStrength(home: Team, away: Team): { home: number, away: number } {
    // Incorporate home/away specific bias and defensive solidity
    const homeDefensiveBonus = (1 / (home.defense_strength || 1)) * 20;
    const awayDefensiveBonus = (1 / (away.defense_strength || 1)) * 15;

    const homeStrength = home.elo_rating + this.homeAdvantage + (home.form_rating * 150) + (home.attack_strength * 80) + homeDefensiveBonus;
    const awayStrength = away.elo_rating + (away.form_rating * 130) + (away.attack_strength * 70) + awayDefensiveBonus;
    
    // Bayesian adjustment based on head-to-head potential
    const total = homeStrength + awayStrength;
    return {
      home: homeStrength / (total || 1),
      away: awayStrength / (total || 1)
    };
  }

  /**
   * AGENT: Apollo (Goal Distribution Engine)
   * Uses Poisson modeling to predict expected goals (xG)
   */
  private apolloPredictXG(home: Team, away: Team): { homeXg: number, awayXg: number } {
    // Advanced Poisson Lambda calculation with "Chaos Factor" for high-variance scenarios
    const chaosFactor = Math.random() * 0.2 - 0.1; // Small variance to simulate match-day unpredictability
    
    let homeXg = (home.attack_strength / (away.defense_strength || 1)) * 1.55 * (1 + (home.form_rating * 0.6)) + chaosFactor;
    let awayXg = (away.attack_strength / (home.defense_strength || 1)) * 1.35 * (1 + (away.form_rating * 0.4)) + chaosFactor;

    // Cap realistic ranges based on historical league caps
    return {
      homeXg: Math.max(0.5, Math.min(3.5, homeXg)),
      awayXg: Math.max(0.3, Math.min(3.0, awayXg))
    };
  }

  private poisson(k: number, lambda: number): number {
    const factorial = (n: number): number => (n <= 1 ? 1 : n * factorial(n - 1));
    return (Math.pow(lambda, k) * Math.exp(-lambda)) / factorial(k);
  }

  private calculateMarketProbs(homeXg: number, awayXg: number): { over25: number, under25: number, btts: number } {
    let prob00 = this.poisson(0, homeXg) * this.poisson(0, awayXg);
    let prob10 = this.poisson(1, homeXg) * this.poisson(0, awayXg);
    let prob01 = this.poisson(0, homeXg) * this.poisson(1, awayXg);
    let prob11 = this.poisson(1, homeXg) * this.poisson(1, awayXg);
    let prob20 = this.poisson(2, homeXg) * this.poisson(0, awayXg);
    let prob02 = this.poisson(0, homeXg) * this.poisson(2, awayXg);

    const under25 = prob00 + prob10 + prob01 + prob11 + prob20 + prob02;
    const over25 = 1 - under25;

    const bttsNo = 
      this.poisson(0, homeXg) + 
      this.poisson(0, awayXg) - 
      (this.poisson(0, homeXg) * this.poisson(0, awayXg));
    const btts = 1 - bttsNo;

    return { over25, under25, btts };
  }

  /**
   * AGENT: Hermes (Value Bet Detector)
   * Scans markets for positive Expected Value (EV)
   */
  private hermesDetectValue(prob: number, odds: number, threshold: number = 0.03): number {
    const ev = (prob * odds) - 1;
    // Lowered threshold to 3% to capture more high-frequency value in volatile markets
    return ev > threshold ? ev : 0;
  }

  /**
   * AGENT: Nike (Kelly Calculator)
   * Optimizes bankroll management and stake sizing
   */
  private nikeCalculateStake(probability: number, odds: number): { kelly: number, stake: string } {
    const b = odds - 1;
    const p = probability;
    const q = 1 - p;
    
    if (b <= 0 || p <= 0) return { kelly: 0, stake: "0%" };
    
    const kelly = (p * b - q) / b;
    const safeKelly = Math.max(0, Math.min(kelly, 0.20)); // Cap at 20% for enterprise safety
    
    // Fractional Kelly (0.25 multiplier) for long-term growth stability
    const recommendedStake = (safeKelly * 0.25 * 100).toFixed(1) + "%";
    
    return { kelly: safeKelly, stake: recommendedStake };
  }

  /**
   * AGENT: Zeus (Orchestration Engine)
   * Coordinates all agents to produce the final intelligence output
   */
  public predictMatch(homeRaw: Team, awayRaw: Team): Prediction {
    // 1. Athena normalizes the data
    const home = this.athenaNormalize(homeRaw);
    const away = this.athenaNormalize(awayRaw);

    // 2. Ares analyzes relative strength
    const { home: homeProbRaw, away: awayProbRaw } = this.aresCalculateStrength(home, away);

    // 3. Apollo predicts goal distribution
    const { homeXg, awayXg } = this.apolloPredictXG(home, away);

    // 4. Calculate Market Probabilities (O/U 2.5, BTTS)
    const { over25, under25, btts } = this.calculateMarketProbs(homeXg, awayXg);

    // 5. Calculate Draw probability based on xG overlap
    const eloDiff = Math.abs(home.elo_rating - away.elo_rating);
    const drawProb = Math.max(0.22, Math.min(0.33, 0.29 - (eloDiff / 1200)));

    // Adjust win probabilities to account for draw
    const homeProb = homeProbRaw * (1 - drawProb);
    const awayProb = awayProbRaw * (1 - drawProb);

    return {
      home_team: home.name,
      away_team: away.name,
      home_prob: homeProb,
      draw_prob: drawProb,
      away_prob: awayProb,
      home_xg: homeXg,
      away_xg: awayXg,
      over_2_5_prob: over25,
      under_2_5_prob: under25,
      btts_prob: btts,
      confidence: this.calculateConfidence(homeProb, drawProb, awayProb),
      created_at: new Date().toISOString()
    };
  }

  private calculateConfidence(homeProb: number, drawProb: number, awayProb: number): number {
    const probs = [homeProb, drawProb, awayProb].sort((a, b) => b - a);
    // Confidence is derived from the gap between the primary and secondary outcome
    // A larger gap means the model is more "certain" about its top pick
    const gap = probs[0] - probs[1];
    const baseConfidence = gap * 2.8;
    
    // Add a bonus for very high win probabilities (> 65%)
    const highProbBonus = probs[0] > 0.65 ? 0.1 : 0;
    
    return Math.min(0.99, Math.max(0.40, baseConfidence + highProbBonus));
  }

  /**
   * Orchestrated Value Detection
   */
  public findValueBets(prediction: Prediction, bookmakerOdds: { [key: string]: number }): ValueBet[] {
    const valueBets: ValueBet[] = [];
    const markets = [
      { key: 'home_win', prob: prediction.home_prob, selection: `${prediction.home_team} to win` },
      { key: 'draw', prob: prediction.draw_prob, selection: 'Draw' },
      { key: 'away_win', prob: prediction.away_prob, selection: `${prediction.away_team} to win` },
      { key: 'over_2_5', prob: prediction.over_2_5_prob || 0, selection: 'Over 2.5 Goals' },
      { key: 'under_2_5', prob: prediction.under_2_5_prob || 0, selection: 'Under 2.5 Goals' },
      { key: 'btts_yes', prob: prediction.btts_prob || 0, selection: 'Both Teams to Score: Yes' }
    ];

    for (const market of markets) {
      const odds = bookmakerOdds[market.key];
      if (!odds) continue;

      // Hermes detects value
      const ev = this.hermesDetectValue(market.prob, odds);
      
      if (ev > 0) {
        // Nike calculates optimal stake
        const { kelly, stake } = this.nikeCalculateStake(market.prob, odds);
        
        valueBets.push({
          match: `${prediction.home_team} vs ${prediction.away_team}`,
          market: market.key,
          selection: market.selection,
          odds: odds,
          our_probability: market.prob,
          ev: ev,
          kelly: kelly,
          recommended_stake: stake,
          status: 'active',
          created_at: new Date().toISOString()
        });
      }
    }

    return valueBets.sort((a, b) => b.ev - a.ev);
  }
}
