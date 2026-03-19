# IELTS-Agent API 接口文档

## 1. 简介

本文档提供了 IELTS-Agent 后端服务的所有 API 接口详细信息，供前端开发工程师参考使用。

## 2. 认证方式

所有需要认证的接口均使用 JWT (JSON Web Token) 进行认证。认证流程如下：

1. 用户通过 `/auth/login` 接口登录，获取 token
2. 后续请求在 HTTP 请求头中添加 `Authorization` 字段：

```http
  Authorization: Bearer <token>
```

## 3. API 接口列表

### 3.1 认证模块 (Auth)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 用户登录 | /auth/login | POST | 使用用户名/手机号和密码登录 | 否 |
| 用户注册 | /auth/register | POST | 使用用户名和密码注册 | 否 |
| 手机号注册 | /auth/register/phone | POST | 使用手机号和密码注册 | 否 |
| 请求重置验证码 | /auth/password/reset/code/request | POST | 请求邮箱/短信验证码用于重置密码 | 否 |
| 验证码重置密码 | /auth/password/reset/code/confirm | POST | 使用验证码重置密码 | 否 |
| 获取当前用户信息 | /auth/me | GET | 获取当前登录用户的信息 | 是 |

说明：出于安全考虑，重置 token/验证码默认不在响应中返回；可通过环境变量 `AUTH_EXPOSE_RESET_TOKEN` / `AUTH_EXPOSE_RESET_CODE` 在开发环境显式开启。

### 3.2 口语模块 (Speaking)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 获取会话列表 | /speaking/sessions | GET | 获取用户的口语练习会话列表 | 是 |
| 获取会话详情 | /speaking/session/{session_id} | GET | 获取指定会话的详细信息 | 是 |
| 创建会话 | /speaking/session | POST | 创建新的口语练习会话 | 是 |
| 开始部分 | /speaking/session/{session_id}/part/{part_index}/start | POST | 开始会话的某个部分 | 是 |
| 上传音频 | /speaking/session/{session_id}/audio | POST | 上传音频片段 | 是 |
| 完成会话 | /speaking/session/{session_id}/finish | POST | 完成会话并生成 transcript | 是 |

### 3.3 评分模块 (Scoring)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 口语评分 | /scoring/speaking | POST | 对口语练习进行评分 | 是 |

### 3.4 报告模块 (Report)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 获取报告 | /report/{session_id} | GET | 获取会话的详细报告 | 是 |

### 3.5 用户档案模块 (Profile)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 获取用户档案 | /profile/me | GET | 获取当前用户的能力档案 | 是 |
| 更新用户档案 | /profile/me | PUT | 更新当前用户的能力档案 | 是 |

### 3.6 学习计划模块 (Plan)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

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
|--------- |------|------|----------|----------|

| 识别同义词 | /reading/synonyms | POST | 识别文本中的常见同义替换 | 是 |
| 分析文章 | /reading/analyze | POST | 分析阅读文章的难度和结构 | 是 |
| 分析长难句 | /reading/long-sentences | POST | 分析文本中的长难句结构 | 是 |
| 获取常见同义词 | /reading/common-synonyms | GET | 获取常见同义词列表 | 是 |
| 获取阅读题库版本 | /reading/quiz/version | GET | 获取阅读题库版本与来源 | 是 |
| 生成阅读测验 | /reading/quiz/generate | POST | 生成阅读题目（可按难度/题型筛选） | 是 |
| 提交阅读测验 | /reading/quiz/submit | POST | 提交答案并返回正确率，错题自动入库 | 是 |

### 3.8 写作模块 (Writing)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 分析Task 1写作 | /writing/task1/analyze | POST | 分析Task 1 (Academic)写作内容 | 是 |
| 保存Task 1练习 | /writing/task1/practice | POST | 保存Task 1 写作练习 | 是 |
| 获取Task 1练习历史 | /writing/task1/practices | GET | 获取Task 1 写作练习历史 | 是 |
| 获取Task 1常用结构 | /writing/task1/common-structures | GET | 获取Task 1 常用写作结构 | 是 |
| 获取Task 1常用词汇 | /writing/task1/common-vocabulary | GET | 获取Task 1 常用词汇 | 是 |

### 3.9 听力模块 (Listening)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 获取音频库 | /listening/library | GET | 获取音频库列表 | 是 |
| 获取音频库版本 | /listening/library/version | GET | 获取音频库版本与来源 | 是 |
| 获取听力题库版本 | /listening/quiz/version | GET | 获取听力题库版本与来源 | 是 |
| 生成听力测验 | /listening/quiz/generate | POST | 生成听力测验题目 | 是 |
| 提交听力测验 | /listening/quiz/submit | POST | 提交答案并返回正确率，错题自动入库 | 是 |
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
|--------- |------|------|----------|----------|

| 获取最近会话 | /history/sessions | GET | 获取最近的练习会话 | 是 |

### 3.11 智能体对话模块 (Chat)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 与智能体对话 | /chat | POST | 与智能体对话接口 | 是 |
| 翻译练习 | /chat/translation | POST | 翻译练习接口 | 是 |

### 3.12 诊断测试模块 (Diagnostic)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 开始诊断测试 | /diagnostic/start | POST | 开始诊断测试 | 是 |
| 提交答案 | /diagnostic/{session_id}/answer | POST | 提交诊断测试答案 | 是 |
| 获取诊断报告 | /diagnostic/{session_id}/report | GET | 获取诊断报告 | 是 |
| 完成诊断测试 | /diagnostic/{session_id}/complete | POST | 完成诊断测试 | 是 |
| 获取题库版本 | /diagnostic/bank/version | GET | 获取诊断题库版本与各模块题量 | 是 |
| 获取题库健康状态 | /diagnostic/bank/health | GET | 获取题库加载状态、总题量与fallback标记 | 是 |
| 重新加载题库 | /diagnostic/bank/reload | POST | 在线重载题库并返回最新健康状态 | 是 |

### 3.13 提醒模块 (Reminder)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 创建提醒 | /reminder | POST | 创建新的提醒 | 是 |
| 获取提醒列表 | /reminder | GET | 获取用户的提醒列表 | 是 |
| 获取提醒详情 | /reminder/{reminder_id} | GET | 获取提醒详情 | 是 |
| 更新提醒状态 | /reminder/{reminder_id}/status | PUT | 更新提醒状态 | 是 |
| 删除提醒 | /reminder/{reminder_id} | DELETE | 删除提醒 | 是 |
| 获取提醒偏好设置 | /reminder/preferences/me | GET | 获取当前用户的提醒偏好设置 | 是 |
| 更新提醒偏好设置 | /reminder/preferences/me | PUT | 更新当前用户的提醒偏好设置 | 是 |

### 3.14 统计模块 (Stats)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 获取统计概览 | /stats/overview | GET | 获取用户学习统计概览 | 是 |
| 获取活动列表 | /stats/activities | GET | 获取用户活动列表 | 是 |
| 获取事件列表 | /stats/events | GET | 获取用户事件列表 | 是 |
| 获取详细统计 | /stats/detailed | GET | 获取详细的学习统计数据 | 是 |

### 3.15 订阅与支付模块 (Subscription)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 获取订阅状态 | /subscription/status | GET | 获取当前会员状态与权益 | 是 |
| 发起订阅 | /subscription/subscribe | POST | 创建订阅订单 | 是 |
| 单次购买 | /payment/purchase | POST | 购买单次服务（如作文批改） | 是 |
| 交易历史 | /payment/history | GET | 获取交易记录 | 是 |

### 3.16 同步模块 (Sync)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 批量同步 | /sync/batch | POST | 上传离线操作记录 | 是 |

### 3.17 反馈与支持模块 (Support)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 提交反馈 | /support/feedback | POST | 提交普通产品建议或Bug | 是 |
| 报错/纠错 | /support/report_error | POST | 针对AI内容（如幻觉）报错 | 是 |

### 3.18 系统模块 (System)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 系统状态 | /system/status | GET | 获取系统维护状态/公告 | 否 |
| 动态配置 | /system/config | GET | 获取客户端配置（功能开关等） | 否 |

### 3.19 词汇模块 (Vocabulary)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 获取词汇列表 | /vocabulary | GET | 获取用户词汇本 | 是 |
| 添加词汇 | /vocabulary/add | POST | 添加词汇到个人词本 | 是 |
| 开始词汇学习会话 | /vocabulary/learn/session | POST | 随机抽取学习词汇 | 是 |
| 生成词汇测试 | /vocabulary/test/generate | POST | 生成词汇测试题（选择/拼写/填空） | 是 |
| 提交词汇测试 | /vocabulary/test/submit | POST | 提交答案并返回正确率 | 是 |
| 获取到期词汇 | /vocabulary/due | GET | 获取到期复习词汇 | 是 |
| 提交词汇复习 | /vocabulary/{vocab_id}/review | POST | 更新词汇掌握度并刷新下次复习时间 | 是 |
| 获取词汇统计 | /vocabulary/stats/summary | GET | 获取词汇总量/到期量/来源分布 | 是 |

### 3.20 错题本模块 (Mistakes)

| 接口名称 | 路径 | 方法 | 功能描述 | 认证要求 |
|--------- |------|------|----------|----------|

| 获取错题列表 | /mistakes | GET | 获取错题（支持按类型/模块筛选） | 是 |
| 创建错题 | /mistakes | POST | 新增一条错题记录 | 是 |
| 获取到期错题 | /mistakes/due | GET | 获取到期复习错题 | 是 |
| 错题分析 | /mistakes/analysis | GET | 获取错因、难度、题型分布统计 | 是 |
| 导出错题 | /mistakes/export | GET | 导出错题（json/csv） | 是 |
| 导入错题 | /mistakes/import | POST | 批量导入错题 | 是 |
| 更新错题状态 | /mistakes/{id}/review | POST | 更新错题掌握程度 | 是 |
| 错题统计摘要 | /mistakes/stats/summary | GET | 获取错题总量与模块分布 | 是 |

## 4. 接口详细信息

### 4.1 认证模块 (Auth)

#### 4.1.1 用户登录

**路径**: `/auth/login`

**方法**: `POST`

**功能描述**: 使用用户名/手机号和密码登录，返回 JWT token

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

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
|------- |------|------|

| token | string | JWT token |

**示例响应**:

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### 4.7.2 生成阅读测验

**路径**: `/reading/quiz/generate`

**方法**: `POST`

**功能描述**: 生成阅读测验题目，支持按难度和题型过滤。

#### 4.7.3 提交阅读测验

**路径**: `/reading/quiz/submit`

**方法**: `POST`

**功能描述**: 提交阅读测验答案并返回正确率；答错自动入错题本（`module=reading`, `question_type=reading_quiz`）。

#### 4.1.2 用户注册

**路径**: `/auth/register`

**方法**: `POST`

**功能描述**: 使用用户名和密码注册新用户

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

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
|------- |------|------|

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
|------- |------|------|------|

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
|------- |------|------|

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
|------- |------|------|

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
|------- |------|------|------|

| limit | integer | 否 | 每页数量，默认20 |
| offset | integer | 否 | 偏移量，默认0 |

**响应格式**:

| 参数名 | 类型 | 描述 |
|------- |------|------|

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
|------- |------|------|

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

**行为说明**:
- 仅允许评分当前登录用户自己的 transcript（跨用户 transcriptId 将返回 404）。
- 对低于 6.5 的维度（FC/LR/GR/PR）会自动沉淀到错题本（`module=speaking`, `question_type=speaking_assessment`）。

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

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
|------- |------|------|

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
|------- |------|------|

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
|------- |------|------|

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
|------- |------|------|------|

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
|------- |------|------|

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
|------- |------|------|------|

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
|------- |------|------|

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

**行为说明**:
- 中高严重度反馈会自动沉淀到错题本（`module=writing`, `question_type=writing_task1`）。
- 低分维度（structure/content/vocabulary/grammar）会写入聚合弱项，便于后续复习。

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

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
|------- |------|------|

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
|------- |------|------|

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

#### 4.9.2 获取音频库版本

**路径**: `/listening/library/version`

**方法**: `GET`

**功能描述**: 返回当前音频库的版本、来源和资源数量（用于排查资源是否正确加载）

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**示例响应**:

```json
{
  "version": "listening-audio-v1",
  "source": "file",
  "count": 3
}
```

#### 4.9.3 生成听力测验

**路径**: `/listening/quiz/generate`

**方法**: `POST`

**功能描述**: 按难度或音频筛选生成听力测验题目

**示例请求**:

```json
{
  "count": 5,
  "difficulty": "intermediate",
  "audio_id": "audio_002"
}
```

#### 4.9.4 提交听力测验

**路径**: `/listening/quiz/submit`

**方法**: `POST`

**功能描述**: 提交听力测验答案并返回正确率；答错题目自动写入错题本（`module=listening`，`question_type=listening_quiz`）

### 4.10 历史记录模块 (History)

#### 4.10.1 获取最近会话

**路径**: `/history/sessions`

**方法**: `GET`

**功能描述**: 获取最近的练习会话

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

| limit | integer | 否 | 数量限制，默认10 |

**响应格式**:

| 参数名 | 类型 | 描述 |
|------- |------|------|

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
|------- |------|------|------|

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
|------- |------|------|

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
|------- |------|------|------|

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
|------- |------|------|

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
  "estimated_questions": 8,
  "bank_version": "v1",
  "next_question": {
    "question_id": "rd_i_1",
    "question": "Which heading best matches paragraph 4?",
    "options": ["economic decline", "technology adoption", "policy failure", "population ageing"],
    "time_limit": 90,
    "module": "reading",
    "difficulty": "intermediate",
    "analysis_hint": "先定位关键词，再看上下文语义。 当前为进阶题，注意准确和速度平衡。"
  }
}
```

#### 4.12.2 提交诊断答案

**路径**: `/diagnostic/{session_id}/answer`

**方法**: `POST`

**功能描述**: 提交当前题答案或空提交拉取下一题。当前实现每次仅允许提交 1 题，且 `question_id` 必须匹配当前 `pending_question`。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|
| answers | array | 是 | 答案数组，可为空数组用于拉取下一题 |

**示例请求**:

```json
{
  "answers": [
    {
      "question_id": "rd_i_1",
      "answer": "technology adoption",
      "time_taken": 38
    }
  ]
}
```

**示例响应**:

```json
{
  "next_question": {
    "question_id": "rd_a_1",
    "question": "T/F/NG: The text proves causation rather than correlation.",
    "options": ["true", "false", "not given"],
    "time_limit": 120,
    "module": "reading",
    "difficulty": "advanced",
    "analysis_hint": "先定位关键词，再看上下文语义。 当前为高阶题，注意推断与反证。"
  },
  "estimated_ability": 6.3,
  "last_result": {
    "question_id": "rd_i_1",
    "module": "reading",
    "difficulty": "intermediate",
    "is_correct": true,
    "expected_answer": "technology adoption",
    "user_answer": "technology adoption",
    "explanation": "reading 题目 rd_i_1：建议先定位关键信息，再排除干扰项。",
    "error_tags": []
  }
}
```

#### 4.12.3 获取题库版本

**路径**: `/diagnostic/bank/version`

**方法**: `GET`

**功能描述**: 返回题库版本和各模块各难度题量。

**示例响应**:

```json
{
  "version": "v1",
  "source": "file",
  "path": "backend/data/diagnostic_question_bank.v1.json",
  "modules": {
    "reading": { "basic": 100, "intermediate": 100, "advanced": 100 },
    "listening": { "basic": 100, "intermediate": 100, "advanced": 100 }
  }
}
```

#### 4.12.4 获取题库健康状态

**路径**: `/diagnostic/bank/health`

**方法**: `GET`

**功能描述**: 返回题库版本、来源、总题量、是否 fallback、最近加载时间。

#### 4.12.5 重新加载题库

**路径**: `/diagnostic/bank/reload`

**方法**: `POST`

**功能描述**: 触发在线重载题库，并返回最新健康状态。

#### 4.12.6 获取诊断历史趋势

**路径**: `/diagnostic/history/summary`

**方法**: `GET`

**功能描述**: 获取最近诊断历史、趋势方向（up/down/flat/insufficient_data）与最近两次分数变化。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|
| limit | integer | 否 | 返回历史条数，默认 10，最大 50 |

**示例响应**:

```json
{
  "total_reports": 3,
  "trend": "up",
  "latest_overall_band": 6.5,
  "previous_overall_band": 6.0,
  "delta_overall_band": 0.5,
  "history": [
    { "report_id": "r_new", "session_id": "s_new", "overall_band": 6.5, "generated_at": 2000, "module_scores": [] },
    { "report_id": "r_old", "session_id": "s_old", "overall_band": 6.0, "generated_at": 1000, "module_scores": [] }
  ]
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
|------- |------|------|------|

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
|------- |------|------|

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
|------- |------|------|------|

| time_range | integer | 否 | 时间范围（秒），默认86400 |

**响应格式**:

| 参数名 | 类型 | 描述 |
|------- |------|------|

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

### 4.15 订阅与支付模块 (Subscription)

#### 4.15.1 获取订阅状态

**路径**: `/subscription/status`

**方法**: `GET`

**功能描述**: 获取当前会员状态与权益

**认证要求**: 需要在请求头中添加 `Authorization: Bearer <token>`

**响应格式**:

| 参数名 | 类型 | 描述 |
|------- |------|------|

| is_vip | boolean | 是否VIP |
| vip_type | string | VIP类型（monthly/yearly/lifetime） |
| expire_at | integer | 过期时间戳 |
| quotas | object | 剩余权益（如本月剩余批改次数） |

#### 4.15.2 单次购买

**路径**: `/payment/purchase`

**方法**: `POST`

**功能描述**: 购买单次服务（如作文批改）

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

| product_id | string | 是 | 商品ID（如 `essay_correction_single`） |
| payment_method | string | 是 | 支付方式（wechat/alipay/apple） |

### 4.16 同步模块 (Sync)

#### 4.16.1 批量同步

**路径**: `/sync/batch`

**方法**: `POST`

**功能描述**: 上传离线操作记录，解决数据冲突

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

| records | array | 是 | 离线操作记录列表 |
| last_sync_time | integer | 是 | 上次同步时间 |

**响应格式**:

| 参数名 | 类型 | 描述 |
|------- |------|------|

| success_count | integer | 成功同步条数 |
| conflicts | array | 冲突记录（需客户端处理） |

### 4.17 反馈与支持模块 (Support)

#### 4.17.1 报错/纠错

**路径**: `/support/report_error`

**方法**: `POST`

**功能描述**: 针对AI内容（如幻觉）报错

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

| content_id | string | 是 | 报错内容ID（如 `transcript_123`） |
| error_type | string | 是 | 错误类型（hallucination/offensive/irrelevant） |
| description | string | 否 | 错误描述 |

### 4.18 系统模块 (System)

#### 4.18.1 动态配置

**路径**: `/system/config`

**方法**: `GET`

**功能描述**: 获取客户端配置（功能开关等）

**响应格式**:

| 参数名 | 类型 | 描述 |
|------- |------|------|

| version | string | 最新版本号 |
| min_version | string | 最低强制更新版本号 |
| feature_flags | object | 功能开关（如 `enable_voice_chat`: true） |

### 4.19 词汇模块 (Vocabulary)

#### 4.19.1 获取词汇列表

**路径**: `/vocabulary`

**方法**: `GET`

**功能描述**: 获取用户词汇本。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|
| limit | integer | 否 | 返回条数，默认 100 |

#### 4.19.2 添加词汇

**路径**: `/vocabulary/add`

**方法**: `POST`

**功能描述**: 向个人词汇本添加词条。

#### 4.19.3 获取到期词汇

**路径**: `/vocabulary/due`

**方法**: `GET`

**功能描述**: 获取已到复习时间的词汇。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|
| limit | integer | 否 | 返回条数，默认 100 |

#### 4.19.4 提交词汇复习

**路径**: `/vocabulary/{vocab_id}/review`

**方法**: `POST`

**功能描述**: 更新词汇掌握度，并按掌握度重排下次复习时间。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|
| mastery_delta | number | 否 | 掌握度增量，默认 0.15 |

#### 4.19.5 获取词汇统计

**路径**: `/vocabulary/stats/summary`

**方法**: `GET`

**功能描述**: 获取词汇总量、到期复习量、平均掌握度、来源分布。

#### 4.19.6 生成词汇测试

**路径**: `/vocabulary/test/generate`

**方法**: `POST`

**功能描述**: 生成词汇测试题，会返回 `test_id` 和问题列表。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|
| mode | string | 否 | `multiple_choice` / `spelling` / `fill_blank`，默认 `multiple_choice` |
| count | integer | 否 | 题目数量，默认 5 |

#### 4.19.7 提交词汇测试

**路径**: `/vocabulary/test/submit`

**方法**: `POST`

**功能描述**: 提交词汇测试答案并返回正确率与逐题结果。

**示例请求**:

```json
{
  "test_id": "test_123",
  "answers": [
    { "question_id": "q_1", "answer": "abandon" }
  ]
}
```

### 4.20 错题本模块 (Mistakes)

#### 4.20.1 获取错题列表

**路径**: `/mistakes`

**方法**: `GET`

**功能描述**: 获取错题（支持按类型/模块筛选）

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|

| module | string | 否 | 模块筛选（listening/reading/writing） |
| error_type | string | 否 | 错误类型筛选 |

#### 4.20.2 获取到期错题

**路径**: `/mistakes/due`

**方法**: `GET`

**功能描述**: 获取已到复习时间的错题列表。

#### 4.20.3 错题分析

**路径**: `/mistakes/analysis`

**方法**: `GET`

**功能描述**: 返回错题总量、到期量、平均掌握度、错因分布、难度分布、题型分布。

#### 4.20.4 导出错题

**路径**: `/mistakes/export`

**方法**: `GET`

**功能描述**: 导出当前用户错题数据，支持 JSON 或 CSV。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|
| format | string | 否 | 导出格式，`json`/`csv`，默认 `json` |
| module | string | 否 | 按模块筛选 |
| limit | integer | 否 | 导出条数，默认 1000，最大 5000 |

#### 4.20.5 导入错题

**路径**: `/mistakes/import`

**方法**: `POST`

**功能描述**: 批量导入错题（JSON）。

**示例请求**:

```json
{
  "items": [
    {
      "module": "reading",
      "question_id": "rd_i_1",
      "question_type": "diagnostic",
      "error_type": "keyword_mismatch",
      "content": "sample question",
      "user_answer": "A",
      "correct_answer": "B",
      "explanation": "sample",
      "difficulty": "intermediate",
      "tags": ["keyword_mismatch"]
    }
  ]
}
```

#### 4.20.6 更新错题复习状态

**路径**: `/mistakes/{mistake_id}/review`

**方法**: `POST`

**功能描述**: 更新掌握度并按掌握度重排下次复习时间。

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
|------- |------|------|------|
| mastery_delta | number | 否 | 掌握度增量，默认 0.2 |

#### 4.20.7 错题统计摘要

**路径**: `/mistakes/stats/summary`

**方法**: `GET`

**功能描述**: 获取错题总量与按模块统计。

## 5. 错误处理

所有 API 接口在遇到错误时，会返回相应的 HTTP 状态码和错误信息。常见的错误状态码如下：

| 状态码 | 描述 |
|------- |------|------|

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
**可靠性说明**:
- 提醒发送失败后会自动重试（指数/固定延迟策略可配置）。
- 重试次数与最近错误信息会写入 reminder `metadata`（如 `retry_count`, `last_error`）。
- 超过最大重试次数后状态变更为 `failed`，避免无限重试。
