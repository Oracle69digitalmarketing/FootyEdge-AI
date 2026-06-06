# FootyEdge AI - Supabase Database Schema (FORCE REPAIR)

This version uses `CASCADE` to force-drop old tables and fix dependency errors. Copy and paste the code below into your **Supabase SQL Editor** and click **Run**.

**Warning:** This script will completely wipe existing FootyEdge data for a fresh start.

```sql
-- ============================================
-- 0. FORCE CLEANUP
-- ============================================
DROP TABLE IF EXISTS players CASCADE;
DROP TABLE IF EXISTS team_ratings_history CASCADE;
DROP TABLE IF EXISTS accas CASCADE;
DROP TABLE IF EXISTS user_bets CASCADE;
DROP TABLE IF EXISTS predictions CASCADE;
DROP TABLE IF EXISTS value_bets CASCADE;
DROP TABLE IF EXISTS matches CASCADE;
DROP TABLE IF EXISTS teams CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;
DROP TABLE IF EXISTS activity_log CASCADE;
DROP TABLE IF EXISTS agent_logs CASCADE;

-- ============================================
-- 1. PROFILES TABLE
-- ============================================
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    avatar_url TEXT,
    is_premium BOOLEAN DEFAULT FALSE,
    role TEXT DEFAULT 'user',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- 2. TEAMS TABLE
-- ============================================
CREATE TABLE teams (
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

-- ============================================
-- 3. PLAYERS TABLE
-- ============================================
CREATE TABLE players (
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
-- 4. MATCHES TABLE
-- ============================================
CREATE TABLE matches (
    id BIGSERIAL PRIMARY KEY,
    home_team_id BIGINT REFERENCES teams(id) ON DELETE CASCADE,
    away_team_id BIGINT REFERENCES teams(id) ON DELETE CASCADE,
    match_date TIMESTAMP NOT NULL,
    league VARCHAR(100),
    home_goals INT,
    away_goals INT,
    home_xg FLOAT,
    away_xg FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 5. PREDICTIONS TABLE
-- ============================================
CREATE TABLE predictions (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT,
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
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 6. VALUE_BETS TABLE
-- ============================================
CREATE TABLE value_bets (
    id BIGSERIAL PRIMARY KEY,
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    market VARCHAR(50),
    selection VARCHAR(100),
    odds FLOAT,
    our_probability FLOAT,
    ev FLOAT,
    status VARCHAR(20) DEFAULT 'active',
    match_timestamp TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- 7. TEAM_RATINGS_HISTORY
-- ============================================
CREATE TABLE team_ratings_history (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT REFERENCES teams(id) ON DELETE CASCADE,
    rating_date DATE NOT NULL,
    elo_rating FLOAT,
    attack_strength FLOAT,
    defense_strength FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- 8. USER_BETS & ACCAS
-- ============================================
CREATE TABLE user_bets (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
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

CREATE TABLE accas (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    selections_json JSONB,
    total_odds FLOAT,
    stake FLOAT,
    potential_return FLOAT,
    bookmaker TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- 9. ACTIVITY LOG
-- ============================================
CREATE TABLE activity_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    action VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- ENABLE ROW LEVEL SECURITY
-- ============================================
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE players ENABLE ROW LEVEL SECURITY;
ALTER TABLE matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE value_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE accas ENABLE ROW LEVEL SECURITY;

-- ============================================
-- PUBLIC READ POLICIES
-- ============================================
CREATE POLICY "Public read profiles" ON profiles FOR SELECT USING (true);
CREATE POLICY "Public read teams" ON teams FOR SELECT USING (true);
CREATE POLICY "Public read players" ON players FOR SELECT USING (true);
CREATE POLICY "Public read matches" ON matches FOR SELECT USING (true);
CREATE POLICY "Public read predictions" ON predictions FOR SELECT USING (true);
CREATE POLICY "Public read value_bets" ON value_bets FOR SELECT USING (true);

-- ============================================
-- USER PRIVATE POLICIES
-- ============================================
CREATE POLICY "Users can update own profile" ON profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "Users can view own bets" ON user_bets FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own bets" ON user_bets FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can view own accas" ON accas FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own accas" ON accas FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ============================================
-- PROFILE AUTOMATION
-- ============================================
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
