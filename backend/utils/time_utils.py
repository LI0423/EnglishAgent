"""时间口径工具。

`daily_tasks.date` 等字段约定存「本地零点的时间戳」，多处代码各写了一遍，
这里统一实现，避免口径漂移。
"""

from __future__ import annotations

import time


def day_start_ts(ts: int) -> int:
    """返回给定时间戳当天 00:00 的本地时间戳。

    与 `plan.py` 写入 `daily_tasks.date` 的口径一致（本地时区的零点秒）。
    """
    local = time.localtime(int(ts))
    return int(
        time.mktime(
            (
                local.tm_year,
                local.tm_mon,
                local.tm_mday,
                0,
                0,
                0,
                local.tm_wday,
                local.tm_yday,
                local.tm_isdst,
            )
        )
    )
