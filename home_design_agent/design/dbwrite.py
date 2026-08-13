"""SQLite 并发写重试。

多窗口并行生图时会有多个请求同时写库。SQLite 开了 WAL 之后读写不互斥，
但「先读后写」的延迟事务在升级为写事务时会立刻返回 SQLITE_BUSY，
`busy_timeout` 对这种升级失败不生效（SQLite 为避免死锁不会等待），
于是仍会出现 `database is locked`。

这里提供一个薄封装：对写操作做指数退避重试，只吞 `database is locked`，
其他数据库错误照常抛出。适用于当前 SQLite 单机试点；换成 PostgreSQL 后
这层重试无害且可直接移除。
"""
from __future__ import annotations

import logging
import random
import time

from django.db import OperationalError, transaction

logger = logging.getLogger(__name__)

WRITE_ATTEMPTS = 6
WRITE_BASE_DELAY = 0.25


def retry_write(operation, attempts: int = WRITE_ATTEMPTS, label: str = ''):
    """执行写操作，遇到 `database is locked` 时退避重试。

    operation 需要是可重复执行的（幂等），例如 `job.save()`、`m2m.set()`。
    每次重试都放在独立的原子事务里，避免半个事务残留。
    """
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            with transaction.atomic():
                return operation()
        except OperationalError as exc:
            if 'database is locked' not in str(exc).lower():
                raise
            last_error = exc
            if attempt == attempts:
                break
            # 退避 + 抖动，避免多个并发任务同频重试
            delay = WRITE_BASE_DELAY * (2 ** (attempt - 1))
            time.sleep(min(delay, 4.0) * (0.7 + random.random() * 0.6))
            logger.info('db locked, retry %s/%s: %s', attempt, attempts, label or operation)
    raise last_error
