# IELTS-Agent API 接口文档

## 1. 简介

本文档提供了 IELTS-Agent 后端服务的所有 API 接口详细信息，供前端开发工程师参考使用。

## 2. 认证方式

所有需要认证的接口均使用 JWT (JSON Web Token) 进行认证。认证流程如下：

1. 用户通过 `/auth/login` 接口登录，获取 token
2. 后续请求在 HTTP 请求头中添加 `Authorization` 字段：

```
  Authorization: Bearer <token>
```

## 3. API 接口列表

### 3.1 认证模块 (Auth)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 用户登录 | /auth/login | POST | 使用用户名/手机号和密码登录 | 否 |
| 用户注册 | /auth/register | POST | 使用用户名和密码注册 | 否 |
| 手机号注册 | /auth/register/phone | POST | 使用手机号和密码注册 | 否 |
| 获取当前用户信息 | /auth/me | GET | 获取当前登录用户的信息 | 是 |

### 3.2 口语模块 (Speaking)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|
| 获取会话列表 | /speaking/sessions | GET | 获取用户的口语练习会话列表 | 是 |
| 获取会话详情 | /speaking/session/{session_id} | GET | 获取指定会话的详细信息 | 是 |
| 创建会话 | /speaking/session | POST | 创建新的口语练习会话 | 是 |
| 开始部分 | /speaking/session/{session_id}/part/{part_index}/start | POST | 开始会话的某个部分 | 是 |
| 上传音频 | /speaking/session/{session_id}/audio | POST | 上传音频片段 | 是 |
| 完成会话 | /speaking/session/{session_id}/finish | POST | 完成会话并生成 transcript | 是 |

### 3.3 评分模块 (Scoring)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 口语评分 | /scoring/speaking | POST | 对口语练习进行评分 | 是 |

### 3.4 报告模块 (Report)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 获取报告 | /report/{session_id} | GET | 获取会话的详细报告 | 是 |

### 3.5 用户档案模块 (Profile)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 获取用户档案 | /profile/me | GET | 获取当前用户的能力档案 | 是 |
| 更新用户档案 | /profile/me | PUT | 更新当前用户的能力档案 | 是 |

### 3.6 学习计划模块 (Plan)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 生成7天计划 | /plan/7d | POST | 根据用户薄弱环节生成7天学习计划 | 是 |
| 创建学习计划 | /plan/create | POST | 创建个性化学习计划 | 是 |
| 获取计划详情 | /plan/{plan_id} | GET | 获取指定学习计划的详细信息 | 是 |
| 获取用户计划列表 | /plan | GET | 获取用户的所有学习计划 | 是 |
| 更新计划状态 | /plan/{plan_id}/status | PUT | 更新学习计划的状态 | 是 |
| 创建每日任务 | /plan/{plan_id}/tasks | POST | 为学习计划创建每日任务 | 是 |
| 获取计划任务列表 | /plan/{plan_id}/tasks | GET | 获取学习计划的所有每日任务 | 是 |
| 获取指定日期任务 | /plan/{plan_id}/tasks/{date} | GET | 获取指定日期的每日任务 | 是 |
| 更新任务完成状态 | /plan/tasks/{task_id}/complete | PUT | 更新任务的完成状态 | 是 |
| 更新任务进度 | /plan/tasks/{task_id}/progress | PUT | 更新任务的进度 | 是 |
| 获取计划进度 | /plan/{plan_id}/progress | GET | 获取学习计划的执行进度 | 是 |

### 3.7 阅读模块 (Reading)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 识别同义词 | /reading/synonyms | POST | 识别文本中的常见同义替换 | 是 |
| 分析文章 | /reading/analyze | POST | 分析阅读文章的难度和结构 | 是 |
| 分析长难句 | /reading/long-sentences | POST | 分析文本中的长难句结构 | 是 |
| 获取常见同义词 | /reading/common-synonyms | GET | 获取常见同义词列表 | 是 |

### 3.8 写作模块 (Writing)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 分析Task 1写作 | /writing/task1/analyze | POST | 分析Task 1 (Academic)写作内容 | 是 |
| 保存Task 1练习 | /writing/task1/practice | POST | 保存Task 1 写作练习 | 是 |
| 获取Task 1练习历史 | /writing/task1/practices | GET | 获取Task 1 写作练习历史 | 是 |
| 获取Task 1常用结构 | /writing/task1/common-structures | GET | 获取Task 1 常用写作结构 | 是 |
| 获取Task 1常用词汇 | /writing/task1/common-vocabulary | GET | 获取Task 1 常用词汇 | 是 |

### 3.9 听力模块 (Listening)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 获取音频库 | /listening/library | GET | 获取音频库列表 | 是 |
| 获取音频文件 | /listening/file/{audio_id} | GET | 获取单个音频文件信息 | 是 |
| 开始播放 | /listening/start | POST | 开始播放音频 | 是 |
| 暂停播放 | /listening/pause | POST | 暂停播放 | 是 |
| 继续播放 | /listening/resume | POST | 继续播放 | 是 |
| 停止播放 | /listening/stop | POST | 停止播放 | 是 |
| 设置语速 | /listening/set-speed | POST | 设置播放语速 | 是 |
| 设置播放位置 | /listening/set-position | POST | 设置播放位置 | 是 |
| 获取播放状态 | /listening/status | GET | 获取当前播放状态 | 是 |
| 获取音频片段 | /listening/segment/{audio_id} | GET | 获取音频片段信息 | 是 |

### 3.10 历史记录模块 (History)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|
| 获取最近会话 | /history/sessions | GET | 获取最近的练习会话 | 是 |

### 3.11 智能体对话模块 (Chat)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 与智能体对话 | /chat | POST | 与智能体对话接口 | 是 |
| 翻译练习 | /chat/translation | POST | 翻译练习接口 | 是 |

### 3.12 诊断测试模块 (Diagnostic)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 开始诊断测试 | /diagnostic/start | POST | 开始诊断测试 | 是 |
| 提交答案 | /diagnostic/{session_id}/answer | POST | 提交诊断测试答案 | 是 |
| 获取诊断报告 | /diagnostic/{session_id}/report | GET | 获取诊断报告 | 是 |
| 完成诊断测试 | /diagnostic/{session_id}/complete | POST | 完成诊断测试 | 是 |

### 3.13 提醒模块 (Reminder)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 创建提醒 | /reminder | POST | 创建新的提醒 | 是 |
| 获取提醒列表 | /reminder | GET | 获取用户的提醒列表 | 是 |
| 获取提醒详情 | /reminder/{reminder_id} | GET | 获取提醒详情 | 是 |
| 更新提醒状态 | /reminder/{reminder_id}/status | PUT | 更新提醒状态 | 是 |
| 删除提醒 | /reminder/{reminder_id} | DELETE | 删除提醒 | 是 |
| 获取提醒偏好设置 | /reminder/preferences/me | GET | 获取当前用户的提醒偏好设置 | 是 |
| 更新提醒偏好设置 | /reminder/preferences/me | PUT | 更新当前用户的提醒偏好设置 | 是 |

### 3.14 统计模块 (Stats)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|---------|------|------|----------|----------|

| 获取统计概览 | /stats/overview | GET | 获取用户学习统计概览 | 是 |
| 获取活动列表 | /stats/activities | GET | 获取用户活动列表 | 是 |
| 获取事件列表 | /stats/events | GET | 获取用户事件列表 | 是 |
| 获取详细统计 | /stats/detailed | GET | 获取详细的学习统计数据 | 是 |

## 4. 接口详细信息

### 4.1 认证模块 (Auth)

#### 4.1.1 用户登录

**路径**: `/auth/login`

**方法**: `POST`

**功能描述**: 使用用户名/手机号和密码登录，返回 JWT token

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|

| username | string | 否 | 用户名（与phone二选一） |
| phone | string | 否 | 手机号（与username二选一） |
| password | string | 是 | 密码 |

**示例请求**:

```json
{
  "phone": "13800138000",
  "password": "your_password"
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|

| token | string | JWT token |

**示例响应**:

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### 4.1.2 用户注册

**路径**: `/auth/register`

**方法**: `POST`

**功能描述**: 使用用户名和密码注册新用户

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |
| email | string | 否 | 邮箱 |

**示例请求**:

```json
{
  "username": "new_user",
  "password": "your_password",
  "email": "user@example.com"
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| token | string | JWT token |

**示例响应**:

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### 4.1.3 手机号注册

**路径**: `/auth/register/phone`

**方法**: `POST`

**功能描述**: 使用手机号和密码注册新用户

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| phone | string | 是 | 手机号 |
| password | string | 是 | 密码 |

**示例请求**:

```json
{
  "phone": "13800138000",
  "password": "your_password"
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| success | boolean | 注册是否成功 |
| message | string | 注册结果消息 |
| data | object | 注册成功时的用户信息 |

**示例响应**:

```json
{
  "success": true,
  "message": "注册成功",
  "data": {
    "user_id": "uuid",
    "username": "user_80000000",
    "phone": "13800138000",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
}
```

#### 4.1.4 获取当前用户信息

**路径**: `/auth/me`

**方法**: `GET`

**功能描述**: 获取当前登录用户的信息

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| userId | string | 用户ID |
| username | string | 用户名 |

**示例响应**:

```json
{
  "userId": "u_demo",
  "username": "demo"
}
```

### 4.2 口语模块 (Speaking)

#### 4.2.1 获取会话列表

**路径**: `/speaking/sessions`

**方法**: `GET`

**功能描述**: 获取用户的口语练习会话列表

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| limit | integer | 否 | 每页数量，默认20 |
| offset | integer | 否 | 偏移量，默认0 |

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| id | string | 会话ID |
| topic | string | 会话主题 |
| created_at | integer | 创建时间戳 |
| transcript_id | string |  transcript ID |

**示例响应**:

```json
[
  {
    "id": "session_123",
    "topic": "General",
    "created_at": 1620000000,
    "transcript_id": "transcript_456"
  }
]
```

#### 4.2.2 创建会话

**路径**: `/speaking/session`

**方法**: `POST`

**功能描述**: 创建新的口语练习会话

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| sessionId | string | 会话ID |
| topic | string | 会话主题 |
| parts | array | 会话部分列表 |

**示例响应**:

```json
{
  "sessionId": "session_123",
  "topic": "General",
  "parts": [
    {
      "index": 1,
      "type": "part1",
      "prompt": "Do you work or study?"
    },
    {
      "index": 2,
      "type": "part2",
      "prompt": "Describe a book you recently read."
    },
    {
      "index": 3,
      "type": "part3",
      "prompt": "How do books influence society?"
    }
  ]
}
```

### 4.3 评分模块 (Scoring)

#### 4.3.1 口语评分

**路径**: `/scoring/speaking`

**方法**: `POST`

**功能描述**: 对口语练习进行评分

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| transcriptId | string | 是 | transcript ID |
| audioUrl | string | 否 | 音频URL |
| meta | object | 否 | 附加信息 |

**示例请求**:

```json
{
  "transcriptId": "transcript_456",
  "audioUrl": "http://example.com/audio.mp3"
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| scores | object | 各项评分 |
| overall | number | 总体评分 |
| rationales | array | 评分理由 |
| actionItems | array | 改进建议 |
| highlights | array | 亮点 |

**示例响应**:

```json
{
  "scores": {
    "FC": 7.5,
    "LR": 7.0,
    "GR": 6.5,
    "PR": 7.0
  },
  "overall": 7.0,
  "rationales": ["Fluency is good with minimal pauses", "Vocabulary is appropriate but could be more varied"],
  "actionItems": [
    {
      "type": "vocabulary",
      "before": "good",
      "after": "excellent",
      "examples": ["The presentation was excellent"],
      "practiceLink": "http://example.com/practice/vocabulary"
    }
  ],
  "highlights": [
    {
      "start": 10.5,
      "end": 15.2,
      "note": "Good use of linking words"
    }
  ]
}
```

### 4.4 报告模块 (Report)

#### 4.4.1 获取报告

**路径**: `/report/{session_id}`

**方法**: `GET`

**功能描述**: 获取会话的详细报告

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| summary | string | 报告摘要 |
| scores | object | 各项评分 |
| suggestions | array | 建议 |
| plan7d | object | 7天计划 |

**示例响应**:

```json
{
  "summary": "Your speaking performance is at band 7.0 level",
  "scores": {
    "FC": 7.5,
    "LR": 7.0,
    "GR": 6.5,
    "PR": 7.0,
    "overall": 7.0
  },
  "suggestions": ["Expand topic-specific vocabulary", "Use more complex sentences"],
  "plan7d": {
    "day1": ["fluency drill: 5-min monologue"],
    "day2": ["linking words practice"]
  }
}
```

### 4.5 用户档案模块 (Profile)

#### 4.5.1 获取用户档案

**路径**: `/profile/me`

**方法**: `GET`

**功能描述**: 获取当前用户的能力档案

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| user_id | string | 用户ID |
| target_band | number | 目标分数 |
| current_band_overall | number | 当前总体分数 |
| current_band_listening | number | 当前听力分数 |
| current_band_reading | number | 当前阅读分数 |
| current_band_writing | number | 当前写作分数 |
| current_band_speaking | number | 当前口语分数 |
| skill_vocabulary | number | 词汇技能 |
| skill_grammar | number | 语法技能 |
| skill_pronunciation | number | 发音技能 |
| skill_fluency | number | 流利度技能 |
| skill_coherence | number | 连贯性技能 |
| learning_total_hours | number | 总学习时长 |
| learning_sessions_count | integer | 学习会话数 |
| learning_streak_days | integer | 连续学习天数 |
| learning_avg_daily_minutes | number | 平均每日学习分钟数 |
| weaknesses | array | 薄弱环节 |
| strong_areas | array | 强项 |
| created_at | integer | 创建时间戳 |
| updated_at | integer | 更新时间戳 |

**示例响应**:

```json
{
  "user_id": "u_demo",
  "target_band": 7.0,
  "current_band_overall": 5.5,
  "current_band_listening": 5.5,
  "current_band_reading": 6.0,
  "current_band_writing": 5.0,
  "current_band_speaking": 5.5,
  "skill_vocabulary": 5.0,
  "skill_grammar": 5.5,
  "skill_pronunciation": 6.0,
  "skill_fluency": 5.0,
  "skill_coherence": 5.5,
  "learning_total_hours": 10.5,
  "learning_sessions_count": 20,
  "learning_streak_days": 5,
  "learning_avg_daily_minutes": 30,
  "weaknesses": ["lack of linking words", "limited vocabulary"],
  "strong_areas": ["pronunciation"],
  "created_at": 1620000000,
  "updated_at": 1620000000
}
```

### 4.6 学习计划模块 (Plan)

#### 4.6.1 生成7天计划

**路径**: `/plan/7d`

**方法**: `POST`

**功能描述**: 根据用户薄弱环节生成7天学习计划

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| weaknesses | array | 否 | 薄弱环节列表 |
| target_score | number | 否 | 目标分数，默认7.0 |
| daily_time_available | string | 否 | 每日可用时间，默认"1-2 hours" |

**示例请求**:

```json
{
  "weaknesses": ["lack of linking words", "limited vocabulary", "grammar errors"],
  "target_score": 7.5,
  "daily_time_available": "2 hours"
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| plan | array | 每日计划列表 |
| summary | string | 计划摘要 |
| total_hours | string | 总学习时长 |

**示例响应**:

```json
{
  "plan": [
    {
      "day": "day1",
      "focus_area": "Foundation: lack of linking words",
      "exercises": [
        {
          "skill": "speaking fluency & coherence",
          "description": "Practice using linking words",
          "time_required": "30 mins",
          "materials": ["recording device"],
          "difficulty": "intermediate"
        }
      ],
      "goals": ["Understand the core issues with lack of linking words"],
      "progress_tip": "Track time and accuracy for each exercise"
    }
  ],
  "summary": "7-day personalized IELTS study plan focusing on lack of linking words, limited vocabulary, grammar errors with a target score of 7.5.",
  "total_hours": "10.5 hours"
}
```

### 4.7 阅读模块 (Reading)

#### 4.7.1 识别同义词

**路径**: `/reading/synonyms`

**方法**: `POST`

**功能描述**: 识别文本中的常见同义替换

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| text | string | 是 | 输入文本 |
| topic | string | 否 | 文本主题，默认"general" |

**示例请求**:

```json
{
  "text": "It is important to improve your English skills to solve problems and find solutions.",
  "topic": "education"
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| results | array | 识别结果 |
| summary | string | 识别结果总结 |

**示例响应**:

```json
{
  "results": [
    {
      "original": "important",
      "synonyms": ["significant", "crucial", "vital"],
      "context": "It is important to improve",
      "position": 6
    }
  ],
  "summary": "Found 4 groups of synonyms"
}
```

### 4.8 写作模块 (Writing)

#### 4.8.1 分析Task 1写作

**路径**: `/writing/task1/analyze`

**方法**: `POST`

**功能描述**: 分析Task 1 (Academic)写作内容

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| text | string | 是 | 写作内容 |
| chart_type | string | 是 | 图表类型 |
| topic | string | 是 | 写作主题 |
| keywords | array | 否 | 关键词列表 |

**示例请求**:

```json
{
  "text": "The line graph illustrates changes in the number of people using smartphones in the UK from 2010 to 2020.",
  "chart_type": "graph",
  "topic": "Smartphone Usage",
  "keywords": ["smartphone", "usage", "trend"]
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| structure_score | integer | 结构分数 |
| content_score | integer | 内容分数 |
| vocabulary_score | integer | 词汇分数 |
| grammar_score | integer | 语法分数 |
| total_score | integer | 总分 |
| feedback | array | 反馈列表 |
| common_mistakes | array | 常见错误 |
| improvement_tips | array | 改进建议 |

**示例响应**:

```json
{
  "structure_score": 7,
  "content_score": 8,
  "vocabulary_score": 7,
  "grammar_score": 6,
  "total_score": 28,
  "feedback": [
    {
      "category": "grammar",
      "severity": "low",
      "message": "句子开头应为大写字母",
      "suggestion": "将 'the' 改为 'The'",
      "position": 0
    }
  ],
  "common_mistakes": [],
  "improvement_tips": []
}
```

### 4.9 听力模块 (Listening)

#### 4.9.1 获取音频库

**路径**: `/listening/library`

**方法**: `GET`

**功能描述**: 获取音频库列表

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| id | string | 音频ID |
| title | string | 音频标题 |
| duration | number | 音频时长（秒） |
| url | string | 音频URL |
| transcript | string | 音频转录文本 |
| difficulty | string | 难度级别 |

**示例响应**:

```json
[
  {
    "id": "audio_001",
    "title": "IELTS Listening Practice Test 1 - Section 1",
    "duration": 600.0,
    "url": "http://example.com/audio001.mp3",
    "transcript": "This is a sample transcript...",
    "difficulty": "easy"
  }
]
```

### 4.10 历史记录模块 (History)

#### 4.10.1 获取最近会话

**路径**: `/history/sessions`

**方法**: `GET`

**功能描述**: 获取最近的练习会话

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| limit | integer | 否 | 数量限制，默认10 |

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| id | string | 会话ID |
| topic | string | 会话主题 |
| type | string | 会话类型 |
| date | string | 会话日期 |
| score | number | 会话分数 |
| status | string | 会话状态 |
| duration | integer | 会话时长 |
| accuracy | number | 准确率 |

**示例响应**:

```json
[
  {
    "id": "session_123",
    "topic": "General",
    "type": "speaking",
    "date": "2023-05-01T00:00:00+00:00",
    "score": 7.0,
    "status": "completed",
    "duration": 600,
    "accuracy": 0.85
  }
]
```

### 4.11 智能体对话模块 (Chat)

#### 4.11.1 与智能体对话

**路径**: `/chat`

**方法**: `POST`

**功能描述**: 与智能体对话接口

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| query | string | 是 | 查询内容 |
| session_id | string | 是 | 会话ID |

**示例请求**:

```json
{
  "query": "How to improve my speaking fluency?",
  "session_id": "session_123"
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| agent | string | 处理智能体 |
| response | string | 响应内容 |
| routing | object | 路由信息 |

**示例响应**:

```json
{
  "agent": "speaking_agent",
  "response": "To improve your speaking fluency, practice 5-minute monologues daily...",
  "routing": {
    "confidence": 0.95,
    "reason": "Query about speaking fluency"
  }
}
```

### 4.12 诊断测试模块 (Diagnostic)

#### 4.12.1 开始诊断测试

**路径**: `/diagnostic/start`

**方法**: `POST`

**功能描述**: 开始诊断测试

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| modules | array | 是 | 测试模块列表 |
| target_time | integer | 否 | 目标测试时间 |

**示例请求**:

```json
{
  "modules": ["listening", "reading", "writing", "speaking"],
  "target_time": 3600
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| id | string | 诊断会话ID |
| user_id | string | 用户ID |
| start_time | integer | 开始时间戳 |
| modules | array | 测试模块列表 |
| estimated_questions | integer | 估算题目数量 |

**示例响应**:

```json
{
  "id": "diagnostic_123",
  "user_id": "u_demo",
  "start_time": 1620000000,
  "modules": ["listening", "reading", "writing", "speaking"],
  "estimated_questions": 25
}
```

### 4.13 提醒模块 (Reminder)

#### 4.13.1 创建提醒

**路径**: `/reminder`

**方法**: `POST`

**功能描述**: 创建新的提醒

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| type | string | 否 | 提醒类型，默认"task" |
| title | string | 是 | 提醒标题 |
| content | string | 是 | 提醒内容 |
| scheduled_at | integer | 是 | 计划时间戳 |
| channel | string | 否 | 提醒渠道，默认"app" |
| metadata | object | 否 | 附加信息 |

**示例请求**:

```json
{
  "type": "task",
  "title": "IELTS Listening Practice",
  "content": "Practice listening for 30 minutes",
  "scheduled_at": 1620000000,
  "channel": "app",
  "metadata": {
    "module": "listening",
    "duration": 30
  }
}
```

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| id | string | 提醒ID |
| user_id | string | 用户ID |
| type | string | 提醒类型 |
| title | string | 提醒标题 |
| content | string | 提醒内容 |
| scheduled_at | integer | 计划时间戳 |
| sent_at | integer | 发送时间戳 |
| status | string | 提醒状态 |
| channel | string | 提醒渠道 |
| metadata | object | 附加信息 |
| created_at | integer | 创建时间戳 |

**示例响应**:

```json
{
  "id": "reminder_123",
  "user_id": "u_demo",
  "type": "task",
  "title": "IELTS Listening Practice",
  "content": "Practice listening for 30 minutes",
  "scheduled_at": 1620000000,
  "sent_at": null,
  "status": "pending",
  "channel": "app",
  "metadata": {
    "module": "listening",
    "duration": 30
  },
  "created_at": 1619996400
}
```

### 4.14 统计模块 (Stats)

#### 4.14.1 获取统计概览

**路径**: `/stats/overview`

**方法**: `GET`

**功能描述**: 获取用户学习统计概览

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|-------|------|------|------|
| time_range | integer | 否 | 时间范围（秒），默认86400 |

**响应格式**:

| 参数名 | 类型 | 描述 |
|-------|------|------|
| total_events | integer | 总事件数 |
| event_counts | object | 事件类型计数 |
| active_days | integer | 活跃天数 |
| time_range | integer | 时间范围 |

**示例响应**:

```json
{
  "total_events": 15,
  "event_counts": {
    "speaking_session_create": 3,
    "speaking_session_finish": 2
  },
  "active_days": 5,
  "time_range": 86400
}
```

## 5. 错误处理

所有 API 接口在遇到错误时，会返回相应的 HTTP 状态码和错误信息。常见的错误状态码如下：

| 状态码 | 描述 |
|-------|------|
| 400 | 请求参数错误 |
| 401 | 未授权，认证失败 |
| 403 | 禁止访问，权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

**示例错误响应**:

```json
{
  "detail": "Invalid credentials"
}
```

## 6. 总结

本文档提供了 IELTS-Agent 后端服务的所有 API 接口详细信息，包括接口路径、方法、参数、响应格式等。前端开发工程师可以根据本文档进行接口调用，实现与后端服务的交互。

如有任何疑问或需要进一步的支持，请联系后端开发团队。
