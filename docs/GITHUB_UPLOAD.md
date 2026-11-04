# 上传到 GitHub

项目公开仓库：[AHuaWinliver/FileAtlas](https://github.com/AHuaWinliver/FileAtlas)。下面说明如何上传自己的副本或发布后续版本。

建议仓库名称为 `FileAtlas`，简介：

> Windows 智能文件整理工具：Claude Code 自动标签、多级分类、目录监控与可撤销归档。

建议 Topics：`windows`、`file-manager`、`file-organizer`、`claude-code`、`pyside6`、`automation`、`tagging`。

## 使用 GitHub 网页上传

1. 在 GitHub 创建空仓库，名称填写 `FileAtlas`。本地已包含 README 和 LICENSE，创建时不必重复生成。
2. 点击 **uploading an existing file** 或 **Add file → Upload files**。
3. 上传此目录中的文件与子目录，保持 `README.md` 位于仓库根目录；包含隐藏的 `.github`、`.gitignore` 等文件。
4. 提交后检查首页截图及文档链接。

网页上传时不要只把整个源码 ZIP 作为一个文件提交。应先解压，上传其中的仓库内容。若文件选择器隐藏点号文件，使用 Git 命令或 GitHub Desktop 更方便。

## 使用 Git 推送

在自己的新仓库目录打开 PowerShell。如果从源码 ZIP 解压，先运行 `git init -b main`。以下示例用于首次推送到自己的空仓库：

```powershell
git add .
git commit -m "Initial release: FileAtlas 0.1.0"
git remote add origin https://github.com/YOUR_USERNAME/FileAtlas.git
git push -u origin main
```

将 `YOUR_USERNAME` 替换为自己的 GitHub 用户名；首次使用 Git 时，先配置自己的提交姓名和邮箱。已有仓库可通过 Fork 或 Clone 继续开发，无需重复创建仓库或添加远程地址。

## 上传可运行程序

在 **Releases → Draft a new release** 中创建 `v0.1.0`，附上单独的 `FileAtlas-0.1.0-win64.zip`，说明文字可使用 [首版发布说明](RELEASE_NOTES_v0.1.0.md)。不要把 EXE、`_internal`、虚拟环境或应用数据库放入源码仓库。

## 自动化流程

推送和 Pull Request 会触发 Windows 核心测试。手动运行 **Build Windows package** 工作流可构建便携包，并在工作流 Artifacts 中下载。该流程只生成构建产物，不会自动创建或发布 Release，也不调用 AI 模型。
