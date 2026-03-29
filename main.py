import os
import warnings

warnings.simplefilter("ignore", category=FutureWarning)

from dotenv import load_dotenv
load_dotenv()  # must be first — before any other imports

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import auth, profile, derma, medisafe, chat, weight


# ── Model warmup ──────────────────────────────────────────────
async def warmup_models():
    """
    Load all AI models into memory at startup.
    This prevents slow response on the first user request.
    Each model is loaded once and cached as a singleton.
    """

    # 1. Skin disease classifier
    try:
        print("[startup] Loading skin disease model...")
        from services.skin_service import load_model as load_skin
        load_skin()
        print("[startup] Skin model ready")
    except FileNotFoundError:
        print("[startup] WARNING: models/skin_model.pth not found — "
              "skin triage will fail until model file is added")
    except Exception as e:
        print(f"[startup] WARNING: Skin model failed to load: {e}")

    # 2. MediSafe prescription OCR
    try:
        print("[startup] Loading MediSafe OCR model from Hugging Face...")
        print("[startup] (First run downloads ~300 MB — please wait)")
        from services.medisafe_service import load_ocr_model
        load_ocr_model()
        print("[startup] MediSafe OCR model ready")
    except Exception as e:
        print(f"[startup] WARNING: MediSafe model failed to load: {e}")

    # 3. Food / meal classifier
    try:
        print("[startup] Loading food classifier from Hugging Face...")
        print("[startup] (First run downloads ~350 MB — please wait)")
        from services.weight_service import load_food_model
        load_food_model()
        print("[startup] Food classifier model ready")
    except Exception as e:
        print(f"[startup] WARNING: Food model failed to load: {e}")

    print("[startup] All models loaded successfully!")


# ── Lifespan ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    print("[startup] DermaAssess backend starting...")

    # Start Telegram bot
    try:
        from bot.runner import start_bot
        await start_bot()
        print("[startup] Telegram bot started")
    except Exception as e:
        print(f"[startup] WARNING: Telegram bot failed to start: {e}")

    # Load all AI models
    await warmup_models()

    print("[startup] DermaAssess backend ready!")

    yield  # server runs here

    # ── Shutdown ──────────────────────────────────────────────
    print("[shutdown] Stopping services...")
    try:
        from bot.runner import stop_bot
        await stop_bot()
        print("[shutdown] Telegram bot stopped")
    except Exception as e:
        print(f"[shutdown] Bot stop warning: {e}")

    print("[shutdown] DermaAssess backend stopped")


# ── App ───────────────────────────────────────────────────────
app = FastAPI(
    title="DermaAssess AI Health Hub",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global error handler ──────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "path":   str(request.url),
        },
    )

# ── Routers ───────────────────────────────────────────────────
app.include_router(auth.router,     prefix="/api/auth",     tags=["Auth"])
app.include_router(profile.router,  prefix="/api/profile",  tags=["Profile"])
app.include_router(derma.router,    prefix="/api/derma",    tags=["DermaAssess"])
app.include_router(medisafe.router, prefix="/api/medisafe", tags=["MediSafe"])
app.include_router(chat.router,     prefix="/api/chat",     tags=["DermaBot"])
app.include_router(weight.router,   prefix="/api/weight",   tags=["Weight"])

# ── Health endpoints ──────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {
        "status":  "ok",
        "service": "DermaAssess AI Health Hub",
    }


@app.get("/health", tags=["Health"])
def health():
    """
    Health check endpoint.
    Returns status of each AI model so you can verify
    everything loaded correctly after deploy.
    """
    model_status = {}

    # Check skin model
    try:
        from services.skin_service import _model as skin_m
        model_status["skin_model"] = "loaded" if skin_m else "not loaded"
    except Exception:
        model_status["skin_model"] = "error"

    # Check medisafe OCR model
    try:
        from services.medisafe_service import _model as medi_m
        model_status["medisafe_ocr"] = "loaded" if medi_m else "not loaded"
    except Exception:
        model_status["medisafe_ocr"] = "error"

    # Check food model
    try:
        from services.weight_service import _model as food_m
        model_status["food_classifier"] = "loaded" if food_m else "not loaded"
    except Exception:
        model_status["food_classifier"] = "error"

    return {
        "status":  "healthy",
        "version": "1.0.0",
        "models":  model_status,
    }
