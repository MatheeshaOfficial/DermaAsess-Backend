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
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
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
            
            # Create indexes
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tls_session_token ON telegram_login_sessions(session_token);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_tls_status ON telegram_login_sessions(status);"))
            
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
