# main.py — clean version, no model loading
import os
from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import auth, profile, derma, medisafe, chat, weight


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────
    print("[startup] DermaAssess backend starting...")

    # Start Telegram bot only
    try:
        from bot.runner import start_bot
        await start_bot()
        print("[startup] Telegram bot started")
    except Exception as e:
        print(f"[startup] Bot warning: {e}")

    # Skin model only — small enough for Railway
    try:
        from services.skin_service import load_model
        load_model()
        print("[startup] Skin model loaded")
    except FileNotFoundError:
        print("[startup] skin_model.pth not found — add it to /models/")
    except Exception as e:
        print(f"[startup] Skin model warning: {e}")

    # MediSafe and Food use HF Inference API
    # No loading needed — they call HF servers per request
    print("[startup] MediSafe + Food AI use HF Inference API")
    print("[startup] DermaAssess ready!")

    yield

    # ── Shutdown ──────────────────────────────────────────────
    try:
        from bot.runner import stop_bot
        await stop_bot()
    except Exception:
        pass


app = FastAPI(
    title="DermaAssess AI Health Hub",
    version="1.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS", "http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "path": str(request.url)},
    )


app.include_router(auth.router,     prefix="/api/auth",     tags=["Auth"])
app.include_router(profile.router,  prefix="/api/profile",  tags=["Profile"])
app.include_router(derma.router,    prefix="/api/derma",    tags=["DermaAssess"])
app.include_router(medisafe.router, prefix="/api/medisafe", tags=["MediSafe"])
app.include_router(chat.router,     prefix="/api/chat",     tags=["DermaBot"])
app.include_router(weight.router,   prefix="/api/weight",   tags=["Weight"])


@app.get("/")
def root():
    return {"status": "ok", "service": "DermaAssess API"}


@app.get("/health")
def health():
    return {
        "status":  "healthy",
        "version": "1.0.0",
        "ai": {
            "skin_triage":   "local model (skin_model.pth)",
            "medisafe_ocr":  "HF Inference API (microsoft/trocr)",
            "food_classifier": "HF Inference API (nateraw/food)",
            "dermabot_chat": "Gemini API",
        },
    }
