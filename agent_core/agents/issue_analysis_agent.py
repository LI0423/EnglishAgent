import logging
from typing import Dict, Any, Optional
from rag_core.intent_recognizer import IntentRecognizer
from rag_core.rag_system import RAGSystem
"""
延迟导入 agent 实例，避免在缺少第三方依赖（如 langchain_core）时包导入失败。
实际使用时 handler 内部会再导入对应的 agent 实例。
"""

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IssueAnalysisAgent:
    """分析用户问题并路由到合适的智能体（Orchestrator）"""

    def __init__(self, confidence_threshold: float = 0.4):
        self._intent = IntentRecognizer()
        # 延迟初始化 RAG，避免在导入模块时加载大型模型
        self._rag = None
        self.confidence_threshold = confidence_threshold
        self._mapping = {
            # 词汇/知识类走检索式RAG
            "synonym": self._handle_rag,
            "definition": self._handle_rag,
            "example": self._handle_rag,
            "pronunciation": self._handle_rag,
            "usage_guidance": self._handle_rag,
            "etymology": self._handle_rag,
            "word_family": self._handle_rag,
            "general": self._handle_rag,
            # 专门的能力
            "speaking": self._handle_speaking,
            "writing": self._handle_writing,
            "reading": self._handle_reading,
            "listening": self._handle_listening,
            "planning": self._handle_planning,
            "translation": self._handle_translation,
            # 新增深度搜索支持
            "deep_search": self._handle_deep_search,
        }

    def analyze_and_route(self, query: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """主入口：识别意图并路由。返回统一结构。"""
        user_context = user_context or {}
        logger.info(f"分析用户查询: {query[:100]}...")
        
        try:
            intent = self._intent.recognize_intent(query, top_k=3)
            logger.info(f"识别到意图: {intent.get('type')}, 置信度: {intent.get('confidence')}")

            # 如果意图置信度较低，先建议澄清
            if float(intent.get("confidence", 0.0)) < self.confidence_threshold:
                logger.info(f"意图置信度低，请求澄清: {intent.get('confidence')} < {self.confidence_threshold}")
                return {
                    "query": query,
                    "intent": intent,
                    "handler": None,
                    "clarify": True,
                    "message": "意图不明确，请提供更多信息或选择下面的候选意图。",
                    "candidates": intent.get("candidates", []),
                }

            itype = intent.get("type", "general")
            handler = self._mapping.get(itype, self._handle_rag)
            logger.info(f"路由到处理器: {handler.__name__}")

            result: Dict[str, Any] = {"query": query, "intent": intent, "handler": handler.__name__}
            try:
                payload = handler(query, intent, user_context)
                result["result"] = payload
                logger.info(f"处理器执行成功: {handler.__name__}")
            except Exception as e:
                error_msg = f"处理器执行失败: {str(e)}"
                result["error"] = error_msg
                logger.error(error_msg, exc_info=True)
            return result
        except Exception as e:
            error_msg = f"分析和路由失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "query": query,
                "error": error_msg,
                "message": "系统处理您的请求时出现错误，请稍后重试。"
            }

    # handlers
    def _handle_rag(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        """处理词汇/知识类问题"""
        # 延迟创建 RAGSystem 实例并执行检索式回答（减少导入时副作用）
        if self._rag is None:
            try:
                self._rag = RAGSystem()
                logger.info("RAGSystem 初始化成功")
            except Exception as e:
                logger.error(f"RAGSystem 初始化失败: {e}")
                return {"error": f"RAGSystem unavailable: {e}"}
        
        # 根据意图类型确定模块
        module_map = {
            "synonym": "vocabulary",
            "definition": "vocabulary",
            "example": "vocabulary",
            "pronunciation": "vocabulary",
            "usage_guidance": "vocabulary",
            "etymology": "vocabulary",
            "word_family": "vocabulary",
            "general": "general"
        }
        module = module_map.get(intent.get("type", "general"), "general")
        
        logger.info(f"使用RAG系统处理 {module} 类型查询")
        try:
            return self._rag.query(query, top_k=5, module=module)
        except Exception as e:
            logger.error(f"RAG查询失败: {e}")
            return {"error": f"RAG query failed: {e}"}

    def _handle_speaking(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        """处理口语相关问题"""
        transcript = ctx.get("transcript")
        logger.info(f"处理口语请求，是否有transcript: {transcript is not None}")
        
        try:
            from agent_core.agent import speaking_agent
            logger.info("speaking_agent 导入成功")
        except Exception as e:
            logger.error(f"speaking_agent 导入失败: {e}")
            return {"error": "speaking_agent not available: %s" % e}

        if transcript:
            try:
                return speaking_agent.evaluate_speaking(transcript)
            except Exception as e:
                logger.error(f"口语评估失败: {e}")
                return {"error": f"Speaking evaluation failed: {e}"}
        return {"message": "请上传口语录音或提供口语文本(transcript)以进行评估。"}

    def _handle_writing(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        """处理写作相关问题"""
        essay = ctx.get("essay")
        logger.info(f"处理写作请求，是否有essay: {essay is not None}")
        
        if essay:
            try:
                from agent_core.agent import writing_agent
                logger.info("writing_agent 导入成功")
            except Exception as e:
                logger.error(f"writing_agent 导入失败: {e}")
                return {"error": "writing_agent not available: %s" % e}
            
            try:
                return writing_agent.evaluate_writing(essay, task_type=ctx.get("task_type", "task2"))
            except Exception as e:
                logger.error(f"写作评估失败: {e}")
                return {"error": f"Writing evaluation failed: {e}"}
        return {"message": "请提供写作文本(essay)以便评估。"}

    def _handle_reading(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        """处理阅读相关问题"""
        passage = ctx.get("passage")
        logger.info(f"处理阅读请求，是否有passage: {passage is not None}")
        
        if passage:
            try:
                from agent_core.agent import reading_agent
                logger.info("reading_agent 导入成功")
            except Exception as e:
                logger.error(f"reading_agent 导入失败: {e}")
                return {"error": "reading_agent not available: %s" % e}
            
            try:
                return reading_agent.analyze_passage(passage)
            except Exception as e:
                logger.error(f"阅读分析失败: {e}")
                return {"error": f"Reading analysis failed: {e}"}
        return {"message": "请提供文章内容(passage)以便分析。"}

    def _handle_listening(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        """处理听力相关问题"""
        transcript = ctx.get("transcript", "")
        answers = ctx.get("answers", [])
        correct = ctx.get("correct_answers", [])
        logger.info(f"处理听力请求，transcript长度: {len(transcript)}, 答案数量: {len(answers)}")
        
        try:
            from agent_core.agent import listening_agent
            logger.info("listening_agent 导入成功")
        except Exception as e:
            logger.error(f"listening_agent 导入失败: {e}")
            return {"error": "listening_agent not available: %s" % e}
        
        try:
            return listening_agent.evaluate_listening(transcript, answers, correct)
        except Exception as e:
            logger.error(f"听力评估失败: {e}")
            return {"error": f"Listening evaluation failed: {e}"}

    def _handle_planning(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        """处理学习计划相关问题"""
        profile = ctx.get("user_profile", {})
        assessment = ctx.get("assessment_results")
        logger.info(f"处理学习计划请求，用户档案: {profile.get('name', '未知')}, 评估结果: {assessment is not None}")
        
        try:
            from agent_core.agent import planning_agent
            logger.info("planning_agent 导入成功")
        except Exception as e:
            logger.error(f"planning_agent 导入失败: {e}")
            return {"error": "planning_agent not available: %s" % e}
        
        try:
            return planning_agent.generate_personalized_plan(profile, assessment)
        except Exception as e:
            logger.error(f"学习计划生成失败: {e}")
            return {"error": f"Planning generation failed: {e}"}

    def _handle_translation(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        """处理翻译相关问题"""
        logger.info(f"处理翻译请求，用户翻译: {ctx.get('user_translation') is not None}, 中文句子: {ctx.get('chinese_sentence') is not None}")
        
        try:
            from agent_core.agent import translation_agent
            logger.info("translation_agent 导入成功")
        except Exception as e:
            logger.error(f"translation_agent 导入失败: {e}")
            return {"error": "translation_agent not available: %s" % e}

        try:
            if ctx.get("user_translation") and ctx.get("chinese_sentence"):
                return translation_agent.check_translation(ctx["chinese_sentence"], ctx["user_translation"])
            return translation_agent.generate_translation_question(difficulty=ctx.get("difficulty", "medium"))
        except Exception as e:
            logger.error(f"翻译处理失败: {e}")
            return {"error": f"Translation processing failed: {e}"}

    def _handle_deep_search(self, query: str, intent: Dict[str, Any], ctx: Dict[str, Any]) -> Any:
        """处理深度搜索相关问题"""
        logger.info(f"处理深度搜索请求: {query[:100]}...")
        
        try:
            from agent_core.agent import deep_search_agent
            logger.info("deep_search_agent 导入成功")
        except Exception as e:
            logger.error(f"deep_search_agent 导入失败: {e}")
            return {"error": "deep_search_agent not available: %s" % e}
        
        try:
            # 调用深度搜索智能体
            result = deep_search_agent.generate_response(query, [])
            return result
        except Exception as e:
            logger.error(f"深度搜索失败: {e}")
            return {"error": f"Deep search failed: {e}"}
