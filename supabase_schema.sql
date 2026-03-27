ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS telegram_id bigint UNIQUE,
  ADD COLUMN IF NOT EXISTS telegram_username text,
  ADD COLUMN IF NOT EXISTS email text UNIQUE,
  ADD COLUMN IF NOT EXISTS google_id text UNIQUE,
  ADD COLUMN IF NOT EXISTS notification_channel text
    DEFAULT 'email'
    CHECK (notification_channel IN ('telegram','email','both')),
  ADD COLUMN IF NOT EXISTS login_method text
    DEFAULT 'telegram'
    CHECK (login_method IN ('telegram','google','both'));

CREATE INDEX IF NOT EXISTS idx_profiles_email
  ON public.profiles (email);

CREATE INDEX IF NOT EXISTS idx_profiles_telegram_id
  ON public.profiles (telegram_id);

CREATE TABLE IF NOT EXISTS public.telegram_login_sessions (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    session_token text UNIQUE NOT NULL,
    telegram_id bigint,
    first_name text,
    username text,
    profile_id uuid REFERENCES public.profiles(id),
    jwt_token text,
    status text DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed')),
    created_at timestamp with time zone DEFAULT now()
);
