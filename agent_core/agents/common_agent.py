import json
import re
from typing import Any, Dict, List, Optional
from agent_core.agents.base_agent import BaseAgent
from langchain_core.messages import HumanMessage, AIMessage

from agent_core.history_store import RedisHistoryStore, RedisSummaryStore

class RouterDecision:
    def __init__(self, agent_key: str, reason: str, confidence: float=1.0):
        self.agent_key = agent_key
        self.reason = reason
        self.confidence = confidence

    def to_dict(self):
        return {"agent_key": self.agent_key, "reason": self.reason, "confidence": self.confidence}


class CommonAgent(BaseAgent):
    """雅思学习智能体核心类"""

    DEFAULT_FALLBACK_MESSAGE = "抱歉，我当前无法立即解决该问题。"
    
    def __init__(self, 
                 temperature: float=0.7, 
                 enable_thinking: bool=True, 
                 use_streamer: bool=True):
        super().__init__(temperature, enable_thinking, use_streamer)
        self.agents: Dict[str, BaseAgent] = {}
        self.fallback_agent = "common_agent"
        self.history_store = RedisHistoryStore()
        self.summary_store = RedisSummaryStore()
        self.routing_keywords: Dict[str, List[str]] = {
            "listening_agent": ["听力", "listening", "听力题", "听力练习", "听写"],
            "reading_agent": ["阅读", "reading", "文章理解", "长篇理解"],
            "writing_agent": ["写作", "writing", "作文"],
            "speaking_agent": ["口语", "speaking", "口头表达"],
            "translation_agent": ["翻译", "translate", "翻译成", "译文"],
            "planning_agent": ["计划", "学习计划", "规划", "schedule", "plan"],
            "deep_search_agent": ["深度搜索", "deep search", "详细搜索", "深入了解"]
        }

    def _summarize_history(self, session_id: str, new_messages: str):
        old_summary = self.summary_store.get(session_id)
        prompt = (
            "你是一个对话摘要器，请将对话压缩为简洁、可供后续继续对话的摘要。\n"
            "要求：\n"
            "1. 保留用户目标、偏好、已确定事实\n"
            "2. 保留未解决的问题\n"
            "3. 删除寒暄、重复内容\n"
            "4. 使用中文\n\n"
            f"【已有摘要】\n{old_summary or '（无）'}\n\n"
            f"【新增对话】\n{new_messages}\n\n"
            "请输出新的【完整摘要】："
        )

        _, summary = self.qwen_llm.invoke(prompt)
        return summary.strip()
    
    def maybe_summarize(self, session_id: str):
        history = self.get_history(session_id)
        if len(history) < 12:
            return
        
        to_summarize = history[:-6]
        remain = history[-6:]

        text = "\n".join(
            f"{h['role']}: {h['content']}" for h in to_summarize
        )

        summary = self._summarize_history(session_id, text)
        self.summary_store.set(session_id, summary)

        self.history_store.clear(session_id)
        for h in remain:
            self.history_store.append(session_id, h['role'], h['content'])

    def build_context(self, session_id: str, max_chars: int = 2000) -> str:
        summary = self.summary_store.get(session_id)
        history = self.get_history(session_id)

        buf = []
        size = 0
        for h in reversed(history):
            line = f"{h['role']}: {h['content']}\n"
            if size + len(line) > max_chars:
                break
            buf.append(line)
            size += len(line)
        recent = "".join(reversed(buf))

        ctx = ""
        if summary:
            ctx += f"【对话摘要】 \n {summary}\n\n"
        ctx += f"【最近对话】\n{recent}"
        return ctx

    def register_agent(self, key: str, agent: BaseAgent, keywords: Optional[List[str]]):
        self.agents[key] = agent
        if keywords is not None:
            self.routing_keywords[key] = [k.lower() for k in keywords]     
        
    def unregister_agent(self, key: str):
        self.agents.pop(key, None)
        self.routing_keywords.pop(key, None)

    def add_user_message(self, session_id: str, content: str) -> None:
        self.history_store.append(session_id, "user", content)

    def add_assistant_message(self, session_id: str, content: str) -> None:
        self.history_store.append(session_id, "assistant", content)

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        return self.history_store.get_history(session_id)
    
    def get_langchain_history(self, session_id: str):
        msgs = []
        for h in self.get_history(session_id):
            if h["role"] == "user":
                msgs.append(HumanMessage(content=h["content"]))
            else:
                msgs.append(AIMessage(content=h["content"]))
        return msgs
    
    def history_as_text(self, session_id: str, max_chars: int = 2000) -> str:
        buf = []
        size = 0
        for h in reversed(self.get_history(session_id)):
            line = f"{h['role']}: {h['content']}\n"
            if size + len(line) > max_chars:
                break
            buf.append(line)
            size += len(line)
        return "".join(reversed(buf))

    def _keyword_route(self, query: str) -> Optional[RouterDecision]:
        q = query.lower()
        for agent_key, kws in self.routing_keywords.items():
            for kw in kws:
                try:
                    if re.search(rf"\b{re.escape(kw)}\b", q) or (any(ord(ch) > 127 for ch in kw) and kw in q):
                        if agent_key in self.agents:
                            reason = f"关键词匹配：'{kw}' -> {agent_key}"
                            return RouterDecision(agent_key, reason, confidence=0.95)
                except re.error:
                    if kw in q and agent_key in self.agents:
                        reason = f"关键词包含：'{kw}' -> {agent_key}"
                        return RouterDecision(agent_key, reason, confidence=0.9)
        return None
    
    def _llm_route(self, query: str, session_id: Optional[str] = None) -> Optional[RouterDecision]:
        if not hasattr(self, "qwen_llm") or self.qwen_llm is None:
            return None

        prompt = (
            "你是一个路由器，请根据用户问题和对话上下文选择最合适的 agent。\n"
            "返回 JSON：{\"agent\":\"xxx\",\"reason\":\"...\",\"confidence\":0.9}\n\n"
            f"agents: {list(self.agents.keys())}\n\n"
            f"context:\n{self.build_context(session_id)}\n\n"
            f"user: {query}"
        )
    
        try:
            _, raw = self.qwen_llm.invoke(prompt)
            j = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
            if j["agent"] in self.agents:
                return RouterDecision(j["agent"], j.get("reason", ""), j.get("confidence", 0.0))
        except Exception:
            return None
        
    def _select_agent(self, query: str, session_id: str) -> RouterDecision:
        return (
            self._keyword_route(query)
            or self._llm_route(query, session_id)
            or RouterDecision(self.fallback_agent, "默认回退", 0.0)
        )
    
    def common_fallback_handle(self, query: str, session_id: str) -> str:
        if not hasattr(self, "qwen_llm") or self.qwen_llm is None:
            return self.DEFAULT_FALLBACK_MESSAGE
        
        prompt = (
            "你是通用助手，只能基于已有上下文回答。\n"
            "返回 JSON：\n"
            '{"solvable":true,"response":"..."} 或 '
            '{"solvable":false,"reason":"..."}\n\n'
            f"context:\n{self.build_context(session_id)}\n\n"
            f"user:{query}"
        )

        try:
            _, raw = self.qwen_llm.invoke(prompt)
            j = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
            return j["response"] if j.get("solvable") else self.DEFAULT_FALLBACK_MESSAGE
        except Exception:
            return self.DEFAULT_FALLBACK_MESSAGE
        
    def route_and_execute(self, query: str, session_id: str) -> Dict[str, Any]:
        self.add_user_message(session_id, query)

        decision = self._select_agent(query, session_id)

        if decision.agent_key == self.fallback_agent or decision.agent_key not in self.agents:
            answer = self.common_fallback_handle(query, session_id)
        else:
            agent = self.agents[decision.agent_key]
            history = self.get_langchain_history(session_id) or self.get_history(session_id)
            answer = agent.generate_response(query, history)

        self.add_assistant_message(session_id, answer)
        
        self.maybe_summarize(session_id)

        return {
            "agent": decision.agent_key,
            "response": answer,
            "routing": decision.to_dict(),
        }
