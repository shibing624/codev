# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import sys


sys.path.append('..')
from codev.terminal_chat import TerminalChat
from codev.config import AppConfig

if __name__ == '__main__':
    terminal = TerminalChat(
        config=AppConfig(),
        prompt="",  # Initial prompt (optional)
        approval_policy="full-auto",  # Options: "suggest", "auto-edit", "full-auto"
    )
    terminal.run()
