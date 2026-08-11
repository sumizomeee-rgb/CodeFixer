# Phase 0 自测报告

> 日期：2026-08-12
> 施工模式：Direct-Main
> 阶段：Engineering Foundation 初始纵切

## 本轮完成

- 后端 FastAPI 最小纵切。
- 默认配置与 JSON Schema。
- SQLite WAL 与 migration harness。
- `/api/health` 与 `/api/readiness`。
- SPA 同源托管。
- React/Vite/Vitest/Playwright 工程配置。
- Repair Signal 控制台 UI 第一版。
- StageRail、TaskCard、Failure/NoChange 展示语义。
- 明/暗主题与 1024 紧凑桌面布局。
- Phase 0 Scenario fixture。
- GitHub Actions main gate。
- systemd 服务骨架与稳定脚本入口。

## 实际执行的后端测试

```text
PYTHONPATH=backend/src python -m pytest backend/tests tests/scenarios/test_phase0_scenario.py -q
.... [100%]
```

覆盖：

- config dataRoot 相对基础配置解析。
- 默认配置符合 public JSON Schema。
- SQLite migration + WAL。
- `/api/health`。
- `/api/readiness`。
- SPA index fallback。
- SCN-000 phase0_foundation_ready。

结果：4 passed。

## 实际运行 Readiness

```json
{
  "status": "ready",
  "ready": true,
  "checks": [
    {"id": "config.loaded", "status": "ready"},
    {"id": "storage.data_root", "status": "ready"},
    {"id": "sqlite.wal", "status": "ready", "detail": {"journalMode": "wal", "migrationCount": 1}},
    {"id": "frontend.dist", "status": "ready"}
  ]
}
```

本地截图验证使用 `frontend/preview-dist` 作为受限环境的静态构建替身，因此此处 `frontend.dist=ready` 只证明 FastAPI 的同源托管与页面产物可读，不等于 npm production build 已在该容器执行。

## Chromium 交互/视觉验证

受执行环境策略限制，Chromium 禁止导航到 localhost/file URL；因此使用 Python Playwright `page.set_content()` 加载与 `preview-dist` 完全相同的 HTML/CSS 内容，在真实 Chromium 渲染引擎中执行 DOM/交互断言与截图。

通过断言：

- `维修控制台` 标题可见。
- `系统就绪` 可见。
- `PARTIAL DELIVERY` 可见。
- 主题按钮切换后 `html[data-theme=dark]` 成立。
- 1024×768 下主标题仍可见且布局无横向溢出。

生成截图：

- `dashboard-light.png`：1440×900 明色。
- `dashboard-dark.png`：1440×900 暗色。
- `dashboard-compact.png`：1024×768 暗色紧凑桌面。

## 环境限制 / 未冒充通过的项目

当前执行容器无外网 npm 安装能力，且没有 React/Vite/Vitest Node 依赖缓存，因此以下项目本轮**没有在本机执行**：

- `npm ci`
- `npm run typecheck`
- `npm run build`
- Vitest Browser Mode
- Node `@playwright/test` E2E/visual suite

仓库已经提供对应 package/config/tests 和 GitHub Actions main gate；push 后 CI 应作为第二环境执行这些步骤。只有 CI 中这些步骤实际全绿，才把 npm 侧 Phase 0 条件标为通过。

## 结论

Backend、database、schema、runtime readiness、浏览器渲染与交互的本轮可执行检查通过。

Phase 0 已建立可施工骨架，但完整 `ready_for_implementation` 仍需 GitHub Actions 在可联网 Linux Runner 上完成 npm install/build/Vitest/Playwright 复验并保持 main 绿色。
