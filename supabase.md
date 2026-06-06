# FootyEdge AI - Supabase Database Schema

Copy and paste the code below into your **Supabase SQL Editor** and click **Run**.

```sql
-- ============================================
-- FOOTYEDGE AI DATABASE SCHEMA
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
    name TEXT NOT NULL,
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

-- 7. USER_BETS TABLE (New for Portfolio)
CREATE TABLE IF NOT EXISTS user_bets (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id),
    match_id BIGINT,
    market TEXT,
    selection TEXT,
    odds FLOAT,
    stake FLOAT,
    potential_win FLOAT,
    profit_loss FLOAT,
    status TEXT DEFAULT 'pending',
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

-- ENABLE RLS
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE value_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE accas ENABLE ROW LEVEL SECURITY;

-- POLICIES
DROP POLICY IF EXISTS "Public profiles are viewable by everyone" ON profiles;
CREATE POLICY "Public profiles are viewable by everyone" ON profiles FOR SELECT USING (true);
DROP POLICY IF EXISTS "Users can update own profile" ON profiles;
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);

DROP POLICY IF EXISTS "Enable read access for all users" ON teams;
CREATE POLICY "Enable read access for all users" ON teams FOR SELECT USING (true);
DROP POLICY IF EXISTS "Enable read access for all users" ON matches;
CREATE POLICY "Enable read access for all users" ON matches FOR SELECT USING (true);
DROP POLICY IF EXISTS "Enable read access for all users" ON predictions;
CREATE POLICY "Enable read access for all users" ON predictions FOR SELECT USING (true);
DROP POLICY IF EXISTS "Enable read access for all users" ON value_bets;
CREATE POLICY "Enable read access for all users" ON value_bets FOR SELECT USING (true);
DROP POLICY IF EXISTS "Enable read access for all users" ON players;
CREATE POLICY "Enable read access for all users" ON players FOR SELECT USING (true);

DROP POLICY IF EXISTS "Users can view their own bets" ON user_bets;
CREATE POLICY "Users can view their own bets" ON user_bets FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert their own bets" ON user_bets;
CREATE POLICY "Users can insert their own bets" ON user_bets FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can view their own accas" ON accas;
CREATE POLICY "Users can view their own accas" ON accas FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "Users can insert their own accas" ON accas;
CREATE POLICY "Users can insert their own accas" ON accas FOR INSERT WITH CHECK (auth.uid() = user_id);

-- PROFILE TRIGGER
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, role, is_premium)
    VALUES (new.id, new.email, 'user', false);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```
