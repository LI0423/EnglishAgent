# 数据库迁移

## 运行方式

迁移由 `backend/db.py` 的 `init_db()` 在**应用每次启动**时按文件名排序逐个 `executescript`：

```python
for name in sorted(os.listdir(mig_dir)):
    if name.endswith(".sql"):
        conn.executescript(f.read())
```

因此有一条硬性约定：

> **每个迁移文件都必须是幂等的**，即所有语句都要能重复执行。

## 为什么 `sm2_*` 列不在迁移文件里

`vocabulary` / `mistakes` 的
`sm2_repetitions`、`sm2_interval_days`、`sm2_ease_factor`、`sm2_lapses`、`sm2_last_quality`
五列由 `init_db()` 用 `_add_column_if_missing()` 添加（见 `backend/db.py`），**不在任何迁移 SQL 中**。

原因：SQLite 不支持 `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`，而迁移每次启动都会重跑；
若写在迁移文件里，第二次启动就会抛 `duplicate column name` 并中断整个迁移循环，导致应用起不来。

> 如果将来引入独立的迁移工具（带版本表、只执行未应用的迁移），可以把这些列补成正式迁移文件。

## 新增迁移的注意事项

- 使用 `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` / `DROP TABLE IF EXISTS`。
- **不要**写裸 `ALTER TABLE ... ADD COLUMN`（不幂等）—— 需要加列时改用 `_add_column_if_missing()`。
- 文件名用 `NNN_描述.sql`，保持三位零填充以便 `sorted()` 得到正确顺序。

## 当前内容

| 文件 | 内容 |
|---|---|
| `001_init.sql` ~ `016_growth_campaigns.sql` | 业务主表与各功能模块表 |
| `017_growth_engine.sql` | `skill_tags` / `learning_event_skill_tags` / `user_skill_state` |
| `018_learning_growth_engine.sql` | `learning_units` / `user_unit_memory` / `user_ability_growth` |
