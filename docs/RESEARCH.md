# Windows 文件管理与自动整理调研

调研日期：2026-11-04。下面按功能匹配选择代表产品，并非性能实测榜单，没有可证明“全球唯一最好”的统一标准。

| 产品 | 官方资料中的重点 | FileAtlas 采用的方向 |
|---|---|---|
| [Directory Opus](https://www.gpsoft.com.au/help/opus12/Documents/Scripting.htm) | 脚本接口可获取文件列表及元数据 | 可配置分类与可追溯操作 |
| [XYplorer](https://www.xyplorer.com/features.php) | 标签、标签检索、注释和脚本 | 标签资料库与分类检索 |
| [TagSpaces](https://docs.tagspaces.org/tagging/) | 文件名或 sidecar 标签，本地文件管理 | 本地优先的标签体验；本版选择 SQLite 存储 |
| [File Juggler](https://www.filejuggler.com/documentation) | 监控文件夹，用条件和动作执行整理 | 稳定检测、自动归档、错误记录 |

本项目针对“现有多级分类 + 独立目标路径 + Claude Code 语义判定 + 监控归档 + 实时目录”组合需求实现。当前版本没有宣称取代这些成熟产品的双栏操作、压缩、FTP、全文索引、插件生态或多年稳定性积累。

Claude 集成依据：[Claude Code 非交互调用文档](https://code.claude.com/docs/en/headless)。启动参数以本机 `claude --help` 实际支持的选项核对。保留现有认证，不使用会忽略订阅登录的 bare 模式；通过工具列表和设置禁用本次分类不需要的执行能力。
