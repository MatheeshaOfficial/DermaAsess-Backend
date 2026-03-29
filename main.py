<<<<<<< HEAD
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config import ALLOWED_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register handlers implicitly through runner
    from bot.runner import start_bot, stop_bot
    await start_bot()
    yield
    await stop_bot()

app = FastAPI(title="DermaAssess API", lifespan=lifespan)

origins = ALLOWED_ORIGINS.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip().rstrip("/") for o in origins if o.strip()],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "path": request.url.path},
    )

from routers import auth, profile, derma, medisafe, chat, weight

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(derma.router, prefix="/api/derma", tags=["derma"])
app.include_router(medisafe.router, prefix="/api/medisafe", tags=["medisafe"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(weight.router, prefix="/api/weight", tags=["weight"])

@app.get("/")
async def root():
    return {"status": "ok", "service": "DermaAssess API"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
=======
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from config import ALLOWED_ORIGINS


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Register handlers implicitly through runner
    from bot.runner import start_bot, stop_bot
    await start_bot()
    yield
    await stop_bot()

app = FastAPI(title="DermaAssess API", lifespan=lifespan)

origins = ALLOWED_ORIGINS.split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip().rstrip("/") for o in origins if o.strip()],
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "path": request.url.path},
    )

from routers import auth, profile, derma, medisafe, chat, weight

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(derma.router, prefix="/api/derma", tags=["derma"])
app.include_router(medisafe.router, prefix="/api/medisafe", tags=["medisafe"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(weight.router, prefix="/api/weight", tags=["weight"])

@app.get("/")
async def root():
    return {"status": "ok", "service": "DermaAssess API"}

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}
>>>>>>> 3efa2a2850a1b0535bb86f92f3a35fd5c8ece0cc
