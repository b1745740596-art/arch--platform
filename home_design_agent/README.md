# 线上家装设计 Agent

基于《线上家装设计Agent_PRD.docx》V1.0 搭建的工程骨架。

## 环境

单端口部署（Django 托管 Vue 构建产物，不走前后端分离）：

- 后端：Python 3.12.13（standalone，`../.toolchain/python`）+ Django 5.0.6 + DRF 3.15.1，venv 在 `.venv/`
- 前端：Node 24.19.0（standalone，`../.toolchain/node`）+ Vue 3 + Vite + vue-router + pinia + axios，源码在 `frontend/`
- 前端 `npm run build` → 产物输出到 `frontend_dist/`，Vite `base=/static/spa/`
- Django 通过模板渲染 `frontend_dist/index.html` 作为 SPA 入口，产物经 `STATICFILES_DIRS` 挂到 `/static/spa/`
- URL 优先级：`/admin/`、`/api/`、`/static/`、`/media/` 优先，其余路径回落给 Vue Router
- **单端口 :8000 访问所有内容，无需常驻 Vite、无跨域**

### 激活虚拟环境

```bash
cd "/Users/didi/Architecture Agent Platform/home_design_agent"
source .venv/bin/activate
```

退出：`deactivate`

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动（推荐：一条命令）

```bash
cd "/Users/didi/Architecture Agent Platform/home_design_agent"
./scripts/serve.sh
```

`scripts/serve.sh` 按顺序做完 5 件事，`Ctrl+C` 停止：

1. `npm run build` 构建前端 → `frontend_dist/`（自动注入 `.toolchain/node` 到 PATH，缺 `node_modules` 时先 `npm install`）
2. `collectstatic` 把产物同步到 `staticfiles/`
3. `migrate` 应用数据库迁移
4. 结束 :8000 上的残留进程（避免旧进程抢请求 / 持有过期静态清单）
5. 前台启动 `runserver --noreload`，并打印各入口 URL

常用参数：

| 参数 | 用途 |
| --- | --- |
| `--no-build` | 只改了后端，跳过前端构建（最快） |
| `--debug` | 以 `DJANGO_DEBUG=true` 启动（详细报错、可浏览 API 页面） |
| `--seed` | 顺带执行 `seed_prompt_modules --update` / `seed_workflows` / `seed_demo` |
| `--port 8010` | 换端口（:8000 被别的用户占用时） |
| `-h` | 查看用法 |

脚本会自动设 `DJANGO_SERVE_MEDIA=true`。这一步不能省：`DEBUG` 默认 **false**，
且本地没有 nginx，不开这个开关时 `/media/renders/*.png` 会 404、前端效果图空白。

> 手工启动等价于（不推荐，容易漏步骤导致白屏）：
>
> ```bash
> source .venv/bin/activate
> (cd frontend && npm run build)          # 改了前端才需要
> python manage.py collectstatic --noinput  # 漏掉这步 → /static/spa/*.js 全 404，整站白屏
> python manage.py migrate
> DJANGO_SERVE_MEDIA=true python manage.py runserver 0.0.0.0:8000 --noreload
> ```
>
> 关键点：`DEBUG=false` 时 `/static/` 由 WhiteNoise 从 `STATIC_ROOT`（`staticfiles/`）托管，
> 而 Vite 产物只落在 `frontend_dist/`；**必须 `collectstatic` 且之后重启 Django**
> （WhiteNoise 只在进程启动时扫描静态清单）。
>
> 也可 `cp .env.example .env` 并把 `DJANGO_DEBUG` 改成 `true` 长期开发；`.env` 已在 `.gitignore` 中。

访问入口：http://localhost:8000/ （前端首页）
设计工作台：`/studio`　效果图列表：`/render`
自检端点：`GET /api/design/health/` → `{"status":"ok",...}`
管理后台：`/admin/`（SimpleUI 主题，账号见团队约定）

首次打开若仍白屏，按 `Cmd+Shift+R` 硬刷新，清掉此前 404 的资源缓存。

### 修改前端后

重跑 `./scripts/serve.sh` 即可（构建 + 收集静态 + 重启一步到位）。

可选：若想用 Vite 热更新加速开发，`npm run dev`（:5173）会代理 `/api`、`/admin`、`/media` 到 Django；
但正式访问与部署统一走 :8000。

## 目录结构

```
home_design_agent/
├── .venv/                  # 虚拟环境（Python 3.12）
├── manage.py
├── requirements.txt
├── docs/                   # PRD 及派生设计文档
├── config/                 # Django 项目配置
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── design/                 # 业务应用
│   ├── models.py           # 数据对象（PRD 七）
│   ├── views.py
│   ├── urls.py
│   ├── admin.py
│   └── migrations/
├── frontend/               # Vue3 + Vite 前端 SPA
│   ├── src/
│   │   ├── api/            # axios 客户端
│   │   ├── router/         # vue-router
│   │   ├── stores/         # pinia
│   │   ├── views/          # 页面
│   │   └── App.vue
│   └── vite.config.js      # base=/static/spa/，产物输出到 ../frontend_dist
├── frontend_dist/          # 前端构建产物（Django 托管，git 忽略）
├── staticfiles/            # collectstatic 输出，WhiteNoise 从这里托管 /static/
├── scripts/
│   └── serve.sh            # 本地一键启动：构建→收集静态→迁移→清端口→起服务
└── tests/
```

`design` 应用后续按 PRD 第五章拆分子模块：户型识别（5.1）、需求对话（5.2）、
方案生成（5.3）、BOM 报价（5.4）、服务商撮合（5.5）、施工监管（5.6）。

## 核心流程：毛坯照片 → AI 效果图

1. 前端 `/render`：上传毛坯照片 + 选空间/风格/预算/需求，`POST /api/design/renders/`（multipart）
2. 后端按工作流执行：上传图预处理 → prompt 控制模块装配提示词 →
   调用生图（默认**图生图**，把预处理后的毛坯照片作为参考图）→ 成图后处理 → 交付；
   服务商与模型在 `GenerationConfig`（后台可填 API Key/端点/模型/提示词模板）里配置
3. 生成后按风格/城市匹配家具（含购买链接）、施工队、设计师，一并返回前端展示
4. 未在后台“生成配置(API)”里启用真实调用时，回退为占位图，保证无 Key 也能跑通

后台配置入口：`/admin/design/generationconfig/` —— 在此填入 API Base URL / API Key / 模型名 / 尺寸 / 提示词模板，勾选“启用真实调用”即接入真实大模型。

示例数据：`python manage.py seed_demo`（家具 15、设计师 3、施工队 3）。
家具带「适用空间」字段，生图时按空间过滤，详见「图生图」一节。

## 支付与额度

效果图生成为按次计费：每位用户一次性赠送 5 次免费额度（`PAYMENT_FREE_CREDITS`，默认 5），
生成一次效果图消耗 1 次，免费额度用完后需购买套餐。充值套餐在
`/admin/payments/pricingplan/` 维护，首次 `migrate` 会自动灌入「灵感包 / 进阶包 / 专业包」三档。

- 用户侧：`/billing`（顶部导航「额度充值」）查看额度、购买套餐、查看充值记录；
  账号设置页也会展示当前免费/已购额度
- 管理侧：`/admin/payments`（顶部导航「营收看板」）展示营业额趋势、渠道占比与收款订单，
  可手动确认待支付订单
- 收款渠道：**Stripe**（国际信用卡）、**微信支付**（Native 扫码）、**支付宝**（当面付扫码）
- 后端模块：`payments/`，模型为 `PricingPlan`（套餐）、`PaymentOrder`（收款订单）、
  `CreditTransaction`（额度流水）；营业额与收款列表在
  `/admin/payments/paymentorder/` 和 `GET /api/payments/admin/stats/`
- 支付状态回调：`POST /api/payments/webhook/{stripe|wechat|alipay}/`

本地默认 `PAYMENT_MODE=mock`，下单后点「模拟支付成功」即可入账，不发真实扣款。
上线前在 `.env` 切到 `PAYMENT_MODE=live` 并配置对应渠道密钥（见 `.env.example`），
依赖 `stripe` 与 `cryptography`（已在 `requirements.txt`）。

生成额度扣减在 `design/views.py::RenderJobViewSet`，创建渲染任务与重新生成都会
先预扣 1 次额度；若生图链路抛异常则原路退回，避免失败消耗用户额度。

## 上线部署

生产形态：Docker Compose（nginx + gunicorn + PostgreSQL），完整步骤见
[`deploy/DEPLOY.md`](deploy/DEPLOY.md)。

```bash
cp .env.example .env   # 至少填 DJANGO_SECRET_KEY / POSTGRES_PASSWORD / DJANGO_ALLOWED_HOSTS
docker compose up -d --build
curl -fsS http://<域名>/api/design/health/
```

关键约束：

- 设置项全部从环境变量读取（`config/settings.py` 用 `django-environ`）；
  未配 `DATABASE_URL` 时自动回落本地 SQLite，开发流程不变。
- 生图是同步长请求，超时链必须满足 `nginx 600s > gunicorn 600s > 前端 360s > 后端轮询 300s`。
- 效果图落在 `MEDIA_ROOT`（compose 中为 `/data/media` 命名卷）。`DEBUG=False` 后
  `/media/` 由 nginx 直发；无 nginx 时把 `DJANGO_SERVE_MEDIA=true` 让 Django 兜底。
- 大模型 API Key 不走环境变量，上线后在 `/admin/design/generationconfig/` 配置。

## Prompt 控制模块

提示词不再硬编码在生图函数里，而是拆成后端预设的「控制模块」（`design/models.py::PromptModule`），
按维度分组：灯光氛围 / 材质质感 / 镜头视角 / 色彩基调 / 布局收纳 / 情绪风格 / 画质控制。

- 组装逻辑在 `design/prompts.py`：`resolve_modules()` 解析模块 → `build_prompt_bundle()`
  产出正向 prompt、负向 prompt 与设计说明补充要求，家具库描述作为一段约束拼入；
- **前端只提交模块 `code`**（`module_codes=lighting_soft,material_stone`），
  提示词文本仅存在于后端，未知 code 直接忽略，不会污染 prompt；
- 未选择任何模块时回退到 `is_default=True` 的默认模块组合；
- 运营在 `/admin/design/promptmodule/` 里直接调优提示词片段、权重与适用范围（可按空间/风格限定）。

预设数据：`python manage.py seed_prompt_modules`（22 个模块，`--update` 可覆盖更新）。

相关接口：

- `GET /api/design/prompt-modules/options/` 下发可选枚举、模块列表、分组选择规则与输入约束
  （前端严格校验与后端二次校验共用同一份口径）
- `GET /api/design/prompt-modules/suggest/?room_type=&style=&budget_tier=` 返回「发散选项」，
  每套方案给出一组模块组合，可一键套用或分别开窗并行生成

## 输入约束（前后端同口径）

`design/prompts.py` 中的 `IMAGE_CONSTRAINTS` / `REQUIREMENT_MAX_LENGTH` / `MAX_MODULES`
是唯一口径，前端下载后本地拦截，后端在 `RenderJobSerializer` 里再校验一次：

- 照片：JPG/PNG/WebP，10KB ~ 10MB，宽高 512 ~ 8000px，长宽比 1:3 ~ 3:1
- 需求描述：≤300 字，禁止手机号/邮箱/身份证/固话、禁止链接、禁止 `< > { }`
- 空间 / 风格 / 预算档：必须来自后端下发的枚举
- 控制模块：最多 6 个，且必须是启用中的已知 code

## 多窗口工作台

`/studio`（前端 `frontend/src/views/StudioView.vue`）：一个页面里可同时开多个任务窗口并行生成。

- 窗口上限 6，同时"生成中"上限 3，超出自动排队，前面完成后出队执行；
  窗口状态机 `draft → validating → queued → running → success/failed`，并发队列在
  `frontend/src/stores/studio.js`，校验在 `frontend/src/utils/validation.js`
- 支持新建 / 复制窗口（复制参数不复制图片）/ 关闭窗口 / 全部提交，每个窗口独立请求与耗时计时
- 每个窗口可单独选「生图流程」（工作流），选项上标注该流程是图生图还是文生图；
  结果区用标签显示本次实际生效的模式，退回文生图时给出告警
- 发散选项：点「换一批灵感」拿到多套方案，可一键套用到当前窗口，
  也可「按每个方案各开一个窗口」一次性并行对比
- `prompt-modules` 接口不可用时自动降级到内置枚举与约束，页面仍可提交

因为多窗口会并行写库，SQLite 已开启 WAL 模式并放宽锁等待（`design/apps.py`、
`config/settings.py` 的 `OPTIONS.timeout`），否则并发提交会出现 `database is locked`。
WAL 下「先读后写」的事务在升级为写事务时仍会立刻返回 BUSY（`busy_timeout` 对此不生效），
因此渲染链路上的写操作统一走 `design/dbwrite.py::retry_write()` 做退避重试。
换成 PostgreSQL 后这层重试无害，可直接移除。
原 `/render` 单窗口页面保留不变。

## 生图工作流（后台可编排）

生图不再是一段写死的代码，而是一条**后台可编辑的流水线**：前端上传的图片先经工作流
处理，再驱动生图，成图继续经后处理，最后才交付给用户。

引擎在 `design/workflow.py`，模型是 `RenderWorkflow` + `WorkflowStep`。
步骤之间通过 `WorkflowContext` 传数据（上传图字节、prompt、生图产物……），
因此可以任意增删与换序。

可用步骤类型：

| 阶段 | 步骤 | 说明 / 主要参数 |
| --- | --- | --- |
| 上传图预处理 | 输入校验 | `min_side` 短边下限 |
| | 按 EXIF 摆正 | 修正手机竖拍被转向 |
| | 缩放上传图 | `max_side`、`format` |
| | 增强上传图 | `brightness` / `contrast` / `sharpness`，修毛坯照片偏暗偏灰 |
| 分析与提示词 | 分析上传图 | 算亮度/色调/构图，`inject_prompt` 决定是否写进 prompt |
| | 匹配家具库 | `limit` 匹配数量，顺带补齐商品图 |
| | 装配提示词 | 走 prompt 控制模块，`use_image_analysis` 决定是否叠加分析结论 |
| | 追加提示词片段 | `positive` / `negative`，用于全局风格兜底 |
| 生图 | 调用生图（文生图） | 只用提示词，按 `GenerationConfig` 选服务商 |
| | 图生图 | 把上传照片作为参考图，`preserve_space` / `fallback_to_text2img` / `max_side` |
| 成图后处理 | 成图调色 | `brightness` / `contrast` / `saturation` / `sharpness` |
| | 缩放成图 | `max_side` 控制交付体积 |
| | 添加水印 | `text` / `position` / `opacity` / `font_size` |
| 交付 | 生成设计说明 | 走文本大模型，失败降级规则文案 |
| | 匹配施工队/设计师 | — |

编排入口：`/admin/design/renderworkflow/` —— 工作流页面内联编辑步骤（顺序、开关、
JSON 参数）；`RenderJob` 详情页有「工作流执行轨迹」，逐步显示状态、摘要与耗时，便于排查。

预置数据：`python manage.py seed_workflows`（`--reset` 按预置重建步骤）

- **标准交付流程**（默认，13 步）：校正 + 增强 + 分析 → 图生图 → 调色 + 水印
- **快速预览流程**（8 步）：图生图，跳过增强与水印，最快出图，适合多窗口并行对比
- **高保真出片流程**（13 步）：图生图，加大输入分辨率与统一质感兜底，用于对外汇报
- **灵感文生图流程**（7 步）：不参考上传照片，只按风格与需求出图，用于早期风格探索

容错策略：默认**单步失败不阻塞整单**，错误写进 `workflow_log` 与 `job.error`，
用户仍能拿到图；把工作流的「步骤失败即终止」或步骤的「本步失败仍继续」取消勾选，
即可改成严格终止。工作流未产出图像时回退占位图。

相关接口：

- `GET /api/design/workflows/` 列出启用中的工作流及其步骤（只读，编排在 admin）
  响应含 `mode`（`img2img` / `text2img`）与 `mode_display`，前端据此提示用户
- `POST /api/design/renders/` 可传 `workflow=<id>` 指定本次使用的工作流，
  不传则用默认工作流；响应含 `workflow_name`、`workflow_steps`（执行轨迹）
  与 `render_mode`（本次实际生效的生图模式）

## 图生图（以上传照片为参考图）

图生图让成图沿用**原始空间**：同一户型、同样的门窗位置、同样的拍摄视角，只把毛坯
变成装完的样子；文生图只按风格出「同类空间」的图，用于早期风格探索。

- 工作流里选 `EDIT_IMAGE`（图生图）步骤即启用，参考图是**预处理后的上传图**
  （已摆正、缩放、增强），所以预处理步骤会真实影响成图；
- 步骤默认追加空间保持约束（`preserve_space`）：保持户型、门窗、层高与视角不变，
  只增加饰面、家具与灯光；
- 参考图提交前会压到 `max_side`（默认 1024）并转 JPEG，控制请求体积；
- 服务商差异由 `design/imagegen.py` 收敛：
  - `maizi`：`POST /v1/images/generations`，参考图放在 `images` 字段（data URL）
  - `openai`：走官方 `images.edit` 端点
  - `pollinations`：不支持参考图
- **降级**：服务商不支持参考图或图生图调用失败时，默认退回文生图
  （`fallback_to_text2img`），降级原因写进 `workflow_log` 与 `job.error`，
  接口 `render_mode` 会变成 `text2img`，前端窗口上会明确提示「本次已退回文生图」；
  取消该参数即改为严格失败。

耗时：图生图比文生图慢，单次约 60-180s，多窗口并行时服务商侧还会排队。后端轮询上限
`MAIZI_POLL_TIMEOUT=300s`（`design/imagegen.py`），前端请求超时 360s（`api/client.js`），
两者需保持前端 > 后端，否则前端会先超时而后端仍在出图。

家具匹配也按空间收敛：`Furniture.rooms`（适用空间）+ `design/prompts.py::ROOM_CATEGORIES`
（空间可用品类）双重过滤，避免图生图下出现「客厅里摆床」这类明显错配；`rooms` 留空表示不限空间，
在 `/admin/design/furniture/` 可直接编辑。

## 已实现（前端 + API）

数据模型（PRD 七）：业主 Owner、房屋项目 Project、设计方案 DesignScheme、线索 Lead、服务商 ServiceProvider。

REST API（`/api/design/`，DRF）：

- `GET/POST /projects/`、`GET /projects/{id}/`
- `POST /projects/{id}/generate_schemes/`  生成 ≥3 套预方案（PRD 5.3，规则生成，接口预留 LLM 替换）
- `GET/POST /schemes/`、`POST /schemes/{id}/toggle_favorite/`
- `GET/POST /leads/`（留资后自动推进项目状态，PRD 5.5）
- `GET /providers/`、`GET/POST /owners/`

前端页面（Vue3 + Element Plus，UI 中文化）：

- `/` 首页：流程引导 + 后端连通性
- `/intake` 上传户型建档，创建后自动生成方案并跳转
- `/projects` 项目列表（状态、方案数、预算区间）
- `/projects/:id` 方案对比：三档预算卡片、收藏、重新生成、预约留资弹窗、可施工校验提示

方案生成逻辑在 `design/services.py`，按经济/品质/高端三档结合面积估算预算，后续可替换为 LLM。

## MVP 范围提要

1. 户型图上传识别（JPG/PNG/PDF），不确定区域标记待确认
2. 需求问卷与 AI 追问，输出强约束/偏好/可妥协项
3. 生成 ≥3 套预方案（布局、风格、预算区间、材料家具建议）
4. 方案对比与局部重生成、预算档位切换
5. 留资与预约顾问线索转化

## 关键非功能约束

- 预方案生成目标 ≤3 分钟，进度可视化
- 生成失败可重试；订单/合同/付款信息必须持久化
- 户型图、地址、联系方式、合同、付款数据需权限隔离与脱敏
- 方案需输出假设、预算口径与不可施工风险提示
