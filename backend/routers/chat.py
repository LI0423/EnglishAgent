from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from agent_core.agent import ielts_agent
from ..deps import get_current_user

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
async def translation_practice(request: dict, current_user = Depends(get_current_user)):
    """翻译练习接口
    
    生成翻译题目或检查翻译
    
    Args:
        request: 包含action、difficulty（生成题目时）或chinese_sentence、user_translation（检查翻译时）的请求
        current_user: 当前登录用户
        
    Returns:
        翻译题目或检查结果
    """
    try:
        from agent_core.agent import translation_agent
        
        action = request.get("action")
        
        if action == "generate":
            # 生成翻译题目
            difficulty = request.get("difficulty", "medium")
            result = translation_agent.generate_translation_question(difficulty)
            return result
        elif action == "check":
            # 检查翻译
            chinese_sentence = request.get("chinese_sentence")
            user_translation = request.get("user_translation")
            
            if not chinese_sentence or not user_translation:
                raise HTTPException(status_code=400, detail="缺少必要参数")
            
            result = translation_agent.check_translation(chinese_sentence, user_translation)
            return result
        else:
            raise HTTPException(status_code=400, detail="无效的action参数")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"翻译处理失败: {str(e)}")


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
