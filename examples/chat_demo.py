# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import sys

sys.path.append('..')
from codev.terminal_chat import TerminalChat

if __name__ == '__main__':
    m = TerminalChat()
    m.send_message_to_model('write a python script to read a pdf file')
