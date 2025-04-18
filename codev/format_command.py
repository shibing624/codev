# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description:
"""
from typing import List
import shlex
import re


def format_command_for_display(command: List[str]) -> str:
    """
    Format a command array for display to the user
    
    Args:
        command: List of command parts (command and arguments)
        
    Returns:
        A formatted string representation of the command
    """
    # Handle empty command
    if not command:
        return ""

    # If the command is already a string, just return it
    if isinstance(command, str):
        return command

    # Join the command parts with proper shell escaping
    try:
        formatted = " ".join(shlex.quote(arg) for arg in command)
        return formatted
    except Exception:
        # Fallback if shlex.quote fails for some reason
        return " ".join(command)


def parse_command(command_str: str) -> List[str]:
    """
    Parse a command string into a list of command parts
    
    Args:
        command_str: The command string to parse
        
    Returns:
        List of command parts
    """
    try:
        return shlex.split(command_str)
    except Exception:
        # Simple fallback if shlex.split fails
        # Split on spaces but preserve quoted strings
        pattern = r'([^\s"\']+)|"([^"]*)"|\'([^\']*)\')'
        return [match[0] or match[1] or match[2] for match in re.findall(pattern, command_str)]
