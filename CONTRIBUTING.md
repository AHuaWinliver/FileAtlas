# 贡献指南

感谢参与 FileAtlas 的改进。

## 本地开发

使用 Windows 11 x64 和 Python 3.12。在独立虚拟环境安装 `requirements-dev.txt`，通过 `python app.py --data-dir validation/dev` 启动隔离的数据目录。

## 提交修改

1. 从 `main` 创建主题分支，每次修改聚焦一个问题。
2. 修改文件移动、复制、路径限制或撤销行为时，补充验证真实行为的测试。
3. 执行 `python -m unittest discover -s tests -v`，涉及监控时运行 `python scripts/validate_worker.py`。
4. 涉及界面时运行 `python scripts/validate_ui.py`，检查渲染、窗口缩放和交互；提交必要截图。
5. 在 PR 中说明触发场景、结果变化、验证方式与未解决的限制。

普通测试不得调用付费模型、访问私人目录或依赖作者电脑。真实 AI 验证是手动可选步骤，使用 `scripts/validate_live.py`。

不要提交应用数据库、模型凭据、`.env`、个人文件、虚拟环境或构建产物。EXE 和发行 ZIP 应作为 Release 附件上传。
