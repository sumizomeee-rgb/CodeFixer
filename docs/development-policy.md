# CodeFixer 开发与迁移约定

> 状态：施工约定。若旧工程文档中的“blocking gate / main_red”措辞与本文冲突，以本文为准。

## 1. 软门禁，而不是仓库锁

CodeFixer 的自动检查用于发现问题和提供第二环境反馈，不作为开发流程的硬阻断条件。

- GitHub Actions 不应配置为项目运行所必需的组件。
- CI 不自动修改、commit 或 push 仓库内容。
- CI 失败不把仓库定义为不可继续施工的 `main_red` 状态。
- lint/typecheck/test/build 的失败应该被记录和修复，但格式、平台差异或与当前纵切无关的失败不得机械阻止后续开发。
- 是否把某项检查设为外部托管平台的 required check，是部署仓库管理员的选择，不属于 CodeFixer 产品本身的前提。
- 每次 push 只运行较轻的 advisory backend/frontend 检查；浏览器/E2E/visual 回归通过手工 workflow 触发。
- Release Candidate 仍应主动跑完整回归，但这是发布决策，不是日常代码编辑的硬锁。

核心原则是：**文档和测试定义“应该验证什么”，GitHub Actions 只是其中一种执行器。** 项目未来迁移到 GitLab、自建 Git、SVN 镜像或纯本地开发时，不需要重构代码才能继续施工。

## 2. 项目内依赖与可迁移性

目标迁移模型：

```text
复制 / clone CodeFixer
  + 64 位 CPython 3.12+
  + Node.js 20.19+ 或 22.12+（推荐当前 Node 22 LTS）
  + npm
  → scripts/bootstrap.ps1（Windows）或 scripts/bootstrap.sh（Linux）
  → 可开发
```

默认依赖位置：

```text
backend/.venv/          Python 虚拟环境和 Python 包
frontend/node_modules/  npm 包
frontend/dist/          production build 产物（执行 build 后）
data/                   默认运行数据（不属于代码依赖）
```

这些目录都不要求全局安装 Python 包或 npm 包。

### 2.1 为什么不复制 `.venv` / `node_modules`

它们虽然位于项目目录内，但仍属于机器相关的可再生缓存：

- Python venv 会关联创建它的基础 Python 安装。
- npm 包可能包含平台相关二进制文件。
- 因此跨 Windows/Linux、换 Python/Node 版本或换目录时，直接复制这些目录并不可靠。

正确做法是在目标机器重新执行 bootstrap。源码、`pyproject.toml`、`package.json` 和 `package-lock.json` 才是可迁移事实。

### 2.2 Playwright 浏览器

浏览器只属于开发/E2E 测试依赖，不属于 CodeFixer 服务运行依赖。

默认 bootstrap 不下载浏览器。需要本机完整浏览器测试时：

```bash
./scripts/bootstrap.sh --with-browser
```

该模式使用 `PLAYWRIGHT_BROWSERS_PATH=0`，把 Chromium 放在 `frontend/node_modules/playwright-core/.local-browsers`，避免默认散落到用户级缓存。Linux 上 Playwright 的系统级浏览器运行库仍可能需要操作系统包；这不影响普通生产运行。

## 3. 常用 bootstrap

开发机：

```bash
./scripts/bootstrap.sh
```

Windows PowerShell 也可以：

```powershell
.\scripts\bootstrap.ps1
```

需要浏览器测试：

```bash
./scripts/bootstrap.sh --with-browser
```

从源码在部署机生成运行环境与前端 production build：

```bash
./scripts/bootstrap.sh --production
```

Bootstrap 入口先验证宿主解释器确实是 64 位 CPython 3.12+，再用它创建项目虚拟环境。运行、测试和 systemd 只允许使用项目内 `backend/.venv`，不得回退到 PATH 中的 `python`。生产部署不要求全局 pip 安装 CodeFixer。

## 4. Secret 与机器绑定

以下内容不得通过迁移源码携带：

- `config/secrets.json`
- 机器私有绝对路径
- Agent/Git/TAPD/Redmine/GitLab 凭据

迁移后通过本机配置或 Web 设置重新绑定。公共项目配置只保存 `SecretRef`、`pathBinding`、`executableBinding` 等稳定引用。
