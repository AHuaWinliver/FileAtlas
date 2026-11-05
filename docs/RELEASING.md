# 构建与发布

1. 更新 `VERSION`、`CHANGELOG.md` 和必要的 README 内容。
2. 在 Windows 11 x64 上用 Python 3.12 安装 `requirements-dev.txt`。
3. 执行核心测试、监控集成测试和界面验证。
4. 运行 `python scripts/build.py`，生成 `release/FileAtlas-<版本>-win64.zip`。
5. 解压到独立目录，验证 EXE 启动。实际 AI 连接需使用自己的 Claude Code 配置另行检查。
6. 在 GitHub 手动创建标签及 Release，上传 ZIP，填写变更与当前限制。

需要安装版时，先安装官方 Inno Setup 6/7，再运行 `python scripts/build_installer.py --iscc <ISCC.exe 路径>`。随后将完整源码纳入 Git 跟踪，运行 `python scripts/package_bundle.py`，生成包含源码、安装程序、便携版及说明的完整 ZIP。此脚本只读取已跟踪文件，不包含 Git 历史、凭据、缓存、应用数据库或虚拟环境。

GitHub Actions 的手动打包流程只上传 Artifact，不自动向用户发布版本。构建脚本包含许可证和 SHA-256 校验文件。

工作流使用官方 Actions：[checkout](https://github.com/actions/checkout)、[setup-python](https://github.com/actions/setup-python)、[upload-artifact](https://github.com/actions/upload-artifact)。
