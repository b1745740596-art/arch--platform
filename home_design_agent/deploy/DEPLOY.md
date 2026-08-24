# 上线部署指南

目标形态：**Linux 服务器 + Docker Compose + PostgreSQL + Redis**，nginx 在前面直发静态并代理私有媒体，
gunicorn 跑 Django，单一入口对外暴露（默认 80 端口）。

## 一、上线前必须知道的三件事

1. **生图是同步长请求**：图生图单次 60–180s，后端轮询上限 300s（`design/imagegen.py`
   的 `MAIZI_POLL_TIMEOUT`），前端 axios 超时 360s。因此超时必须满足
   `nginx(600s) > gunicorn(600s) > 前端(360s) > 后端轮询(300s)`，本仓库的配置已按此设定。
   任何一层调小都会出现「前端报错但后端还在出图」。
2. **效果图是私有本地文件**：全部落在 `MEDIA_ROOT`，compose 里挂到命名卷 `media`，
   下载必须经过 Django 的登录态与对象归属校验，禁止 nginx 匿名目录直发。
   容器重建不会丢，但**换机器要迁移这个卷**，否则历史效果图全部 404。
3. **文本和生图密钥分离**：TalkBot 的 DeepSeek Key 只放服务器 `.env` 或 Secret 管理器，
   生图和谈单机器人配置可在后台 `/admin/design/generationconfig/` 分区维护。DeepSeek 未启用或暂时不可用时，
   TalkBot 自动回退规则回复，不影响会话与转化链路。

## 二、首次部署（5 步）

```bash
# 1. 拉代码到服务器
git clone <你的仓库地址> && cd home_design_agent

# 2. 准备环境变量
cp .env.example .env
python3 -c "import secrets;print(secrets.token_urlsafe(64))"   # 填进 DJANGO_SECRET_KEY
vi .env    # 至少改：DJANGO_SECRET_KEY / POSTGRES_PASSWORD / DJANGO_ALLOWED_HOSTS / DJANGO_HEALTHCHECK_HOST / TLS 与短信配置

# 3. 构建并启动（首次把 SEED_ON_START 设为 1，会灌入 prompt 模块与生图工作流）
docker compose up -d --build

# 4. 看启动日志确认迁移与种子完成
docker compose logs -f web

# 5. 自检（同时检查数据库、Redis 与 TalkBot 默认数据）
curl -fsS https://<域名>/api/talkbot/health/
```

访问入口：

- 前台：`https://<域名>/`，多窗口工作台 `/studio`
- 后台：`https://<域名>/admin/`。首次启动后执行
  `docker compose exec web python manage.py createsuperuser` 创建独立强密码管理员；示例配置不会创建默认管理员。

首次跑通后建议把 `.env` 里的 `SEED_ON_START` 改回 `0`，避免每次重启重复灌示例数据。

## 三、环境变量清单

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | 是 | 生产密钥，勿用仓库默认值 |
| `DJANGO_ALLOWED_HOSTS` | 是 | 域名/IP，逗号分隔，不带 scheme |
| `POSTGRES_PASSWORD` | 是 | 数据库密码 |
| `DJANGO_DEBUG` | — | 生产固定 `false` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | HTTPS 时必填 | 需带 scheme，如 `https://design.example.com` |
| `DJANGO_SECURE_SSL_REDIRECT` / `DJANGO_SECURE_COOKIES` | — | 生产 Compose 强制为 `true`，发布前必须先配好 TLS 边缘代理 |
| `DJANGO_NUM_PROXIES` | 是 | 当前 TLS 边缘代理 + Compose nginx 为 `2`；链路变化时同步调整 |
| `SEED_ON_START` | — | 首次 `1`，之后 `0` |
| `GUNICORN_TIMEOUT` | — | 默认 600，必须 > 前端 360s |
| `TALKBOT_LLM_ENABLED` | — | `.env` 回退配置的开关；后台已保存机器人 Key 时由后台开关接管 |
| `DEEPSEEK_API_KEY` | 使用 `.env` 回退配置时必填 | DeepSeek 平台生成的 API Key；也可改在后台加密保存 |
| `DEEPSEEK_API_BASE` | — | 默认官方端点 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | — | 默认 `deepseek-v4-flash`，可切换 `deepseek-v4-pro` |
| `PAYMENT_MODE` | 是 | 生产必须 `live`；`mock` 只用于本地联调 |
| `PAYMENT_FREE_CREDITS` | — | 每用户一次性免费生成次数，默认 5 |
| `PAYMENT_STRIPE_SECRET_KEY` / `PAYMENT_STRIPE_PUBLIC_KEY` / `PAYMENT_STRIPE_WEBHOOK_SECRET` | 用 Stripe 时必填 | Stripe 密钥与 webhook 验签密钥 |
| `PAYMENT_WECHAT_*` | 用微信支付时必填 | AppID / 商户号 / 证书序列号 / 商户私钥 / API v3 密钥 / 平台公钥 / 回调地址 |
| `PAYMENT_ALIPAY_*` | 用支付宝时必填 | AppID / 应用私钥 / 支付宝公钥 / 回调地址 |

启用 DeepSeek 后，就绪端点会返回 `llm_enabled=true`、`llm_configured=true` 和实际模型名。
若打开开关但漏配 Key，端点返回 503，自动部署不会把该配置误判为成功。

## 三.1 支付上线配置（务必阅读）

1. 复制 `.env.example` 后，把 `PAYMENT_MODE` 改为 `live`，并按实际开通的渠道填入密钥。
2. 渠道回调地址必须配置为公网 HTTPS 地址，并指向本服务：
   - Stripe：`https://你的域名/api/payments/webhook/stripe/`
   - 微信支付：`https://你的域名/api/payments/webhook/wechat/`
   - 支付宝：`https://你的域名/api/payments/webhook/alipay/`
3. 密钥是敏感数据，只放在服务器 `.env`（已被 `.gitignore` 排除），不要写进仓库或前端。
4. 上线后用真实账号完成一次最小金额充值，验证「支付 → 回调 → 额度到账 → 营收看板」全链路。
5. 微信/支付宝需要商户号与证书，请先在企业后台开通并下载；PEM 私钥需要含
   `-----BEGIN ... PRIVATE KEY-----` 完整文本，多行值在 `.env` 中用引号包裹或换行转义。

## 四、配 HTTPS

必须在服务器已有的 nginx / SLB 上做 TLS 卸载，把 `HTTP_PORT` 改成仅边缘代理可访问的
内网端口（如 8080），由外层透传 `X-Forwarded-Proto: https`。防火墙必须禁止公网绕过
边缘代理直连源站端口，否则可信代理计数与 IP 限流都可能失真。
然后在 `.env` 里：

```
DJANGO_CSRF_TRUSTED_ORIGINS=https://design.example.com
DJANGO_SECURE_COOKIES=true
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_NUM_PROXIES=2
```

## 五、日常运维

```bash
docker compose ps                          # 状态
docker compose logs -f web                 # 应用日志（含 gunicorn 请求耗时）
docker compose up -d --build               # 更新代码后重新发布
docker compose exec web python manage.py createsuperuser   # 手工加管理员
docker compose exec web python manage.py migrate           # 手工迁移

# 数据库备份（务必做定时任务）
docker compose exec -T db pg_dump -U home_design home_design | gzip > backup_$(date +%F).sql.gz

# 效果图备份
docker run --rm -v home_design_agent_media:/m -v "$PWD":/b alpine \
  tar czf /b/media_$(date +%F).tar.gz -C /m .
```

## 六、从现有 SQLite 迁移到 PostgreSQL

本地 `db.sqlite3` 里的家具库、工作流、prompt 模块可以带上线：

```bash
# 本地导出（排除会冲突的表）
source .venv/bin/activate
python manage.py dumpdata design --natural-foreign --natural-primary --indent 2 > seed.json

# 传到服务器后导入
docker compose cp seed.json web:/tmp/seed.json
docker compose exec web python manage.py loaddata /tmp/seed.json
```

媒体文件同步：`rsync -av media/ user@server:/tmp/media/`，再拷进 `media` 卷。

## 七、容量与扩容建议

- 单机起步：2C4G 起，`GUNICORN_WORKERS=3`、`GUNICORN_THREADS=8`，可支撑约 20 路并发生图等待。
- 效果图很吃磁盘（当前本地 `media/` 已 78MB），建议独立数据盘并做清理策略。
- 若并发生图压力上来，下一步是把生图从「同步请求」改成 Celery/RQ 异步任务 + 前端轮询，
  这是当前架构最大的伸缩瓶颈，但 MVP 阶段同步方案够用。
- 换到 PostgreSQL 后，`design/dbwrite.py::retry_write()` 这层 SQLite 锁重试已无必要，可择机移除。

## 八、关于用 GitHub 部署

- **GitHub Pages 不行**：Pages 只能托管静态文件，本项目需要 Django 进程、PostgreSQL、Redis
  和本地媒体存储，跑不起来。
- **可行做法**：代码放 GitHub，用 `.github/workflows/deploy.yml`（本仓库已提供）在推
  `main` 时自动 SSH 到服务器执行 `git pull && docker compose up -d --build`。
  需要在仓库 Settings → Secrets 配 `SSH_HOST`、`SSH_USER`、`SSH_KEY`、`DEPLOY_PATH`。
- 推代码前确认 `.env`、`db.sqlite3`、`media/` 均被 `.gitignore` 排除（已配置），
  避免把密钥和用户数据推到远端仓库。
