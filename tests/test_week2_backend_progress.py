import asyncio
import time
import uuid
import sys
import types

import pytest
from starlette.responses import Response

if "jose" not in sys.modules:
    jose_stub = types.ModuleType("jose")

    class _JWTError(Exception):
        pass

    class _JWT:
        @staticmethod
        def encode(payload, key, algorithm=None):
            return "stub-token"

        @staticmethod
        def decode(token, key, algorithms=None):
            return {"sub": "u1"}

    jose_stub.JWTError = _JWTError
    jose_stub.jwt = _JWT
    sys.modules["jose"] = jose_stub

if "bcrypt" not in sys.modules:
    bcrypt_stub = types.ModuleType("bcrypt")
    bcrypt_stub.gensalt = lambda: b"salt"
    bcrypt_stub.hashpw = lambda password, salt: b"hashed"
    bcrypt_stub.checkpw = lambda password, hashed: True
    sys.modules["bcrypt"] = bcrypt_stub

if "celery" not in sys.modules:
    celery_stub = types.ModuleType("celery")

    class _Celery:
        def __init__(self, *args, **kwargs):
            self.conf = types.SimpleNamespace(update=lambda **k: None)

        def task(self, fn=None, *args, **kwargs):
            if fn is not None and callable(fn):
                return fn

            def _decorator(f):
                return f

            return _decorator

    celery_stub.Celery = _Celery
    sys.modules["celery"] = celery_stub

if "dotenv" not in sys.modules:
    dotenv_stub = types.ModuleType("dotenv")
    dotenv_stub.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_stub

if "agent_core" not in sys.modules:
    agent_core_stub = types.ModuleType("agent_core")
    agent_core_stub.speaking_agent = types.SimpleNamespace(
        evaluate_speaking=lambda text, audio_url=None: {
            "scores": {"FC": 6.5, "LR": 6.5, "GR": 6.5, "PR": 6.5},
            "overall": 6.5,
            "rationales": ["stub"],
            "actionItems": [],
            "highlights": [],
        }
    )
    sys.modules["agent_core"] = agent_core_stub

from backend import db as db_module
from backend.routers import auth as auth_router
from backend.routers import diagnostic as diagnostic_router
from backend.routers import listening as listening_router
from backend.routers import mistakes as mistakes_router
from backend.routers import plan as plan_router
from backend.routers import report as report_router
from backend.routers import reading as reading_router
from backend.routers import history as history_router
from backend.routers import scoring as scoring_router
from backend.routers import speaking as speaking_router
from backend.routers import vocabulary as vocabulary_router
from backend.routers import writing as writing_router
from backend.routers import gamification as gamification_router
from backend.services import reminder_service
from backend.tasks import reminder_tasks
from backend.tasks import intelligent_reminder_tasks
from backend.tasks.review_tasks import schedule_due_review_reminders


@pytest.fixture()
def isolated_db(tmp_path):
    test_db = tmp_path / "week2_test.db"
    db_module.DB_PATH = str(test_db)
    db_module.init_db()
    diagnostic_router.session_runtime.clear()

    _ensure_user("u1", "u1")
    _ensure_user("u2", "u2")
    return str(test_db)


def _ensure_user(user_id: str, username: str):
    conn = db_module.get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, "test-hash", 0),
        )
        conn.commit()
    finally:
        conn.close()


def test_auth_password_reset_flow(isolated_db, monkeypatch):
    monkeypatch.setattr(auth_router, "EXPOSE_RESET_TOKEN", True)
    req = asyncio.run(
        auth_router.request_password_reset(
            auth_router.PasswordResetRequest(account="u1"),
        )
    )
    assert req.success is True
    assert req.reset_token

    done = asyncio.run(
        auth_router.confirm_password_reset(
            auth_router.PasswordResetConfirm(
                reset_token=req.reset_token,
                new_password="newpass123",
            )
        )
    )
    assert done.success is True

    with pytest.raises(Exception) as e:
        asyncio.run(
            auth_router.confirm_password_reset(
                auth_router.PasswordResetConfirm(
                    reset_token=req.reset_token,
                    new_password="newpass123",
                )
            )
        )
    status = getattr(e.value, "status_code", None)
    assert status == 400


def test_auth_password_reset_rate_limit(isolated_db, monkeypatch):
    monkeypatch.setattr(auth_router, "PASSWORD_RESET_RATE_LIMIT", 2)
    monkeypatch.setattr(auth_router, "PASSWORD_RESET_RATE_WINDOW_SECONDS", 3600)
    for _ in range(3):
        resp = asyncio.run(
            auth_router.request_password_reset(
                auth_router.PasswordResetRequest(account="u1"),
            )
        )
    assert resp.success is True
    assert "频繁" in resp.message
    assert resp.reset_token is None


def test_auth_password_reset_code_flow(isolated_db, monkeypatch):
    monkeypatch.setattr(auth_router, "EXPOSE_RESET_CODE", True)
    conn = db_module.get_conn()
    try:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", ("u1@example.com", "u1"))
        conn.commit()
    finally:
        conn.close()

    requested = asyncio.run(
        auth_router.request_password_reset_code(
            auth_router.PasswordResetCodeRequest(account="u1", channel="email")
        )
    )
    assert requested.success is True
    assert requested.verification_code

    done = asyncio.run(
        auth_router.confirm_password_reset_by_code(
            auth_router.PasswordResetCodeConfirm(
                account="u1",
                code=requested.verification_code,
                new_password="newpass123",
            )
        )
    )
    assert done.success is True

    with pytest.raises(Exception) as e:
        asyncio.run(
            auth_router.confirm_password_reset_by_code(
                auth_router.PasswordResetCodeConfirm(
                    account="u1",
                    code=requested.verification_code,
                    new_password="newpass123",
                )
            )
        )
    status = getattr(e.value, "status_code", None)
    assert status == 400


def test_listening_library_version_endpoint(isolated_db):
    listening_router.player_states.clear()
    listening_router._load_audio_library()
    info = asyncio.run(
        listening_router.get_audio_library_version(
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert info.count >= 1
    assert isinstance(info.version, str)
    assert info.source in {"file", "builtin"}


def test_listening_library_fallback_when_file_missing(isolated_db, monkeypatch):
    monkeypatch.setenv("LISTENING_AUDIO_LIBRARY_PATH", "/tmp/non-existent-listening-library.json")
    listening_router._load_audio_library()
    assert listening_router.AUDIO_LIBRARY_VERSION == "builtin-fallback"
    assert "audio_001" in listening_router.AUDIO_LIBRARY
    monkeypatch.delenv("LISTENING_AUDIO_LIBRARY_PATH", raising=False)
    listening_router._load_audio_library()


def test_listening_quiz_generate_submit_and_mistake_sink(isolated_db):
    listening_router.AUDIO_QUIZ_RUNTIME.clear()
    listening_router._load_listening_question_bank()

    quiz = asyncio.run(
        listening_router.generate_listening_quiz(
            listening_router.ListeningQuizGenerateRequest(count=2, difficulty="easy"),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert quiz.quiz_id
    assert len(quiz.questions) >= 1

    wrong_answers = [
        listening_router.ListeningQuizAnswer(question_id=q.id, answer="wrong-answer")
        for q in quiz.questions
    ]
    result = asyncio.run(
        listening_router.submit_listening_quiz(
            listening_router.ListeningQuizSubmitRequest(
                quiz_id=quiz.quiz_id,
                answers=wrong_answers,
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert result.total == len(quiz.questions)
    assert result.correct == 0

    mistakes = db_module.get_user_mistakes("u1", module="listening", limit=20, question_type="listening_quiz")
    assert len(mistakes) >= len(quiz.questions)
    allowed_listening_error_types = {
        "listening_option_misjudge",
        "listening_spelling_or_form_error",
        "listening_keyword_capture_miss",
        "listening_location_mapping_error",
        "listening_matching_mismatch",
        "listening_content_miss",
    }
    assert all((m.get("error_type") in allowed_listening_error_types) for m in mistakes[: len(quiz.questions)])
    assert all("taxonomy:v1" in (m.get("tags") or []) for m in mistakes[: len(quiz.questions)])


def test_listening_question_bank_fallback_when_file_missing(isolated_db, monkeypatch):
    monkeypatch.setenv("LISTENING_QUESTION_BANK_PATH", "/tmp/non-existent-listening-questions.json")
    listening_router._load_listening_question_bank()
    assert listening_router.LISTENING_QUESTION_BANK_VERSION == "builtin-fallback"
    assert len(listening_router.LISTENING_QUESTION_BANK) >= 1
    monkeypatch.delenv("LISTENING_QUESTION_BANK_PATH", raising=False)
    listening_router._load_listening_question_bank()


def test_reading_quiz_generate_submit_and_mistake_sink(isolated_db):
    reading_router.READING_QUIZ_RUNTIME.clear()
    reading_router._load_reading_question_bank()

    quiz = asyncio.run(
        reading_router.generate_reading_quiz(
            reading_router.ReadingQuizGenerateRequest(count=2, difficulty="intermediate"),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert quiz.quiz_id
    assert len(quiz.questions) >= 1

    wrong_answers = [
        reading_router.ReadingQuizAnswer(question_id=q.id, answer="wrong-answer")
        for q in quiz.questions
    ]
    result = asyncio.run(
        reading_router.submit_reading_quiz(
            reading_router.ReadingQuizSubmitRequest(
                quiz_id=quiz.quiz_id,
                answers=wrong_answers,
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert result.total == len(quiz.questions)
    assert result.correct == 0

    mistakes = db_module.get_user_mistakes("u1", module="reading", limit=20, question_type="reading_quiz")
    assert len(mistakes) >= len(quiz.questions)
    allowed_reading_error_types = {
        "reading_tfng_misjudge",
        "reading_heading_mismatch",
        "reading_attitude_misjudge",
        "reading_inference_error",
        "reading_matching_mismatch",
        "reading_summary_fill_error",
        "reading_content_miss",
    }
    assert all((m.get("error_type") in allowed_reading_error_types) for m in mistakes[: len(quiz.questions)])
    assert all("taxonomy:v1" in (m.get("tags") or []) for m in mistakes[: len(quiz.questions)])


def test_reading_question_bank_fallback_when_file_missing(isolated_db, monkeypatch):
    monkeypatch.setenv("READING_QUESTION_BANK_PATH", "/tmp/non-existent-reading-questions.json")
    reading_router._load_reading_question_bank()
    assert reading_router.READING_QUESTION_BANK_VERSION == "builtin-fallback"
    assert len(reading_router.READING_QUESTION_BANK) >= 1
    monkeypatch.delenv("READING_QUESTION_BANK_PATH", raising=False)
    reading_router._load_reading_question_bank()


def test_speaking_session_user_isolation(isolated_db):
    created_u1 = asyncio.run(
        speaking_router.create_session(current_user={"id": "u1", "username": "u1"})
    )
    created_u2 = asyncio.run(
        speaking_router.create_session(current_user={"id": "u2", "username": "u2"})
    )
    assert created_u1.sessionId != created_u2.sessionId

    list_u1 = asyncio.run(
        speaking_router.list_sessions(limit=20, offset=0, current_user={"id": "u1", "username": "u1"})
    )
    ids_u1 = {x.id for x in list_u1}
    assert created_u1.sessionId in ids_u1
    assert created_u2.sessionId not in ids_u1

    with pytest.raises(Exception) as e:
        asyncio.run(
            speaking_router.get_session_detail(
                created_u1.sessionId,
                current_user={"id": "u2", "username": "u2"},
            )
        )
    status = getattr(e.value, "status_code", None)
    assert status == 404


def test_speaking_turn_and_summary_flow(isolated_db):
    created = asyncio.run(
        speaking_router.create_session(current_user={"id": "u1", "username": "u1"})
    )
    sid = created.sessionId

    started = asyncio.run(
        speaking_router.start_part(
            sid,
            1,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert started.ok is True
    assert started.partIndex == 1

    turn = asyncio.run(
        speaking_router.submit_turn(
            sid,
            speaking_router.SpeakingTurnRequest(
                userText="I study computer science because I enjoy solving real problems in teams.",
                mode="coach",
                partIndex=1,
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert turn.ok is True
    assert turn.partIndex == 1
    assert turn.turnIndex >= 1
    assert turn.followUpQuestion
    assert isinstance(turn.feedback, dict)
    assert "content" in turn.feedback

    summary = asyncio.run(
        speaking_router.summarize_session(
            sid,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert summary.sessionId == sid
    assert summary.transcriptWordCount >= 1
    assert len(summary.highlights) >= 1
    assert len(summary.drills) >= 1


def test_history_sessions_user_isolation(isolated_db):
    db_module.create_session(
        "s_u1_hist",
        "General",
        [{"index": 1, "type": "part1", "prompt": "x"}],
        user_id="u1",
    )
    db_module.create_session(
        "s_u2_hist",
        "General",
        [{"index": 1, "type": "part1", "prompt": "x"}],
        user_id="u2",
    )
    rows = history_router.get_recent_sessions(limit=20, current_user={"id": "u1", "username": "u1"})
    ids = {r.id for r in rows}
    assert "s_u1_hist" in ids
    assert "s_u2_hist" not in ids


def test_scoring_transcript_user_isolation_and_mistake_sink(isolated_db, monkeypatch):
    created = asyncio.run(
        speaking_router.create_session(current_user={"id": "u1", "username": "u1"})
    )
    sid = created.sessionId
    asyncio.run(
        speaking_router.ingest_audio(
            sid,
            speaking_router.AudioChunk(textPartial="I like reading books and discuss ideas."),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    finished = asyncio.run(
        speaking_router.finish_session(sid, current_user={"id": "u1", "username": "u1"})
    )
    tid = finished.transcriptId

    monkeypatch.setattr(
        scoring_router.speaking_agent,
        "evaluate_speaking",
        lambda text, audio_url=None: {
            "scores": {"FC": 6.0, "LR": 6.0, "GR": 6.5, "PR": 6.0},
            "overall": 6.1,
            "rationales": ["ok"],
            "actionItems": [{"type": "improve", "before": "x", "after": "y", "examples": []}],
            "highlights": [{"start": 0.0, "end": 1.0, "note": "test"}],
        },
    )

    result = asyncio.run(
        scoring_router.score_speaking(
            scoring_router.ScoringRequest(transcriptId=tid),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert result.overall > 0

    speaking_mistakes = db_module.get_user_mistakes(
        "u1", module="speaking", limit=20, question_type="speaking_assessment"
    )
    assert len(speaking_mistakes) >= 1
    allowed_speaking_error_types = {
        "speaking_fluency_coherence_low",
        "speaking_lexical_resource_low",
        "speaking_grammar_range_accuracy_low",
        "speaking_pronunciation_low",
        "speaking_general_low_band",
    }
    assert all((m.get("error_type") in allowed_speaking_error_types) for m in speaking_mistakes)
    assert all("taxonomy:v1" in (m.get("tags") or []) for m in speaking_mistakes)

    with pytest.raises(Exception) as e:
        asyncio.run(
            scoring_router.score_speaking(
                scoring_router.ScoringRequest(transcriptId=tid),
                current_user={"id": "u2", "username": "u2"},
            )
        )
    status = getattr(e.value, "status_code", None)
    assert status == 404


def test_writing_analysis_sinks_medium_high_feedback_to_mistakes(isolated_db):
    req = writing_router.Task1WritingRequest(
        text="this sentence has no proper introduction and it is short",
        chart_type="chart",
        topic="population trend",
        keywords=["population"],
    )
    result = asyncio.run(
        writing_router.analyze_task1_writing(
            req,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert result.total_score >= 0

    mistakes = db_module.get_user_mistakes("u1", module="writing", limit=50, question_type="writing_task1")
    assert len(mistakes) >= 1
    allowed_writing_error_types = {
        "writing_structure_issue",
        "writing_content_issue",
        "writing_vocabulary_issue",
        "writing_grammar_issue",
        "writing_structure_low_band",
        "writing_content_low_band",
        "writing_vocabulary_low_band",
        "writing_grammar_low_band",
        "writing_general_issue",
        "writing_general_low_band",
    }
    assert all((m.get("error_type") in allowed_writing_error_types) for m in mistakes)
    assert all("taxonomy:v1" in (m.get("tags") or []) for m in mistakes)


def test_writing_peer_review_flow(isolated_db):
    submission = asyncio.run(
        writing_router.submit_peer_writing(
            writing_router.PeerSubmissionCreateRequest(
                task_type="task1",
                topic="Bar chart discussion",
                content="The chart illustrates a clear increase in urban travel demand over the period and provides several comparable indicators.",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert submission.submission_id

    claimed = asyncio.run(
        writing_router.claim_peer_submission(
            current_user={"id": "u2", "username": "u2"},
        )
    )
    assert claimed.claimed is True
    assert claimed.submission is not None
    assert claimed.submission.id == submission.submission_id

    reviewed = asyncio.run(
        writing_router.submit_peer_review(
            writing_router.PeerReviewSubmitRequest(
                submission_id=submission.submission_id,
                tr_score=6.5,
                cc_score=6.0,
                lr_score=6.5,
                gra_score=6.0,
                strengths="Structure is clear.",
                improvements="Use more precise data comparisons.",
                comment_text="Good overall organization. Add one more concrete comparison sentence.",
            ),
            current_user={"id": "u2", "username": "u2"},
        )
    )
    assert reviewed.overall_score > 0
    assert reviewed.quality_tier in {"basic", "standard", "advanced"}

    subs = asyncio.run(
        writing_router.get_my_peer_submissions(
            limit=20,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    target = next((x for x in subs if x.id == submission.submission_id), None)
    assert target is not None
    assert target.review_count >= 1

    received = asyncio.run(
        writing_router.get_received_peer_reviews(
            submission_id=submission.submission_id,
            limit=20,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(received) >= 1


def test_writing_peer_ai_assist_and_stats(isolated_db):
    submission = asyncio.run(
        writing_router.submit_peer_writing(
            writing_router.PeerSubmissionCreateRequest(
                task_type="task2",
                topic="Should university be free?",
                content=(
                    "I believe free university education should be considered in many countries. "
                    "On the one hand, this policy can reduce inequality and expand social mobility. "
                    "For example, students from low-income families may access higher education without heavy debt. "
                    "However, governments should still design sustainable funding models and quality control measures. "
                    "In conclusion, free access can be beneficial if combined with strict quality assurance."
                ),
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert submission.submission_id

    claimed = asyncio.run(
        writing_router.claim_peer_submission(
            current_user={"id": "u2", "username": "u2"},
        )
    )
    assert claimed.claimed is True
    assert claimed.submission is not None

    assist = asyncio.run(
        writing_router.get_peer_review_ai_assist(
            writing_router.PeerReviewAssistRequest(submission_id=submission.submission_id),
            current_user={"id": "u2", "username": "u2"},
        )
    )
    assert assist.overall_score > 0
    assert len(assist.sample_comment) > 0
    assert len(assist.strengths) >= 1

    reviewed = asyncio.run(
        writing_router.submit_peer_review(
            writing_router.PeerReviewSubmitRequest(
                submission_id=submission.submission_id,
                tr_score=assist.tr_score,
                cc_score=assist.cc_score,
                lr_score=assist.lr_score,
                gra_score=assist.gra_score,
                strengths=" ".join(assist.strengths),
                improvements=" ".join(assist.improvements),
                comment_text=assist.sample_comment,
            ),
            current_user={"id": "u2", "username": "u2"},
        )
    )
    assert reviewed.overall_score > 0

    stats = asyncio.run(
        writing_router.get_peer_stats(
            current_user={"id": "u2", "username": "u2"},
        )
    )
    assert stats.total_reviews_written >= 1
    assert stats.total_points >= 1
    assert len(stats.reviewer_badges) >= 1

    leaderboard = asyncio.run(
        writing_router.get_peer_leaderboard(
            limit=10,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(leaderboard) >= 1
    assert any(item.reviewer_id == "u2" for item in leaderboard)
    assert all(item.reviewer_alias.startswith("互评同学#") for item in leaderboard)

    received = asyncio.run(
        writing_router.get_received_peer_reviews(
            submission_id=submission.submission_id,
            limit=20,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(received) >= 1
    assert (received[0].reviewer_alias or "").startswith("互评同学#")


def test_gamification_overview_leaderboard_and_redeem(isolated_db):
    for i in range(2):
        submission = asyncio.run(
            writing_router.submit_peer_writing(
                writing_router.PeerSubmissionCreateRequest(
                    task_type="task1",
                    topic=f"chart-{i}",
                    content=(
                        "The chart illustrates a clear trend and provides notable comparisons. "
                        "Overall, changes remain steady over time with some fluctuations."
                    ),
                ),
                current_user={"id": "u1", "username": "u1"},
            )
        )
        asyncio.run(
            writing_router.submit_peer_review(
                writing_router.PeerReviewSubmitRequest(
                    submission_id=submission.submission_id,
                    tr_score=6.0,
                    cc_score=6.0,
                    lr_score=6.0,
                    gra_score=6.0,
                    strengths="Clear structure and readable progression.",
                    improvements="Add more specific comparisons with exact data.",
                    comment_text=(
                        "The response is generally coherent and easy to follow. "
                        "To improve band score, include more accurate data references and better lexical variety."
                    ),
                ),
                current_user={"id": "u2", "username": "u2"},
            )
        )

    overview = asyncio.run(
        gamification_router.get_overview(
            current_user={"id": "u2", "username": "u2"},
        )
    )
    assert overview.total_points > 0
    assert overview.level in {"bronze", "silver", "gold", "diamond"}
    assert overview.event_count >= 1

    achievements = asyncio.run(
        gamification_router.get_achievements(
            limit=20,
            current_user={"id": "u2", "username": "u2"},
        )
    )
    assert len(achievements) >= 1

    leaderboard = asyncio.run(
        gamification_router.get_leaderboard(
            limit=10,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(leaderboard) >= 1
    assert any(item.user_id == "u2" for item in leaderboard)

    if overview.total_points >= 30:
        redeemed = asyncio.run(
            gamification_router.redeem_item(
                gamification_router.RedemptionRequest(item_code="coupon_peer_boost"),
                current_user={"id": "u2", "username": "u2"},
            )
        )
        assert redeemed.cost_points == 30
        assert redeemed.total_points == overview.total_points - 30


def test_reminder_retry_backoff_and_failover(isolated_db, monkeypatch):
    rid = str(uuid.uuid4())
    db_module.create_reminder(
        rid,
        "u1",
        {
            "type": "study_reminder",
            "title": "test",
            "content": "test",
            "scheduled_at": int(time.time()) - 10,
            "status": "pending",
            "channel": "app",
            "metadata": {},
        },
    )

    class _FailService:
        def send_reminder(self, reminder):
            return False

    monkeypatch.setattr(
        reminder_tasks,
        "MAX_RETRY_COUNT",
        1,
    )
    monkeypatch.setattr(
        reminder_tasks,
        "RETRY_DELAY_SECONDS",
        1,
    )
    monkeypatch.setattr(
        reminder_service,
        "get_reminder_service",
        lambda: _FailService(),
    )

    out1 = reminder_tasks.send_reminder(rid)
    assert out1 is False
    r1 = db_module.get_reminder(rid)
    assert r1["status"] == "pending"
    assert int((r1.get("metadata") or {}).get("retry_count", 0)) == 1

    out2 = reminder_tasks.send_reminder(rid)
    assert out2 is False
    r2 = db_module.get_reminder(rid)
    assert r2["status"] == "failed"


def test_intelligent_reminder_reads_real_learning_data(isolated_db):
    db_module.save_user_activity(
        str(uuid.uuid4()),
        "u1",
        {
            "activity_type": "practice",
            "module": "listening",
            "duration": 35,
            "score": 6.5,
            "metadata": {"source": "test"},
        },
    )
    sessions = intelligent_reminder_tasks._get_user_learning_sessions("u1")
    assert len(sessions) >= 1
    assert any(str(s.get("type")) in {"listening", "practice"} for s in sessions)


def test_diagnostic_session_owner_and_pending_guard_errors(isolated_db):
    start = asyncio.run(
        diagnostic_router.start_diagnostic(
            diagnostic_router.DiagnosticStart(modules=["reading", "listening"]),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    session_id = start.id
    pending_qid = start.next_question.question_id

    with pytest.raises(Exception) as e1:
        asyncio.run(
            diagnostic_router.submit_answer(
                session_id,
                diagnostic_router.DiagnosticAnswers(
                    answers=[diagnostic_router.DiagnosticAnswer(question_id="fake_qid", answer="A")]
                ),
                current_user={"id": "u1", "username": "u1"},
            )
        )
    detail_1 = getattr(e1.value, "detail", str(e1.value))
    assert "pending" in str(detail_1).lower()

    ok = asyncio.run(
        diagnostic_router.submit_answer(
            session_id,
            diagnostic_router.DiagnosticAnswers(
                answers=[diagnostic_router.DiagnosticAnswer(question_id=pending_qid, answer="A")]
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert ok.estimated_ability is not None

    with pytest.raises(Exception) as e2:
        asyncio.run(
            diagnostic_router.get_report(
                session_id=session_id,
                current_user={"id": "u2", "username": "u2"},
            )
        )
    status_2 = getattr(e2.value, "status_code", None)
    detail_2 = getattr(e2.value, "detail", str(e2.value))
    assert status_2 == 403 or "permission" in str(detail_2).lower()


def test_diagnostic_bank_health_and_reload(isolated_db):
    version_info = asyncio.run(
        diagnostic_router.get_diagnostic_bank_version(current_user={"id": "u1", "username": "u1"})
    )
    assert "version" in version_info
    assert version_info["source"] in {"file", "builtin"}

    health = asyncio.run(
        diagnostic_router.get_diagnostic_bank_health(current_user={"id": "u1", "username": "u1"})
    )
    assert health["total_questions"] >= 1
    assert "last_loaded_at" in health

    reloaded = asyncio.run(
        diagnostic_router.reload_diagnostic_bank(current_user={"id": "u1", "username": "u1"})
    )
    assert reloaded["total_questions"] >= 1


def test_mistakes_due_analysis_export_import(isolated_db):
    created = asyncio.run(
        mistakes_router.create_mistake(
            mistakes_router.MistakeCreate(
                module="reading",
                question_id="rd_i_1",
                question_type="diagnostic",
                error_type="keyword_mismatch",
                content="sample question",
                user_answer="A",
                correct_answer="B",
                explanation="sample",
                difficulty="intermediate",
                tags=["keyword_mismatch"],
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )

    conn = db_module.get_conn()
    try:
        conn.execute("UPDATE mistakes SET next_review_date = 0 WHERE id = ?", (created.id,))
        conn.commit()
    finally:
        conn.close()

    due = asyncio.run(
        mistakes_router.list_due_mistakes(module=None, limit=50, current_user={"id": "u1", "username": "u1"})
    )
    assert any(x.id == created.id for x in due)

    by_day = asyncio.run(
        mistakes_router.list_mistakes(
            module=None,
            question_type=None,
            created_from=0,
            created_to=int(created.created_at),
            limit=50,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert any(x.id == created.id for x in by_day)

    analysis = asyncio.run(mistakes_router.analysis(current_user={"id": "u1", "username": "u1"}))
    assert analysis.total >= 1
    assert isinstance(analysis.by_error_type, dict)
    assert isinstance(analysis.by_error_and_question_type, dict)
    assert analysis.vocabulary_test_wrong_count >= 0
    assert analysis.vocabulary_test_wrong_ratio >= 0

    review_queue = asyncio.run(
        mistakes_router.prioritized_review_queue(
            module=None,
            question_type=None,
            next_review_from=0,
            next_review_to=10,
            limit=20,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(review_queue) >= 1
    assert hasattr(review_queue[0], "priority_score")
    assert hasattr(review_queue[0], "priority_reason")
    assert hasattr(review_queue[0], "expected_mastery_gain")
    assert hasattr(review_queue[0], "projected_mastery_after_review")
    batch = asyncio.run(
        mistakes_router.batch_review(
            mistakes_router.BatchReviewRequest(
                mistake_ids=[x.id for x in review_queue[:2]],
                mastery_delta=0.2,
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert batch.reviewed >= 1
    assert batch.requested >= batch.reviewed

    clusters = asyncio.run(
        mistakes_router.clusters(
            module=None,
            question_type=None,
            limit=10,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(clusters) >= 1
    assert hasattr(clusters[0], "count")
    assert hasattr(clusters[0], "risk_score")

    trends = asyncio.run(
        mistakes_router.trends(
            days=7,
            module=None,
            question_type=None,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(trends) == 7
    assert hasattr(trends[0], "created_count")
    assert hasattr(trends[0], "reviewed_count")
    assert hasattr(trends[0], "due_snapshot")
    assert sum(getattr(x, "reviewed_count", 0) for x in trends) >= 1

    hotspot_rows = asyncio.run(
        mistakes_router.hotspots(
            days=14,
            module=None,
            limit=20,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(hotspot_rows) >= 1
    assert hasattr(hotspot_rows[0], "module")
    assert hasattr(hotspot_rows[0], "error_type")
    assert hasattr(hotspot_rows[0], "risk_score")

    rec_rows = asyncio.run(
        mistakes_router.recommendations(
            days=14,
            module=None,
            limit=5,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(rec_rows) >= 1
    assert hasattr(rec_rows[0], "rank")
    assert hasattr(rec_rows[0], "action")
    assert hasattr(rec_rows[0], "error_type")

    module_rows = asyncio.run(
        mistakes_router.module_comparison(
            days=14,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(module_rows) >= 1
    assert hasattr(module_rows[0], "module")
    assert hasattr(module_rows[0], "unique_error_types")
    assert hasattr(module_rows[0], "risk_index")

    weekly_focus = asyncio.run(
        mistakes_router.weekly_focus(
            days=14,
            total_daily_minutes=90,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert isinstance(weekly_focus.focus_module, str)
    assert weekly_focus.total_daily_minutes >= 30
    assert isinstance(weekly_focus.module_allocations, list)

    review_effectiveness = asyncio.run(
        mistakes_router.review_effectiveness(
            days=7,
            module=None,
            question_type=None,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(review_effectiveness) == 7
    assert hasattr(review_effectiveness[0], "review_count")
    assert hasattr(review_effectiveness[0], "avg_mastery_gain")
    assert sum(getattr(x, "review_count", 0) for x in review_effectiveness) >= 1

    exported_json = asyncio.run(
        mistakes_router.export_mistakes(
            format="json",
            module=None,
            limit=1000,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert exported_json["count"] >= 1
    assert isinstance(exported_json["items"], list)

    exported_csv = asyncio.run(
        mistakes_router.export_mistakes(
            format="csv",
            module=None,
            limit=1000,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert isinstance(exported_csv, Response)
    assert "question_id" in exported_csv.body.decode("utf-8")

    imported = asyncio.run(
        mistakes_router.import_mistakes(
            mistakes_router.MistakeImportPayload(
                items=[
                    mistakes_router.MistakeCreate(
                        module="writing",
                        question_id=f"wt_{uuid.uuid4().hex[:6]}",
                        question_type="manual",
                        error_type="grammar",
                        content="x",
                        user_answer="x",
                        correct_answer="y",
                        explanation="z",
                        difficulty="basic",
                        tags=["grammar"],
                    )
                ]
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert imported.imported == 1


def test_vocabulary_due_review_stats(isolated_db):
    created = asyncio.run(
        vocabulary_router.add_word(
            vocabulary_router.WordCreate(
                word="abandon",
                definition="to leave",
                examples=["he abandoned the plan"],
                pronunciation="/əˈbændən/",
                part_of_speech="verb",
                tags=["core"],
                source_module="manual",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )

    conn = db_module.get_conn()
    try:
        conn.execute("UPDATE vocabulary SET next_review_date = 0 WHERE id = ?", (created.id,))
        conn.commit()
    finally:
        conn.close()

    due = asyncio.run(vocabulary_router.list_due_vocabulary(limit=100, current_user={"id": "u1", "username": "u1"}))
    assert any(x.id == created.id for x in due)

    reviewed = asyncio.run(
        vocabulary_router.mark_word_reviewed(
            vocab_id=created.id,
            mastery_delta=0.15,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert reviewed.mastery_level >= 0

    stats = asyncio.run(vocabulary_router.vocabulary_summary(current_user={"id": "u1", "username": "u1"}))
    assert stats.total >= 1
    assert isinstance(stats.by_source_module, dict)


def test_vocabulary_strategy_scheduler_behaviour(isolated_db):
    # root strategy: 优先带常见词缀
    asyncio.run(
        vocabulary_router.add_word(
            vocabulary_router.WordCreate(
                word="transportation",
                definition="n.",
                examples=["public transportation is convenient"],
                source_module="manual",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    asyncio.run(
        vocabulary_router.add_word(
            vocabulary_router.WordCreate(
                word="book",
                definition="n.",
                examples=[],
                source_module="manual",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )

    root_session = asyncio.run(
        vocabulary_router.start_learning_session(
            vocabulary_router.LearnSessionRequest(strategy="root", count=1),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(root_session.words) == 1
    assert root_session.words[0].word == "transportation"
    assert root_session.words[0].scheduler_score >= 0
    assert root_session.words[0].scheduler_reason

    # context strategy: 优先带例句
    context_session = asyncio.run(
        vocabulary_router.start_learning_session(
            vocabulary_router.LearnSessionRequest(strategy="context", count=1),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(context_session.words) == 1
    assert len(context_session.words[0].examples) >= 1
    assert context_session.words[0].scheduler_score >= 0

    # spaced strategy: 优先到期项
    conn = db_module.get_conn()
    try:
        conn.execute("UPDATE vocabulary SET next_review_date = ? WHERE word = ?", (0, "book"))
        conn.execute("UPDATE vocabulary SET next_review_date = ? WHERE word = ?", (9999999999, "transportation"))
        conn.commit()
    finally:
        conn.close()

    spaced_session = asyncio.run(
        vocabulary_router.start_learning_session(
            vocabulary_router.LearnSessionRequest(strategy="spaced", count=1),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(spaced_session.words) == 1
    assert spaced_session.words[0].word == "book"
    assert spaced_session.words[0].scheduler_score >= 0

    mixed_session = asyncio.run(
        vocabulary_router.start_learning_session(
            vocabulary_router.LearnSessionRequest(strategy="mixed", count=1),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(mixed_session.words) == 1
    assert mixed_session.strategy == "mixed"

    insights = asyncio.run(
        vocabulary_router.vocabulary_strategy_insights(
            days=30,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(insights) >= 1
    assert any(getattr(x, "strategy", "") == "spaced" for x in insights)
    assert all(getattr(x, "session_count", 0) >= 1 for x in insights)
    assert all(hasattr(x, "avg_mastery_gain_7d") for x in insights)
    assert all(hasattr(x, "wrong_rate_7d") for x in insights)


def test_due_review_reminder_task_is_deduplicated(isolated_db):
    m = asyncio.run(
        mistakes_router.create_mistake(
            mistakes_router.MistakeCreate(
                module="reading",
                question_id="rd_due_1",
                question_type="diagnostic",
                error_type="inference_error",
                content="sample",
                user_answer="a",
                correct_answer="b",
                explanation="x",
                difficulty="intermediate",
                tags=["inference_error"],
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    v = asyncio.run(
        vocabulary_router.add_word(
            vocabulary_router.WordCreate(
                word="coherent",
                definition="logical",
                examples=["a coherent argument"],
                pronunciation="/kəʊˈhɪərənt/",
                part_of_speech="adj",
                tags=["writing"],
                source_module="writing",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )

    conn = db_module.get_conn()
    try:
        conn.execute("UPDATE mistakes SET next_review_date = 0 WHERE id = ?", (m.id,))
        conn.execute("UPDATE vocabulary SET next_review_date = 0 WHERE id = ?", (v.id,))
        conn.commit()
    finally:
        conn.close()

    first = schedule_due_review_reminders()
    assert first["created"] >= 2

    second = schedule_due_review_reminders()
    assert second["created"] == 0
    assert second["skipped"] >= 2


def test_vocabulary_test_generate_and_submit(isolated_db):
    created = asyncio.run(
        vocabulary_router.add_word(
            vocabulary_router.WordCreate(
                word="abandon",
                definition="to leave something behind",
                examples=["he abandoned the old plan"],
                source_module="manual",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert created.word == "abandon"

    generated = asyncio.run(
        vocabulary_router.generate_vocab_test(
            vocabulary_router.VocabTestGenerateRequest(mode="spelling", count=1),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert generated.test_id
    assert len(generated.questions) == 1

    qid = generated.questions[0].id
    submitted = asyncio.run(
        vocabulary_router.submit_vocab_test(
            vocabulary_router.VocabTestSubmitRequest(
                test_id=generated.test_id,
                answers=[vocabulary_router.VocabTestAnswer(question_id=qid, answer="abandon")],
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert submitted.total == 1
    assert submitted.correct == 1
    assert submitted.accuracy == 1.0


def test_vocabulary_test_wrong_answer_creates_mistake(isolated_db):
    asyncio.run(
        vocabulary_router.add_word(
            vocabulary_router.WordCreate(
                word="coherent",
                definition="logical and consistent",
                examples=["a coherent argument"],
                source_module="manual",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )

    generated = asyncio.run(
        vocabulary_router.generate_vocab_test(
            vocabulary_router.VocabTestGenerateRequest(mode="spelling", count=1),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    qid = generated.questions[0].id
    submitted = asyncio.run(
        vocabulary_router.submit_vocab_test(
            vocabulary_router.VocabTestSubmitRequest(
                test_id=generated.test_id,
                answers=[vocabulary_router.VocabTestAnswer(question_id=qid, answer="wrong_word")],
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert submitted.total == 1
    assert submitted.correct == 0

    mistakes = db_module.get_user_mistakes("u1", module="vocabulary", limit=20)
    matched = [
        m for m in mistakes
        if m.get("question_id") == qid and m.get("question_type") == "vocabulary_test"
    ]
    assert len(matched) >= 1
    assert any(any(str(t).startswith("word_id:") for t in (m.get("tags") or [])) for m in matched)


def test_diagnostic_history_summary_trend(isolated_db):
    db_module.create_diagnostic_session("s_old", "u1", ["reading", "writing"])
    db_module.create_diagnostic_report(
        "r_old",
        "s_old",
        {
            "overall_band": 5.5,
            "module_scores": [
                {"module": "reading", "score": 5.5, "max_score": 9.0},
                {"module": "writing", "score": 5.5, "max_score": 9.0},
            ],
            "weaknesses": [],
            "recommendations": [],
        },
    )
    db_module.create_diagnostic_session("s_new", "u1", ["reading", "writing"])
    db_module.create_diagnostic_report(
        "r_new",
        "s_new",
        {
            "overall_band": 6.5,
            "module_scores": [
                {"module": "reading", "score": 6.0, "max_score": 9.0},
                {"module": "writing", "score": 7.0, "max_score": 9.0},
            ],
            "weaknesses": [],
            "recommendations": [],
        },
    )
    conn = db_module.get_conn()
    try:
        conn.execute("UPDATE diagnostic_reports SET generated_at = ? WHERE id = ?", (1000, "r_old"))
        conn.execute("UPDATE diagnostic_reports SET generated_at = ? WHERE id = ?", (2000, "r_new"))
        conn.commit()
    finally:
        conn.close()

    summary = asyncio.run(
        diagnostic_router.get_diagnostic_history_summary(limit=10, current_user={"id": "u1", "username": "u1"})
    )
    assert summary.total_reports >= 2
    assert summary.trend == "up"
    assert summary.delta_overall_band == 1.0
    assert len(summary.history) >= 2


def test_mistake_csv_export_contains_header(isolated_db):
    asyncio.run(
        mistakes_router.create_mistake(
            mistakes_router.MistakeCreate(
                module="reading",
                question_id="rd_x_1",
                question_type="diagnostic",
                error_type="keyword_mismatch",
                content="content",
                user_answer="x",
                correct_answer="y",
                explanation="z",
                difficulty="basic",
                tags=["tag1", "tag2"],
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    exported_csv = asyncio.run(
        mistakes_router.export_mistakes(
            format="csv",
            module=None,
            limit=10,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    body = exported_csv.body.decode("utf-8")
    header_line = body.splitlines()[0]
    expected = ["id", "module", "question_id", "question_type", "error_type"]
    for col in expected:
        assert col in header_line
    # basic sanity: data row exists
    assert len(body.splitlines()) >= 2


def test_mistakes_question_type_filter(isolated_db):
    asyncio.run(
        mistakes_router.create_mistake(
            mistakes_router.MistakeCreate(
                module="reading",
                question_id="rd_filter_1",
                question_type="diagnostic",
                error_type="inference_error",
                content="a",
                user_answer="a",
                correct_answer="b",
                explanation="x",
                difficulty="medium",
                tags=["x"],
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    asyncio.run(
        mistakes_router.create_mistake(
            mistakes_router.MistakeCreate(
                module="vocabulary",
                question_id="voc_filter_1",
                question_type="vocabulary_test",
                error_type="vocabulary_test_wrong",
                content="a",
                user_answer="a",
                correct_answer="b",
                explanation="x",
                difficulty="medium",
                tags=["x"],
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )

    only_vocab_test = asyncio.run(
        mistakes_router.list_mistakes(
            module=None,
            question_type="vocabulary_test",
            limit=50,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(only_vocab_test) >= 1
    assert all(item.question_type == "vocabulary_test" for item in only_vocab_test)


def test_plan_generate_weekly_tasks_skip_existing_day(isolated_db):
    created = asyncio.run(
        plan_router.create_plan(
            plan_router.LearningPlanCreate(
                target_band=7.0,
                daily_minutes=90,
                focus_modules=["listening", "reading"],
                duration_weeks=2,
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    plan_id = created.plan_id

    first = asyncio.run(
        plan_router.generate_weekly_tasks(
            plan_id,
            plan_router.WeeklyTaskGenerateRequest(days=3),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert first.generated_days == 3
    assert first.skipped_days == 0

    second = asyncio.run(
        plan_router.generate_weekly_tasks(
            plan_id,
            plan_router.WeeklyTaskGenerateRequest(days=3),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert second.generated_days == 0
    assert second.skipped_days == 3

    tasks = db_module.get_daily_tasks_by_plan(plan_id)
    assert len(tasks) == 3
    assert all(len(item.get("tasks", [])) >= 2 for item in tasks)


def test_plan_update_settings_daily_minutes_and_focus_modules(isolated_db):
    created = asyncio.run(
        plan_router.create_plan(
            plan_router.LearningPlanCreate(
                target_band=7.0,
                daily_minutes=90,
                focus_modules=["listening", "reading"],
                duration_weeks=2,
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    plan_id = created.plan_id

    updated = asyncio.run(
        plan_router.update_plan_settings(
            plan_id,
            plan_router.PlanSettingsUpdate(
                daily_minutes=120,
                focus_modules=["writing", "speaking"],
                status="active",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert updated.daily_minutes == 120
    assert updated.focus_modules == ["writing", "speaking"]
    assert updated.status == "active"


def test_plan_calibration_log_and_report_health(isolated_db):
    created = asyncio.run(
        plan_router.create_plan(
            plan_router.LearningPlanCreate(
                target_band=7.0,
                daily_minutes=100,
                focus_modules=["listening", "reading"],
                duration_weeks=2,
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    plan_id = created.plan_id

    asyncio.run(
        plan_router.generate_weekly_tasks(
            plan_id,
            plan_router.WeeklyTaskGenerateRequest(days=2),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    tasks = db_module.get_daily_tasks_by_plan(plan_id)
    first_daily = tasks[0]
    first_task_id = first_daily["tasks"][0]["id"]
    asyncio.run(
        plan_router.update_progress(
            first_daily["id"],
            plan_router.TaskProgressUpdate(task_id=first_task_id, completed=True, progress=100, time_spent=30),
            current_user={"id": "u1", "username": "u1"},
        )
    )

    updated = asyncio.run(
        plan_router.update_plan_settings(
            plan_id,
            plan_router.PlanSettingsUpdate(
                daily_minutes=85,
                focus_modules=["reading", "writing"],
                source="auto_calibration",
                note="test-calibration",
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert updated.daily_minutes == 85

    logs = db_module.get_plan_calibration_logs(plan_id, limit=10)
    assert len(logs) >= 1
    latest = logs[0]
    assert latest["source"] == "auto_calibration"
    assert latest["before_daily_minutes"] == 100
    assert latest["after_daily_minutes"] == 85

    health = asyncio.run(
        report_router.get_current_plan_health(
            plan_id=plan_id,
            days=14,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert health.plan_id == plan_id
    assert health.task_total >= 1
    assert health.task_done >= 1
    assert health.health_level in {"healthy", "watch", "at_risk", "unknown"}

    calibration_rows = asyncio.run(
        report_router.get_current_plan_calibrations(
            plan_id=plan_id,
            limit=10,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert len(calibration_rows) >= 1
    assert calibration_rows[0].source == "auto_calibration"


def test_plan_intervention_preview_and_apply(isolated_db):
    created = asyncio.run(
        plan_router.create_plan(
            plan_router.LearningPlanCreate(
                target_band=6.5,
                daily_minutes=80,
                focus_modules=["reading", "writing"],
                duration_weeks=2,
            ),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    plan_id = created.plan_id

    preview = asyncio.run(
        plan_router.get_intervention_preview(
            plan_id=plan_id,
            days=14,
            remedial_days=3,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert preview.plan_id == plan_id
    assert preview.remedial_days == 3
    assert len(preview.intervention_daily_tasks) >= 1

    before_tasks = db_module.get_daily_tasks_by_plan(plan_id)
    apply_result = asyncio.run(
        plan_router.apply_intervention_plan(
            plan_id=plan_id,
            payload=plan_router.InterventionApplyRequest(days=14, remedial_days=3),
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert apply_result.intervention_batch_id
    assert apply_result.task_count_added == 3
    after_tasks = db_module.get_daily_tasks_by_plan(plan_id)
    assert len(after_tasks) >= len(before_tasks)
    added = 0
    for day in after_tasks:
        for t in day.get("tasks", []):
            if str(t.get("title", "")).startswith("干预 ·"):
                added += 1
    assert added >= 3

    intervention_status = asyncio.run(
        report_router.get_current_plan_intervention_status(
            plan_id=plan_id,
            days=14,
            current_user={"id": "u1", "username": "u1"},
        )
    )
    assert intervention_status.plan_id == plan_id
    assert intervention_status.intervention_total >= 3
    assert intervention_status.batch_count >= 1
