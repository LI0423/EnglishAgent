# EnglishAgent

基于人工智能的雅思学习智能体，为用户提供全方位的智能学习伙伴，通过个性化教学、精准评估和即时反馈，帮助用户高效备考雅思考试，实现目标分数。

## 项目概述

EnglishAgent是一个基于AI的智能学习系统，专为雅思考试备考设计。它集成了多种智能体模块，包括听力、阅读、写作、口语、翻译、深度搜索等，为用户提供个性化的学习体验和精准的能力评估。

### 核心价值

- **个性化学习**：根据用户水平和学习进度，提供定制化的学习计划和内容
- **智能评估**：AI驱动的写作批改、口语评估和能力诊断
- **即时反馈**：实时提供学习反馈和改进建议
- **全方位覆盖**：涵盖雅思考试的所有模块和题型
- **高效备考**：智能规划学习路径，帮助用户快速提升

## 功能特性

### 核心模块

- **听力模块**：自适应练习、专项题型训练、精听与泛听模式、场景词汇库
- **阅读模块**：同义替换智能识别、长难句分析器、逻辑结构梳理、阅读策略训练
- **写作模块**：AI智能批改与评分、思路生成与头脑风暴、范文库与精析、模板与句型库
- **口语模块**：AI模拟口语考官、多维度口语评估、即时反馈与报告、话题思路拓展
- **翻译模块**：双向翻译练习、智能评分与反馈、主题分类练习、难点解析
- **深度搜索模块**：多源信息整合、迭代式搜索、智能摘要生成、学术资源检索

### 智能学习系统

- **个性化学习计划**：智能计划生成、计划执行与跟踪、智能提醒与督促、计划调整与优化
- **诊断与测评**：初始水平诊断、薄弱点诊断、阶段性测评、诊断报告生成
- **错题管理系统**：智能错题收集、错因分析、间隔重复复习、错题导出与分享
- **词汇学习模块**：智能词汇本、词汇学习策略、词汇测试与巩固、词汇复习机制、场景化词汇

### 增值功能

- **游戏化与激励体系**：积分系统、等级与成就、打卡与激励、排行榜机制
- **社区与社交功能**：学习社区、学习小组、口语对练、作文互评、好友与动态
- **多平台支持**：移动端App、Web端、小程序
- **离线功能**：词汇学习、听力材料、错题复习、学习记录

## 系统架构

### 智能体层级结构

- **通用智能体（CommonAgent）**：作为系统入口，负责接收用户查询并进行路由
- **专用智能体**：
  - ListeningAgent：处理听力相关问题
  - ReadingAgent：处理阅读相关问题
  - WritingAgent：处理写作相关问题
  - SpeakingAgent：处理口语相关问题
  - TranslationAgent：处理翻译相关问题
  - PlanningAgent：处理学习计划相关问题
  - DeepSearchAgent：处理深度搜索相关问题
  - VocabularyAgent：处理词汇相关问题
- **IssueAnalysisAgent**：分析用户问题并路由到合适的智能体

### 技术栈

- **自然语言处理**：语音识别(ASR)、自然语言理解(NLU)、文本生成(NLG)、情感分析
- **个性化学习引擎**：用户画像、推荐系统、知识图谱
- **智能体系统**：基于LangChain或自定义框架实现
- **计划执行系统**：基于Celery或Redis的定时任务系统
- **数据存储**：Redis、Milvus向量数据库
- **前端**：移动端App (iOS & Android)、Web端、小程序

## 快速开始

### 环境要求

- Python 3.10+
- Redis
- Milvus向量数据库
- 相关Python依赖

### 安装

1. **克隆仓库**

```bash
git clone https://github.com/yourusername/EnglishAgent.git
cd EnglishAgent
```

2. **创建虚拟环境**

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
```

3. **安装依赖**

```bash
pip install -r requirements.txt
```

4. **配置环境变量**

创建 `.env` 文件并配置相关环境变量：

```
# 数据库配置
REDIS_URL=redis://localhost:6379
MILVUS_URL=localhost:19530

# 模型配置
EMBEDDING_MODEL=your_embedding_model
GENERATOR_MODEL=your_generator_model
RERANKER_MODEL=your_reranker_model

# API密钥
DASHSCOPE_API_KEY=your_dashscope_api_key
```

5. **启动服务**

```bash
# 启动Redis服务
redis-server

# 启动Milvus服务
# 参考Milvus官方文档

# 启动应用
python script/run.py
```

### 使用示例

#### 1. 基础对话

```python
from agent_core.agent import ielts_agent

# 发送用户查询
result = ielts_agent.route_and_execute("如何提高英语口语？", "session_id_123")
print(result["response"])
```

#### 2. 写作批改

```python
from agent_core.agent import writing_agent

# 提交作文进行批改
essay = "Some people think that technology is making our lives easier, while others believe it is making them more complicated. Discuss both views and give your own opinion."
result = writing_agent.evaluate_writing(essay, "task2")
print(result)
```

#### 3. 口语评估

```python
from agent_core.agent import speaking_agent

# 提交口语录音文本进行评估
transcript = "I think technology has changed our lives a lot in recent years. It has made communication easier and more convenient."
result = speaking_agent.evaluate_speaking(transcript)
print(result)
```

#### 4. 深度搜索

```python
from agent_core.agent import deep_search_agent

# 进行深度搜索
query = "雅思写作Task 2教育类话题的最新趋势"
result = deep_search_agent.generate_response(query, [])
print(result)
```

## 商业模式

### 会员订阅

| 会员类型 | 价格 | 权益 |
| :--- | :--- | :--- |
| **月度会员** | ¥98/月 | 全功能解锁、无限AI批改、专属学习计划 |
| **季度会员** | ¥268/季 | 月度会员权益 + 优先客服 + 专属礼遇 |
| **年度会员** | ¥998/年 | 季度会员权益 + 1次免费重考机会 + 专属周边 |
| **终身会员** | ¥2,998/次 | 永久会员权益 + 未来所有新功能 |

### 单次付费

| 服务类型 | 价格 | 说明 |
| :--- | :--- | :--- |
| **AI作文批改** | ¥15/篇 | 单篇付费，无订阅用户 |
| **口语模考** | ¥30/次 | 全真模拟考试+详细反馈 |
| **诊断测评** | ¥49/次 | 完整水平诊断+详细报告 |
| **专项突破** | ¥99/模块 | 单一模块深度训练课程 |

### 增值服务

| 服务类型 | 价格 | 说明 |
| :--- | :--- | :--- |
| **一对一辅导** | ¥200/小时 | 专业老师1对1辅导 |
| **作文人工批改** | ¥50/篇 | 资深教师详细批改 |
| **学习顾问** | ¥99/月 | 专属学习顾问跟踪指导 |
| **定制学习计划** | ¥199/次 | 资深顾问量身定制 |

## 技术栈

### 核心技术

- **后端**：Python 3.10+, FastAPI
- **数据库**：Redis, Milvus
- **AI模型**：
  - 语音识别：Whisper
  - 文本嵌入：Sentence-BERT
  - 文本生成：Qwen
  - 重排序：Cross-Encoder
- **智能体框架**：LangChain
- **任务队列**：Celery
- **前端**：React Native (App), React (Web), 小程序

### 非功能性需求

- **性能**：核心功能响应时间低于3秒
- **可用性**：界面简洁直观，学习路径清晰
- **可靠性**：系统稳定，故障率低，保障用户数据安全
- **可扩展性**：架构设计便于未来增加新功能

## 未来规划

### 版本路线图

| 版本 | 目标时间 | 核心功能 |
| :--- | :--- | :--- |
| **MVP** | 第1个月 | 听说读写基础练习、AI批改、用户系统 |
| **v1.0** | 第2个月 | 学习计划、词汇学习、错题本、诊断测评 |
| **v1.5** | 第4个月 | 社区功能、口语对练、游戏化激励 |
| **v2.0** | 第6个月 | 高级功能、企业版、API开放 |

### 长期愿景

- **拓展考试类型**：支持多邻国、PTE等其他英语考试
- **全球化**：支持多语言界面和本地化内容
- **教育生态**：构建完整的英语学习生态系统
- **AI能力提升**：持续优化AI模型，提高评估准确性和学习效果

## 贡献指南

我们欢迎社区贡献，包括代码改进、功能开发、bug修复、文档完善等。

### 开发流程

1. Fork 仓库
2. 创建分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

### 代码规范

- 遵循 PEP 8 编码规范
- 编写清晰的文档和注释
- 确保代码测试覆盖率
- 提交前运行代码格式化工具

## 许可证

本项目采用 MIT 许可证。详情请参阅 [LICENSE](LICENSE) 文件。

## 联系我们

- **官方网站**：[https://englishagent.com](https://englishagent.com)
- **邮箱**：contact@englishagent.com
- **社交媒体**：
  - Twitter: @EnglishAgentAI
  - Facebook: EnglishAgent
  - Instagram: @englishagent.ai

---

**EnglishAgent** - 您的智能雅思学习伙伴

*让每一次学习都更有价值* 🚀
