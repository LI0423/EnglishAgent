from datetime import datetime, UTC
from typing import Dict, cast, Any

from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
from typing_extensions import Literal

from agent_core.context import Context
from agent_core.state.state import State, InputState
from agent_core.tools import get_tools
from agent_core.agents import CommonAgent
from models.generator_model import GeneratorModel


# 创建CommonAgent实例
common_agent = CommonAgent()


def load_chat_model(model_name: str) -> Any:
    """加载聊天模型"""
    return GeneratorModel()


async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, Any]:
    """调用模型节点"""
    # 获取用户输入
    if not state.messages:
        return {"messages": [], "current_module": getattr(state, 'current_module', None)}
    
    last_message = state.messages[-1]
    user_input = last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    # 使用CommonAgent处理用户输入
    session_id = getattr(state, 'session_id', 'default_session')
    result = common_agent.route_and_execute(user_input, session_id)
    
    # 创建AIMessage
    ai_message = AIMessage(
        content=result['response'],
        id=f"msg_{datetime.now(tz=UTC).timestamp()}"
    )

    return {"messages": [ai_message], "current_module": result['agent'], "routing": result['routing']}


async def dynamic_tools_node(
        state: State, runtime: Runtime[Context]
) -> Dict[str, Any]:
    """工具节点"""
    available_tools = await get_tools()
    tool_node = ToolNode(available_tools)
    result = await tool_node.ainvoke(state)
    return {**cast(Dict[str, Any], result), "current_module": getattr(state, 'current_module', None)}


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    """模型输出路由"""
    if not state.messages:
        return "__end__"
    
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        return "__end__"

    # 只保留工具调用的路由
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    else:
        return "__end__"


def route_workflow_output(state: State) -> Literal["__end__", "call_model"]:
    """工作流输出路由"""
    # 工作流完成后返回模型进行总结
    return "call_model"


# 创建状态图
builder = StateGraph(State, input_schema=InputState, context_schema=Context)

# 添加节点
builder.add_node("call_model", call_model)
builder.add_node("tools", dynamic_tools_node)

# 添加边
builder.add_edge("__start__", "call_model")
builder.add_conditional_edge("call_model", route_model_output)
builder.add_edge("tools", "call_model")

# 编译图
graph = builder.compile(name="IELTS Learning Agent Workflow")
