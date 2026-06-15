# justfile PyPI release 入口验证

- Flow mode: light
- Stage: Verification
- Review status: Accepted
- Date: 2026-06-15

## What changed

1. `docs/requirement/20260615-pypi-release-makefile.md` 已按用户反馈标记为 `Accepted`，并记录：对外入口必须是 `just release`、不加入 TestPyPI、制品命名固定。
2. `justfile` 增加 `build` 和 `release` recipe。
3. `just --list` 可展示 `release VERSION` recipe。
4. 新增 `release` 目标：
   - 未传 `VERSION` 时直接失败并提示用法。
   - 上传前检查 `dist/termbridge-{{VERSION}}.tar.gz` 是否存在。
   - 上传前检查 `dist/termbridge-{{VERSION}}-py3-none-any.whl` 是否存在。
   - 仅对上述两个精确匹配的指定版本制品执行 `uvx twine upload`。

## Acceptance

1. `justfile` 提供 `release` recipe，并可通过 `just --list` 查看：已满足。
2. `release` 目标要求显式指定版本号：已满足。
3. 只匹配并上传指定版本的 sdist 和 wheel：已满足。
4. `VERSION` 未指定时失败且提示清晰：已验证。
5. 指定版本制品缺失时上传前失败：已验证。
6. 对外入口为 `just release <version>`：已满足。

## Commands

1. `just --list`
   - 结果：通过，输出包含 `release VERSION` recipe。
2. `just --dry-run release 0.1.6`
   - 结果：通过，dry-run 展示只会检查并上传 `dist/termbridge-0.1.6.tar.gz` 与 `dist/termbridge-0.1.6-py3-none-any.whl`。
3. `just --dry-run release`
   - 结果：符合预期失败，错误为缺少参数的 just 用法提示；recipe 内部提示为 `VERSION is required. Usage: just release 0.1.6`。
4. `just release 0.0.0`
   - 结果：符合预期失败，上传前报错 `Missing dist/termbridge-0.0.0.tar.gz`。

## Remaining risk

1. 未执行真实 `just release 0.1.6`，避免在未明确授权的情况下向真实 PyPI 上传制品。
2. 真实发布仍依赖执行环境已配置 PyPI 凭据，例如 `TWINE_USERNAME` / `TWINE_PASSWORD` 或 `~/.pypirc`。
3. 当前工作区存在本次未触及的 `uv.lock` 修改，提交前建议确认是否与本次变更拆分。
