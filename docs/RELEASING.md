# 构建与发布

1. 更新 `VERSION`、`CHANGELOG.md` 和必要的 README 内容。
2. 在 Windows 11 x64 上用 Python 3.12 安装 `requirements-dev.txt`。
3. 执行核心测试、监控集成测试和界面验证。
4. 运行 `python scripts/build.py`，生成 `release/FileAtlas-<版本>-win64.zip`。
5. 解压到独立目录，验证 EXE 启动。实际 AI 连接需使用自己的 Claude Code 配置另行检查。
6. 在 GitHub 手动创建标签及 Release，上传 ZIP，填写变更与当前限制。

GitHub Actions 的手动打包流程只上传 Artifact，不自动向用户发布版本。构建脚本包含许可证和 SHA-256 校验文件。

工作流使用官方 Actions：[checkout](https://github.com/actions/checkout)、[setup-python](https://github.com/actions/setup-python)、[upload-artifact](https://github.com/actions/upload-artifact)。
