from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agent_core.agent import ielts_agent

router = APIRouter()


class ChatRequest(BaseModel):
    query: str
    session_id: str


class ChatResponse(BaseModel):
    agent: str
    response: str
    routing: dict


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """与智能体对话接口
    
    用户发送问题，由CommonAgent根据问题选择合适的专用智能体处理
    如果专用智能体无法处理，会回退到CommonAgent处理
    
    Args:
        request: 包含查询内容和会话ID的请求
        
    Returns:
        包含处理智能体、响应内容和路由信息的响应
    """
    try:
        # 使用CommonAgent处理查询
        result = ielts_agent.route_and_execute(request.query, request.session_id)
        
        # 返回结果
        return ChatResponse(
            agent=result['agent'],
            response=result['response'],
            routing=result['routing']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"对话处理失败: {str(e)}")


@router.post("/translation")
async def translation_practice(request: dict):
    """翻译练习接口
    
    生成翻译题目或检查翻译
    
    Args:
        request: 包含action、difficulty（生成题目时）或chinese_sentence、user_translation（检查翻译时）的请求
        
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
