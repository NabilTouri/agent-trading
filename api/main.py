from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from api.routes import trades, positions, signals, system, control

app = FastAPI(
    title="AI Trading Bot API",
    version="1.0.0",
    description="Multi-agent crypto trading bot API"
)

# CORS for Next.js dashboard (dashboard connects directly via NEXT_PUBLIC_API_URL)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(trades.router, prefix="/api/trades", tags=["Trades"])
app.include_router(positions.router, prefix="/api/positions", tags=["Positions"])
app.include_router(signals.router, prefix="/api/signals", tags=["Signals"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(control.router, prefix="/api/control", tags=["Control"])


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "AI Trading Bot API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup():
    logger.info("API server starting...")


@app.on_event("shutdown")
async def shutdown():
    logger.info("API server shutting down...")
