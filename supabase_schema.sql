-- ============================================
-- FOOTYEDGE AI DATABASE SCHEMA (PRODUCTION-READY)
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
    name TEXT UNIQUE NOT NULL,
    country TEXT,
    logo_url TEXT,
    league_name TEXT,
    elo_rating FLOAT DEFAULT 1500,
    attack_strength FLOAT DEFAULT 1.0,
    defense_strength FLOAT DEFAULT 1.0,
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
    created_at TIMESTAMP DEFAULT NOW(),
    -- Ensures unique matches to prevent duplicates
    CONSTRAINT unique_match UNIQUE (home_team_id, away_team_id, match_date)
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
    model_version VARCHAR(20),
    actual_result VARCHAR(10), -- Required for accuracy tracking
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
    ev FLOAT,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. PLAYERS TABLE
CREATE TABLE IF NOT EXISTS players (
    id BIGSERIAL PRIMARY KEY,
    external_id BIGINT,
    team_id BIGINT REFERENCES teams(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position TEXT,
    nationality TEXT,
    age INT,
    photo_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Constraint required for upsert to work properly
    UNIQUE(name, team_id)
);

-- ============================================
-- INDEXES
-- ============================================

CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Function to handle new user profiles
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, role, is_premium)
    VALUES (new.id, new.email, 'user', (new.email = 'sophiemabel69@gmail.com'));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Trigger for new user signup
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- RLS Policies (Simplified for production)
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Public read access" ON teams FOR SELECT USING (true);
CREATE POLICY "Admin full access" ON teams FOR ALL USING (auth.jwt()->>'email' = 'sophiemabel69@gmail.com');

-- 6. BETS TABLE (FOR USER TRACKING)
CREATE TABLE IF NOT EXISTS bets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    match_id BIGINT REFERENCES matches(id),
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    odds FLOAT NOT NULL,
    stake FLOAT NOT NULL,
    potential_win FLOAT NOT NULL,
    status TEXT DEFAULT 'active', -- 'active', 'won', 'lost', 'void'
    booking_code TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
