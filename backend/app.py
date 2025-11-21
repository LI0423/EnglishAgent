from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, speaking, scoring, report, profile, plan, reading, writing, listening, history
from .db import init_db


app = FastAPI(title="IELTS-Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(speaking.router, prefix="/speaking", tags=["speaking"])
app.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
app.include_router(report.router, prefix="/report", tags=["report"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(plan.router, prefix="/plan", tags=["plan"])  # 个性化学习计划
app.include_router(reading.router, prefix="/reading", tags=["reading"])  # 阅读模块
app.include_router(writing.router, prefix="/writing", tags=["writing"])  # 写作模块
app.include_router(listening.router, prefix="/listening", tags=["listening"])  # 听力模块
app.include_router(history.router, prefix="/history", tags=["history"])  # 学习历史记录


@app.get("/")
async def root():
    return {"message": "IELTS-Agent API is running"}


@app.on_event("startup")
async def on_startup():
    init_db()


