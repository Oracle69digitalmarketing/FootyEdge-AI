-- ============================================
-- FOOTYEDGE AI DATABASE SCHEMA
-- Run this in Supabase SQL Editor
-- ============================================

-- 1. TEAMS TABLE
CREATE TABLE teams (
    id BIGSERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    country TEXT,
    league TEXT,
    elo_rating FLOAT DEFAULT 1500,
    attack_strength FLOAT DEFAULT 1.0,
    defense_strength FLOAT DEFAULT 1.0,
    home_advantage FLOAT DEFAULT 50,
    form_rating FLOAT DEFAULT 0.5,
    total_matches INT DEFAULT 0,
    wins INT DEFAULT 0,
    draws INT DEFAULT 0,
    losses INT DEFAULT 0,
    goals_scored INT DEFAULT 0,
    goals_conceded INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. MATCHES TABLE
CREATE TABLE matches (
    id BIGSERIAL PRIMARY KEY,
    home_team_id BIGINT REFERENCES teams(id),
    away_team_id BIGINT REFERENCES teams(id),
    match_date TIMESTAMP NOT NULL,
    league VARCHAR(50),
    season VARCHAR(20),
    home_goals INT,
    away_goals INT,
    home_xg FLOAT,
    away_xg FLOAT,
    home_possession FLOAT,
    away_possession FLOAT,
    home_shots INT,
    away_shots INT,
    home_shots_on_target INT,
    away_shots_on_target INT,
    home_corners INT,
    away_corners INT,
    home_yellow_cards INT,
    away_yellow_cards INT,
    home_red_cards INT,
    away_red_cards INT,
    weather VARCHAR(50),
    temperature FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. PREDICTIONS TABLE
CREATE TABLE predictions (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT REFERENCES matches(id),
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    home_prob FLOAT,
    draw_prob FLOAT,
    away_prob FLOAT,
    home_xg FLOAT,
    away_xg FLOAT,
    confidence FLOAT,
    best_bet_market VARCHAR(50),
    best_bet_selection VARCHAR(100),
    best_bet_odds FLOAT,
    best_bet_ev FLOAT,
    best_bet_kelly FLOAT,
    model_version VARCHAR(20),
    actual_result VARCHAR(10),
    prediction_error FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. VALUE_BETS TABLE
CREATE TABLE value_bets (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT REFERENCES matches(id),
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    market VARCHAR(50),
    selection VARCHAR(100),
    odds FLOAT,
    our_probability FLOAT,
    implied_probability FLOAT,
    ev FLOAT,
    kelly_percentage FLOAT,
    recommended_stake_percentage FLOAT,
    recommended_stake_amount FLOAT,
    bankroll_used FLOAT,
    status VARCHAR(20) DEFAULT 'active',
    settled BOOLEAN DEFAULT FALSE,
    actual_win BOOLEAN,
    profit_loss FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. TEAM_RATINGS_HISTORY (Time-series)
CREATE TABLE team_ratings_history (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT REFERENCES teams(id),
    rating_date DATE NOT NULL,
    elo_rating FLOAT,
    attack_strength FLOAT,
    defense_strength FLOAT,
    form_rating FLOAT,
    position_in_league INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. USER_BETS (for tracking user bets)
CREATE TABLE user_bets (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    match_id BIGINT REFERENCES matches(id),
    market VARCHAR(50),
    selection VARCHAR(100),
    odds FLOAT,
    stake FLOAT,
    potential_win FLOAT,
    value_bet_id BIGINT REFERENCES value_bets(id),
    actual_result VARCHAR(10),
    profit_loss FLOAT,
    settled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 7. AGENT_LOGS (for debugging)
CREATE TABLE agent_logs (
    id BIGSERIAL PRIMARY KEY,
    agent_name VARCHAR(50),
    action VARCHAR(100),
    input_data JSONB,
    output_data JSONB,
    execution_time_ms INT,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- INDEXES FOR PERFORMANCE
-- ============================================

CREATE INDEX idx_predictions_created ON predictions(created_at DESC);
CREATE INDEX idx_predictions_match ON predictions(match_id);
CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_matches_teams ON matches(home_team_id, away_team_id);
CREATE INDEX idx_value_bets_active ON value_bets(status, created_at);
CREATE INDEX idx_team_ratings_date ON team_ratings_history(rating_date DESC);
CREATE INDEX idx_agent_logs_created ON agent_logs(created_at DESC);

-- ============================================
-- ENABLE ROW LEVEL SECURITY
-- ============================================

ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE value_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_ratings_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;

-- Public read access
CREATE POLICY "Enable read access for all users" ON teams FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON matches FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON predictions FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON value_bets FOR SELECT USING (true);
CREATE POLICY "Enable read access for all users" ON team_ratings_history FOR SELECT USING (true);

-- Authenticated write access
CREATE POLICY "Enable insert for authenticated users" ON predictions FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable insert for authenticated users" ON value_bets FOR INSERT WITH CHECK (true);

-- ============================================
-- ENABLE REALTIME SUBSCRIPTIONS
-- ============================================

ALTER TABLE predictions REPLICA IDENTITY FULL;
ALTER TABLE value_bets REPLICA IDENTITY FULL;

ALTER PUBLICATION supabase_realtime ADD TABLE predictions;
ALTER PUBLICATION supabase_realtime ADD TABLE value_bets;

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Calculate team stats after match
CREATE OR REPLACE FUNCTION update_team_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Update home team stats
    UPDATE teams
    SET 
        total_matches = total_matches + 1,
        goals_scored = goals_scored + NEW.home_goals,
        goals_conceded = goals_conceded + NEW.away_goals,
        wins = wins + CASE WHEN NEW.home_goals > NEW.away_goals THEN 1 ELSE 0 END,
        draws = draws + CASE WHEN NEW.home_goals = NEW.away_goals THEN 1 ELSE 0 END,
        losses = losses + CASE WHEN NEW.home_goals < NEW.away_goals THEN 1 ELSE 0 END
    WHERE id = NEW.home_team_id;
    
    -- Update away team stats
    UPDATE teams
    SET 
        total_matches = total_matches + 1,
        goals_scored = goals_scored + NEW.away_goals,
        goals_conceded = goals_conceded + NEW.home_goals,
        wins = wins + CASE WHEN NEW.away_goals > NEW.home_goals THEN 1 ELSE 0 END,
        draws = draws + CASE WHEN NEW.away_goals = NEW.home_goals THEN 1 ELSE 0 END,
        losses = losses + CASE WHEN NEW.away_goals < NEW.home_goals THEN 1 ELSE 0 END
    WHERE id = NEW.away_team_id;
    
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER after_match_insert AFTER INSERT ON matches
    FOR EACH ROW EXECUTE FUNCTION update_team_stats();

-- 8. ACTIVITY_LOG TABLE
CREATE TABLE activity_log (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    action VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_activity_log_created ON activity_log(created_at DESC);
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable read access for admin users" ON activity_log FOR SELECT USING (true); -- Should be restricted to admin

-- 9. ACCAS TABLE
CREATE TABLE accas (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    selections_json JSONB,
    total_odds FLOAT,
    stake FLOAT,
    potential_return FLOAT,
    bookmaker VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE accas ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable insert for authenticated users" ON accas FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable read for own accas" ON accas FOR SELECT USING (true); -- Simplified
