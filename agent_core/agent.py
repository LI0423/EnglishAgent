from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from models.generator_model import GeneratorModel
from .tools import retrieve


class IELTSAgent:
    """雅思学习智能体核心类"""
    
    def __init__(self):
        self.generator = GeneratorModel()
        self.tools = [retrieve]
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的雅思学习智能助手，能够提供听、说、读、写四个模块的训练和评估。"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
    def generate_response(self, query: str, chat_history: List[Dict[str, str]] = None) -> str:
        """生成智能体响应"""
        if chat_history is None:
            chat_history = []
        
        # 转换聊天历史格式
        messages = []
        for msg in chat_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
        
        # 构建完整提示
        full_prompt = f"""你是一位专业的雅思学习智能助手，请根据用户的问题提供准确、有用的回答。

用户问题: {query}

请严格按照以下要求回答：
1. 回答要清晰、准确，适合英语学习者理解
2. 如果涉及雅思考试相关内容，请确保信息准确
3. 回答要具体，提供实际的学习建议和方法
4. 保持友好、鼓励的语气

请开始回答："""
        
        # 使用生成模型获取回答
        _, response = self.generator.communicate(full_prompt)
        return response
    
    def generate_personalized_plan(self, user_profile: Dict[str, Any], assessment_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成个性化学习计划"""
        prompt = f"""请作为专业的雅思学习规划师，根据用户的个人资料和评估结果，生成一份个性化的雅思学习计划。

用户资料：
- 目标分数：{user_profile.get('target_score', '未指定')}
- 当前分数：{user_profile.get('current_score', '未指定')}
- 学习时间：{user_profile.get('study_hours_per_week', '未指定')}小时/周
- 薄弱项：{user_profile.get('weaknesses', '未指定')}
- 考试日期：{user_profile.get('exam_date', '未指定')}

评估结果：
{assessment_results if assessment_results else '暂无详细评估结果'}

请生成一份详细的学习计划，包含以下内容：
1. 总体学习策略
2. 每周学习计划（建议按4-8周规划）
3. 每个模块（听、说、读、写）的针对性训练建议
4. 每日学习安排
5. 复习和模拟考试计划
6. 学习资源推荐

请使用JSON格式输出，包含以下字段：
- overall_strategy: str
- weekly_plans: [{{"week": int, "focus": str, "tasks": [str]}}]
- module_specific: {{"listening": [str], "reading": [str], "writing": [str], "speaking": [str]}}
- daily_schedule: [{{"time_slot": str, "activity": str}}]
- review_plan: [str]
- resources: [{{"type": str, "name": str, "description": str}}]
"""
        
        _, response = self.generator.communicate(prompt)
        return self._parse_personalized_plan(response)
    
    def _parse_personalized_plan(self, response: str) -> Dict[str, Any]:
        """解析个性化学习计划响应"""
        # 这里需要添加JSON解析逻辑，目前返回模拟数据
        return {
            "overall_strategy": "采用模块化训练+定期模考的策略，重点提升薄弱项，同时保持其他模块的稳定进步",
            "weekly_plans": [
                {
                    "week": 1,
                    "focus": "基础巩固",
                    "tasks": [
                        "完成雅思核心词汇500词",
                        "练习听力精听3篇",
                        "完成阅读基础训练2篇",
                        "学习写作Task1结构",
                        "进行口语话题准备"
                    ]
                },
                {
                    "week": 2,
                    "focus": "技能提升",
                    "tasks": [
                        "完成雅思核心词汇500词",
                        "练习听力精听4篇",
                        "完成阅读强化训练3篇",
                        "练习写作Task1 2篇",
                        "进行口语模拟练习"
                    ]
                }
            ],
            "module_specific": {
                "listening": [
                    "每天进行30分钟精听练习",
                    "重点练习数字和细节捕捉",
                    "听不同口音的英语材料"
                ],
                "reading": [
                    "每天完成1篇阅读练习",
                    "学习定位关键词和同义替换",
                    "练习快速扫描和略读技巧"
                ],
                "writing": [
                    "每周完成2篇Task1和1篇Task2",
                    "学习高分范文结构",
                    "练习使用高级词汇和复杂句型"
                ],
                "speaking": [
                    "每天进行15分钟口语练习",
                    "练习Part2话题准备",
                    "录制自己的回答并进行自我评估"
                ]
            },
            "daily_schedule": [
                {"time_slot": "08:00-09:00", "activity": "词汇学习"},
                {"time_slot": "09:30-11:00", "activity": "听力和阅读练习"},
                {"time_slot": "14:00-15:30", "activity": "写作练习"},
                {"time_slot": "16:00-17:00", "activity": "口语练习"},
                {"time_slot": "19:30-20:30", "activity": "复习和总结"}
            ],
            "review_plan": [
                "每周日进行一次全面复习",
                "每两周进行一次模拟考试",
                "定期回顾错题本",
                "考前一周进行密集复习"
            ],
            "resources": [
                {"type": "词汇", "name": "雅思核心词汇", "description": "包含雅思考试高频词汇"},
                {"type": "听力", "name": "剑雅真题", "description": "剑桥雅思真题集，包含真实考试听力材料"},
                {"type": "阅读", "name": "雅思阅读真经", "description": "包含大量阅读练习和技巧讲解"},
                {"type": "写作", "name": "雅思写作高分范文", "description": "包含高分范文和写作技巧"},
                {"type": "口语", "name": "雅思口语题库", "description": "包含最新口语话题和参考答案"}
            ]
        }


def _parse_evaluation_response(response: str) -> Dict[str, Any]:
    """解析评估响应"""
    # 这里需要添加JSON解析逻辑，目前返回模拟数据
    return {
        "scores": {"FC": 6.5, "LR": 6.0, "GR": 6.5, "PR": 6.0},
        "overall": 6.3,
        "rationales": [
            "流利度较好，但偶尔有停顿",
            "词汇使用基本准确，但缺乏多样性",
            "语法结构较为简单，有少量错误",
            "发音清晰，但有部分单词重音错误"
        ],
        "actionItems": [
            {
                "type": "lexical",
                "before": "very good",
                "after": "excellent/outstanding",
                "examples": ["an outstanding example"]
            },
            {
                "type": "cohesion",
                "before": "and then",
                "after": "moreover/furthermore",
                "examples": ["Furthermore, this suggests..."]
            }
        ],
        "highlights": [
            {"start": 12.3, "end": 18.7, "note": "Long pause and fillers"}
        ]
    }


class SpeakingAgent(IELTSAgent):
    """口语智能体"""
    
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的雅思口语考官和教练，能够模拟口语考试并提供详细的评估和改进建议。"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
    
    def evaluate_speaking(self, transcript: str, audio_url: Optional[str] = None) -> Dict[str, Any]:
        """评估口语表现"""
        prompt = f"""请作为专业的雅思口语考官，从以下四个维度评估学生的口语表现：
1. 流利度与连贯性(Fluency & Coherence, FC)
2. 词汇资源(Lexical Resource, LR)
3. 语法范围与准确性(Grammatical Range & Accuracy, GR)
4. 发音(Pronunciation, PR)

学生的回答：{transcript}

请提供：
- 每个维度的分数(1-9分)
- 总体分数(1-9分)
- 每个维度的详细评价
- 具体的改进建议

请使用JSON格式输出，包含以下字段：
scores: {{"FC": float, "LR": float, "GR": float, "PR": float}}
overall: float
rationales: [str]
actionItems: [{{"type": str, "before": str, "after": str, "examples": [str]}}]
highlights: [{{"start": float, "end": float, "note": str}}]
"""
        
        _, response = self.generator.communicate(prompt)
        return _parse_evaluation_response(response)


def _parse_writing_evaluation(response: str) -> Dict[str, Any]:
    """解析写作评估响应"""
    # 这里需要添加JSON解析逻辑，目前返回模拟数据
    return {
        "scores": {"TR": 7.0, "CC": 6.5, "LR": 6.5, "GRA": 6.0},
        "overall": 6.5,
        "rationales": [
            "任务回应完整，观点明确",
            "文章结构基本清晰，但衔接词使用不够多样",
            "词汇使用较为准确，但缺乏高级词汇",
            "语法结构有一定变化，但存在一些错误"
        ],
        "actionItems": [
            {
                "type": "lexical",
                "before": "important",
                "after": "crucial/significant",
                "examples": ["This is a crucial point to consider"]
            },
            {
                "type": "grammar",
                "before": "I think that is good",
                "after": "I believe this approach to be effective",
                "examples": ["I believe this method to be more efficient"]
            }
        ]
    }


class WritingAgent(IELTSAgent):
    """写作智能体"""
    
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的雅思写作考官和教练，能够评估学生的写作并提供详细的反馈和改进建议。"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
    
    def evaluate_writing(self, essay: str, task_type: str = "task2") -> Dict[str, Any]:
        """评估写作表现"""
        prompt = f"""请作为专业的雅思写作考官，从以下四个维度评估学生的{task_type}写作：
1. 任务回应(Task Response, TR)
2. 连贯与衔接(Coherence & Cohesion, CC)
3. 词汇资源(Lexical Resource, LR)
4. 语法范围与准确性(Grammatical Range & Accuracy, GRA)

学生的作文：{essay}

请提供：
- 每个维度的分数(1-9分)
- 总体分数(1-9分)
- 每个维度的详细评价
- 具体的改进建议

请使用JSON格式输出，包含以下字段：
scores: {"TR": float, "CC": float, "LR": float, "GRA": float}
overall: float
rationales: [str]
actionItems: [{"type": str, "before": str, "after": str, "examples": [str]}]
"""
        
        _, response = self.generator.communicate(prompt)
        return _parse_writing_evaluation(response)


class ReadingAgent(IELTSAgent):
    """阅读智能体"""
    
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的雅思阅读教练，能够提供阅读技巧指导和练习评估。"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
    
    def analyze_passage(self, passage: str) -> Dict[str, Any]:
        """分析阅读文章"""
        prompt = f"""请作为专业的雅思阅读教练，分析以下文章：

{passage}

请提供：
1. 文章的主题和结构
2. 关键的同义替换
3. 长难句分析
4. 阅读技巧建议

请使用JSON格式输出，包含以下字段：
主题: str
结构: str
synonymReplacements: [{"original": str, "replacement": str, "sentence": str}]
complexSentences: [{"sentence": str, "analysis": str}]
tips: [str]
"""
        
        _, response = self.generator.communicate(prompt)
        return self._parse_reading_analysis(response)
    
    def _parse_reading_analysis(self, response: str) -> Dict[str, Any]:
        """解析阅读分析响应"""
        # 这里需要添加JSON解析逻辑，目前返回模拟数据
        return {
            "主题": "气候变化对海洋生态系统的影响",
            "结构": "介绍-影响-解决方案-结论",
            "synonymReplacements": [
                {
                    "original": "impact",
                    "replacement": "effect",
                    "sentence": "The impact of climate change on marine ecosystems is significant."
                },
                {
                    "original": "solution",
                    "replacement": "approach",
                    "sentence": "Various solutions have been proposed to address this issue."
                }
            ],
            "complexSentences": [
                {
                    "sentence": "While climate change is often discussed in terms of global warming, its effects on marine ecosystems, including ocean acidification and rising sea levels, are equally concerning.",
                    "analysis": "这是一个复合句，while引导让步状语从句，主句中包含including引导的插入语，解释说明effects的具体内容。"
                }
            ],
            "tips": [
                "先浏览题目，再阅读文章",
                "注意定位关键词和同义替换",
                "练习快速扫描和略读技巧"
            ]
        }


def _parse_listening_evaluation(response: str) -> Dict[str, Any]:
    """解析听力评估响应"""
    # 这里需要添加JSON解析逻辑，目前返回模拟数据
    return {
        "overall": "听力表现良好，但在数字和细节捕捉方面存在不足",
        "errorAnalysis": [
            "数字识别错误，尤其是电话号码和日期",
            "细节信息遗漏，如说话人的职业",
            "同义替换识别困难"
        ],
        "tips": [
            "练习数字听写，提高数字敏感度",
            "注意信号词，如first, however, finally",
            "积累常见同义替换"
        ],
        "practiceRecommendations": [
            "每天进行15分钟的精听练习",
            "练习填空题和选择题",
            "听不同口音的英语材料"
        ]
    }


class ListeningAgent(IELTSAgent):
    """听力智能体"""
    
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的雅思听力教练，能够提供听力技巧指导和练习评估。"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
    
    def evaluate_listening(self, transcript: str, answers: List[str], correct_answers: List[str]) -> Dict[str, Any]:
        """评估听力表现"""
        # 计算正确率
        correct_count = sum(1 for a, ca in zip(answers, correct_answers) if a == ca)
        accuracy = correct_count / len(answers) if answers else 0
        
        prompt = f"""请作为专业的雅思听力教练，评估学生的听力表现：

听力文本：{transcript}
学生答案：{answers}
正确答案：{correct_answers}
正确率：{accuracy:.2f}

请提供：
1. 总体评价
2. 错误分析
3. 改进建议
4. 针对性练习推荐

请使用JSON格式输出，包含以下字段：
overall: str
errorAnalysis: [str]
tips: [str]
practiceRecommendations: [str]
"""
        
        _, response = self.generator.communicate(prompt)
        return _parse_listening_evaluation(response)


class PlanningAgent(IELTSAgent):
    """个性化学习计划智能体"""
    
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的雅思学习规划师，能够根据用户的个人资料和评估结果，生成个性化的雅思学习计划。"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
    
    def generate_personalized_plan(self, user_profile: Dict[str, Any], assessment_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成个性化学习计划"""
        # 计算备考时间（如果有考试日期）
        prep_time = "未指定"
        if 'exam_date' in user_profile and user_profile['exam_date'] != '未指定':
            try:
                from datetime import datetime
                exam_date = datetime.strptime(user_profile['exam_date'], '%Y-%m-%d')
                today = datetime.now()
                weeks_left = (exam_date - today).days // 7
                if weeks_left > 0:
                    prep_time = f"{weeks_left}周"
            except:
                pass
        
        prompt = f"""请作为专业的雅思学习规划师，根据用户的个人资料和评估结果，生成一份个性化的雅思学习计划。

用户资料：
- 目标分数：{user_profile.get('target_score', '未指定')}
- 当前分数：{user_profile.get('current_score', '未指定')}
- 学习时间：{user_profile.get('study_hours_per_week', '未指定')}小时/周
- 薄弱项：{user_profile.get('weaknesses', '未指定')}
- 考试日期：{user_profile.get('exam_date', '未指定')}
- 备考时间：{prep_time}

评估结果：
{assessment_results if assessment_results else '暂无详细评估结果'}

请生成一份详细的学习计划，包含以下内容：
1. 总体学习策略
2. 每周学习计划（根据备考时间调整，建议按4-12周规划）
3. 每个模块（听、说、读、写）的针对性训练建议
4. 每日学习安排（根据每周学习时间分配）
5. 复习和模拟考试计划
6. 学习资源推荐
7. 进步跟踪建议

请使用JSON格式输出，包含以下字段：
- overall_strategy: str
- weekly_plans: [{{"week": int, "focus": str, "tasks": [str]}}]
- module_specific: {{"listening": [str], "reading": [str], "writing": [str], "speaking": [str]}}
- daily_schedule: [{{"time_slot": str, "activity": str}}]
- review_plan: [str]
- resources: [{{"type": str, "name": str, "description": str}}]
- progress_tracking: [str]
"""
        
        _, response = self.generator.communicate(prompt)
        return self._parse_personalized_plan(response)
    
    def update_personalized_plan(self, original_plan: Dict[str, Any], progress: Dict[str, Any], new_assessment: Dict[str, Any] = None) -> Dict[str, Any]:
        """根据学习进度和新的评估结果更新个性化学习计划"""
        prompt = f"""请作为专业的雅思学习规划师，根据用户的原始学习计划、学习进度和新的评估结果，更新个性化的雅思学习计划。

原始学习计划：
{original_plan}

学习进度：
{progress}

新的评估结果：
{new_assessment if new_assessment else '暂无新的评估结果'}

请根据以下原则更新学习计划：
1. 保留原始计划中有效的部分
2. 调整未完成或需要改进的任务
3. 根据新的评估结果调整薄弱项训练
4. 考虑学习进度，合理安排剩余时间
5. 保持计划的可行性和针对性

请使用与原始计划相同的JSON格式输出更新后的学习计划。
"""
        
        _, response = self.generator.communicate(prompt)
        return self._parse_personalized_plan(response)
    
    def _parse_personalized_plan(self, response: str) -> Dict[str, Any]:
        """解析个性化学习计划响应"""
        # 这里需要添加JSON解析逻辑，目前返回模拟数据
        return {
            "overall_strategy": "采用模块化训练+定期模考的策略，重点提升薄弱项，同时保持其他模块的稳定进步",
            "weekly_plans": [
                {
                    "week": 1,
                    "focus": "基础巩固",
                    "tasks": [
                        "完成雅思核心词汇500词",
                        "练习听力精听3篇",
                        "完成阅读基础训练2篇",
                        "学习写作Task1结构",
                        "进行口语话题准备"
                    ]
                },
                {
                    "week": 2,
                    "focus": "技能提升",
                    "tasks": [
                        "完成雅思核心词汇500词",
                        "练习听力精听4篇",
                        "完成阅读强化训练3篇",
                        "练习写作Task1 2篇",
                        "进行口语模拟练习"
                    ]
                },
                {
                    "week": 3,
                    "focus": "模考评估",
                    "tasks": [
                        "完成1套完整模考",
                        "分析模考结果",
                        "针对性强化薄弱项",
                        "练习写作Task2 2篇",
                        "进行口语Part3练习"
                    ]
                },
                {
                    "week": 4,
                    "focus": "冲刺训练",
                    "tasks": [
                        "完成2套完整模考",
                        "复习所有错题",
                        "强化写作和口语模板",
                        "进行听力和阅读限时训练",
                        "调整心态，准备考试"
                    ]
                }
            ],
            "module_specific": {
                "listening": [
                    "每天进行30分钟精听练习",
                    "重点练习数字和细节捕捉",
                    "听不同口音的英语材料"
                ],
                "reading": [
                    "每天完成1篇阅读练习",
                    "学习定位关键词和同义替换",
                    "练习快速扫描和略读技巧"
                ],
                "writing": [
                    "每周完成2篇Task1和1篇Task2",
                    "学习高分范文结构",
                    "练习使用高级词汇和复杂句型"
                ],
                "speaking": [
                    "每天进行15分钟口语练习",
                    "练习Part2话题准备",
                    "录制自己的回答并进行自我评估"
                ]
            },
            "daily_schedule": [
                {"time_slot": "08:00-09:00", "activity": "词汇学习"},
                {"time_slot": "09:30-11:00", "activity": "听力和阅读练习"},
                {"time_slot": "14:00-15:30", "activity": "写作练习"},
                {"time_slot": "16:00-17:00", "activity": "口语练习"},
                {"time_slot": "19:30-20:30", "activity": "复习和总结"}
            ],
            "review_plan": [
                "每周日进行一次全面复习",
                "每两周进行一次模拟考试",
                "定期回顾错题本",
                "考前一周进行密集复习"
            ],
            "resources": [
                {"type": "词汇", "name": "雅思核心词汇", "description": "包含雅思考试高频词汇"},
                {"type": "听力", "name": "剑雅真题", "description": "剑桥雅思真题集，包含真实考试听力材料"},
                {"type": "阅读", "name": "雅思阅读真经", "description": "包含大量阅读练习和技巧讲解"},
                {"type": "写作", "name": "雅思写作高分范文", "description": "包含高分范文和写作技巧"},
                {"type": "口语", "name": "雅思口语题库", "description": "包含最新口语话题和参考答案"}
            ],
            "progress_tracking": [
                "每周记录各模块练习成绩",
                "使用错题本跟踪错误类型",
                "定期进行自我评估",
                "记录学习时间和完成情况",
                "考前进行模考成绩对比"
            ]
        }


class TranslationAgent(IELTSAgent):
    """翻译练习智能体"""
    
    def __init__(self):
        super().__init__()
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的英语翻译教练，能够提供中文句子翻译练习和详细的评分反馈。"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
    
    def generate_translation_question(self, difficulty: str = "medium") -> Dict[str, Any]:
        """生成翻译练习题"""
        prompt = f"""请作为专业的英语翻译教练，生成一个中文句子作为翻译练习题目。

难度级别：{difficulty}（easy/medium/hard）

请生成一个符合以下要求的中文句子：
1. 符合指定难度级别
2. 适合英语学习者练习翻译
3. 包含常见的语法结构和词汇
4. 句子长度适中

请使用JSON格式输出，包含以下字段：
- chinese_sentence: str
- difficulty: str
- topic: str
"""
        
        _, response = self.generator.communicate(prompt)
        return self._parse_translation_question(response)
    
    def check_translation(self, chinese_sentence: str, user_translation: str) -> Dict[str, Any]:
        """检查翻译并给出评价"""
        prompt = f"""请作为专业的英语翻译教练，检查用户的翻译并给出详细评价。

中文原句：{chinese_sentence}
用户翻译：{user_translation}

请从以下几个方面进行评价：
1. 准确性（Accuracy）：翻译是否准确传达了原句的意思
2. 流畅度（Fluency）：翻译是否自然流畅
3. 语法（Grammar）：是否存在语法错误
4. 词汇（Vocabulary）：词汇使用是否恰当
5. 改进建议（Suggestions）：具体的改进建议

请使用JSON格式输出，包含以下字段：
- accuracy: float（0-10分）
- fluency: float（0-10分）
- grammar: float（0-10分）
- vocabulary: float（0-10分）
- overall: float（0-10分）
- evaluation: str
- suggestions: [str]
- correct_translation: str
"""
        
        _, response = self.generator.communicate(prompt)
        return self._parse_translation_evaluation(response)
    
    def _parse_translation_question(self, response: str) -> Dict[str, Any]:
        """解析翻译题目响应"""
        # 这里需要添加JSON解析逻辑，目前返回模拟数据
        return {
            "chinese_sentence": "随着科技的发展，人们的生活方式发生了巨大变化。",
            "difficulty": "medium",
            "topic": "technology"
        }
    
    def _parse_translation_evaluation(self, response: str) -> Dict[str, Any]:
        """解析翻译评价响应"""
        # 这里需要添加JSON解析逻辑，目前返回模拟数据
        return {
            "accuracy": 8.5,
            "fluency": 8.0,
            "grammar": 9.0,
            "vocabulary": 8.5,
            "overall": 8.5,
            "evaluation": "翻译整体准确，流畅度较好，语法正确，词汇使用恰当。",
            "suggestions": [
                "可以使用'with the development of'代替'as technology develops'，更符合英语表达习惯",
                "'巨大变化'可以翻译为'dramatic changes'，比'great changes'更地道"
            ],
            "correct_translation": "With the development of technology, people's lifestyles have undergone dramatic changes."
        }


# 智能体实例
speaking_agent = SpeakingAgent()
writing_agent = WritingAgent()
reading_agent = ReadingAgent()
listening_agent = ListeningAgent()
planning_agent = PlanningAgent()
translation_agent = TranslationAgent()
ielts_agent = IELTSAgent()
