from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from .routers import auth, speaking, scoring, report, profile, plan, reading, writing, listening, history, chat, diagnostic, reminder, stats, mistakes, vocabulary, gamification, community, study_group, payment, admin, campaign
from .db import init_db


app = FastAPI(title="IELTS-Agent API", version="0.1.0")


def _load_cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOW_ORIGINS", "").strip()
    if raw:
        origins = [x.strip() for x in raw.split(",") if x.strip()]
    else:
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    # allow_credentials=True 时避免 wildcard 导致浏览器拒绝
    origins = [o for o in origins if o != "*"]
    return origins or ["http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_cors_origins(),
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
app.include_router(chat.router, prefix="/chat", tags=["chat"])  # 智能体对话接口
app.include_router(diagnostic.router, prefix="/diagnostic", tags=["diagnostic"])  # 诊断测评
app.include_router(reminder.router, prefix="/reminder", tags=["reminder"])  # 提醒管理
app.include_router(stats.router)  # 学习统计
app.include_router(mistakes.router, prefix="/mistakes", tags=["mistakes"])  # 错题管理
app.include_router(vocabulary.router, prefix="/vocabulary", tags=["vocabulary"])  # 词汇学习
app.include_router(gamification.router)  # 游戏化激励系统
app.include_router(community.router, prefix="/community", tags=["community"])  # 学习社区
app.include_router(study_group.router, prefix="/study-group", tags=["study-group"])  # 学习小组
app.include_router(payment.router)  # 支付与权益
app.include_router(admin.router)  # 运营后台
app.include_router(campaign.router)  # 活动系统


@app.get("/")
async def root():
    return {"message": "IELTS-Agent API is running"}


@app.on_event("startup")
async def on_startup():
    init_db()
