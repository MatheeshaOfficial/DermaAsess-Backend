ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS telegram_id bigint UNIQUE,
  ADD COLUMN IF NOT EXISTS telegram_username text,
  ADD COLUMN IF NOT EXISTS email text UNIQUE,
  ADD COLUMN IF NOT EXISTS google_id text UNIQUE,
  ADD COLUMN IF NOT EXISTS notification_channel text
    DEFAULT 'email'
    CHECK (notification_channel IN ('telegram','email','both')),
  ADD COLUMN IF NOT EXISTS login_method text
    DEFAULT 'email'
    CHECK (login_method IN ('telegram','google','both'));

CREATE INDEX IF NOT EXISTS idx_profiles_email
  ON public.profiles (email);

CREATE INDEX IF NOT EXISTS idx_profiles_telegram_id
  ON public.profiles (telegram_id);
