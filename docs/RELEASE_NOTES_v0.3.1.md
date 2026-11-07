# FileAtlas v0.3.1

发布日期为 2026-11-07。此版本提供 Windows 11 x64 安装程序、便携版、源码和完整交付包，包含 v0.3.0 源码标签中的整包整理功能及后续预览修复。

## 相比上一个安装版 v0.2.1

### 文件夹优先整理

软件从整理源上层判断目录归属。完整文件夹名匹配唯一规则时，可将整个目录作为一个整理项。分类依据支持 `文件夹规则：齿轮箱台架交付 | 电驱试验资料包`，多个名称用 `|` 分隔。

与唯一可归档分类同名的目录也可进入整包判断。若分类带有扩展名规则，包内文件类型须符合规则。嵌套目录命中其他显式归属时，软件继续检查下一层。

对于明确命名但缺少规则的目录，Claude Code 可根据目录名、父级名称和有限的浅层相对名称判断归属。模型结果按目录证据与分类设置缓存。混合目录、通用名称或证据不足时继续下钻。目录判断发送的名称会使用当前配置的模型服务。

整包保留原有文件、相对路径和空子目录，共享一个索引条目、归档记录和撤销入口。复制和移动前后进行结构与内容校验，归档时处理同名冲突。整包发生变化时，撤销会保留副本并给出原因。模型判断的整包在移动模式下先进入待审核。CAE 求解材料与工况保护规则继续参与判断。

### 工作台与进度

- “启动整理”扫描现有材料并持续监控源目录。
- “暂停整理”在当前文件或整包完成后暂停，“继续整理”检查剩余材料。
- “停止整理”在当前项完成后结束本轮，再次启动时重新扫描。
- “扫描源文件夹”执行单次扫描。
- 工作台显示当前阶段和 `已处理/本轮总数`，整包计一项。处理计数包含失败的尝试，具体异常可在整理记录中查阅。
- 目录导入与导出、复制校验、撤销、CAE 模板、文件预览及 Claude Code 检测提供进度反馈。

### 活动、目录与说明

“清空动态”和“清空日志”同步从下一条新消息开始显示，设置会保存在本地。历史归档记录和撤销入口可继续使用。文件资料库和待审核页支持单独清空预览。

资料库、分类树和 Markdown 导出为目录整包显示标识。中英文 README 使用七张应用截图，串起设置规则、扫描、审核、查看目录与撤销的完整流程。截图来自临时演示数据，散件分类使用模拟模型响应。

## v0.3.0 源码标签之后的修复

修复后台预览任务已完成而界面偶尔停留在“正在读取预览”的问题。预览结果通过窗口持有的信号回到界面线程，切换选择或清空预览后的过期结果会被忽略。

## 下载与升级

| 文件 | 用途 |
| --- | --- |
| `FileAtlas-0.3.1-Setup.exe` | 当前用户 Windows 安装程序 |
| `FileAtlas-0.3.1-win64.zip` | 解压运行的便携版，保留 `_internal` |
| `FileAtlas-0.3.1-source.zip` | 该发布提交的源码和构建脚本 |
| `FileAtlas-0.3.1-complete.zip` | 安装程序、便携版、源码、使用说明和内部校验清单 |
| `SHA256SUMS.txt` | 四个发行文件的 SHA-256 |

1. 从托盘退出正在运行的 FileAtlas。
2. 备份 `%LOCALAPPDATA%\FileAtlas`，其中包含分类、标签、设置和操作记录。
3. 运行安装程序，或将便携版解压到单独目录后运行。
4. 核对整理源与保存地址，再在工作台启动整理。已有 SQLite 数据库会自动补充整包类型字段。
5. AI 判断需要本机可用的 Claude Code 和模型配置。

## 验证范围

本机验证覆盖 31 项核心测试、从空闲启动监控、文件更新和同名归档、整包内部不逐文件分类、七个界面演示以及 Windows EXE 启动。另用临时样例验证了 C 盘与 G 盘之间的整包移动和撤销。模型分支使用模拟响应验证。

安装程序完成编译与文件完整性检查。真实安装和卸载流程、大规模长时间运行、断电故障注入及长期网络盘使用仍需进一步验证。中断操作会标记为 `recovery`，可据源路径和目标路径人工核对。图片、扫描 PDF、旧版 Office、音视频与压缩包分类使用名称及元数据。

## English release notes

FileAtlas v0.3.1 packages the folder-first workflow introduced by the v0.3.0 source tag and includes the subsequent preview fix.

- Evaluate folders from the top down. Match explicit folder-name rules or use category names and shallow model evidence. Descend into mixed folders and conflicting nested scopes.
- Keep a delivery folder intact, including relative paths and empty directories. A bundle has one catalog entry, operation record, progress item, and verified undo action.
- Start, pause, resume, or stop filing from the dashboard. The current pass displays `processed/total`. Failed attempts count as processed attempts and have separate activity details.
- Show progress for folder import and export, filing, undo, previews, CAE templates, and Claude Code detection.
- Clear activity views and previews. Browse operation history and undo archived items.
- Read illustrated Chinese and English READMEs with seven application screenshots. The screenshots use demo data and a simulated model response.
- Fix asynchronous preview results occasionally leaving the interface at the loading message. Stale results are ignored after the selection changes or the preview is cleared.

For an upgrade, exit FileAtlas from its tray menu, back up `%LOCALAPPDATA%\FileAtlas`, and install or extract the new version. Verify the source and destination paths, then start filing. Existing databases receive the folder-type migration automatically.

Download the installer, portable ZIP, source ZIP, or complete bundle from this release. Verify the downloads using `SHA256SUMS.txt`. AI classification requires a configured local Claude Code installation and its selected model service. Model-selected bundles require review in move mode.

Validation includes 31 core tests, monitoring integration, the illustrated workflow, EXE startup, and a C-to-G-drive bundle move and undo. Model branches use simulated responses. Installer compilation and integrity checks have been performed. Installation and uninstallation, power-failure injection, endurance, and long-running network-drive behavior need further validation.
