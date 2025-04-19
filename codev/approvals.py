# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description:
"""
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

# Approval policy types
ApprovalPolicy = str  # "suggest", "auto-edit", or "full-auto"


@dataclass
class ApplyPatchCommand:
    """Represents a patch to be applied to a file"""
    file_path: str
    content: str


def generate_command_explanation(command: List[str], model: str) -> str:
    """
    Generate a human-readable explanation of what a command does
    
    Args:
        command: The command to explain
        model: The model to use for explanation
    
    Returns:
        A string explaining what the command does
    """
    command_str = str(command)
    return f"This command would execute: `{command_str}`\n\nThis might affect your system. Please review carefully."


def confirm_command(command: List[str], patch: Optional[ApplyPatchCommand] = None) -> Tuple[str, Optional[str]]:
    """
    Get confirmation from the user for executing a command
    
    Args:
        command: The command to confirm
        patch: Optional file patch to apply
    
    Returns:
        Tuple of (decision, custom_deny_message)
    """
    command_str = " ".join(command)

    if patch:
        print(f"\nThe AI assistant wants to edit file: {patch.file_path}")
        print(f"Preview of changes:")
        print("```")
        lines = patch.content.split('\n')
        # Only show first 10 lines if too long
        if len(lines) > 10:
            print('\n'.join(lines[:10]))
            print(f"... and {len(lines) - 10} more lines")
        else:
            print(patch.content)
        print("```")
    else:
        print(f"\nThe AI assistant wants to run: {command_str}")

    print("\nOptions:")
    print("  (a)pprove - Run the command")
    print("  (d)eny - Reject the command")
    print("  (e)xplain - Ask for an explanation")
    print("  (m)odify - Modify the command before running")

    decision = ""
    while decision not in ["a", "d", "e", "m"]:
        decision = input("Your choice [a/d/e/m]: ").lower()

    custom_deny_message = None
    if decision == "d":
        custom_deny_message = input("Reason for denial (optional): ")

    # Map decision to return values
    decision_map = {
        "a": "approve",
        "d": "deny",
        "e": "explain",
        "m": "modify"
    }

    return decision_map[decision], custom_deny_message
