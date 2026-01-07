from datetime import datetime, UTC
from typing import Dict, List, cast

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.runtime import Runtime
from typing_extensions import Literal

from agent_core.context import Context
from agent_core.state.state import State, InputState


async def call_model(state: State, runtime: Runtime[Context]) -> Dict[str, List[AIMessage]]:
    available_tools = await get_tools()
    model = load_chat_model(runtime.context.model).bind_tools(available_tools)
    system_message = runtime.context.system_prompt.format(
        system_time=datetime.now(tz=UTC).isoformat()
    )

    response = cast(
        AIMessage,
        await model.ainvoke(
            [{"role": "system", "context": system_message}, *state.messages]
        )
    )

    if state.is_last_step and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
            ]
        }
    return {"messages": [response]}


async def dynamic_tools_node(
        state: State, runtime: Runtime[Context]
) -> Dict[str, List[ToolMessage]]:
    available_tools = await get_tools()
    tool_node = ToolNode(available_tools)
    result = await tool_node.ainvoke(state)
    return cast(Dict[str, List[ToolMessage]], result)


builder = StateGraph(State, input_schema=InputState, context_schema=Context)
builder.add_node(call_model)
builder.add_node("tools", dynamic_tools_node)
builder.add_edge("__start__", "call_mode")


def route_model_output(state: State) -> Literal["__end__", "tools"]:
    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(f"Expected AIMessage in output edges, but got {type(last_message).__name__}")

    if not last_message.tool_calls:
        return "__end__"

    return "tools"


builder.add_conditional_edge("call_model", route_model_output)

builder.add_edge("tools", "call_model")

grpah = builder.compile(name="ReAct Agent")
