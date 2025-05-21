# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Command processing module, implements various interactive commands
"""

import os
import enum
import asyncio
from loguru import logger
from agentica.model.message import SystemMessage

from codev.models import get_available_models


class ApprovalPolicy(str, enum.Enum):
    """Command approval policy enumeration"""
    SUGGEST = "suggest"  # Requires user confirmation for all operations
    AUTO_EDIT = "auto-edit"  # Automatically edits files, but requires command confirmation
    FULL_AUTO = "full-auto"  # Fully automatic mode, no confirmation needed


class TermColor:
    """Terminal color definitions"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_BLACK = "\033[90m"
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"


# Color mapping
COLOR_MAP = {
    "red": TermColor.RED,
    "green": TermColor.GREEN,
    "yellow": TermColor.YELLOW,
    "blue": TermColor.BLUE,
    "magenta": TermColor.MAGENTA,
    "cyan": TermColor.CYAN,
    "white": TermColor.WHITE,
    "bright_red": TermColor.BRIGHT_RED,
    "bright_green": TermColor.BRIGHT_GREEN,
    "bright_yellow": TermColor.BRIGHT_YELLOW,
    "bright_blue": TermColor.BRIGHT_BLUE,
    "bright_magenta": TermColor.BRIGHT_MAGENTA,
    "bright_cyan": TermColor.BRIGHT_CYAN,
    "bright_white": TermColor.BRIGHT_WHITE,
}

# Policy colors
POLICY_COLORS = {
    "suggest": TermColor.WHITE,
    "auto-edit": TermColor.BRIGHT_GREEN,
    "full-auto": TermColor.GREEN,
}


class CommandHandler:
    """Command handler, manages processing logic for all special commands"""

    def __init__(self, terminal):
        """
        Initialize command handler
        
        Args:
            terminal: TerminalChat instance reference, for accessing and updating terminal state
        """
        self.terminal = terminal
        self.commands = {
            "/help": self.show_help,
            "/model": self.switch_model,
            "/approval": self.switch_approval_policy,
            "/history": self.show_history,
            "/clear": self.clear_screen,
            "/clearhistory": self.clear_history,
            "/compact": self.compact_context,
            "/exit": self.exit_app,
            "/quit": self.exit_app,
        }

    def handle_command(self, command: str) -> bool:
        """
        Process special commands
        
        Args:
            command: User input command
            
        Returns:
            True if command was processed, False if not a special command
        """
        cmd_parts = command.strip().split()
        cmd = cmd_parts[0].lower() if cmd_parts else ""
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []

        if cmd in self.commands:
            handler = self.commands[cmd]
            # Check if arguments are supported
            if handler.__code__.co_argcount > 1:  # First argument is self
                handler(args)
            else:
                handler()
            return True
        return False

    def show_help(self):
        """Display help information"""
        help_text = """
╭──────────────────────────────────────────────────────────────────────────────╮
│ Available Commands                                                           │
│                                                                              │
│ Slash Commands                                                               │
│ /help – Show this help information                                           │
│ /model – Switch language model in session                                    │
│ /approval – Switch approval mode                                             │
│ /history [all] [full] – Show command and file history                        │
│ /clear – Clear screen and context                                            │
│ /clearhistory – Clear command history                                        │
│ /compact – Compress conversation context to summary                          │
│                                                                              │
│ Keyboard Shortcuts                                                           │
│ Enter+Enter – Send message                                                         │
│ Ctrl+C – Exit Codev                                                          │
╰──────────────────────────────────────────────────────────────────────────────╯
"""
        print(help_text)

    def switch_model(self):
        """Switch model"""
        try:
            available_models = get_available_models()

            if not available_models:
                print(f"{TermColor.RED}Unable to get list of available models.{TermColor.RESET}")
                return

            print(f"{TermColor.CYAN}Available models:{TermColor.RESET}")
            for i, model in enumerate(available_models, 1):
                current = " (currently used)" if model == self.terminal.config.model else ""
                print(f"{i}. {model}{current}")

            print(f"\nCurrent model: {TermColor.GREEN}{self.terminal.config.model}{TermColor.RESET}")
            print(f"Please enter the model number or name to use:")

            selection = input("> ").strip()

            # Check if it's a number
            if selection.isdigit() and 1 <= int(selection) <= len(available_models):
                model = available_models[int(selection) - 1]
            else:
                # Assume it's a model name
                model = selection
                if model not in available_models:
                    print(
                        f"{TermColor.YELLOW}Warning: '{model}' is not in the list of available models.{TermColor.RESET}")
                    model = self.terminal.config.model  # Keep current model if invalid selection

            # Update model
            self.terminal.config.model = model
            print(f"{TermColor.GREEN}Switched to model: {model}{TermColor.RESET}")

            # Add system message to conversation history
            self.terminal.agent.agent.memory.add_message(SystemMessage(content=f"Model has been switched to {model}."))

        except Exception as e:
            print(f"{TermColor.RED}Error switching model: {str(e)}{TermColor.RESET}")
            logger.exception("Error switching model:")

    def switch_approval_policy(self):
        """Switch command approval policy"""
        policies = [policy.value for policy in ApprovalPolicy]
        policy_descriptions = {
            "suggest": "Requires user confirmation for all operations",
            "auto-edit": "Automatically edits files, but requires command confirmation",
            "full-auto": "Fully automatic mode, no confirmation needed"
        }

        # Custom colors
        policy_colors = {
            "suggest": TermColor.WHITE,
            "auto-edit": TermColor.BRIGHT_GREEN,
            "full-auto": TermColor.GREEN,
        }

        print(f"{TermColor.CYAN}Available approval policies:{TermColor.RESET}")
        for i, policy in enumerate(policies, 1):
            current = " (currently used)" if policy == self.terminal.approval_policy else ""
            policy_color = policy_colors.get(policy, TermColor.WHITE)
            print(f"{i}. {policy_color}{policy}{TermColor.RESET} - {policy_descriptions[policy]}{current}")

        print(f"\nCurrent policy: {policy_colors.get(self.terminal.approval_policy, TermColor.WHITE)}"
              f"{self.terminal.approval_policy}{TermColor.RESET}")
        print(f"Please enter the policy number or name to use:")

        selection = input("> ").strip().lower()

        # Check if it's a number
        if selection.isdigit() and 1 <= int(selection) <= len(policies):
            policy = policies[int(selection) - 1]
        else:
            # Assume it's a policy name
            policy = selection
            if policy not in policies:
                print(f"{TermColor.RED}Invalid policy: '{policy}'. Keeping current policy unchanged.{TermColor.RESET}")
                return

        # Update policy
        self.terminal.approval_policy = policy
        print(f"{TermColor.GREEN}Switched approval policy to: {policy_colors.get(policy, TermColor.WHITE)}"
              f"{policy}{TermColor.RESET}")

        self.terminal.agent.agent.memory.add_message(SystemMessage(content= f"Approval policy has been switched to {policy}."))

    def show_history(self, args=None):
        """
        Show command and file edit history
        
        Args:
            args: Command argument list, may include 'all' or 'full'
        """
        args = args or []
        show_all = 'all' in args  # Whether to show all history, not just current session
        show_full = 'full' in args  # Whether to show full history, without limit on entries

        # Use history manager to display history
        if hasattr(self.terminal, 'history_manager'):
            self.terminal.history_manager.show_history(
                limit=None if show_full else 20,
                session_only=not show_all
            )
        else:
            # If no history manager, use simple display method
            self._show_simple_history()

    def _show_simple_history(self):
        """When history manager is not available, use simple method to display history"""
        print(f"\n{TermColor.CYAN}Session History:{TermColor.RESET}")

        if not self.terminal.command_history and not self.terminal.file_edit_history:
            print("No commands or file edits in this session yet.")
            return

        print(f"\n{TermColor.YELLOW}Command History:{TermColor.RESET}")
        if self.terminal.command_history:
            for i, cmd in enumerate(self.terminal.command_history, 1):
                print(f"{i}. {cmd}")
        else:
            print("No commands executed in this session yet.")

        print(f"\n{TermColor.YELLOW}File Edit History:{TermColor.RESET}")
        if self.terminal.file_edit_history:
            for i, file in enumerate(self.terminal.file_edit_history, 1):
                print(f"{i}. {file}")
        else:
            print("No file edits in this session yet.")

    def clear_screen(self):
        """Clear screen and redisplay header"""
        os.system("clear" if os.name == "posix" else "cls")
        self.terminal.print_header()

    def clear_history(self):
        """Clear command and file edit history"""
        # Optional: Add user confirmation
        confirm = input("Are you sure you want to clear command and file edit history? (y/n): ")
        if confirm.lower() != 'y':
            print("Operation cancelled")
            return

        # Use history manager to clear history
        if hasattr(self.terminal, 'history_manager'):
            self.terminal.history_manager.clear_history(session_only=True)
            print(
                f"{TermColor.GREEN}Command and file edit history for current session has been cleared.{TermColor.RESET}")
        else:
            # Simple clearing of in-memory history
            self.terminal.command_history = []
            self.terminal.file_edit_history = []
            print(f"{TermColor.GREEN}Command and file edit history has been cleared.{TermColor.RESET}")

    async def _generate_summary(self, messages):
        """Asynchronous method to generate conversation summary"""
        try:
            messages = [
                {"role": "system",
                 "content": "You are a professional programming assistant. Please generate a concise summary of the previous conversation, "
                            "including tasks executed, files modified, and important decisions. "
                            "输出语言保持跟用户输入一致，如果用户输入包含中文，输出中文，否则输出英文。"
                 },
                *messages
            ]
            # Call the model to generate summary
            response = await self.terminal.agent.agent.arun(messages)
            return response.content
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return None

    def compact_context(self):
        """Compress conversation context into a summary"""
        if len(self.terminal.agent.conversation_history) <= 2:
            print(f"{TermColor.YELLOW}Conversation history too short, no need to compress. "
                  f"chat size: {len(self.terminal.agent.conversation_history)}{TermColor.RESET}")
            return

        print(f"{TermColor.CYAN}Compressing conversation context...{TermColor.RESET}")

        # Set loading state
        self.terminal.loading = True

        try:
            # Get summary
            loop = asyncio.get_event_loop()
            summary = loop.run_until_complete(
                self._generate_summary(self.terminal.agent.conversation_history)
            )

            if not summary:
                print(f"{TermColor.RED}Unable to generate summary.{TermColor.RESET}")
                self.terminal.loading = False
                return

            # Reset conversation history, keeping only the summary
            self.terminal.agent.conversation_history = [
                {"role": "system", "content": "You are a helpful programming assistant."},
                {"role": "user", "content": f"Conversation summary: {summary}"}
            ]

            print(f"{TermColor.GREEN}Conversation context has been compressed.{TermColor.RESET}")
            print(f"{TermColor.BLUE}Summary:{TermColor.RESET} {summary}")

        except Exception as e:
            print(f"{TermColor.RED}Error compressing context: {str(e)}{TermColor.RESET}")
            logger.exception("Error compressing context:")
        finally:
            self.terminal.loading = False

    def exit_app(self):
        """Exit application"""
        self.terminal.should_exit = True
