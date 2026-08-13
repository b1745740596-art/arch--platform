"""Gunicorn 生产配置。

关键点：生图是**同步长请求**（图生图 60-180s，后端轮询上限 300s，前端超时 360s），
所以 worker 超时必须显著大于 360s，否则请求会被 gunicorn 掐断，
表现为前端报错但后端仍在出图。
"""

import multiprocessing
import os

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8000')

# 生图期间 worker 大部分时间在等 HTTP 响应（IO 等待），线程模型比堆进程更省内存
worker_class = os.environ.get('GUNICORN_WORKER_CLASS', 'gthread')
workers = int(os.environ.get('GUNICORN_WORKERS', max(2, multiprocessing.cpu_count() // 2)))
threads = int(os.environ.get('GUNICORN_THREADS', 8))

# 必须 > 前端 axios timeout(360s) 与后端 MAIZI_POLL_TIMEOUT(300s)
timeout = int(os.environ.get('GUNICORN_TIMEOUT', 600))
graceful_timeout = int(os.environ.get('GUNICORN_GRACEFUL_TIMEOUT', 60))
keepalive = int(os.environ.get('GUNICORN_KEEPALIVE', 65))

max_requests = int(os.environ.get('GUNICORN_MAX_REQUESTS', 500))
max_requests_jitter = 50

accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')
# 记录真实客户端 IP 与耗时，方便排查慢生图
access_log_format = '%({x-forwarded-for}i)s %(h)s "%(r)s" %(s)s %(b)s %(L)ss'
