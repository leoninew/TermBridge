# 环境运行时管理验证

Review status: Draft

当前：严格模式 / strict，验证 / Verification

## Requirement alignment

- 环境管理页按 Windows / Cygwin / WSL tabs 组织运行环境能力。
- `ttyd` 作为独立区域检测和配置，返回可用性、路径、版本或失败原因。
- Cygwin tab 检测 bash 和 tmux，并支持持久化 Cygwin bash path。
- Windows / WSL tab 仅做基础可用性检测，未扩展到完整终端定义管理。
- 后端检测失败以 `available=false` 响应表达，不作为页面级异常处理。
- 现有 terminal settings、terminal definitions、session restart/delete 相关 API 保留。

## Spec alignment

本需求按用户要求跳过独立 Spec 文档；验证以 Requirement 和 Plan 为准。

## Plan alignment

已按计划覆盖：

- `src/cc_ttyd/models.py`：新增运行时检测、Cygwin settings、Windows/WSL/Cygwin 检测响应模型。
- `src/cc_ttyd/services.py`：新增 ttyd、Cygwin、Windows、WSL 检测逻辑，并让 Cygwin terminal resolution 可回退到持久化 bash path。
- `src/cc_ttyd/api.py`：新增环境检测和 Cygwin settings API。
- `frontend/src/types/sessions.ts`：新增前端运行时检测相关类型。
- `frontend/src/api/sessions.ts`：新增环境检测和 Cygwin settings API client。
- `frontend/src/components/EnvironmentManagement.vue`：重构为独立 ttyd panel 与 Windows / Cygwin / WSL tabs。
- `frontend/src/i18n/locales/zh-CN.json`、`frontend/src/i18n/locales/en-US.json`：补充环境管理文案。
- `tests/test_terminal_service.py`、`tests/test_api.py`：新增服务和 API 覆盖。

计划外但相关的改动：

- `frontend/src/assets/cygwin-logo-medium.png`
- `frontend/src/assets/tmux-logo-medium.png`

这两个资源用于环境管理页展示 Cygwin/tmux 标识，属于 UI 呈现补充，未扩大运行时能力范围。

## Actual diff summary

当前 staged diff：14 个文件，1193 insertions，117 deletions。

Changed files:

- `docs/requirement/20260609-environment-runtime-management.md`
- `docs/plan/20260609-environment-runtime-management.md`
- `frontend/src/api/sessions.ts`
- `frontend/src/assets/cygwin-logo-medium.png`
- `frontend/src/assets/tmux-logo-medium.png`
- `frontend/src/components/EnvironmentManagement.vue`
- `frontend/src/i18n/locales/en-US.json`
- `frontend/src/i18n/locales/zh-CN.json`
- `frontend/src/types/sessions.ts`
- `src/cc_ttyd/api.py`
- `src/cc_ttyd/models.py`
- `src/cc_ttyd/services.py`
- `tests/test_api.py`
- `tests/test_terminal_service.py`

## Acceptance criteria checklist

- [x] 环境管理页有 Windows、Cygwin、WSL tab 导航。
- [x] ttyd 配置作为 tab 外独立区域显示。
- [x] ttyd 检测响应包含 available/path/version/reason。
- [x] 用户可保存 explicit ttyd path，并复用既有 terminal settings 持久化。
- [x] Cygwin tab 支持 bash/tmux 检测。
- [x] Cygwin 检测展示 bash 和 tmux 的可用性、路径、版本或原因。
- [x] 用户可保存 explicit Cygwin bash path，后续检测和 Cygwin terminal 启动可优先使用。
- [x] tmux 检测只在 Cygwin tab 出现。
- [x] 后端检测失败返回正常 unavailable 响应，不以未安装作为 500。
- [x] 现有 `/terminals` 终端管理能力有回归测试覆盖。
- [x] 现有会话创建、删除、restart 相关流程未在本改动中移除；相关现有测试继续通过。

## Commands

已执行并通过：

```text
uv run pytest tests/test_terminal_service.py tests/test_api.py
```

结果：25 passed, 1 warning。warning 来自 FastAPI TestClient / Starlette 对 httpx 的 deprecation 提示。

```text
uv run ruff format --check src/cc_ttyd/models.py src/cc_ttyd/services.py src/cc_ttyd/api.py tests/test_terminal_service.py tests/test_api.py
```

结果：5 files already formatted。

```text
yarn --cwd frontend typecheck
```

结果：vue-tsc --noEmit 通过。

```text
yarn --cwd frontend lint
```

结果：eslint . 通过。

```text
yarn --cwd frontend prettier --check src/components/EnvironmentManagement.vue src/api/sessions.ts src/types/sessions.ts src/i18n/locales/zh-CN.json src/i18n/locales/en-US.json
```

结果：All matched files use Prettier code style。

## Missed or expanded scope

- 未执行浏览器手工验证；用户指定本次使用 lint/test/format 即可。
- 未实现自动安装 Cygwin、tmux、ttyd 或 WSL，符合 Non-goals。
- 未实现 WSL distro 管理，符合已决策范围。
- 未迁移 terminal definitions 管理到环境管理页，符合 Non-goals。

## Risks and incomplete items

- 不同本机环境下 Cygwin bash、tmux、ttyd、WSL 的实际检测结果依赖安装路径和 PATH；当前验证主要覆盖代码路径和 mock 行为。
- 浏览器交互未手工验证，因此 UI 视觉布局和真实 API 联动仍建议在合并前人工点检一次。
- FastAPI TestClient deprecation warning 不影响当前测试结果，但未来依赖升级时可能需要处理。

## Conclusion

当前实现与已接受的 Requirement 和 Plan 对齐。自动化验证命令均已通过；剩余风险主要是本机运行时依赖差异和未执行浏览器手工点检。
