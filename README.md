[**🇨🇳中文**](https://github.com/shibing624/codev/blob/main/README.md) | [**🌐English**](https://github.com/shibing624/codev/blob/main/README_EN.md)

<div align="center">
  <a href="https://github.com/shibing624/codev">
    <img src="https://github.com/shibing624/codev/blob/main/docs/codev-logo.png" height="130" alt="Logo">
  </a>
</div>

-----------------

# Codev: Coding Agent That Runs in Your Terminal
[![PyPI version](https://badge.fury.io/py/pycodev.svg)](https://badge.fury.io/py/pycodev)
[![Contributions welcome](https://img.shields.io/badge/contributions-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![License Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![python_vesion](https://img.shields.io/badge/Python-3.10%2B-green.svg)](requirements.txt)
[![GitHub issues](https://img.shields.io/github/issues/shibing624/codev.svg)](https://github.com/shibing624/codev/issues)
[![Wechat Group](https://img.shields.io/badge/wechat-group-green.svg?logo=wechat)](#联系我们)

Codev CLI 是一个基于 agentica 库的 AI 编码助手，它提供了一个交互式终端界面，让您可以与 AI 助手进行对话，执行命令和编辑文件。

## 功能特点

- 💬 在终端直接交互的聊天界面
- 🚀 支持命令执行和文件编辑
- 📝 历史记录管理，包括命令和文件编辑历史
- 🔒 多种审批策略（suggest、auto-edit、full-auto）
- 🖼️ 支持图像输入（用于视觉模型）
- 🛠️ 支持MCP服务器和工具集成

## 安装

### 方式一：通过 pip 安装
```bash
pip install pycodev
```

### 方式二：从源码安装
```bash
# 克隆仓库
git clone https://github.com/shibing624/codev.git
cd codev
pip install -r requirements.txt
pip install -e .
```

### 设置 OpenAI API 密钥
```bash
export OPENAI_API_KEY=你的API密钥
export OPENAI_BASE_URL=你的API基础URL # https://api.openai.com/v1
```

您也可以在 `~/.agentica/.env` 文件中设置这些环境变量。

## 使用方法

### 基本使用

```bash
codev
```

### 使用初始提示

```bash
codev --prompt "创建一个简单的 Python HTTP 服务器"
```

### 指定模型

```bash
codev --model gpt-4o --prompt "优化这段代码"
```

### 使用图像

```bash
codev --image path/to/image.png --prompt "解释这张图中的代码"
```

### 设置审批策略

```bash
# 建议模式（默认）：AI 助手会请求您确认命令和文件编辑
codev --approval suggest

# 自动编辑模式：AI 助手可以自动编辑文件，但需要您确认命令
codev --approval auto-edit

# 完全自动模式：AI 助手可以自动执行命令和编辑文件，无需确认
codev --approval full-auto
```

### 使用配置文件

```bash
codev --config path/to/config.json
```

配置文件示例（config.json）：

```json
{
  "model": "gpt-4o",
  "instructions": "你是一个专注于 Python 开发的 AI 助手",
  "theme": {
    "user": "blue",
    "assistant": "green",
    "system": "yellow",
    "error": "red",
    "loading": "cyan"
  }
}
```

## 命令行选项

| 参数 | 描述 |
|----------|-------------|
| `--model`, `-m` | 使用的模型（例如 gpt-4o, gpt-4-turbo） |
| `--prompt`, `-p` | 初始提示发送给模型 |
| `--image`, `-i` | 图像文件路径（可多次使用） |
| `--approval`, `-a` | 命令审批策略（suggest, auto-edit, full-auto） |
| `--full-stdout`, `-f` | 显示完整的命令输出 |
| `--config`, `-c` | 配置文件路径 |
| `--version`, `-v` | 显示版本信息 |

## 审批策略

- `suggest`：AI 助手会建议命令和文件编辑，但需要您的批准
- `auto-edit`：AI 助手可以自动编辑文件，但需要您批准 shell 命令
- `full-auto`：AI 助手可以自动执行命令和编辑文件，无需批准

## 交互式命令

在交互式会话中，您可以使用以下命令：

- `/help` - 显示帮助信息
- `/model [model_name]` - 查看或更改当前使用的模型
- `/approval [policy]` - 查看或更改当前的审批策略
- `/history [all] [full]` - 显示历史记录
- `/clear` - 清除当前会话
- `/clearhistory [session]` - 清除历史记录
- `/compact` - 将对话上下文压缩为摘要
- `/exit` 或 `/quit` - 退出程序

## 键盘快捷键

- Enter - 发送消息
- Ctrl+J - 插入换行符
- 上/下方向键 - 滚动浏览提示历史
- Esc(×2) - 中断当前操作
- Ctrl+C - 退出 Codev

## 使用 agentica 库

此版本的 Codev CLI 使用 agentica 库作为底层 AI 交互框架。agentica 是一个强大的框架，用于构建智能、具备反思能力、可协作的多模态 AI 代理。

更多关于 agentica 的信息，请访问：https://github.com/shibing624/agentica


## 联系我们

- 问题和建议：[![GitHub issues](https://img.shields.io/github/issues/shibing624/codev.svg)](https://github.com/shibing624/codev/issues)
- 邮件：xuming624@qq.com
- 微信：加我微信（ID：xuming624），备注："姓名-公司-NLP"加入我们的NLP讨论群。

<img src="https://github.com/shibing624/codev/blob/main/docs/wechat.jpeg" width="200" />

## 引用

如果你在研究中使用了`codev`，请按如下格式引用：

APA:
```
Xu, M. Codev: coding agent that runs in your terminal (Version 0.0.2) [Computer software]. https://github.com/shibing624/codev
```

BibTeX:
```
@misc{Xu_codev,
  title={Codev: coding agent that runs in your terminal},
  author={Xu Ming},
  year={2025},
  howpublished={\url{https://github.com/shibing624/codev}},
}
```

## 许可证

本项目采用[Apache License 2.0](/LICENSE)授权协议，可免费用于商业用途。请在产品说明中附加`codev`的链接和授权协议。

## 贡献

我们欢迎对这个项目进行改进的贡献！在提交拉取请求之前，请：

1. 在`tests`目录中添加适当的单元测试
2. 运行`python -m pytest`确保所有测试通过
3. 提交PR时附上清晰的更改描述

## 致谢

- [openai/codex](https://github.com/openai/codex)

感谢他们的杰出工作！ 