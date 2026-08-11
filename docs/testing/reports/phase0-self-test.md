# Phase 0 自测报告

> 日期：2026-08-12
> 施工模式：Direct-Main
> 阶段：Engineering Foundation
> 结论：`ready_for_implementation`

## 完成范围

- 后端 FastAPI 最小纵切。
- 默认配置与 JSON Schema。
- SQLite WAL 与 migration harness。
- `/api/health` 与 `/api/readiness`。
- React SPA 同源托管。
- React/Vite/Vitest/Playwright 工程。
- Repair Signal 控制台 UI 第一版。
- StageRail、TaskCard、Failure/NoChange 展示语义。
- 明/暗主题与紧凑桌面布局。
- Phase 0 Scenario fixture。
- GitHub Actions Direct-Main gate。
- systemd 服务骨架与稳定脚本入口。
- npm lockfile。
- Linux/Chromium visual golden baseline。

## 本地后端测试

```text
PYTHONPATH=backend/src python -m pytest backend/tests tests/scenarios/test_phase0_scenario.py -q
.... [100%]
```

结果：4 passed。

覆盖：

- config dataRoot 相对基础配置解析。
- 默认配置符合 public JSON Schema。
- SQLite migration + WAL。
- `/api/health`。
- `/api/readiness`。
- SPA index fallback。
- `SCN-000 phase0_foundation_ready`。

## 本地 Readiness

实际运行结果：

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

## 本地 Chromium 视觉检查

受执行容器网络策略限制，本地 Chromium 不能导航到 localhost/file URL，因此用 Python Playwright `page.set_content()` 将与预览产物相同的 HTML/CSS 注入真实 Chromium 渲染引擎，执行 DOM、主题切换和布局断言。

通过：

- `维修控制台` 可见。
- `系统就绪` 可见。
- `PARTIAL DELIVERY` 可见。
- 主题按钮可切换 `html[data-theme=dark]`。
- 1024×768 紧凑桌面无横向溢出。

生成：

- `dashboard-light.png`：1440 宽明色。
- `dashboard-dark.png`：1440 宽暗色。
- `dashboard-compact.png`：1024 宽暗色紧凑布局。

## GitHub Actions Linux 复验

Main gate run `31517713323` 在 Ubuntu Runner 上完成完整 Phase 0 复验，两项 job 均成功。

Backend：

- Python 环境安装成功。
- backend unit/contract/integration + Phase 0 Scenario 成功。

Frontend：

- npm dependency install 成功。
- TypeScript typecheck 成功。
- Vite production build 成功。
- Playwright Chromium 安装成功。
- Vitest Browser Mode 成功。
- 使用真实 `frontend/dist` 启动 FastAPI 同源服务成功。
- `/api/readiness` 在 production build 下通过。
- Playwright E2E 成功。
- Playwright visual snapshot 成功。

Bootstrap 完成后 CI 生成并提交：

- `frontend/package-lock.json`。
- `frontend/e2e/phase0.spec.ts-snapshots/dashboard-light-chromium-linux.png`。

## 回归中实际发现并修复的问题

1. TypeScript 7 无 Vite client 类型时无法接受 CSS side-effect import。补充 `src/vite-env.d.ts` 后 production build 通过。
2. `@vitest/browser-playwright` 与 `@playwright/test` 初始解析到不同 Playwright browser revision。统一 Playwright 版本后 Browser Mode 通过。
3. Vitest 与 Playwright E2E 的文件匹配范围显式隔离，避免 `e2e/*.spec.ts` 被组件测试误收集。
4. 初始仓库没有 lockfile；CI bootstrap 首次生成，随后 Direct-Main 使用 `npm ci` 进行确定性安装。

这些问题均由真实 CI 暴露，不通过跳过测试或放宽门禁规避。

## Phase 0 开工条件核对

- [x] architecture repository structure 生效。
- [x] design system 生效。
- [x] testing strategy 生效。
- [x] backend/frontend/contracts/tests/deploy/scripts 建立。
- [x] Backend health/readiness。
- [x] Frontend production build + Backend 同源托管。
- [x] SQLite migration harness + WAL。
- [x] pytest。
- [x] Vitest Browser Mode。
- [x] Playwright E2E。
- [x] Scenario fixture。
- [x] visual golden baseline。
- [x] 稳定 bootstrap/test/build/readiness 脚本。
- [x] Linux CI 不依赖本机绝对路径与 Secret。

## 结论

Phase 0 的工程基础、测试底座、CI、视觉基线和最小运行纵切已经通过本地与 Linux Runner 双重验证。

仓库达到 `ready_for_implementation`，可以进入第一版正式功能施工。后续任何阶段仍必须遵守 Direct-Main pre-commit gate、Main 全量复验、Scenario Regression 与 visual regression，不因 Phase 0 通过而降低门禁。
