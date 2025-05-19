# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""

import sys
import asyncio

sys.path.append('..')
from codev.terminal_chat import TerminalChat


async def simple_chat():
    """
    A simple chat demo that sends a single message and displays the response
    """
    # Initialize the terminal chat
    terminal = TerminalChat()

    # Send a message to the agent
    await terminal.send_message_to_agent("Hello, can you help me with Python programming?")

    # You can send another message if you want
    # await terminal.send_message_to_agent("How do I read a CSV file in Python?")


if __name__ == '__main__':
    # Run the async function
    asyncio.run(simple_chat())