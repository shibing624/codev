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
[![python_vesion](https://img.shields.io/badge/Python-3.8%2B-green.svg)](requirements.txt)
[![GitHub issues](https://img.shields.io/github/issues/shibing624/codev.svg)](https://github.com/shibing624/codev/issues)
[![Wechat Group](https://img.shields.io/badge/wechat-group-green.svg?logo=wechat)](#Contact)

## 简介

CodeV是一个在您的终端中运行的编码助手，帮助您更高效地编写、编辑和执行代码。

## 特性

- 💬 在终端直接交互的聊天界面
- 🚀 执行AI建议的命令
- ✏️ 用AI生成的代码编辑文件
- 🖼️ 支持上传图片提供视觉上下文
- 🔒 灵活的批准策略（建议、自动编辑、全自动）
- 📝 清晰的命令解释
- 🛠️ 支持MCP服务器和工具集成

## 安装

### 选项1：通过pip安装
```bash
pip install pycodev
```

### 选项2：从源代码安装
```bash
git clone https://github.com/shibing624/codev.git
cd codev
pip install -e .
```

### 设置您的OpenAI API密钥：
```bash
export OPENAI_API_KEY=your_api_key_here
export OPENAI_BASE_URL=your_base_url_here # https://api.openai.com/v1
```

## 使用方法

### 基本用法：
```bash
codev
```

### 使用初始提示：
```bash
codev --prompt "创建一个带有REST API的Flask应用程序"
```

### 使用批准策略：
```bash
codev --approval-policy suggest|auto-edit|full-auto
```

## 命令行参数

| 参数 | 描述 |
|----------|-------------|
| `--model` | 要使用的模型（默认：gpt-4o） |
| `--prompt` | 发送给模型的初始提示 |
| `--image` | 与提示一起包含的图片文件路径（可多次使用） |
| `--approval-policy` | 命令的批准策略（suggest、auto-edit、full-auto） |
| `--writable` | 额外的可写目录（可多次使用） |
| `--full-stdout` | 显示命令的完整标准输出 |
| `--notify` | 启用桌面通知 |
| `--config` | 配置文件路径 |

## 批准策略

- `suggest`：AI建议命令和文件编辑，但需要您的批准
- `auto-edit`：AI自动编辑文件，但需要批准shell命令
- `full-auto`：AI自动执行命令和编辑文件，无需批准

## 聊天命令

- `/help` - 显示帮助信息
- `/model` - 在会话中切换LLM模型
- `/approval` - 切换批准策略模式
- `/history` - 显示会话中的命令和文件历史
- `/clear` - 清除屏幕和上下文
- `/clearhistory` - 清除命令历史
- `/compact` - 将上下文压缩为摘要
- `/exit` 或 `/quit` - 退出应用程序

## 键盘快捷键

- Enter - 发送消息
- Ctrl+J - 插入换行符
- Up/Down - 滚动提示历史记录
- Esc(×2) - 中断当前操作
- Ctrl+C - 退出Codev

## 配置

您可以创建一个具有以下结构的JSON配置文件：

```json
{
  "model": "gpt-4o",
  "instructions": "给AI的自定义指令",
  "notify": false,
  "theme": {
    "user": "blue",
    "assistant": "green",
    "system": "yellow",
    "error": "red",
    "loading": "cyan"
  }
}
```

然后使用以下命令：
```bash
codev --config path/to/config.json
```

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