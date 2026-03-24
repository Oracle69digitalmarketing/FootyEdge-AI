-- FootyEdge AI Engine - Database Schema
-- Run this in your Supabase SQL Editor

-- 1. Teams Table
CREATE TABLE IF NOT EXISTS public.teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    elo_rating INTEGER NOT NULL DEFAULT 1500,
    attack_strength FLOAT NOT NULL DEFAULT 1.0,
    defense_strength FLOAT NOT NULL DEFAULT 1.0,
    form_rating FLOAT NOT NULL DEFAULT 0.0,
    league TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Predictions Table
CREATE TABLE IF NOT EXISTS public.predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    home_prob FLOAT NOT NULL,
    draw_prob FLOAT NOT NULL,
    away_prob FLOAT NOT NULL,
    home_xg FLOAT NOT NULL,
    away_xg FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    best_bet_market TEXT,
    best_bet_selection TEXT,
    best_bet_odds FLOAT,
    best_bet_ev FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Value Bets Table
CREATE TABLE IF NOT EXISTS public.value_bets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID REFERENCES public.predictions(id) ON DELETE CASCADE,
    match TEXT NOT NULL,
    market TEXT NOT NULL,
    selection TEXT NOT NULL,
    odds FLOAT NOT NULL,
    our_probability FLOAT NOT NULL,
    ev FLOAT NOT NULL,
    kelly_percentage FLOAT NOT NULL,
    recommended_stake TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'won', 'lost'
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL DEFAULT 'user', -- 'user', 'admin'
    is_premium BOOLEAN NOT NULL DEFAULT false,
    premium_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 5. Enable RLS
ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.value_bets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- 6. Create Policies (Allow public read for demo, authenticated for write)
CREATE POLICY "Allow public read on teams" ON public.teams FOR SELECT USING (true);
CREATE POLICY "Allow public read on predictions" ON public.predictions FOR SELECT USING (true);
CREATE POLICY "Allow public read on value_bets" ON public.value_bets FOR SELECT USING (true);
CREATE POLICY "Allow public read on profiles" ON public.profiles FOR SELECT USING (true);

CREATE POLICY "Allow authenticated insert on predictions" ON public.predictions FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated insert on value_bets" ON public.value_bets FOR INSERT WITH CHECK (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated update on value_bets" ON public.value_bets FOR UPDATE USING (auth.role() = 'authenticated');
CREATE POLICY "Allow authenticated update on profiles" ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- 6. Seed Data (Optional - Initial Teams)
INSERT INTO public.teams (name, elo_rating, attack_strength, defense_strength, form_rating, league)
VALUES 
    ('Manchester City', 1950, 2.4, 0.8, 0.8, 'Premier League'),
    ('Liverpool', 1900, 2.2, 0.9, 0.7, 'Premier League'),
    ('Arsenal', 1880, 2.1, 0.7, 0.9, 'Premier League'),
    ('Real Madrid', 1920, 2.3, 1.0, 0.6, 'La Liga'),
    ('Bayern Munich', 1850, 2.5, 1.1, 0.5, 'Bundesliga'),
    ('Inter Milan', 1870, 1.9, 0.6, 0.8, 'Serie A'),
    ('Barcelona', 1820, 2.0, 1.2, 0.4, 'La Liga'),
    ('PSG', 1800, 2.4, 1.3, 0.3, 'Ligue 1')
ON CONFLICT (name) DO NOTHING;
