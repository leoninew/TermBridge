# Makefile PyPI release 入口

- Flow mode: light
- Stage: Requirement
- Review status: Accepted
- Date: 2026-06-15

## Goal

为项目根目录 `Makefile` 添加一个 `release` 入口，用于将 `dist` 目录中指定版本的 Python 分发制品上传到 PyPI，减少手动拼写上传命令的出错概率。

## Non-goal

1. 不在本次变更中自动执行真实上传或发布新版本。
2. 不修改 `pyproject.toml` 中的项目版本号、构建配置或包元数据。
3. 不改变现有 `build` 目标的构建流程。
4. 不引入 PyPI token、用户名、密码等凭据到仓库。
5. 不处理 TestPyPI 发布流程，除非后续明确要求。

## Acceptance

1. `Makefile` 提供 `release` 目标，并在 `help` 输出中展示用法。
2. `release` 目标要求调用方显式指定版本号，例如 `make release VERSION=0.1.6`。
3. 目标只匹配并上传 `dist/termbridge-$(VERSION).tar.gz` 和 `dist/termbridge-$(VERSION)-py3-none-any.whl`，避免误传其他版本制品。
4. 当 `VERSION` 未指定时，命令应失败并给出清晰提示。
5. 当指定版本对应的 dist 制品缺失时，命令应在上传前失败。
6. 对用户暴露的发布入口是 `make release VERSION=<version>`；目标内部可复用项目现有 Python 工具链调用 `twine`，不要求把 `twine` 固定加入项目依赖。

## Risk

1. 真实 PyPI 上传依赖调用环境中已配置的 PyPI 凭据，例如 `TWINE_USERNAME` / `TWINE_PASSWORD` 或 `~/.pypirc`，本需求不记录或管理凭据。
2. `release` 目标会执行外部发布操作，验证阶段只能做 Makefile 语法和失败路径检查，不应在未授权情况下真实上传。
3. 如果未来制品命名或 wheel tag 发生变化，当前按版本精确匹配的文件名可能需要同步调整。

## User Review Notes

- 2026-06-15: 用户通过 SpecFlow 提出：为 `Makefile` 添加一个 `release` 入口，上传 `dist` 里指定版本的制品到 PyPI。
- 2026-06-15: 用户确认对外入口必须是 `make release`；TestPyPI 已验证过，不需要加入 TestPyPI；制品命名固定，开始实现。
