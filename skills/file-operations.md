---
name: file_ops
label: 文件操作
description: 读写和管理工作目录中的文件
tools:
  - read_file
  - write_file
  - list_files
---

# 文件操作能力

你可以使用以下工具来操作独立工作目录中的文件：

- **read_file** — 读取文件内容，参数 `file_path`（相对路径）
- **write_file** — 创建或覆盖文件，参数 `file_path` 和 `content`
- **list_files** — 列出目录内容，参数 `path`（可选，默认当前目录）

## 使用建议

1. 在写入文件前，先用 list_files 确认目录结构
2. 对大型输出优先写入文件而非在对话中直接输出全部内容
3. 所有路径操作均在你的独立工作目录内进行，无需担心与其他智能体冲突
