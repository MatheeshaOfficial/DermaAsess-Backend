-- ==============================================================================
-- DERMAASSESS AI HUB - COMPLETE SUPABASE SCHEMA
-- Run this entire script in your Supabase SQL Editor to create/update all tables
-- ==============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. PROFILES TABLE
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    first_name TEXT,
    last_name TEXT,
    telegram_id BIGINT UNIQUE,
    telegram_username TEXT,
    email TEXT UNIQUE,
    google_id TEXT UNIQUE,
    age INTEGER,
    height NUMERIC,
    weight NUMERIC,
    allergies TEXT,
    conditions TEXT,
    notification_channel TEXT DEFAULT 'telegram' CHECK (notification_channel IN ('telegram', 'email', 'both')),
    login_method TEXT DEFAULT 'telegram' CHECK (login_method IN ('telegram', 'google', 'both')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles (email);
CREATE INDEX IF NOT EXISTS idx_profiles_telegram_id ON public.profiles (telegram_id);

-- 2. BOT_USERS TABLE
CREATE TABLE IF NOT EXISTS public.bot_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    telegram_id BIGINT UNIQUE NOT NULL,
    first_name TEXT,
    telegram_username TEXT,
    profile_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    current_state TEXT DEFAULT 'idle',
    session_data JSONB DEFAULT '{}'::jsonb,
    onboarded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. WEIGHT_LOGS TABLE
CREATE TABLE IF NOT EXISTS public.weight_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    weight_kg NUMERIC NOT NULL,
    meal_description TEXT,
    meal_image_url TEXT,
    calories_estimate INTEGER,
    protein_g NUMERIC,
    carbs_g NUMERIC,
    fat_g NUMERIC,
    ai_advice TEXT,
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 4. SKIN_ASSESSMENTS TABLE
CREATE TABLE IF NOT EXISTS public.skin_assessments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    symptoms TEXT,
    severity_score INTEGER,
    contagion_risk TEXT,
    recommended_action TEXT,
    diagnosis TEXT,
    possible_conditions JSONB DEFAULT '[]'::jsonb,
    advice TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 5. PRESCRIPTIONS TABLE
CREATE TABLE IF NOT EXISTS public.prescriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL,
    medicines_found JSONB DEFAULT '[]'::jsonb,
    medicines_count INTEGER DEFAULT 0,
    overall_safety TEXT,
    safety_advice TEXT,
    interactions JSONB DEFAULT '[]'::jsonb,
    allergy_alerts JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 6. CHAT_MESSAGES TABLE
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id TEXT NOT NULL,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON public.chat_messages (session_id);

-- 7. TELEGRAM_LOGIN_SESSIONS TABLE
CREATE TABLE IF NOT EXISTS public.telegram_login_sessions (
    token TEXT PRIMARY KEY,
    user_id UUID REFERENCES public.profiles(id) ON DELETE CASCADE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- ==============================================================================
-- ADD ANY MISSING COLUMNS IF TABLES ALREADY EXISTED
-- ==============================================================================
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS first_name TEXT,
  ADD COLUMN IF NOT EXISTS last_name TEXT,
  ADD COLUMN IF NOT EXISTS telegram_id BIGINT UNIQUE,
  ADD COLUMN IF NOT EXISTS telegram_username TEXT,
  ADD COLUMN IF NOT EXISTS email TEXT UNIQUE,
  ADD COLUMN IF NOT EXISTS google_id TEXT UNIQUE,
  ADD COLUMN IF NOT EXISTS notification_channel TEXT DEFAULT 'telegram' CHECK (notification_channel IN ('telegram','email','both')),
  ADD COLUMN IF NOT EXISTS login_method TEXT DEFAULT 'telegram' CHECK (login_method IN ('telegram','google','both'));

-- Reload schema cache (Note: Supabase PostgREST might still need a restart via the dashboard to clear the cache)
NOTIFY pgrst, 'reload schema';
