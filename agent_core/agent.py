from .agents import SpeakingAgent, WritingAgent, ReadingAgent, ListeningAgent, \
    PlanningAgent, TranslationAgent, CommonAgent
from .agents.deep_search_agent import DeepSearchAgent
from .agents.vocabulary_agent import VocabularyAgent

# 智能体实例
speaking_agent = SpeakingAgent()
writing_agent = WritingAgent()
reading_agent = ReadingAgent()
listening_agent = ListeningAgent()
planning_agent = PlanningAgent()
translation_agent = TranslationAgent()
deep_search_agent = DeepSearchAgent()
vocabulary_agent = VocabularyAgent()
ielts_agent = CommonAgent()

# 注册智能体到CommonAgent
ielts_agent.register_agent("speaking_agent", speaking_agent, None)
ielts_agent.register_agent("writing_agent", writing_agent, None)
ielts_agent.register_agent("reading_agent", reading_agent, None)
ielts_agent.register_agent("listening_agent", listening_agent, None)
ielts_agent.register_agent("planning_agent", planning_agent, None)
ielts_agent.register_agent("translation_agent", translation_agent, None)
ielts_agent.register_agent("deep_search_agent", deep_search_agent, None)
ielts_agent.register_agent("vocabulary_agent", vocabulary_agent, None)
