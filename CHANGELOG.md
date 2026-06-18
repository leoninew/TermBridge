# Changelog

All notable changes to TermBridge will be documented in this file.

This project currently follows a pre-release changelog format. Versioning and release channels may change before the first stable release.

## [0.1.9] - 2026-06-18

### Added

- **Session 内联重命名**：侧边栏 session 树节点新增悬停编辑图标，点击弹出模态框即可重命名；新增 `PATCH /api/sessions/{session_id}` 端点，含名称校验和重复拒绝；重命名通过 `FileSessionRepository` 持久化，session key 与 entry name 保持同步；保存时直接更新本地 session 状态，无需整树刷新。
- **Shortcut 拖拽排序**：环境组内的 shortcut 卡片支持拖拽重新排序。
- **Shortcut 独立存储与用量统计**：shortcuts 单独持久化，并记录使用次数。
- **Session 树批量 tmux 状态检查**：新增 refresh 参数，支持批量 tmux 状态轮询。
- **实时状态检查与乐观 UI 更新**：session 状态实时反馈到前端，操作即时响应。
- **Terminal tab 名称包含 workspace 上下文**：tab 标题显示所属 workspace 信息。
- **前端加载状态与防抖保护**：action buttons 添加 loading 状态和 debounce，防止重复点击。
- **非活跃 session 目录默认折叠**：自动折叠不活跃的 session 目录，减少干扰。
- **非活跃状态主题适配**：terminal 非活跃状态颜色跟随 app 主题。
- **运行时设置集中管理**：粗粒度 runtime settings 统一收敛到 config 层。
- **PyPI 发布自动化**：新增 Makefile `release` target，支持 twine 上传；PyPI 凭证通过 `.env` 配置。
- **ttyd 文件模式启动头与日志路径修复**：ttyd 文件模式下输出启动 header 并修正 log 路径。

### Fixed

- **Cygwin 路径构造修复**：非 Windows 平台不再错误拼接 Cygwin 路径。
- **Cygwin 环境使用 Windows PATH 语义**：统一 Windows 路径规则。
- **Workspace 路径转换**：直接通过 `cygpath.exe` 转换，更可靠。
- **Tmux window ID 过期恢复**：刷新时按名称恢复失效的 tmux window ID。
- **Session 重命名后 tmux window 名称同步**：保持 tmux 与 session 数据一致。
- **运行时状态刷新为权威来源**：确保刷新结果覆盖本地缓存。
- **Session 元数据在刷新中保留**：刷新不丢失 session 附加信息。
- **Session 表单保留初始 host 并在创建时重置**：表单状态正确管理。
- **Toast 自动关闭时序移入 store**：避免组件卸载后的时序问题。
- **CI 构建不再因缺少 Makefile 失败**：修复 CI 环境依赖。

### Changed

- **项目任务迁移到 just**：用 `just` 替代 Makefile/shell scripts 管理开发任务。
- **Shortcut 管理重构**：底层数据结构变更，shortcuts 独立存储。

## [0.1.8] - 2026-06-17

### Added

- **实时状态检查与乐观 UI 更新**：session 状态实时反馈到前端，操作即时响应。
- **Session 树批量 tmux 状态检查**：新增 refresh 参数，支持批量 tmux 状态轮询。
- **避免 create/delete 触发整树刷新**：前端在创建和删除 session 时跳过不必要的 session-tree 刷新。

### Fixed

- **Session 元数据在刷新中保留**：刷新不丢失 session 附加信息。

## [0.1.7] - 2026-06-17

### Added

- **前端加载状态与防抖保护**：action buttons 添加 loading 状态和 debounce，防止重复点击。
- **非活跃 session 目录默认折叠**：自动折叠不活跃的 session 目录，减少干扰。
- **非活跃状态主题适配**：terminal 非活跃状态颜色跟随 app 主题。
- **运行时设置集中管理**：粗粒度 runtime settings 统一收敛到 config 层。

## [0.1.6] - 2026-06-16

### Added

- **Terminal tab 名称包含 workspace 上下文**：tab 标题显示所属 workspace 信息。
- **PyPI 发布自动化**：新增 Makefile `release` target，支持 twine 上传。
- **Shortcut 独立存储与用量统计**：shortcuts 单独持久化，并记录使用次数。
- **项目任务迁移到 just**：用 `just` 管理开发任务。

## [0.1.5] - 2026-06-16

### Added

- **ttyd 安全加固**：支持 Basic Auth 和 FastAPI proxy 认证。
- **Session 拖拽排序**：session 侧边栏支持拖拽重新排序。
- **两级 session 分组**：侧边栏实现两级分组展示。
- **默认 session name**：创建 session 时自动填充默认名称。
- **Session 状态可视化增强**：更丰富的状态指示。
- **ttyd 颜色主题适配**：terminal 颜色跟随 app 主题。
- **Disconnected terminal state**：新增断开的终端状态。

### Changed

- **表单校验迁移到客户端**：替换原生 form validation 为内联 client-side 校验。
- **API 异常统一映射**：业务异常集中处理。

## [0.1.4] - 2026-06-15

### Added

- **可配置的 ttyd 日志模式**：支持文件日志输出。
- **Terminal-first 无边框 UI**：全新设计的终端优先界面。
- **ttyd 安全加固文档**：FastAPI WebSocket proxy 和 auth 配置指南。

## [0.1.3] - 2026-06-11

### Added

- Open-source readiness documentation.
- MIT license.
- README sections for architecture, session model, security boundary, runtime providers, configuration, Docker, build, and development checks.
- Contributing and security policy documents.
- Toast close button and standardized environment labels.

### Changed

- Default Claude Code and Codex shortcuts now use plain `claude` and `codex` commands instead of permission- or sandbox-bypassing example flags.
- Public-facing documentation examples were generalized to avoid local usernames, machine paths, and private workflow names.
- Stopped session lifecycle simplified and session storage reorganized.

### Security

- Documented that TermBridge is intended for local/trusted environments and does not currently include auth, HTTPS, multi-user isolation, or command sandboxing.

## [0.1.2] - 2026-06-10

### Added

- **WSL runtime 支持**：readiness-based WSL runtimes 检测。
- **多标签终端 UI**：multi-tab terminal 界面。
- **树形 session 列表**：侧边栏树状 session 展示。
- **Home onboarding 页面**：vue-router + Pinia 实现的首页引导。
- **Close-all sessions**：一键关闭所有 session 功能（含确认对话框）。

### Fixed

- Tmux window 生命周期修复，session storage 重组。

## [0.1.1] - 2026-06-09

### Added

- **Environment model 重构**：以 tmux-backed hosts 为核心的环境模型。
- **Bundled frontend distribution**：打包前端静态资源。

### Fixed

- Dev server 绑定到 localhost。

## [0.1.0] - 2026-06-09

### Added

- Initial release.
- Project rename and source restoration.
- Basic terminal session workspace built on ttyd and tmux.
