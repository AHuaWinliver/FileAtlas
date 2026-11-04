# 第三方组件

FileAtlas 的 MIT 许可证仅适用于本项目自有代码，不替代依赖组件的许可证。

| 组件 | 项目 | 说明 |
| --- | --- | --- |
| PySide6 / Qt for Python / Shiboken | https://www.qt.io/qt-for-python | 使用开源分发中的相应许可证；以发行包附带的 LGPL/GPL 及其他许可原文为准 |
| watchdog | https://github.com/gorakhargosh/watchdog | 文件系统监控 |
| pypdf | https://github.com/py-pdf/pypdf | PDF 文本提取 |
| python-docx | https://github.com/python-openxml/python-docx | DOCX 文本提取 |
| lxml | https://lxml.de/ | XML 处理及其依赖许可证 |
| Python | https://www.python.org/ | Python 运行时及其第三方组件 |
| PyInstaller | https://pyinstaller.org/ | 构建工具；其发行例外以项目许可原文为准 |

`scripts/build.py` 会复制已安装依赖的可用许可文件与包元数据到发行目录 `licenses/`。Qt DLL 采用动态分发，保留独立 DLL 以便替换兼容版本。原始安装包和对应源码可从上述项目或包元数据记录的上游地址获取。

Claude Code 是用户单独安装的外部工具，不包含在本项目的源码或便携发行包中。模型服务使用条款由对应服务提供方决定。
