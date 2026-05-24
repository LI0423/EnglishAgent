# ATENGS 文档导航目录

> 目的：作为项目统一文档入口，帮助新成员、开发者、测试同学快速定位资料。

## 1. 阅读路径（按角色）

### 1.1 新成员 / 首次接手
1. [项目总览（README）](README.md)
2. [需求文档](docs/需求.md)
3. [实施方案](docs/实施方案.md)
4. [开发计划](docs/开发计划.md)
5. [开发进度文档](docs/开发进度文档.md)

### 1.2 后端开发
1. [API接口文档](docs/API接口文档.md)
2. [代码风格指南](docs/代码风格指南.md)
3. [测试接口文档](docs/测试接口文档.md)
4. [迁移脚本目录](migrations/)
5. [后端入口（FastAPI）](backend/app.py)

### 1.3 前端开发 / UI
1. [前端说明（frontend README）](frontend/README.md)
2. [代码风格指南](docs/代码风格指南.md)
3. [UI设计风格指南](docs/UI/UI设计风格指南.md)
4. [UI设计-首页仪表盘](docs/UI/UI设计-首页仪表盘.md)
5. [UI设计-听力模块](docs/UI/UI设计-听力模块.md)
6. [UI设计-口语模块](docs/UI/UI设计-口语模块.md)
7. [UI设计-阅读模块](docs/UI/UI设计-阅读模块.md)
8. [UI设计-写作模块](docs/UI/UI设计-写作模块.md)
9. [UI设计-登录注册页面](docs/UI/UI设计-登录注册页面.md)
10. [UI设计-辅助功能页面](docs/UI/UI设计-辅助功能页面.md)

### 1.4 测试与发布
1. [测试计划文档](docs/测试计划文档.md)
2. [测试进度文档](docs/测试进度文档.md)
3. [发布前检查清单](docs/发布前检查清单.md)

## 2. 产品与规划文档索引

- [需求文档](docs/需求.md)
- [实施方案](docs/实施方案.md)
- [开发计划](docs/开发计划.md)
- [详细每周进度计划](docs/详细每周进度计划.md)
- [开发进度文档](docs/开发进度文档.md)
- [商业化建议](docs/商业化建议.md)

## 3. 核心技术文档索引

- [API接口文档](docs/API接口文档.md)
- [代码风格指南](docs/代码风格指南.md)
- [测试接口文档](docs/测试接口文档.md)
- [数据库迁移脚本](migrations/)
- [后端代码目录](backend/)
- [前端代码目录](frontend/)
- [测试代码目录](tests/)

## 4. 学习模块对照入口

- 听力：
  - 前端页面：[Listening.jsx](frontend/src/pages/Listening.jsx)
  - 后端路由：[listening.py](backend/routers/listening.py)
- 口语：
  - 前端页面：[Speaking.jsx](frontend/src/pages/Speaking.jsx)
  - 后端路由：[speaking.py](backend/routers/speaking.py)
- 阅读：
  - 前端页面：[Reading.jsx](frontend/src/pages/Reading.jsx)
  - 后端路由：[reading.py](backend/routers/reading.py)
- 写作：
  - 前端页面：[Writing.jsx](frontend/src/pages/Writing.jsx)
  - 后端路由：[writing.py](backend/routers/writing.py)
- 词汇：
  - 前端页面：[Vocabulary.jsx](frontend/src/pages/Vocabulary.jsx)
  - 后端路由：[vocabulary.py](backend/routers/vocabulary.py)
- 错题本：
  - 前端页面：[Mistakes.jsx](frontend/src/pages/Mistakes.jsx)
  - 后端路由：[mistakes.py](backend/routers/mistakes.py)
- 提醒中心：
  - 前端页面：[ReminderCenter.jsx](frontend/src/pages/ReminderCenter.jsx)
  - 后端路由：[reminder.py](backend/routers/reminder.py)
- 学习计划：
  - 前端页面：[Plans.jsx](frontend/src/pages/Plans.jsx)
  - 后端路由：[plan.py](backend/routers/plan.py)
- 学习报告：
  - 前端页面：[Reports.jsx](frontend/src/pages/Reports.jsx)
  - 后端路由：[report.py](backend/routers/report.py)

## 5. 开发与测试常用命令

### 5.1 后端
```bash
# 启动后端
PYTHONPATH=src ./venv/bin/python -m uvicorn server.app:app --host 127.0.0.1 --port 8200
```

> 如果当前分支的后端入口改为 `backend/app.py`，请以该入口为准运行。

### 5.2 前端
```bash
npm --prefix frontend run dev
npm --prefix frontend run build
```

### 5.3 测试
```bash
# 核心回归
PYTHONPATH=. ./venv/bin/pytest -q tests/test_week2_backend_progress.py

# 全量测试（按需）
./venv/bin/pytest -q
```

## 6. 文档维护规则

1. 新增文档时，必须在本文件增加链接。
2. 文档移动或重命名后，需同步更新本文件路径。
3. 每完成一个“大模块”交付，至少更新：
   - [开发进度文档](docs/开发进度文档.md)
   - [API接口文档](docs/API接口文档.md)（如有接口变化）
4. PR 合并前，检查本目录链接是否可访问。

---

最后更新：2026-05-19
