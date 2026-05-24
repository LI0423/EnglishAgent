import time

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal

from agent_core.agent import ielts_agent, translation_agent, deep_search_agent
from ..deps import get_current_user
from ..services.ability_service import record_practice_result

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    session_id: str
    enable_agentic_rag: bool = False
    rag_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="可选的 Agentic RAG 配置覆盖，如 long_memory_ttl_seconds/short_memory_window 等",
    )


class ChatResponse(BaseModel):
    agent: str
    response: str
    routing: dict
    rag: Optional[dict] = None


class TranslationPracticeRequest(BaseModel):
    action: Literal["generate", "check"]
    difficulty: str = "medium"
    direction: str = "zh_to_en"
    topic: str = "general"
    chinese_sentence: Optional[str] = None
    source_sentence: Optional[str] = None
    user_translation: Optional[str] = None
    practice_mode: Optional[str] = None
    used_hint: bool = False


class DeepSearchRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    enable_agentic_rag: bool = True
    rag_config: Optional[Dict[str, Any]] = Field(default=None)
    max_iterations: Optional[int] = Field(default=None, ge=1, le=6)


class DeepSearchResponse(BaseModel):
    agent: str
    response: str
    routing: Dict[str, Any]
    rag: Optional[Dict[str, Any]] = None
    search: Dict[str, Any]


class ChatHistoryItem(BaseModel):
    message_id: Optional[str] = None
    session_id: str
    user_id: str
    role: str
    content: str
    created_at: Optional[int] = None
    turn_index: Optional[int] = None
    agent_key: Optional[str] = ""
    meta: Optional[Dict[str, Any]] = None


class ChatSessionItem(BaseModel):
    session_id: str
    message_count: int
    last_created_at: int
    last_turn_index: int
    last_role: str
    last_agent_key: str
    last_preview: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user = Depends(get_current_user)):
    """与智能体对话接口
    
    用户发送问题，由CommonAgent根据问题选择合适的专用智能体处理
    如果专用智能体无法处理，会回退到CommonAgent处理
    
    Args:
        request: 包含查询内容和会话ID的请求
        current_user: 当前登录用户
        
    Returns:
        包含处理智能体、响应内容和路由信息的响应
    """
    try:
        # 使用CommonAgent处理查询
        result = ielts_agent.route_and_execute(
            request.query,
            request.session_id,
            user_context={
                "user_id": str(current_user.get("id")),
                "enable_agentic_rag": request.enable_agentic_rag,
                "rag_config": request.rag_config or {},
            },
        )
        
        # 返回结果
        return ChatResponse(
            agent=result['agent'],
            response=result['response'],
            routing=result['routing'],
            rag=result.get("rag"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话处理失败: {str(e)}")


@router.post("/translation")
async def translation_practice(request: TranslationPracticeRequest, current_user = Depends(get_current_user)):
    """翻译练习接口
    
    生成翻译题目或检查翻译
    
    Args:
        request: 包含action、difficulty（生成题目时）或chinese_sentence、user_translation（检查翻译时）的请求
        current_user: 当前登录用户
        
    Returns:
        翻译题目或检查结果
    """
    try:
        if request.action == "generate":
            # 生成翻译题目
            difficulty = request.difficulty or "medium"
            try:
                result = translation_agent.generate_translation_question(
                    difficulty=difficulty,
                    direction=request.direction,
                    topic=request.topic,
                )
            except TypeError:
                result = translation_agent.generate_translation_question(difficulty=difficulty)
            return result
        if request.action == "check":
            # 检查翻译
            source_sentence = (request.source_sentence or request.chinese_sentence or "").strip()
            user_translation = (request.user_translation or "").strip()
            
            if not source_sentence or not user_translation:
                raise HTTPException(status_code=400, detail="缺少必要参数")
            
            try:
                result = translation_agent.check_translation(
                    source_sentence=source_sentence,
                    user_translation=user_translation,
                    direction=request.direction,
                    topic=request.topic,
                )
            except TypeError:
                result = translation_agent.check_translation(source_sentence, user_translation)
            record_practice_result(
                str(current_user["id"]),
                "translation",
                result,
                difficulty=request.difficulty,
                topic=request.topic,
                direction=request.direction,
                practice_mode=request.practice_mode or "",
                used_hint=request.used_hint,
                source="translation_search",
            )
            return result
        raise HTTPException(status_code=400, detail="无效的action参数")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译处理失败: {str(e)}")


@router.post("/deep-search", response_model=DeepSearchResponse)
async def deep_search(request: DeepSearchRequest, current_user = Depends(get_current_user)):
    """深度搜索专用接口：返回对话结论 + 结构化证据结果。"""
    query = (request.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query不能为空")

    session_id = request.session_id or f"deep_search_{int(time.time() * 1000)}"
    try:
        route_result = ielts_agent.route_and_execute(
            f"深度搜索：{query}",
            session_id,
            user_context={
                "user_id": str(current_user.get("id")),
                "enable_agentic_rag": bool(request.enable_agentic_rag),
                "rag_config": request.rag_config or {},
            },
        )

        previous_iterations = deep_search_agent.max_iterations
        if request.max_iterations:
            deep_search_agent.max_iterations = int(request.max_iterations)
        try:
            search_result = deep_search_agent.deep_search(query)
        finally:
            deep_search_agent.max_iterations = previous_iterations

        return DeepSearchResponse(
            agent=route_result.get("agent", "deep_search_agent"),
            response=route_result.get("response", ""),
            routing=route_result.get("routing", {}),
            rag=route_result.get("rag"),
            search=search_result,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"深度搜索处理失败: {str(e)}")


@router.get("/history/sessions", response_model=List[ChatSessionItem])
async def list_chat_sessions(limit: int = 30, current_user=Depends(get_current_user)):
    """读取当前用户的聊天会话列表（来自 Milvus Lite）"""
    try:
        user_id = str(current_user.get("id"))
        rows = ielts_agent.list_persistent_sessions(user_id=user_id, limit=limit)
        return [ChatSessionItem(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取会话列表失败: {str(e)}")


@router.get("/history/{session_id}", response_model=List[ChatHistoryItem])
async def get_chat_history(session_id: str, limit: int = 200, current_user=Depends(get_current_user)):
    """读取 Milvus Lite 中的会话消息记录"""
    try:
        user_id = str(current_user.get("id"))
        rows = ielts_agent.get_persistent_history(session_id=session_id, user_id=user_id, limit=limit)
        return [ChatHistoryItem(**row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取聊天历史失败: {str(e)}")
