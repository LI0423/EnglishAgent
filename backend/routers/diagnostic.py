from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple
import json
import os
import time
import uuid

from ..db import (
    create_diagnostic_session,
    complete_diagnostic_session,
    create_diagnostic_report,
    get_diagnostic_session,
    get_diagnostic_report,
    list_user_diagnostic_reports,
    save_mistake,
)
from ..deps import get_current_user


router = APIRouter()
session_runtime: Dict[str, Dict[str, Any]] = {}

DIFFICULTY_ORDER = ["basic", "intermediate", "advanced"]
DIFFICULTY_SCORE = {"basic": 1.0, "intermediate": 2.0, "advanced": 3.0}
DEFAULT_MODULES = ["listening", "reading", "writing", "speaking"]
DEFAULT_QUESTION_BANK: Dict[str, Dict[str, List[Dict[str, Any]]]] = {
    "listening": {
        "basic": [
            {"id": "lst_b_1", "question": "In the conversation, where will the student meet the tutor?", "answer": "library", "options": ["library", "cafeteria", "lab", "hall"]},
            {"id": "lst_b_2", "question": "What time does the lecture start?", "answer": "9", "options": ["8", "9", "10", "11"]},
        ],
        "intermediate": [
            {"id": "lst_i_1", "question": "Which problem does the speaker mention first?", "answer": "budget", "options": ["schedule", "budget", "staff", "venue"]},
            {"id": "lst_i_2", "question": "How many participants are expected?", "answer": "120", "options": ["80", "100", "120", "150"]},
        ],
        "advanced": [
            {"id": "lst_a_1", "question": "What is implied about the final proposal?", "answer": "needs revision", "options": ["approved", "rejected", "needs revision", "delayed"]},
            {"id": "lst_a_2", "question": "The speaker's tone can best be described as:", "answer": "cautiously optimistic", "options": ["frustrated", "neutral", "cautiously optimistic", "sarcastic"]},
        ],
    },
    "reading": {
        "basic": [
            {"id": "rd_b_1", "question": "T/F/NG: The passage says all cities reduced pollution by 2020.", "answer": "false", "options": ["true", "false", "not given"]},
            {"id": "rd_b_2", "question": "What is the main topic of paragraph 2?", "answer": "transport policy", "options": ["housing", "transport policy", "education", "tourism"]},
        ],
        "intermediate": [
            {"id": "rd_i_1", "question": "Which heading best matches paragraph 4?", "answer": "technology adoption", "options": ["economic decline", "technology adoption", "policy failure", "population ageing"]},
            {"id": "rd_i_2", "question": "The author's attitude to the study is mostly:", "answer": "supportive", "options": ["critical", "supportive", "uncertain", "dismissive"]},
        ],
        "advanced": [
            {"id": "rd_a_1", "question": "T/F/NG: The text proves causation rather than correlation.", "answer": "not given", "options": ["true", "false", "not given"]},
            {"id": "rd_a_2", "question": "Which inference is best supported by the final paragraph?", "answer": "long-term monitoring is required", "options": ["current data is sufficient", "policy is unnecessary", "long-term monitoring is required", "technology solved all issues"]},
        ],
    },
    "writing": {
        "basic": [
            {"id": "wt_b_1", "question": "Task 1: Which sentence is a valid overview?", "answer": "overall, there was an upward trend", "options": ["i think the chart is interesting", "overall, there was an upward trend", "in conclusion i like this topic", "the graph has many numbers"]},
            {"id": "wt_b_2", "question": "Choose the best connector for contrast.", "answer": "however", "options": ["therefore", "however", "for example", "meanwhile"]},
        ],
        "intermediate": [
            {"id": "wt_i_1", "question": "Task 2: Which thesis is clearer?", "answer": "while both views have merit, i largely agree that public transport should be prioritized", "options": ["this topic is very hard", "while both views have merit, i largely agree that public transport should be prioritized", "there are many opinions", "transport is important"]},
            {"id": "wt_i_2", "question": "Which paragraph order is most coherent?", "answer": "thesis -> body1 -> body2 -> conclusion", "options": ["examples -> thesis -> intro -> conclusion", "thesis -> body1 -> body2 -> conclusion", "conclusion -> body -> intro", "body2 -> body1 -> thesis -> intro"]},
        ],
        "advanced": [
            {"id": "wt_a_1", "question": "Best improvement for lexical resource:", "answer": "replace repeated common words with precise topic vocabulary", "options": ["use shorter essay", "replace repeated common words with precise topic vocabulary", "avoid any examples", "remove topic sentence"]},
            {"id": "wt_a_2", "question": "Most effective concession structure:", "answer": "although opponents argue x, this view overlooks y", "options": ["x is true and false", "although opponents argue x, this view overlooks y", "i do not know", "many people think many things"]},
        ],
    },
    "speaking": {
        "basic": [
            {"id": "sp_b_1", "question": "Part 1: Which answer is more natural?", "answer": "i usually read before bed because it helps me relax", "options": ["book good", "i usually read before bed because it helps me relax", "yes", "reading"]},
            {"id": "sp_b_2", "question": "Which phrase buys thinking time politely?", "answer": "that's an interesting question", "options": ["i don't know", "that's an interesting question", "next", "no comment"]},
        ],
        "intermediate": [
            {"id": "sp_i_1", "question": "Part 2: Best structure for a 2-minute talk:", "answer": "context -> details -> reflection", "options": ["reflection only", "context -> details -> reflection", "random ideas", "memorized list"]},
            {"id": "sp_i_2", "question": "Which response shows better coherence?", "answer": "firstly... in addition... as a result...", "options": ["firstly... in addition... as a result...", "and... and... and...", "i forgot", "none"]},
        ],
        "advanced": [
            {"id": "sp_a_1", "question": "Part 3: Which move adds analytical depth?", "answer": "compare short-term and long-term impacts", "options": ["repeat the question", "compare short-term and long-term impacts", "change topic", "answer with one word"]},
            {"id": "sp_a_2", "question": "Best way to improve grammatical range in speaking:", "answer": "mix simple, compound and complex sentences naturally", "options": ["speak very fast", "use only simple sentences", "mix simple, compound and complex sentences naturally", "memorize one template"]},
        ],
    },
}

QUESTION_BANK: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
QUESTION_INDEX: Dict[str, Dict[str, Any]] = {}
QUESTION_BANK_VERSION = "builtin-fallback"
QUESTION_BANK_SOURCE = "builtin"
QUESTION_BANK_LAST_LOADED_AT = 0
QUESTION_BANK_LOAD_ERROR = ""


def _bank_path() -> str:
    return os.environ.get(
        "DIAGNOSTIC_QUESTION_BANK_PATH",
        os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data",
            "diagnostic_question_bank.v1.json",
        ),
    )


def _rebuild_question_index(bank: Dict[str, Dict[str, List[Dict[str, Any]]]]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for module, levels in bank.items():
        for difficulty, questions in levels.items():
            for q in questions:
                qid = str(q.get("id", ""))
                if not qid:
                    continue
                index[qid] = {
                    "module": module,
                    "difficulty": difficulty,
                    "answer": q.get("answer", ""),
                    "question": q.get("question", ""),
                }
    return index


def _load_question_bank() -> None:
    global QUESTION_BANK, QUESTION_INDEX, QUESTION_BANK_VERSION
    global QUESTION_BANK_SOURCE, QUESTION_BANK_LAST_LOADED_AT, QUESTION_BANK_LOAD_ERROR
    path = _bank_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        modules = payload.get("modules")
        version = str(payload.get("version") or "unknown")
        if not isinstance(modules, dict) or not modules:
            raise ValueError("invalid bank modules")
        QUESTION_BANK = modules
        QUESTION_INDEX = _rebuild_question_index(QUESTION_BANK)
        QUESTION_BANK_VERSION = version
        QUESTION_BANK_SOURCE = "file"
        QUESTION_BANK_LOAD_ERROR = ""
        QUESTION_BANK_LAST_LOADED_AT = int(time.time())
    except Exception:
        QUESTION_BANK = DEFAULT_QUESTION_BANK
        QUESTION_INDEX = _rebuild_question_index(QUESTION_BANK)
        QUESTION_BANK_VERSION = "builtin-fallback"
        QUESTION_BANK_SOURCE = "builtin"
        QUESTION_BANK_LOAD_ERROR = f"Failed to load bank from {path}"
        QUESTION_BANK_LAST_LOADED_AT = int(time.time())


_load_question_bank()


class DiagnosticModule(BaseModel):
    name: str
    questions: int
    time_limit: int


class DiagnosticStart(BaseModel):
    modules: List[str]
    target_time: Optional[int] = None


class DiagnosticAnswer(BaseModel):
    question_id: str
    answer: Any
    time_taken: Optional[int] = None


class DiagnosticAnswers(BaseModel):
    answers: List[DiagnosticAnswer]


class ModuleScore(BaseModel):
    module: str
    score: float
    max_score: float


class Weakness(BaseModel):
    module: str
    skills: List[str]
    error_types: List[str]
    total_questions: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    accuracy_rate: float = 0.0
    difficulty_breakdown: Dict[str, Dict[str, int]] = Field(default_factory=dict)


class Recommendation(BaseModel):
    type: str
    content: str
    priority: int
    focus_difficulty: str = ""
    evidence_summary: str = ""


class DiagnosticReport(BaseModel):
    overall_band: float
    module_scores: List[ModuleScore]
    weaknesses: List[Weakness]
    recommendations: List[Recommendation]


class NextQuestion(BaseModel):
    question_id: Optional[str] = None
    question: Optional[str] = None
    options: Optional[List[str]] = None
    time_limit: Optional[int] = None
    module: Optional[str] = None
    difficulty: Optional[str] = None
    analysis_hint: Optional[str] = None


class DiagnosticSession(BaseModel):
    id: str
    user_id: str
    start_time: int
    modules: List[str]
    estimated_questions: int
    bank_version: Optional[str] = None
    next_question: Optional[NextQuestion] = None


class AnswerResponse(BaseModel):
    next_question: Optional[NextQuestion] = None
    estimated_ability: Optional[float] = None
    last_result: Optional[Dict[str, Any]] = None


class DiagnosticHistoryItem(BaseModel):
    report_id: str
    session_id: str
    overall_band: float
    generated_at: int
    module_scores: List[ModuleScore]


class DiagnosticHistorySummary(BaseModel):
    total_reports: int
    trend: str
    latest_overall_band: Optional[float] = None
    previous_overall_band: Optional[float] = None
    delta_overall_band: Optional[float] = None
    latest_module_scores: Optional[List[ModuleScore]] = None
    previous_module_scores: Optional[List[ModuleScore]] = None
    delta_module_scores: Optional[List[ModuleScore]] = None
    history: List[DiagnosticHistoryItem] = []


def _normalize_modules(raw_modules: List[str]) -> List[str]:
    if not raw_modules:
        return DEFAULT_MODULES
    normalized = []
    for m in raw_modules:
        key = (m or "").strip().lower()
        if key in QUESTION_BANK and key not in normalized:
            normalized.append(key)
    return normalized or DEFAULT_MODULES


def _normalize_text(v: Any) -> str:
    return str(v or "").strip().lower()


def _is_correct_by_key(answer: DiagnosticAnswer) -> Tuple[bool, str, str]:
    q_meta = QUESTION_INDEX.get(answer.question_id)
    if not q_meta:
        # 兼容历史调用：无法定位题目时走旧逻辑
        value = answer.answer
        if isinstance(value, bool):
            return value, "general", "intermediate"
        if isinstance(value, dict) and "is_correct" in value:
            return bool(value["is_correct"]), "general", "intermediate"
        if isinstance(value, str):
            lowered = value.strip().lower()
            return lowered in {"true", "correct", "1", "yes", "y"}, "general", "intermediate"
        if isinstance(value, (int, float)):
            return value > 0, "general", "intermediate"
        return False, "general", "intermediate"

    expected = _normalize_text(q_meta["answer"])
    actual = _normalize_text(answer.answer)
    return actual == expected, str(q_meta["module"]), str(q_meta["difficulty"])


def _default_error_tags(module: str, difficulty: str) -> List[str]:
    tags = {
        "listening": ["detail_miss", "distractor_confusion"],
        "reading": ["inference_error", "keyword_mismatch"],
        "writing": ["logic_coherence", "lexical_precision"],
        "speaking": ["fluency_coherence", "response_depth"],
    }.get(module, ["accuracy_issue"])
    if difficulty == "advanced":
        return tags + ["high_level_reasoning"]
    return tags


def _question_explanation(question_id: str, module: str) -> str:
    return f"{module} 题目 {question_id}：建议先定位关键信息，再排除干扰项。"


def _question_hint(module: str, difficulty: str) -> str:
    hints = {
        "listening": "先读选项，听时抓转折和数字信息。",
        "reading": "先定位关键词，再看上下文语义。",
        "writing": "优先保证论点清晰和段落衔接。",
        "speaking": "先给直接答案，再补充原因和例子。",
    }
    prefix = hints.get(module, "先抓主干信息。")
    if difficulty == "advanced":
        return prefix + " 当前为高阶题，注意推断与反证。"
    if difficulty == "basic":
        return prefix + " 当前为基础题，先保证准确率。"
    return prefix + " 当前为进阶题，注意准确和速度平衡。"


def _difficulty_to_time_limit(level: str) -> int:
    if level == "basic":
        return 75
    if level == "advanced":
        return 120
    return 90


def _pick_question(runtime: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    modules = runtime.get("modules", [])
    if not modules:
        return None

    asked = set(runtime.get("asked_questions", []))
    module_cursor = int(runtime.get("module_cursor", 0))
    module = modules[module_cursor % len(modules)]
    difficulty_idx_map = runtime.get("difficulty_idx", {})
    module_order = [module] + [m for m in modules if m != module]

    for m in module_order:
        # 每个模块都按自己的当前难度 [当前, 向上, 向下] 选题
        module_idx = int(difficulty_idx_map.get(m, 1))
        candidate_order = [module_idx, min(module_idx + 1, 2), max(module_idx - 1, 0)]
        for idx in candidate_order:
            level = DIFFICULTY_ORDER[idx]
            questions = QUESTION_BANK.get(m, {}).get(level, [])
            for q in questions:
                if q["id"] in asked:
                    continue
                runtime["module_cursor"] = (modules.index(m) + 1) % len(modules)
                return {
                    "question_id": q["id"],
                    "question": q["question"],
                    "options": q.get("options"),
                    "time_limit": _difficulty_to_time_limit(level),
                    "module": m,
                    "difficulty": level,
                    "analysis_hint": _question_hint(m, level),
                }
    return None


def _update_difficulty(runtime: Dict[str, Any], module: str, difficulty: str, is_correct: bool) -> None:
    if module not in QUESTION_BANK:
        return
    current = int(runtime["difficulty_idx"].get(module, 1))
    if difficulty in DIFFICULTY_ORDER:
        current = DIFFICULTY_ORDER.index(difficulty)
    if is_correct:
        runtime["difficulty_idx"][module] = min(current + 1, 2)
    else:
        runtime["difficulty_idx"][module] = max(current - 1, 0)


def _estimate_ability(answers: List[Dict[str, Any]]) -> float:
    if not answers:
        return 4.5
    total_weight = 0.0
    gained = 0.0
    for item in answers:
        level = str(item.get("difficulty") or "intermediate")
        w = float(DIFFICULTY_SCORE.get(level, 2.0))
        total_weight += w
        if item.get("is_correct"):
            gained += w
    ratio = (gained / total_weight) if total_weight > 0 else 0.0
    return round(4.5 + ratio * 3.5, 1)


def _build_report_from_answers(modules: List[str], answers: List[Dict[str, Any]]) -> Dict[str, Any]:
    module_stats: Dict[str, Dict[str, float]] = {}
    for module in modules:
        module_stats[module] = {
            "weight": 0.0,
            "gain": 0.0,
            "total": 0.0,
            "correct": 0.0,
            "basic_total": 0.0,
            "basic_correct": 0.0,
            "intermediate_total": 0.0,
            "intermediate_correct": 0.0,
            "advanced_total": 0.0,
            "advanced_correct": 0.0,
        }

    for item in answers:
        module = item.get("module", "general")
        if module not in module_stats:
            module_stats[module] = {
                "weight": 0.0,
                "gain": 0.0,
                "total": 0.0,
                "correct": 0.0,
                "basic_total": 0.0,
                "basic_correct": 0.0,
                "intermediate_total": 0.0,
                "intermediate_correct": 0.0,
                "advanced_total": 0.0,
                "advanced_correct": 0.0,
            }
        level = str(item.get("difficulty") or "intermediate")
        w = float(DIFFICULTY_SCORE.get(level, 2.0))
        module_stats[module]["weight"] += w
        module_stats[module]["total"] += 1
        level_key = level if level in {"basic", "intermediate", "advanced"} else "intermediate"
        module_stats[module][f"{level_key}_total"] += 1
        if item.get("is_correct"):
            module_stats[module]["gain"] += w
            module_stats[module]["correct"] += 1
            module_stats[module][f"{level_key}_correct"] += 1

    module_scores = []
    weaknesses = []
    recommendations = []
    band_scores = []

    for module, stat in module_stats.items():
        ratio = (stat["gain"] / stat["weight"]) if stat["weight"] > 0 else 0.0
        band = round(4.5 + ratio * 3.5, 1)
        band_scores.append(band)
        module_scores.append({"module": module, "score": band, "max_score": 9.0})
        total_questions = int(stat["total"] or 0)
        correct_count = int(stat["correct"] or 0)
        wrong_count = max(total_questions - correct_count, 0)
        accuracy_rate = round((correct_count / total_questions * 100.0), 2) if total_questions > 0 else 0.0
        difficulty_breakdown = {
            "basic": {
                "total": int(stat["basic_total"] or 0),
                "correct": int(stat["basic_correct"] or 0),
            },
            "intermediate": {
                "total": int(stat["intermediate_total"] or 0),
                "correct": int(stat["intermediate_correct"] or 0),
            },
            "advanced": {
                "total": int(stat["advanced_total"] or 0),
                "correct": int(stat["advanced_correct"] or 0),
            },
        }

        if ratio < 0.6:
            focus_difficulty = "basic" if ratio < 0.4 else "intermediate"
            weaknesses.append(
                {
                    "module": module,
                    "skills": ["accuracy", "time_management", "question_strategy"],
                    "error_types": ["concept_gaps", "careless_mistakes"],
                    "total_questions": total_questions,
                    "correct_count": correct_count,
                    "wrong_count": wrong_count,
                    "accuracy_rate": accuracy_rate,
                    "difficulty_breakdown": difficulty_breakdown,
                }
            )
            recommendations.append(
                {
                    "type": module,
                    "content": f"Prioritize {module} drills at {focus_difficulty} level and reattempt missed items.",
                    "priority": 1,
                    "focus_difficulty": focus_difficulty,
                    "evidence_summary": f"{module}: correct {correct_count}/{total_questions}, accuracy {accuracy_rate}%",
                }
            )
        else:
            recommendations.append(
                {
                    "type": module,
                    "content": f"Maintain {module} with mixed timed sets and add advanced questions.",
                    "priority": 2,
                    "focus_difficulty": "advanced",
                    "evidence_summary": f"{module}: correct {correct_count}/{total_questions}, accuracy {accuracy_rate}%",
                }
            )

    overall_band = round(sum(band_scores) / len(band_scores), 1) if band_scores else 5.0
    return {
        "overall_band": overall_band,
        "module_scores": module_scores,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
    }


def _require_session_owner(session_id: str, user_id: str) -> Dict[str, Any]:
    session = get_diagnostic_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Diagnostic session not found")
    if str(session.get("user_id")) != str(user_id):
        raise HTTPException(status_code=403, detail="No permission for this diagnostic session")
    return session


@router.post("/start", response_model=DiagnosticSession)
async def start_diagnostic(
    diagnostic_data: DiagnosticStart,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    modules = _normalize_modules(diagnostic_data.modules)
    session_id = str(uuid.uuid4())
    create_diagnostic_session(session_id, user_id, modules)

    # 总题量按模块数估算，且限制在 [8, 24]
    estimated_questions = min(max(len(modules) * 2, 8), 24)
    runtime = {
        "modules": modules,
        "answers": [],
        "asked_questions": [],
        "module_cursor": 0,
        "difficulty_idx": {m: 1 for m in modules},  # 默认 intermediate
        "started_at": int(time.time()),
        "estimated_questions": estimated_questions,
    }
    session_runtime[session_id] = runtime

    first_question = _pick_question(runtime)
    if first_question:
        runtime["asked_questions"].append(first_question["question_id"])
        runtime["pending_question"] = first_question["question_id"]

    return DiagnosticSession(
        id=session_id,
        user_id=user_id,
        start_time=int(time.time()),
        modules=modules,
        estimated_questions=estimated_questions,
        bank_version=QUESTION_BANK_VERSION,
        next_question=NextQuestion(**first_question) if first_question else None,
    )


@router.get("/bank/version")
async def get_diagnostic_bank_version(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    module_stats = {}
    for module, levels in QUESTION_BANK.items():
        module_stats[module] = {
            "basic": len(levels.get("basic", [])),
            "intermediate": len(levels.get("intermediate", [])),
            "advanced": len(levels.get("advanced", [])),
        }
    return {
        "version": QUESTION_BANK_VERSION,
        "source": QUESTION_BANK_SOURCE,
        "path": _bank_path(),
        "modules": module_stats,
    }


@router.get("/bank/health")
async def get_diagnostic_bank_health(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    module_stats = {}
    total_questions = 0
    for module, levels in QUESTION_BANK.items():
        basic = len(levels.get("basic", []))
        intermediate = len(levels.get("intermediate", []))
        advanced = len(levels.get("advanced", []))
        module_total = basic + intermediate + advanced
        total_questions += module_total
        module_stats[module] = {
            "basic": basic,
            "intermediate": intermediate,
            "advanced": advanced,
            "total": module_total,
        }
    module_totals = [v.get("total", 0) for v in module_stats.values()]
    min_module_total = min(module_totals) if module_totals else 0
    if total_questions >= 160 and min_module_total >= 35:
        coverage_status = "strong"
    elif total_questions >= 80 and min_module_total >= 15:
        coverage_status = "standard"
    else:
        coverage_status = "starter"

    return {
        "version": QUESTION_BANK_VERSION,
        "source": QUESTION_BANK_SOURCE,
        "path": _bank_path(),
        "total_questions": total_questions,
        "module_count": len(module_stats),
        "modules": module_stats,
        "coverage_status": coverage_status,
        "recommended_total_questions": 160,
        "recommended_min_questions_per_module": 35,
        "has_fallback": QUESTION_BANK_VERSION == "builtin-fallback",
        "load_error": QUESTION_BANK_LOAD_ERROR,
        "last_loaded_at": QUESTION_BANK_LAST_LOADED_AT,
    }


@router.post("/bank/reload")
async def reload_diagnostic_bank(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")
    _load_question_bank()
    return await get_diagnostic_bank_health(current_user=current_user)


@router.get("/history/summary", response_model=DiagnosticHistorySummary)
async def get_diagnostic_history_summary(
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    rows = list_user_diagnostic_reports(str(user_id), limit=max(1, min(limit, 50)))
    history_items: List[DiagnosticHistoryItem] = []
    for r in rows:
        module_scores = [ModuleScore(**m) for m in (r.get("module_scores") or [])]
        history_items.append(
            DiagnosticHistoryItem(
                report_id=str(r.get("id")),
                session_id=str(r.get("session_id")),
                overall_band=float(r.get("overall_band") or 0.0),
                generated_at=int(r.get("generated_at") or 0),
                module_scores=module_scores,
            )
        )

    latest = history_items[0] if history_items else None
    previous = history_items[1] if len(history_items) > 1 else None
    delta_overall = None
    trend = "insufficient_data"
    delta_module_scores: List[ModuleScore] = []
    if latest and previous:
        delta_overall = round(latest.overall_band - previous.overall_band, 2)
        if delta_overall > 0:
            trend = "up"
        elif delta_overall < 0:
            trend = "down"
        else:
            trend = "flat"

        prev_map = {m.module: m.score for m in previous.module_scores}
        all_modules = {m.module for m in latest.module_scores} | set(prev_map.keys())
        for m in sorted(all_modules):
            new_score = next((x.score for x in latest.module_scores if x.module == m), 0.0)
            old_score = float(prev_map.get(m, 0.0))
            delta_module_scores.append(ModuleScore(module=m, score=round(new_score - old_score, 2), max_score=9.0))

    return DiagnosticHistorySummary(
        total_reports=len(history_items),
        trend=trend,
        latest_overall_band=(latest.overall_band if latest else None),
        previous_overall_band=(previous.overall_band if previous else None),
        delta_overall_band=delta_overall,
        latest_module_scores=(latest.module_scores if latest else None),
        previous_module_scores=(previous.module_scores if previous else None),
        delta_module_scores=(delta_module_scores or None),
        history=history_items,
    )


@router.post("/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    session_id: str,
    answer_data: DiagnosticAnswers,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    _require_session_owner(session_id, str(user_id))
    runtime = session_runtime.get(session_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Diagnostic session not found")

    # 允许空提交：用于拉取下一题
    if answer_data.answers:
        if len(answer_data.answers) > 1:
            raise HTTPException(status_code=400, detail="Only one answer is allowed per request")

        pending_qid = str(runtime.get("pending_question") or "")
        answered_ids = {str(item.get("question_id")) for item in runtime.get("answers", [])}
        last_result = None
        for ans in answer_data.answers:
            if pending_qid and str(ans.question_id) != pending_qid:
                raise HTTPException(status_code=400, detail="Submitted question is not the current pending question")
            if str(ans.question_id) in answered_ids:
                raise HTTPException(status_code=400, detail="Question already answered in this session")
            is_correct, module, difficulty = _is_correct_by_key(ans)
            q_meta = QUESTION_INDEX.get(ans.question_id, {})
            expected_answer = str(q_meta.get("answer") or "")
            runtime["answers"].append(
                {
                    "question_id": ans.question_id,
                    "is_correct": is_correct,
                    "module": module,
                    "difficulty": difficulty,
                    "time_taken": ans.time_taken or 0,
                }
            )
            _update_difficulty(runtime, module, difficulty, is_correct)
            runtime["pending_question"] = None
            last_result = {
                "question_id": ans.question_id,
                "module": module,
                "difficulty": difficulty,
                "is_correct": is_correct,
                "expected_answer": expected_answer,
                "user_answer": str(ans.answer),
                "explanation": _question_explanation(ans.question_id, module),
                "error_tags": [] if is_correct else _default_error_tags(module, difficulty),
            }
            if not is_correct:
                save_mistake(
                    str(uuid.uuid4()),
                    str(user_id),
                    {
                        "module": module,
                        "question_id": str(ans.question_id),
                        "question_type": "diagnostic",
                        "error_type": ((last_result.get("error_tags") or ["general"])[0] if last_result else "general"),
                        "content": str(q_meta.get("question") or ""),
                        "user_answer": str(ans.answer),
                        "correct_answer": expected_answer,
                        "explanation": last_result.get("explanation") if last_result else "",
                        "difficulty": difficulty,
                        "tags": last_result.get("error_tags") if last_result else [],
                    },
                )
        runtime["last_result"] = last_result

    estimated_ability = _estimate_ability(runtime["answers"])

    # 达到题量上限则不再出题
    next_question = None
    if len(runtime["answers"]) < int(runtime.get("estimated_questions", 8)):
        next_question = _pick_question(runtime)
        if next_question:
            runtime["asked_questions"].append(next_question["question_id"])
            runtime["pending_question"] = next_question["question_id"]
        else:
            runtime["pending_question"] = None

    return AnswerResponse(
        next_question=NextQuestion(**next_question) if next_question else None,
        estimated_ability=estimated_ability,
        last_result=runtime.get("last_result"),
    )


@router.get("/{session_id}/report", response_model=DiagnosticReport)
async def get_report(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    _require_session_owner(session_id, str(user_id))
    report = get_diagnostic_report(session_id)
    if report:
        module_scores = []
        for item in report.get("module_scores") or []:
            module_scores.append(
                ModuleScore(
                    module=item["module"],
                    score=item["score"],
                    max_score=item.get("max_score", 9.0),
                )
            )
        weaknesses = []
        for item in report.get("weaknesses") or []:
            weaknesses.append(
                Weakness(
                    module=item["module"],
                    skills=item["skills"],
                    error_types=item["error_types"],
                    total_questions=int(item.get("total_questions") or 0),
                    correct_count=int(item.get("correct_count") or 0),
                    wrong_count=int(item.get("wrong_count") or 0),
                    accuracy_rate=float(item.get("accuracy_rate") or 0.0),
                    difficulty_breakdown=dict(item.get("difficulty_breakdown") or {}),
                )
            )
        recommendations = []
        for item in report.get("recommendations") or []:
            recommendations.append(
                Recommendation(
                    type=item["type"],
                    content=item["content"],
                    priority=item.get("priority", 1),
                    focus_difficulty=str(item.get("focus_difficulty") or ""),
                    evidence_summary=str(item.get("evidence_summary") or ""),
                )
            )
        return DiagnosticReport(
            overall_band=report["overall_band"],
            module_scores=module_scores,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )

    runtime = session_runtime.get(session_id)
    if runtime:
        computed = _build_report_from_answers(runtime.get("modules", []), runtime.get("answers", []))
        return DiagnosticReport(
            overall_band=computed["overall_band"],
            module_scores=[ModuleScore(**s) for s in computed["module_scores"]],
            weaknesses=[Weakness(**w) for w in computed["weaknesses"]],
            recommendations=[Recommendation(**r) for r in computed["recommendations"]],
        )

    return DiagnosticReport(
        overall_band=5.0,
        module_scores=[ModuleScore(module=m, score=5.0, max_score=9.0) for m in DEFAULT_MODULES],
        weaknesses=[
            Weakness(
                module="general",
                skills=["diagnostic_incomplete"],
                error_types=["insufficient_data"],
            )
        ],
        recommendations=[
            Recommendation(
                type="general",
                content="Complete at least one full diagnostic session to generate personalized recommendations.",
                priority=1,
            )
        ],
    )


@router.post("/{session_id}/complete")
async def complete_diagnostic(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="User ID not found")

    _require_session_owner(session_id, str(user_id))
    runtime = session_runtime.get(session_id, {"modules": [], "answers": []})
    answers = runtime.get("answers", [])
    report_data = _build_report_from_answers(runtime.get("modules", []), answers)

    end_time = int(time.time())
    complete_diagnostic_session(
        session_id=session_id,
        end_time=end_time,
        total_questions=max(1, int(runtime.get("estimated_questions", len(answers) or 1))),
        completed_questions=len(answers),
        estimated_band=report_data["overall_band"],
    )

    report_id = str(uuid.uuid4())
    create_diagnostic_report(report_id, session_id, report_data)

    return {
        "message": "Diagnostic completed successfully",
        "report_id": report_id,
        "estimated_band": report_data["overall_band"],
    }
