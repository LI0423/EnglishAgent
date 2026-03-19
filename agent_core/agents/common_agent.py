import json
import logging
import re
from typing import Any, Dict, List, Optional

from agent_core.agents.issue_analysis_agent import IssueAnalysisAgent
from rag_core.agentic.schemas import AgenticRAGConfig
from rag_core.rag_system import RAGSystem
from .base_agent import BaseAgent
from langchain_core.messages import HumanMessage, AIMessage

from agent_core.history_store import RedisHistoryStore, RedisSummaryStore
from agent_core.milvus_chat_store import MilvusChatMessageStore
from agent_core.milvus_query_cache import MilvusQueryCacheStore

logger = logging.getLogger(__name__)

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
    GREETING_MESSAGE = "你好，我在。你可以问我词汇解释、写作/口语建议、学习计划或深度搜索问题。"
    SELF_INTRO_MESSAGE = "我是 IELTS Agent，你的雅思备考助手。可以帮你做词汇解释、听说读写训练建议、学习计划和深度检索。"
    AMBIGUOUS_MESSAGE = "我收到了你的输入，但意图还不够明确。你可以直接说：词汇解释、写作批改、口语练习、学习计划或深度搜索。"
    BUILTIN_WORD_EXPLANATIONS = {
        "simulate": (
            "simulate 的含义是“模拟、仿真；假装、冒充”。\n"
            "常见用法：\n"
            "1) simulate a situation/process（模拟某个场景/过程）\n"
            "2) simulate illness/emotion（装病/假装某种情绪）"
        )
    }
    WORD_EXPLAIN_FORMAT_VERSION = 2
    CACHE_MATCH_HIGH_SIMILARITY = 0.93
    CACHE_MATCH_LOW_DISTANCE = 0.07
    CACHE_REJECT_MID_LOW = 0.35
    CACHE_REJECT_MID_HIGH = 0.65
    BARE_WORD_AMBIGUOUS = {"simulate", "test", "demo", "try", "start", "go", "ok", "okay", "run"}
    
    def __init__(self, 
                 temperature: float=0.7, 
                 enable_thinking: bool=True, 
                 use_streamer: bool=True):
        super().__init__(temperature, enable_thinking, use_streamer)
        self.agents: Dict[str, BaseAgent] = {}
        self.fallback_agent = "common_agent"
        self.history_store = RedisHistoryStore()
        self.summary_store = RedisSummaryStore()
        self.message_store = MilvusChatMessageStore()
        self.query_cache_store = MilvusQueryCacheStore()
        self.issue_analysis_agent = IssueAnalysisAgent()
        self._rag_system: Optional[RAGSystem] = None
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

        _, summary = self.qwen_llm.communicate(prompt)
        return summary.strip()
    
    def maybe_summarize(self, session_id: str, user_id: Optional[str] = None):
        history = self.get_history(session_id, user_id=user_id)
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

    def build_context(self, session_id: str, max_chars: int = 2000, user_id: Optional[str] = None) -> str:
        summary = self.summary_store.get(session_id)
        history = self.get_history(session_id, user_id=user_id)

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

    def add_user_message(
        self,
        session_id: str,
        content: str,
        user_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.history_store.append(session_id, "user", content)
        current_history = self.history_store.get_history(session_id)
        self.message_store.append(
            session_id=session_id,
            user_id=str(user_id or "default"),
            role="user",
            content=content,
            turn_index=len(current_history),
            agent_key="",
            meta=meta,
        )

    def add_assistant_message(
        self,
        session_id: str,
        content: str,
        user_id: Optional[str] = None,
        agent_key: str = "",
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.history_store.append(session_id, "assistant", content)
        current_history = self.history_store.get_history(session_id)
        self.message_store.append(
            session_id=session_id,
            user_id=str(user_id or "default"),
            role="assistant",
            content=content,
            turn_index=len(current_history),
            agent_key=agent_key,
            meta=meta,
        )

    def get_history(self, session_id: str, user_id: Optional[str] = None) -> List[Dict[str, str]]:
        history = self.history_store.get_history(session_id)
        if history:
            return history
        # Redis 不可用或为空时，尝试从 Milvus 持久层回填
        rows = self.message_store.get_session_messages(
            session_id=session_id,
            user_id=str(user_id or "default"),
            limit=200,
        )
        if not rows:
            return []
        rebuilt: List[Dict[str, str]] = []
        for row in rows:
            role = str(row.get("role", "assistant"))
            content = str(row.get("content", ""))
            rebuilt.append({"role": role, "content": content})
            self.history_store.append(session_id, role, content)
        return rebuilt

    def get_persistent_history(self, session_id: str, user_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        return self.message_store.get_session_messages(session_id=session_id, user_id=user_id, limit=limit)

    def list_persistent_sessions(self, user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        return self.message_store.list_sessions(user_id=user_id, limit=limit)
    
    def get_langchain_history(self, session_id: str, user_id: Optional[str] = None):
        msgs = []
        for h in self.get_history(session_id, user_id=user_id):
            if h["role"] == "user":
                msgs.append(HumanMessage(content=h["content"]))
            else:
                msgs.append(AIMessage(content=h["content"]))
        return msgs
    
    def history_as_text(self, session_id: str, max_chars: int = 2000, user_id: Optional[str] = None) -> str:
        buf = []
        size = 0
        for h in reversed(self.get_history(session_id, user_id=user_id)):
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
    
    def _llm_route(
        self,
        query: str,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[RouterDecision]:
        if not hasattr(self, "qwen_llm") or self.qwen_llm is None:
            return None

        prompt = (
            "你是一个路由器，请根据用户问题和对话上下文选择最合适的 agent。\n"
            "返回 JSON：{\"agent\":\"xxx\",\"reason\":\"...\",\"confidence\":0.9}\n\n"
            f"agents: {list(self.agents.keys())}\n\n"
            f"context:\n{self.build_context(session_id, user_id=user_id)}\n\n"
            f"user: {query}"
        )
    
        try:
            _, raw = self.qwen_llm.communicate(prompt)
            j = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
            if j["agent"] in self.agents:
                return RouterDecision(j["agent"], j.get("reason", ""), j.get("confidence", 0.0))
        except Exception:
            return None

    @staticmethod
    def _is_ambiguous_query(query: str) -> bool:
        q = (query or "").strip().lower()
        if not q:
            return True
        vague_tokens = {
            "simulate", "test", "demo", "try", "start", "go", "ok", "okay", "run",
            "测试", "试试", "模拟", "开始", "随便",
        }
        parts = [x for x in re.split(r"\s+", q) if x]
        if len(parts) == 1 and parts[0] in vague_tokens:
            return True
        if len(q) <= 8 and q in vague_tokens:
            return True
        return False

    @staticmethod
    def _extract_meaning_words(query: str) -> List[str]:
        q_raw = (query or "").strip()
        if not q_raw:
            return []
        q = q_raw.lower()
        suffix_match = re.search(
            r"(各自的意思是什么|各自是什么意思|是什么意思|的含义|有什么含义|有啥含义|有什么意思|meaning)",
            q,
            flags=re.IGNORECASE,
        )
        if not suffix_match:
            # 追问省略句：如 “inference呢” / “那 inference 呢”
            followup_match = re.match(
                r"^(?:那|那么|那么说)?\s*([a-zA-Z][a-zA-Z\-']*)\s*(?:呢|吗|嘛|？|\?)\s*$",
                q,
                flags=re.IGNORECASE,
            )
            if followup_match:
                return [followup_match.group(1).lower()]
            compact = re.sub(r"\s+", "", q)
            for tail in ("呢", "吗", "嘛", "？", "?"):
                if compact.endswith(tail):
                    base = compact[: -len(tail)]
                    base = re.sub(r"^(那|那么|那么说)", "", base, flags=re.IGNORECASE)
                    if re.fullmatch(r"[a-zA-Z][a-zA-Z\-']*", base or ""):
                        return [base.lower()]
            # 裸词提问：如 "inference"
            bare = compact.strip()
            if re.fullmatch(r"[a-zA-Z][a-zA-Z\-']*", bare or ""):
                ambiguous_words = {"simulate", "test", "demo", "try", "start", "go", "ok", "okay", "run"}
                if bare.lower() not in ambiguous_words:
                    return [bare.lower()]
            return []
        phrase = q[:suffix_match.start()].strip()
        if not phrase:
            return []

        has_each = ("各自" in q)
        has_multi_delimiter = bool(re.search(r"(,|，|、|/|\band\b|和|\s+)", phrase, flags=re.IGNORECASE))
        tokens = [t.lower() for t in re.findall(r"[a-zA-Z][a-zA-Z\-']*", phrase)]
        if not tokens:
            return []

        unique_tokens: List[str] = []
        for token in tokens:
            if token not in unique_tokens:
                unique_tokens.append(token)

        if has_each or has_multi_delimiter:
            return unique_tokens
        return unique_tokens[-1:]

    @staticmethod
    def _extract_compare_words(query: str) -> List[str]:
        q = (query or "").strip().lower()
        if not q:
            return []
        patterns = [
            r"([a-zA-Z][a-zA-Z\-']*)\s*(?:和|与|跟|vs|v\.s\.|versus)\s*([a-zA-Z][a-zA-Z\-']*)\s*(?:有什么区别|有何区别|区别是什么|怎么区别|difference|differences?)",
            r"([a-zA-Z][a-zA-Z\-']*)\s*(?:和|与|跟|vs|v\.s\.|versus)\s*([a-zA-Z][a-zA-Z\-']*)\s*(?:呢|吗|嘛|？|\?)\s*$",
            r"(?:difference|differences?)\s*(?:between|of)?\s*([a-zA-Z][a-zA-Z\-']*)\s*(?:and|vs|versus)\s*([a-zA-Z][a-zA-Z\-']*)",
        ]
        for p in patterns:
            m = re.search(p, q, flags=re.IGNORECASE)
            if m:
                w1 = m.group(1).lower().strip()
                w2 = m.group(2).lower().strip()
                if w1 and w2 and w1 != w2:
                    return [w1, w2]
        return []

    @staticmethod
    def _parse_pair_followup_intent(query: str) -> Optional[str]:
        q = (query or "").strip().lower()
        if not q:
            return None
        if q in {"1", "1.", "①"}:
            return "meaning"
        if q in {"2", "2.", "②"}:
            return "compare"
        if any(k in q for k in ["意思", "含义", "解释", "meaning"]):
            return "meaning"
        if any(k in q for k in ["区别", "不同", "difference"]):
            return "compare"
        return None

    def _find_latest_word_pair_context(self, session_id: str, user_id: Optional[str] = None) -> List[str]:
        history = self.get_history(session_id, user_id=user_id)
        if not history:
            return []
        # 跳过当前轮刚写入的用户输入，向前找最近一组词对上下文
        scan = history[:-1] if len(history) > 0 else history
        for msg in reversed(scan):
            content = str(msg.get("content", "") or "")
            pair = self._extract_compare_words(content) or self._extract_ambiguous_word_pair(content)
            if len(pair) == 2:
                return pair
            m = re.search(
                r"`([a-zA-Z][a-zA-Z\-']*)`\s*和\s*`([a-zA-Z][a-zA-Z\-']*)`",
                content,
                flags=re.IGNORECASE,
            )
            if m:
                w1, w2 = m.group(1).lower(), m.group(2).lower()
                if w1 != w2:
                    return [w1, w2]
        return []

    def _generate_compare_response(self, w1: str, w2: str) -> str:
        if hasattr(self, "qwen_llm") and self.qwen_llm is not None:
            prompt = (
                "你是英语词汇老师。请比较两个英文词的区别。\n"
                "请严格按模板输出，不要加粗，不要输出JSON：\n"
                f"【{w1} vs {w2}】\n"
                "核心区别：...\n"
                "语气/使用场景：...\n"
                f"{w1} 例句：...\n"
                f"{w1} 中文：...\n"
                f"{w2} 例句：...\n"
                f"{w2} 中文：...\n"
                "易错点：...\n"
            )
            try:
                _, ans = self.qwen_llm.communicate(prompt, temperature=0.2, max_tokens=520)
                if ans and ans.strip():
                    return ans.strip()
            except Exception:
                pass
        return (
            f"【{w1} vs {w2}】\n"
            "核心区别：两者词形接近，但含义和用法不同。\n"
            f"{w1} 与 {w2} 使用语境不同。\n"
            "你可以给我一个具体句子，我帮你判断该用哪个词。"
        )

    def _generate_dual_meaning_response(self, w1: str, w2: str) -> str:
        if hasattr(self, "qwen_llm") and self.qwen_llm is not None:
            prompt = (
                "你是英语词汇教练。请分别解释两个英文词。\n"
                "请严格按以下模板输出，不要加粗，不要输出JSON：\n"
                "【word】\n"
                "核心含义：...\n"
                "常见词性：...\n"
                "英文例句：...\n"
                "中文释义：...\n\n"
                f"目标词：{w1}, {w2}"
            )
            try:
                _, ans = self.qwen_llm.communicate(prompt, temperature=0.2, max_tokens=620)
                if ans and ans.strip():
                    return self._normalize_meaning_response(ans, [w1, w2])
            except Exception:
                pass
        return (
            f"【{w1}】\n核心含义：常见英文词。\n常见词性：名词/动词（依语境）\n英文例句：Please provide a sentence with {w1}.\n中文释义：请提供包含 {w1} 的句子，我可按语境细化。\n\n"
            f"【{w2}】\n核心含义：常见英文词。\n常见词性：名词/动词（依语境）\n英文例句：Please provide a sentence with {w2}.\n中文释义：请提供包含 {w2} 的句子，我可按语境细化。"
        )

    def _resolve_pair_followup(self, query: str, session_id: str, user_id: Optional[str] = None) -> Optional[str]:
        intent = self._parse_pair_followup_intent(query)
        if not intent:
            return None
        pair = self._find_latest_word_pair_context(session_id, user_id=user_id)
        if len(pair) != 2:
            return None
        w1, w2 = pair
        if intent == "compare":
            return self._generate_compare_response(w1, w2)
        return self._generate_dual_meaning_response(w1, w2)

    @staticmethod
    def _extract_ambiguous_word_pair(query: str) -> List[str]:
        """识别仅给出两个单词但未说明意图（词义/区别）的输入。"""
        q = (query or "").strip().lower()
        if not q:
            return []
        # 已明确是对比意图则不归到歧义对
        if CommonAgent._extract_compare_words(q):
            return []
        # 明确是词义提问也不归到歧义对
        if CommonAgent._extract_meaning_words(q):
            return []

        patterns = [
            r"^\s*([a-zA-Z][a-zA-Z\-']*)\s*(?:和|与|跟|and|vs|v\.s\.|versus|,|，|/)\s*([a-zA-Z][a-zA-Z\-']*)\s*$",
            r"^\s*([a-zA-Z][a-zA-Z\-']*)\s+([a-zA-Z][a-zA-Z\-']*)\s*$",
        ]
        for p in patterns:
            m = re.match(p, q, flags=re.IGNORECASE)
            if m:
                w1, w2 = m.group(1).lower(), m.group(2).lower()
                if w1 != w2:
                    return [w1, w2]
        return []

    @staticmethod
    def _high_priority_common_reason(query: str) -> Optional[str]:
        q = (query or "").strip().lower()
        if not q:
            return "空输入直达通用助手"
        greeting_patterns = [
            "你好", "您好", "hi", "hello", "hey", "早上好", "中午好", "下午好", "晚上好",
        ]
        if any(p in q for p in greeting_patterns):
            return "问候语直达通用助手"
        self_intro_patterns = [
            "介绍一下你自己",
            "自我介绍",
            "你是谁",
            "what are you",
            "who are you",
        ]
        if any(p in q for p in self_intro_patterns):
            return "自我介绍直达通用助手"
        if CommonAgent._extract_meaning_words(query):
            return "词义请求直达通用助手"
        if CommonAgent._extract_compare_words(query):
            return "词汇对比请求直达通用助手"
        if CommonAgent._extract_ambiguous_word_pair(query):
            return "词汇歧义请求澄清直达通用助手"
        q_compact = re.sub(r"\s+", "", q)
        if re.fullmatch(r"[a-zA-Z][a-zA-Z\-']*", q_compact or "") and q_compact not in CommonAgent.BARE_WORD_AMBIGUOUS:
            return "裸词词义请求直达通用助手"
        if CommonAgent._is_followup_sentence_request(query):
            return "造句续写直达通用助手"
        if CommonAgent._extract_sentence_word(query):
            return "造句请求直达通用助手"
        if CommonAgent._is_ambiguous_query(query):
            return "模糊输入收紧到通用助手"
        return None

    @staticmethod
    def _extract_sentence_word(query: str) -> Optional[str]:
        q = (query or "").strip()
        patterns = [
            r"用\s*([a-zA-Z][a-zA-Z\-']*)\s*(写一个句子|写一个例句|造句|例句)",
            r"给我用\s*([a-zA-Z][a-zA-Z\-']*)\s*(写一个句子|写一个例句|造句|例句)",
            r"([a-zA-Z][a-zA-Z\-']*)\s*(写一个句子|写一个例句|造句|例句)",
            r"(?:write|make)\s+(?:a\s+)?sentence\s+(?:with|using)\s+([a-zA-Z][a-zA-Z\-']*)",
            r"(?:give|show)\s+(?:me\s+)?(?:an?\s+)?example\s+sentence\s+(?:with|using)\s+([a-zA-Z][a-zA-Z\-']*)",
        ]
        for pattern in patterns:
            m = re.search(pattern, q, flags=re.IGNORECASE)
            if m:
                return m.group(1).lower()
        return None

    def _extract_followup_sentence_word(
        self,
        query: str,
        session_id: str,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        q = (query or "").strip().lower()
        followup_patterns = [
            r"再给我写一个",
            r"再写一个",
            r"再来一个",
            r"再来一句",
            r"再给我来一个",
            r"one more",
            r"another one",
        ]
        if not any(re.search(p, q) for p in followup_patterns):
            return None

        history = self.get_history(session_id, user_id=user_id)
        # 跳过当前这条用户输入，向前找最近一次“用某词造句”请求
        for msg in reversed(history[:-1] if len(history) > 0 else history):
            if msg.get("role") != "user":
                continue
            word = self._extract_sentence_word(msg.get("content", ""))
            if word:
                return word
        return None

    @staticmethod
    def _is_followup_sentence_request(query: str) -> bool:
        q = (query or "").strip().lower()
        followup_patterns = [
            r"再给我写一个",
            r"再写一个",
            r"再来一个",
            r"再来一句",
            r"再给我来一个",
            r"one more",
            r"another one",
        ]
        return any(re.search(p, q) for p in followup_patterns)

    def _generate_sentence_for_word(self, word: str) -> str:
        if hasattr(self, "qwen_llm") and self.qwen_llm is not None:
            sentence_prompt = (
                "你是英语老师。用户想要用一个词造句。\n"
                "输出要求：\n"
                "1) 给出1个自然、地道的英文句子\n"
                "2) 句子长度适中（10-18词）\n"
                "3) 给出对应中文翻译\n"
                "4) 不要输出JSON\n\n"
                f"目标词：{word}"
            )
            try:
                _, sentence_answer = self.qwen_llm.communicate(sentence_prompt, temperature=0.3, max_tokens=220)
                if sentence_answer and sentence_answer.strip():
                    return sentence_answer.strip()
            except Exception:
                pass
        return (
            f'Example: I am practicing the word "{word}" in this sentence.\n'
            f'中文：我正在这个句子里练习单词“{word}”。'
        )
        
    def _select_agent(self, query: str, session_id: str, user_id: Optional[str] = None) -> RouterDecision:
        """使用IssueAnalysisAgent增强路由能力"""
        reason = self._high_priority_common_reason(query)
        if reason:
            return RouterDecision(self.fallback_agent, reason, 1.0)
        q = (query or "").strip().lower()
        deep_search_markers = ["深度搜索", "deep search", "深入检索", "多源搜索", "学术检索"]
        if any(m in q for m in deep_search_markers) and "deep_search_agent" in self.agents:
            return RouterDecision("deep_search_agent", "深度搜索显式优先路由", 0.99)

        try:
            # 尝试使用IssueAnalysisAgent进行智能路由
            analysis_result = self.issue_analysis_agent.analyze_and_route(query)
            
            # 如果IssueAnalysisAgent成功识别意图且有对应的处理器
            if not analysis_result.get("clarify") and analysis_result.get("handler"):
                handler_name = analysis_result["handler"]
                
                # 将IssueAnalysisAgent的处理器映射到CommonAgent的智能体
                handler_to_agent = {
                    "_handle_rag": "vocabulary_agent",
                    "_handle_speaking": "speaking_agent",
                    "_handle_writing": "writing_agent",
                    "_handle_reading": "reading_agent",
                    "_handle_listening": "listening_agent",
                    "_handle_planning": "planning_agent",
                    "_handle_translation": "translation_agent",
                    "_handle_deep_search": "deep_search_agent"
                }
                
                agent_key = handler_to_agent.get(handler_name, self.fallback_agent)
                
                # 确保映射的智能体存在
                if agent_key in self.agents:
                    reason = f"IssueAnalysisAgent 路由: {analysis_result.get('intent', {}).get('type', 'general')}"
                    confidence = float(analysis_result.get('intent', {}).get('confidence', 0.9))
                    return RouterDecision(agent_key, reason, confidence)
        except Exception as e:
            # 如果IssueAnalysisAgent失败，回退到原来的路由方式
            print(f"IssueAnalysisAgent 路由失败，回退到默认路由: {e}")
        
        # 回退到原来的路由方式
        return (
            self._keyword_route(query)
            or self._llm_route(query, session_id, user_id=user_id)
            or RouterDecision(self.fallback_agent, "默认回退", 0.0)
        )
    
    def common_fallback_handle(self, query: str, session_id: str, user_id: Optional[str] = None) -> str:
        q = (query or "").strip().lower()
        greeting_patterns = [
            "你好", "您好", "hi", "hello", "hey", "早上好", "中午好", "下午好", "晚上好",
        ]
        if any(p in q for p in greeting_patterns):
            return self.GREETING_MESSAGE
        self_intro_patterns = [
            "介绍一下你自己",
            "自我介绍",
            "你是谁",
            "what are you",
            "who are you",
        ]
        if any(p in q for p in self_intro_patterns):
            return self.SELF_INTRO_MESSAGE
        pair_followup_answer = self._resolve_pair_followup(query, session_id, user_id=user_id)
        if pair_followup_answer:
            return pair_followup_answer
        if self._is_ambiguous_query(query):
            return self.AMBIGUOUS_MESSAGE
        if self._is_followup_sentence_request(query):
            followup_word = self._extract_followup_sentence_word(query, session_id, user_id=user_id)
            if followup_word:
                return self._generate_sentence_for_word(followup_word)
            return "可以的。请告诉我你想用哪个单词造句，比如：用 simulate 写一个句子。"
        compare_words = self._extract_compare_words(query)
        if len(compare_words) == 2:
            w1, w2 = compare_words
            return self._generate_compare_response(w1, w2)
        ambiguous_pair = self._extract_ambiguous_word_pair(query)
        if len(ambiguous_pair) == 2:
            w1, w2 = ambiguous_pair
            return (
                f"你是想了解 `{w1}` 和 `{w2}` 的“意思”，还是想比较它们的“区别”？\n"
                f"你可以直接回复：\n"
                f"1) `{w1}` 和 `{w2}` 的意思\n"
                f"2) `{w1}` 和 `{w2}` 的区别"
            )
        sentence_word = self._extract_sentence_word(query)
        if sentence_word:
            return self._generate_sentence_for_word(sentence_word)
        # 词汇释义直答：支持单词和“多个词各自是什么意思”
        meaning_words = self._extract_meaning_words(query)
        if not meaning_words:
            q_compact = re.sub(r"\s+", "", q)
            if re.fullmatch(r"[a-zA-Z][a-zA-Z\-']*", q_compact or "") and q_compact not in self.BARE_WORD_AMBIGUOUS:
                meaning_words = [q_compact.lower()]
        if meaning_words:
            if len(meaning_words) > 1 and hasattr(self, "qwen_llm") and self.qwen_llm is not None:
                words_txt = ", ".join(meaning_words)
                explain_prompt = (
                    "你是英语词汇教练。请分别解释多个英文词。\n"
                    "请严格按以下模板输出，不要加粗，不要输出JSON：\n"
                    "【word】\n"
                    "核心含义：...\n"
                    "常见词性：...\n"
                    "英文例句：...\n"
                    "中文释义：...\n\n"
                    "要求：\n"
                    "1) 每个词都必须完整输出以上4行\n"
                    "2) 全中文讲解，英文例句保留英文\n"
                    "3) 不要添加额外小标题\n\n"
                    f"目标词：{words_txt}"
                )
                try:
                    _, meaning_answer = self.qwen_llm.communicate(explain_prompt, temperature=0.2, max_tokens=600)
                    if meaning_answer and meaning_answer.strip():
                        return self._normalize_meaning_response(meaning_answer, meaning_words)
                except Exception:
                    pass
                return "\n".join(
                    f"{w}: 常见英文词。你可以给我一个包含该词的句子，我会按语境精确解释。"
                    for w in meaning_words
                )

            word = meaning_words[0]
            # 优先动态释义，避免“只对写死词条可用”
            if hasattr(self, "qwen_llm") and self.qwen_llm is not None:
                explain_prompt = (
                    "你是英语词汇教练。请用中文解释一个英文词。\n"
                    "请严格按以下模板输出，不要加粗，不要输出JSON：\n"
                    "【word】\n"
                    "核心含义：...\n"
                    "常见词性：...\n"
                    "英文例句：...\n"
                    "中文释义：...\n\n"
                    "要求：\n"
                    "1) 仅输出1个英文例句与对应中文释义\n"
                    "2) 不要添加额外小标题\n\n"
                    f"目标词：{word}"
                )
                try:
                    _, meaning_answer = self.qwen_llm.communicate(explain_prompt, temperature=0.2, max_tokens=400)
                    if meaning_answer and meaning_answer.strip():
                        return self._normalize_meaning_response(meaning_answer, [word])
                except Exception:
                    pass
            if word in self.BUILTIN_WORD_EXPLANATIONS:
                return self.BUILTIN_WORD_EXPLANATIONS[word]
            return f"{word} 是常见英文词。你可以给我一句包含该词的句子，我会按语境精确解释。"

        if not hasattr(self, "qwen_llm") or self.qwen_llm is None:
            return self.DEFAULT_FALLBACK_MESSAGE
        
        prompt = (
            "你是通用助手，只能基于已有上下文回答。\n"
            "返回 JSON：\n"
            '{"solvable":true,"response":"..."} 或 '
            '{"solvable":false,"reason":"..."}\n\n'
            f"context:\n{self.build_context(session_id, user_id=user_id)}\n\n"
            f"user:{query}"
        )

        try:
            _, raw = self.qwen_llm.communicate(prompt)
            j = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
            return j["response"] if j.get("solvable") else self.DEFAULT_FALLBACK_MESSAGE
        except Exception:
            return self.DEFAULT_FALLBACK_MESSAGE

    @staticmethod
    def _build_agentic_config(overrides: Optional[Dict[str, Any]]) -> AgenticRAGConfig:
        if not overrides:
            return AgenticRAGConfig()
        allowed_fields = set(AgenticRAGConfig.__dataclass_fields__.keys())
        safe_payload = {k: v for k, v in overrides.items() if k in allowed_fields}
        return AgenticRAGConfig(**safe_payload)

    def _should_try_query_cache(self, query: str) -> bool:
        q = (query or "").strip()
        if not q or len(q) < 2:
            return False
        if self._is_followup_sentence_request(q):
            return False
        greeting_patterns = ["你好", "您好", "hi", "hello", "hey"]
        if any(p in q.lower() for p in greeting_patterns):
            return False
        return True

    def _response_format_version_for_query(self, query: str) -> int:
        if self._extract_meaning_words(query):
            return self.WORD_EXPLAIN_FORMAT_VERSION
        return 1

    @staticmethod
    def _normalize_meaning_response(answer: str, words: List[str]) -> str:
        text = (answer or "").strip()
        if not text:
            return text
        if not words:
            return text
        first_word = words[0]
        # 修正模型偶发输出："【word】\\naccount" -> "【account】"
        pattern = re.compile(r"^\s*【\s*word\s*】\s*\n\s*([a-zA-Z][a-zA-Z\-']*)", flags=re.IGNORECASE)
        m = pattern.search(text)
        if m:
            w = m.group(1).lower()
            return pattern.sub(f"【{w}】", text, count=1)
        # 如果第一段仍是占位符，兜底替换为目标词
        text = re.sub(r"^\s*【\s*word\s*】", f"【{first_word}】", text, count=1, flags=re.IGNORECASE)
        return text

    def _is_cacheable_answer(self, answer: str) -> bool:
        text = (answer or "").strip()
        if not text:
            return False
        blocked = [
            self.DEFAULT_FALLBACK_MESSAGE,
            "请求失败，请稍后重试。",
            "对话处理失败",
            "Invalid token",
            "该问题超出当前智能体的处理能力",
        ]
        return not any(x in text for x in blocked)

    def _judge_cache_match(
        self,
        query: str,
        candidate_query: str,
        candidate_answer: str,
        score: float,
    ) -> bool:
        # Milvus COSINE 可能返回 similarity（越大越好）或 distance（越小越好）
        # 先用数值强规则短路，减少 LLM 判定开销。
        numeric_hint_match = False
        numeric_hint_reject = False
        if 0.0 <= score <= 1.0:
            numeric_hint_match = (
                score >= self.CACHE_MATCH_HIGH_SIMILARITY
                or score <= self.CACHE_MATCH_LOW_DISTANCE
            )
            numeric_hint_reject = (
                self.CACHE_REJECT_MID_LOW <= score <= self.CACHE_REJECT_MID_HIGH
            )
        elif score > 1.0:
            numeric_hint_match = score >= self.CACHE_MATCH_HIGH_SIMILARITY
            numeric_hint_reject = score < 0.6
        if numeric_hint_match:
            return True
        if numeric_hint_reject:
            return False

        if not hasattr(self, "qwen_llm") or self.qwen_llm is None:
            return False
        prompt = (
            "你是缓存命中判定器。请判断候选答案能否直接回答当前用户问题。\n"
            "只输出JSON：{\"match\":true/false,\"reason\":\"...\"}\n\n"
            f"当前问题：{query}\n"
            f"候选问题：{candidate_query}\n"
            f"候选答案：{candidate_answer}\n"
        )
        try:
            _, raw = self.qwen_llm.communicate(prompt, temperature=0.0, max_tokens=120)
            j = json.loads(raw[raw.find("{") : raw.rfind("}") + 1])
            return bool(j.get("match", False))
        except Exception:
            return False

    def _try_query_cache_hit(self, query: str, user_id: str) -> Optional[Dict[str, Any]]:
        if not self.query_cache_store.enabled() or not self._should_try_query_cache(query):
            return None
        expected_format_version = self._response_format_version_for_query(query)
        query_meaning_words = self._extract_meaning_words(query)
        exact_candidates = self.query_cache_store.get_exact(user_id=user_id, query=query, limit=1)
        candidates = exact_candidates or self.query_cache_store.search_similar(user_id=user_id, query=query, top_k=2)
        llm_judge_used = 0
        max_llm_judge = 1
        for c in candidates:
            c_query = str(c.get("query", "")).strip()
            c_answer = str(c.get("answer", "")).strip()
            score = float(c.get("score", 0.0))
            meta = c.get("meta", {}) if isinstance(c.get("meta"), dict) else {}
            cached_version = int(meta.get("format_version", 1))
            if cached_version < expected_format_version:
                continue
            if not c_query or not c_answer:
                continue
            # 词义问法改写场景：若提取到相同词集，直接视为可复用
            if query_meaning_words:
                candidate_words = self._extract_meaning_words(c_query)
                if candidate_words and set(candidate_words) == set(query_meaning_words):
                    cache_id = str(c.get("cache_id", "")).strip()
                    if cache_id:
                        self.query_cache_store.touch(cache_id)
                    return c

            # 非强匹配时，限制每次请求最多一次 LLM 判定，控制开销
            if llm_judge_used >= max_llm_judge:
                continue
            if self._judge_cache_match(query, c_query, c_answer, score):
                cache_id = str(c.get("cache_id", "")).strip()
                if cache_id:
                    self.query_cache_store.touch(cache_id)
                return c
            llm_judge_used += 1
        return None

    def _execute_agentic_rag(
        self,
        query: str,
        module: str,
        session_id: str,
        user_id: str,
        rag_config: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if self._rag_system is None:
            self._rag_system = RAGSystem()
        cfg = self._build_agentic_config(rag_config)
        return self._rag_system.query_agentic(
            question=query,
            module=module,
            config=cfg,
            session_id=session_id,
            user_id=user_id,
            return_legacy_payload=True,
        )
        
    def route_and_execute(
        self,
        query: str,
        session_id: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        user_context = user_context or {}
        user_id = str(user_context.get("user_id") or "default")
        self.add_user_message(session_id, query, user_id=user_id)

        followup_answer = self._resolve_pair_followup(query, session_id, user_id=user_id)
        if followup_answer:
            self.add_assistant_message(
                session_id,
                followup_answer,
                user_id=user_id,
                agent_key=self.fallback_agent,
                meta={
                    "routing": RouterDecision(self.fallback_agent, "词汇对比多轮追问承接", 1.0).to_dict(),
                    "rag": None,
                },
            )
            self.maybe_summarize(session_id, user_id=user_id)
            return {
                "agent": self.fallback_agent,
                "response": followup_answer,
                "routing": RouterDecision(self.fallback_agent, "词汇对比多轮追问承接", 1.0).to_dict(),
                "rag": None,
            }

        cache_hit = self._try_query_cache_hit(query=query, user_id=user_id)
        if cache_hit:
            cached_answer = str(cache_hit.get("answer", "")).strip() or self.DEFAULT_FALLBACK_MESSAGE
            cached_agent = str(cache_hit.get("agent_key", "")).strip() or self.fallback_agent
            self.add_assistant_message(
                session_id,
                cached_answer,
                user_id=user_id,
                agent_key=cached_agent,
                meta={
                    "rag": {
                        "cache_hit": True,
                        "cache_id": cache_hit.get("cache_id"),
                        "cache_score": cache_hit.get("score"),
                    },
                    "routing": RouterDecision(cached_agent, "向量缓存命中", 0.98).to_dict(),
                },
            )
            self.maybe_summarize(session_id, user_id=user_id)
            return {
                "agent": cached_agent,
                "response": cached_answer,
                "routing": RouterDecision(cached_agent, "向量缓存命中", 0.98).to_dict(),
                "rag": {
                    "cache_hit": True,
                    "cache_id": cache_hit.get("cache_id"),
                    "cache_score": cache_hit.get("score"),
                },
            }

        # 高优先级通用请求（问候/词义/造句等）优先执行，避免被检索链路吞掉
        direct_reason = self._high_priority_common_reason(query)
        if direct_reason:
            answer = self.common_fallback_handle(query, session_id, user_id=user_id)
            self.add_assistant_message(
                session_id,
                answer,
                user_id=user_id,
                agent_key=self.fallback_agent,
                meta={
                    "routing": RouterDecision(self.fallback_agent, direct_reason, 1.0).to_dict(),
                    "rag": None,
                },
            )
            if self._is_cacheable_answer(answer):
                self.query_cache_store.put(
                    user_id=user_id,
                    query=query,
                    answer=answer,
                    agent_key=self.fallback_agent,
                    meta={
                        "source": "direct_common",
                        "session_id": session_id,
                        "format_version": self._response_format_version_for_query(query),
                    },
                )
            self.maybe_summarize(session_id, user_id=user_id)
            return {
                "agent": self.fallback_agent,
                "response": answer,
                "routing": RouterDecision(self.fallback_agent, direct_reason, 1.0).to_dict(),
                "rag": None,
            }

        decision = self._select_agent(query, session_id, user_id=user_id)
        rag_payload: Optional[Dict[str, Any]] = None
        enable_agentic_rag = bool(user_context.get("enable_agentic_rag", False))
        rag_config = user_context.get("rag_config") or {}

        # 仅在检索型代理启用 Agentic RAG，避免影响评分/生成型工作流
        rag_agent_map = {
            "vocabulary_agent": "vocabulary",
            "deep_search_agent": "deep_search",
        }
        if enable_agentic_rag and decision.agent_key in rag_agent_map:
            try:
                rag_payload = self._execute_agentic_rag(
                    query=query,
                    module=rag_agent_map[decision.agent_key],
                    session_id=session_id,
                    user_id=user_id,
                    rag_config=rag_config,
                )
                answer = str(rag_payload.get("answer", "")).strip() or self.DEFAULT_FALLBACK_MESSAGE
            except Exception as e:
                logger.exception("Agentic RAG failed, fallback to non-RAG response: %s", e)
                rag_payload = {
                    "accepted": False,
                    "fallback_action": "rag_error_fallback",
                    "error": str(e),
                }
                if decision.agent_key == self.fallback_agent or decision.agent_key not in self.agents:
                    answer = self.common_fallback_handle(query, session_id, user_id=user_id)
                else:
                    agent = self.agents[decision.agent_key]
                    history = self.get_langchain_history(session_id, user_id=user_id) or self.get_history(session_id, user_id=user_id)
                    answer = agent.generate_response(query, history)
        elif decision.agent_key == self.fallback_agent or decision.agent_key not in self.agents:
            answer = self.common_fallback_handle(query, session_id, user_id=user_id)
        else:
            agent = self.agents[decision.agent_key]
            history = self.get_langchain_history(session_id, user_id=user_id) or self.get_history(session_id, user_id=user_id)
            try:
                answer = agent.generate_response(query, history)
            except Exception as e:
                logger.exception("Agent execution failed for %s, fallback to common: %s", decision.agent_key, e)
                answer = self.common_fallback_handle(query, session_id, user_id=user_id)

        self.add_assistant_message(
            session_id,
            answer,
            user_id=user_id,
            agent_key=decision.agent_key,
            meta={
                "routing": decision.to_dict(),
                "rag": rag_payload,
            },
        )
        if self._is_cacheable_answer(answer):
            self.query_cache_store.put(
                user_id=user_id,
                query=query,
                answer=answer,
                agent_key=decision.agent_key,
                meta={
                    "source": "normal_route",
                    "session_id": session_id,
                    "format_version": self._response_format_version_for_query(query),
                },
            )
        
        self.maybe_summarize(session_id, user_id=user_id)

        return {
            "agent": decision.agent_key,
            "response": answer,
            "routing": decision.to_dict(),
            "rag": rag_payload,
        }
