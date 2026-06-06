-- ============================================
-- FOOTYEDGE AI DATABASE SCHEMA
-- Run this in Supabase SQL Editor
-- ============================================

-- 0. PROFILES TABLE
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_premium BOOLEAN DEFAULT FALSE,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 1. TEAMS TABLE
CREATE TABLE IF NOT EXISTS teams (
    id BIGINT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL, -- UNIQUE required for upsert on name
    country TEXT,
    logo_url TEXT,
    league_name TEXT,
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. MATCHES TABLE
CREATE TABLE IF NOT EXISTS matches (
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
CREATE TABLE IF NOT EXISTS predictions (
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
CREATE TABLE IF NOT EXISTS value_bets (
    id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT REFERENCES predictions(id) ON DELETE CASCADE,
    match_id BIGINT,
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    market VARCHAR(50),
    selection VARCHAR(100),
    odds FLOAT,
    stake_units FLOAT,
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
    match_timestamp TIMESTAMP WITH TIME ZONE,
    tier VARCHAR(20) DEFAULT 'Neutral',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. TEAM_RATINGS_HISTORY
CREATE TABLE IF NOT EXISTS team_ratings_history (
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

-- 6. ACCAS TABLE
CREATE TABLE IF NOT EXISTS accas (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    selections_json JSONB,
    total_odds FLOAT,
    stake FLOAT,
    potential_return FLOAT,
    bookmaker TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. AGENT_LOGS
CREATE TABLE IF NOT EXISTS agent_logs (
    id BIGSERIAL PRIMARY KEY,
    agent_name VARCHAR(50),
    action VARCHAR(100),
    input_data JSONB,
    output_data JSONB,
    execution_time_ms INT,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. ACTIVITY_LOG
CREATE TABLE IF NOT EXISTS activity_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    action VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 10. PLAYERS TABLE
CREATE TABLE IF NOT EXISTS players (
    id BIGSERIAL PRIMARY KEY,
    external_id BIGINT,
    team_id BIGINT REFERENCES teams(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position TEXT,
    nationality TEXT,
    age INT,
    photo_url TEXT,
    number INT,
    is_injured BOOLEAN DEFAULT FALSE,
    is_suspended BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(name, team_id)
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_predictions_match ON predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_matches_teams ON matches(home_team_id, away_team_id);
CREATE INDEX IF NOT EXISTS idx_value_bets_active ON value_bets(status, created_at);
CREATE INDEX IF NOT EXISTS idx_team_ratings_date ON team_ratings_history(rating_date DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_created ON agent_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_created ON activity_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);
CREATE INDEX IF NOT EXISTS idx_players_team ON players(team_id);
CREATE INDEX IF NOT EXISTS idx_players_name ON players(name);

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Update team stats after match result
CREATE OR REPLACE FUNCTION update_team_stats()
RETURNS TRIGGER AS $$
BEGIN
    -- Home Team
    UPDATE teams
    SET 
        total_matches = total_matches + 1,
        goals_scored = goals_scored + NEW.home_goals,
        goals_conceded = goals_conceded + NEW.away_goals,
        wins = wins + CASE WHEN NEW.home_goals > NEW.away_goals THEN 1 ELSE 0 END,
        draws = draws + CASE WHEN NEW.home_goals = NEW.away_goals THEN 1 ELSE 0 END,
        losses = losses + CASE WHEN NEW.home_goals < NEW.away_goals THEN 1 ELSE 0 END
    WHERE id = NEW.home_team_id;
    
    -- Away Team
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

-- Profile on Signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, role, is_premium)
    VALUES (new.id, new.email, 'user', (new.email = 'sophiemabel69@gmail.com'));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Check if trigger exists before creating
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'on_auth_user_created') THEN
        CREATE TRIGGER on_auth_user_created
            AFTER INSERT ON auth.users
            FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
    END IF;
END $$;

-- ============================================
-- RLS POLICIES
-- ============================================

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE value_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_ratings_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE accas ENABLE ROW LEVEL SECURITY;
ALTER TABLE activity_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE players ENABLE ROW LEVEL SECURITY;

-- Select: Public
CREATE POLICY "Public read access" ON profiles FOR SELECT USING (true);
CREATE POLICY "Public read access" ON teams FOR SELECT USING (true);
CREATE POLICY "Public read access" ON matches FOR SELECT USING (true);
CREATE POLICY "Public read access" ON predictions FOR SELECT USING (true);
CREATE POLICY "Public read access" ON value_bets FOR SELECT USING (true);
CREATE POLICY "Public read access" ON players FOR SELECT USING (true);

-- Auth Profile
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);

-- Accas
CREATE POLICY "Users can insert their own accas" ON accas FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can view their own accas" ON accas FOR SELECT USING (auth.uid() = user_id);

-- Admin / Maintenance (Email based for simplicity in this project)
CREATE POLICY "Admin full access" ON teams FOR ALL USING (auth.jwt()->>'email' = 'sophiemabel69@gmail.com');
CREATE POLICY "Admin full access" ON matches FOR ALL USING (auth.jwt()->>'email' = 'sophiemabel69@gmail.com');
CREATE POLICY "Admin full access" ON predictions FOR ALL USING (auth.jwt()->>'email' = 'sophiemabel69@gmail.com');
CREATE POLICY "Admin full access" ON value_bets FOR ALL USING (auth.jwt()->>'email' = 'sophiemabel69@gmail.com');
CREATE POLICY "Admin full access" ON players FOR ALL USING (auth.jwt()->>'email' = 'sophiemabel69@gmail.com');

-- ============================================
-- REALTIME
-- ============================================

ALTER TABLE predictions REPLICA IDENTITY FULL;
ALTER TABLE value_bets REPLICA IDENTITY FULL;
ALTER TABLE accas REPLICA IDENTITY FULL;

-- Publications
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        CREATE PUBLICATION supabase_realtime;
    END IF;
END $$;

ALTER PUBLICATION supabase_realtime ADD TABLE predictions;
ALTER PUBLICATION supabase_realtime ADD TABLE value_bets;
ALTER PUBLICATION supabase_realtime ADD TABLE accas;
