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
[![Wechat Group](https://img.shields.io/badge/wechat-group-green.svg?logo=wechat)](#Contact)

## Introduction

Codev is a command-line interface for AI-powered code generation. This Python implementation provides an interactive coding assistant in your terminal, leveraging the OpenAI Chat Completions API to help you write, edit, and execute code more efficiently.

## Features

- 💬 Interactive chat interface directly in your terminal
- 🚀 Execute commands suggested by the AI
- ✏️ Edit files with AI-generated code
- 🖼️ Support for image uploads for visual context
- 🔒 Flexible approval policies (suggest, auto-edit, full-auto)
- 📝 Clear command explanations
- 🛠️ Support for MCP Servers and Tools integration

## Installation

### Option 1: Install via pip
```bash
pip install pycodev
```

### Option 2: Install from source
```bash
git clone https://github.com/shibing624/codev.git
cd codev
pip install -r requirements.txt
pip install -e .
```

### Set up your OpenAI API key:
```bash
export OPENAI_API_KEY=your_api_key_here
export OPENAI_BASE_URL=your_base_url_here # https://api.openai.com/v1
```

You can also set these environment variables in the `~/.agentica/.env` file.

## Usage

### Basic usage:
```bash
codev
```

### With initial prompt:
```bash
codev --prompt "Create a Flask application with a REST API"
```

### With model specification:
```bash
codev --model gpt-4o --prompt "Optimize this code"
```

### With image input:
```bash
codev --image path/to/image.png --prompt "Explain the code in this image"
```

### With approval policy:
```bash
codev --approval suggest|auto-edit|full-auto
```

### With configuration file:
```bash
codev --config path/to/config.json
```

## Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--model`, `-m` | The model to use (default: gpt-4o) |
| `--prompt`, `-p` | Initial prompt to send to the model |
| `--image`, `-i` | Image file paths to include with the prompt (can be used multiple times) |
| `--approval`, `-a` | Approval policy for commands (suggest, auto-edit, full-auto) |
| `--full-stdout`, `-f` | Show full stdout for commands |
| `--config`, `-c` | Path to config file |
| `--version`, `-v` | Show version information |

## Approval Policies

- `suggest`: The AI suggests commands and file edits but requires your approval
- `auto-edit`: The AI automatically edits files but requires approval for shell commands
- `full-auto`: The AI automatically executes commands and edits files without approval

## In-Chat Commands

- `/help` - Show help information
- `/model` - Switch the LLM model during a session
- `/approval` - Switch approval policy mode
- `/history` - Show command & file history for the session
- `/clear` - Clear screen and context
- `/clearhistory` - Clear command history
- `/compact` - Condense context into a summary
- `/exit` or `/quit` - Exit the application

## Keyboard Shortcuts

- Enter - Send message
- Ctrl+J - Insert newline
- Up/Down - Scroll prompt history
- Esc(×2) - Interrupt current action
- Ctrl+C - Quit Codev

## Configuration

You can create a JSON configuration file with the following structure:

```json
{
  "model": "gpt-4o",
  "instructions": "Custom instructions for the AI",
  "theme": {
    "user": "blue",
    "assistant": "green",
    "system": "yellow",
    "error": "red",
    "loading": "cyan"
  }
}
```

Then use it with:
```bash
codev --config path/to/config.json
```

## Contact

- Issues and suggestions: [![GitHub issues](https://img.shields.io/github/issues/shibing624/codev.svg)](https://github.com/shibing624/codev/issues)
- Email: xuming624@qq.com
- WeChat: Add me (WeChat ID: xuming624) with the message: "Name-Company-NLP" to join our NLP discussion group.

<img src="https://github.com/shibing624/codev/blob/main/docs/wechat.jpeg" width="200" />

## Citation

If you use `codev` in your research, please cite:

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

## License

This project is licensed under [The Apache License 2.0](/LICENSE) and can be used freely for commercial purposes. Please include a link to `codev` and the license in your product documentation.

## Contribute

We welcome contributions to improve this project! Before submitting a pull request, please:

1. Add appropriate unit tests in the `tests` directory
2. Run `python -m pytest` to ensure all tests pass
3. Submit your PR with clear descriptions of the changes

## Acknowledgements

- [openai/codex](https://github.com/openai/codex)

Thanks for their great work!
