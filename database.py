import supabase
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY, DATABASE_URL

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Warning: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in environment/config")

supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# Direct PostgreSQL Setup
engine = None
SessionLocal = None

if DATABASE_URL:
    try:
        import urllib.parse
        safe_db_url = DATABASE_URL
        if safe_db_url.startswith("postgresql://") or safe_db_url.startswith("postgres://"):
            try:
                scheme, rest = safe_db_url.split("://", 1)
                if "@" in rest:
                    user_pass, host_part = rest.rsplit("@", 1)
                    if ":" in user_pass:
                        user, password = user_pass.split(":", 1)
                        encoded_password = urllib.parse.quote(urllib.parse.unquote(password))
                        safe_db_url = f"{scheme}://{user}:{encoded_password}@{host_part}"
            except Exception as parse_e:
                print(f"Warning: URL parsing failed: {parse_e}")
                
        engine = create_engine(safe_db_url, pool_pre_ping=True)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    except Exception as e:
        print(f"Error creating database engine: {e}")
else:
    print("Warning: Missing DATABASE_URL in environment/config")

def get_db():
    if not SessionLocal:
        raise Exception("Database not configured. Missing DATABASE_URL.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    if not engine:
        print("Skipping DB init: No database engine available.")
        return
        
    print("Initializing database...")
    try:
        with engine.begin() as conn:
            # Create telegram_login_sessions table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS telegram_login_sessions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_token TEXT UNIQUE NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    telegram_id BIGINT NULL,
                    telegram_username TEXT NULL,
                    telegram_name TEXT NULL,
                    profile_id UUID NULL,
                    jwt_token TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    completed_at TIMESTAMPTZ NULL,
                    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '10 minutes',
                    CONSTRAINT chk_status CHECK (status IN ('pending', 'completed', 'expired'))
                );
            """))
            
            # Profiles
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    full_name TEXT NULL,
                    email TEXT UNIQUE NULL,
                    notification_channel TEXT NULL,
                    login_method TEXT NULL,
                    age INT NULL,
                    weight_kg FLOAT NULL,
                    height_cm FLOAT NULL,
                    allergies JSONB NULL,
                    chronic_conditions JSONB NULL,
                    telegram_id BIGINT UNIQUE NULL,
                    telegram_username TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """))

            # Bot Users
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS bot_users (
                    telegram_id BIGINT PRIMARY KEY,
                    first_name TEXT NULL,
                    telegram_username TEXT NULL,
                    profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
                    onboarded BOOLEAN DEFAULT FALSE,
                    current_state TEXT DEFAULT 'idle',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """))

            # Weight Logs
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS weight_logs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
                    weight_kg FLOAT NOT NULL,
                    meal_description TEXT NULL,
                    calories_estimate FLOAT NULL,
                    protein_g FLOAT NULL,
                    carbs_g FLOAT NULL,
                    fat_g FLOAT NULL,
                    meal_image_url TEXT NULL,
                    logged_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """))

            # Skin Assessments
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS skin_assessments (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
                    image_url TEXT NULL,
                    severity_score INT NULL,
                    contagion_risk TEXT NULL,
                    recommended_action TEXT NULL,
                    diagnosis TEXT NULL,
                    possible_conditions JSONB NULL,
                    advice TEXT NULL,
                    symptoms TEXT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """))

            # Prescriptions
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS prescriptions (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
                    image_url TEXT NULL,
                    medicines_found JSONB NULL,
                    medicines_count INT NULL,
                    overall_safety TEXT NULL,
                    safety_advice TEXT NULL,
                    interactions JSONB NULL,
                    allergy_alerts JSONB NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """))

            # Chat Messages
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    session_id TEXT NOT NULL,
                    user_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """))
            
            # Create indexes
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tls_session_token ON telegram_login_sessions(session_token);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tls_status ON telegram_login_sessions(status);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);"))
            
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
