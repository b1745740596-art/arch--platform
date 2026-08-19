# Arch AI 上线 SOP

> 用途：供其他聊天窗口 / 运维同学直接照做，完成 Web 端和 Android APK 的上线发布。
> 适用范围：`home_design_agent` 项目，线上域名 `https://plankeai-home.com`。

## 一、关键事实

- 仓库：`github.com/b1745740596-art/arch--platform`
- 主分支：`main`
- 前端：Vue 3 + Vite，源码在 `home_design_agent/frontend`
- 后端：Django，入口 `home_design_agent/manage.py`
- 线上部署：GitHub Actions `deploy.yml`，推 `main` 自动触发
- APK 构建：GitHub Actions `build-apk.yml`，手动触发
- App 是 Capacitor 壳，运行时加载 `https://plankeai-home.com`
- APK 下载地址：`https://plankeai-home.com/media/app/arch-ai.apk`

## 二、发布前必须判断：这是 Web 改动还是 APK 改动？

| 改动类型 | 需要做 |
| --- | --- |
| 页面/组件/文案/后端接口 | 只走 Web 发布流程，不需要重新打 APK |
| `capacitor.config.json`、原生插件、App 版本号、状态栏/原生能力 | 走 Web 发布 + APK 构建 + APK 上传 |

## 三、Web 发布流程

### 1. 改完代码后，在项目根目录执行

```bash
cd /Users/didi/Architecture\ Agent\ Platform/home_design_agent

# 后端检查与测试
.venv/bin/python manage.py check
.venv/bin/python -m pytest -q

# 前端构建
cd frontend
PATH="/Users/didi/Architecture Agent Platform/.toolchain/node/bin:$PATH" npm run build
cd ..

# 收集静态文件
.venv/bin/python manage.py collectstatic --noinput
```

### 2. 提交并推送

```bash
cd /Users/didi/Architecture\ Agent\ Platform

git status
git add <本次改动的文件>
git commit -m "type: 描述"
git push origin main
```

### 3. 等待自动部署

推送后，GitHub Actions 的 `Deploy` 会自动执行：

`check` → `build frontend` → SSH 服务器 → `docker compose up -d --build` → 重启 nginx。

### 4. 验证 Web 已上线

```bash
# 健康检查
curl -fsS https://plankeai-home.com/api/design/health/

# 确认首页资源已更新（asset 名应变化）
curl -sS https://plankeai-home.com/ | grep -o 'index-[^"]*\.js' | head -1
```

## 四、APK 发布流程

只有涉及原生层时才需要这一步。

### 1. 同步版本号

改两个文件，保持一致：

- `home_design_agent/frontend/capacitor.config.json` 的 `version`
- `home_design_agent/app_release.json` 的 `version`、`build`、`apk_url`、`changelog`

示例：

```json
{
  "version": "1.2.1",
  "build": 6,
  "apk_url": "/media/app/arch-ai.apk?v=1.2.1",
  "changelog": ["本次更新内容"],
  "force_update": false
}
```

`apk_url` 必须带版本查询参数，避免 CDN/浏览器缓存导致用户下载到旧包。

### 2. 提交版本号

```bash
cd /Users/didi/Architecture\ Agent\ Platform

git add home_design_agent/frontend/capacitor.config.json home_design_agent/app_release.json
git commit -m "chore: bump app version to <version>"
git push origin main
```

### 3. 触发 APK 构建

方式 A：GitHub 网页

- 打开仓库 → Actions → `Build APK` → `Run workflow` → 选择 `main`。

方式 B：本地 gh CLI

```bash
gh workflow run "Build APK" --ref main
gh run watch
```

构建完成后会发布到 GitHub Release 的 `apk` tag。

### 4. 下载 APK

```bash
rm -rf /tmp/apk-build && mkdir -p /tmp/apk-build
gh release download apk --pattern '*.apk' --dir /tmp/apk-build

# 或用 curl
curl -L --fail -o /tmp/arch-ai.apk \
  https://github.com/b1745740596-art/arch--platform/releases/download/apk/app-debug.apk
```

### 5. 上传 APK 到服务器

```bash
SSH_HOST=<服务器IP或域名>
SSH_USER=<SSH用户名>
SSH_KEY=~/.ssh/arch_deploy_ed25519

scp -i "$SSH_KEY" /tmp/arch-ai.apk "$SSH_USER@$SSH_HOST:/tmp/arch-ai.apk"

ssh -i "$SSH_KEY" "$SSH_USER@$SSH_HOST" \
  "docker run --rm -v home_design_agent_media:/data -v /tmp:/src alpine sh -c 'mkdir -p /data/app && cp /src/arch-ai.apk /data/app/arch-ai.apk'"
```

### 6. 验证 APK

```bash
curl -fsSI https://plankeai-home.com/media/app/arch-ai.apk | head

curl -sS https://plankeai-home.com/api/design/app-version/ | python3 -m json.tool
```

确认返回的 `apk_url` 与版本号正确，`HTTP/1.1 200` 正常。

## 五、上线验证清单

- [ ] Web 首页能打开
- [ ] `/api/design/health/` 返回 `ok`
- [ ] App 端打开直接进入「我的家」
- [ ] App 底部导航与页面跳转正常
- [ ] 新 APK 下载、安装正常
- [ ] 「我的 → 设置 → 检查更新」能识别新版本

## 六、回滚

### Web 回滚

```bash
git revert <错误提交>
git push origin main
```

服务器会自动重新构建并部署。

### APK 回滚

把上一版 `app-debug.apk` 重新上传覆盖：

```bash
scp -i ~/.ssh/arch_deploy_ed25519 /tmp/old-arch-ai.apk root@47.242.59.208:/tmp/arch-ai.apk

ssh -i ~/.ssh/arch_deploy_ed25519 root@47.242.59.208 \
  "docker run --rm -v home_design_agent_media:/data -v /tmp:/src alpine sh -c 'mkdir -p /data/app && cp /src/arch-ai.apk /data/app/arch-ai.apk'"
```

同时把 `app_release.json` 的 `version`、`apk_url` 回退到上一版。

## 七、常见坑

1. 只改网页不要动 APK；改原生插件/版本号必须重打 APK。
2. 推 `main` 后不要立刻判断失败，部署通常需要约 1–2 分钟。
3. `app_release.json` 的 `apk_url` 忘记带 `?v=` 时，用户可能因缓存拿不到新 APK。
4. 本地没有 Java/Android SDK，请优先用 GitHub Actions 打 APK，不要本机 `gradlew`。
5. 前端构建使用仓库内置 Node，路径必须包含：
   `"/Users/didi/Architecture Agent Platform/.toolchain/node/bin"`。
