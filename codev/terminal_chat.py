# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description:
"""

import os
import sys
from loguru import logger
from typing import List, Optional, Dict, Any, Callable

from codev.config import AppConfig, CLI_VERSION
from codev.agent import ReviewDecision, CommandConfirmation, ApplyPatchCommand, CodevAgent
from codev.format_command import format_command_for_display
from codev.approvals import generate_command_explanation, ApprovalPolicy
from codev.commands import CommandHandler, TermColor, COLOR_MAP, POLICY_COLORS
from codev.history_manager import HistoryManager
import readline


def colored_text(text: str, color: str) -> str:
    """
    Add color to text for terminal output
    
    Args:
        text: The text to color
        color: The color to use
        
    Returns:
        Colored text string
    """
    color_code = COLOR_MAP.get(color, TermColor.WHITE)
    return f"{color_code}{text}{TermColor.RESET}"


def short_cwd() -> str:
    """
    Get a shortened version of the current working directory
    
    Returns:
        Shortened path string
    """
    home = os.path.expanduser("~")
    cwd = os.getcwd()
    if cwd.startswith(home):
        return "~" + cwd[len(home):]
    return cwd


class TerminalChat:
    """
    Terminal-based chat interface for interacting with the AI assistant using agentica's Agent
    """

    def __init__(
            self,
            config: AppConfig = AppConfig(),
            prompt: Optional[str] = None,
            image_paths: Optional[List[str]] = None,
            approval_policy: ApprovalPolicy = "suggest",
            full_stdout: bool = False,
    ):
        """
        Initialize the terminal chat interface
        
        Args:
            config: Application configuration
            prompt: Initial prompt to send to the model
            image_paths: Paths to images to include with the prompt
            approval_policy: Approval policy for commands, 'auto-edit', 'full-auto', or 'suggest'
            full_stdout: Whether to show full command output
        """
        self.config = config
        self.initial_prompt = prompt
        self.initial_image_paths = image_paths or []
        self.approval_policy = approval_policy
        self.full_stdout = full_stdout

        self.command_history = []
        self.file_edit_history = []
        self.loading = False
        self.thinking_seconds = 0
        self.should_exit = False
        self._input_history = []  # Initialize input history

        # Initialize history manager
        self.history_manager = HistoryManager()

        # Initialize CodevAgent
        self.agent = CodevAgent(
            config=self.config,
            approval_policy=self.approval_policy,
            on_message=self.handle_agent_message,
            on_loading=self.handle_loading_state,
            get_command_confirmation=self.get_command_confirmation,
            history_manager=self.history_manager,
            instructions=self.config.instructions,
            debug=self.config.debug,
        )
        # Initialize command handler
        self.command_handler = CommandHandler(self)
        
    def handle_agent_message(self, message):
        """
        Handle messages from the agent
        
        Args:
            message: The message from the agent
        """
        role = message.get("role", "")
        content = message.get("content", "")

        if role == "assistant":
            # Print without "Assistant:" prefix
            print(f"\n{content}")
        elif role == "system":
            print(f"{colored_text('System: ', 'yellow')}{content}")
        elif role == "error":
            print(f"{colored_text('Error: ', 'bright_red')}{content}")

    def handle_loading_state(self, is_loading: bool):
        """
        Handle loading state changes
        
        Args:
            is_loading: Whether the agent is loading
        """
        self.loading = is_loading
        if is_loading:
            self.thinking_seconds = 0
        else:
            # Clear the thinking indicator
            sys.stdout.write("\r" + " " * 20 + "\r")
            sys.stdout.flush()

    def get_command_confirmation(self, command: List[str],
                                 apply_patch: Optional[ApplyPatchCommand]) -> CommandConfirmation:
        """
        Get confirmation from the user for executing a command
        
        Args:
            command: The command to execute
            apply_patch: Optional patch to apply
            
        Returns:
            CommandConfirmation with user's decision
        """
        # Display the command for confirmation
        command_str = format_command_for_display(command)

        if apply_patch:
            print(f"\n{TermColor.YELLOW}The AI assistant wants to edit file: {apply_patch.file_path}{TermColor.RESET}")
            print(f"{TermColor.YELLOW}Preview of changes:{TermColor.RESET}")
            print(f"{TermColor.CYAN}```{TermColor.RESET}")
            lines = apply_patch.content.split('\n')
            # Only show first 10 lines if too long
            if len(lines) > 10:
                print('\n'.join(lines[:10]))
                print(f"... and {len(lines) - 10} more lines")
            else:
                print(apply_patch.content)
            print(f"{TermColor.CYAN}```{TermColor.RESET}")
        else:
            print(f"\n{TermColor.YELLOW}The AI assistant wants to run: {command_str}{TermColor.RESET}")

        print("\nOptions:")
        print(f"  {TermColor.GREEN}(a)pprove{TermColor.RESET} - Execute the command")
        print(f"  {TermColor.RED}(d)eny{TermColor.RESET} - Reject the command")
        print(f"  {TermColor.BLUE}(e)xplain{TermColor.RESET} - Ask for an explanation")
        print(f"  {TermColor.MAGENTA}(m)odify{TermColor.RESET} - Modify the command before running")

        decision = ""
        while decision not in ["a", "d", "e", "m"]:
            decision = input("Your choice [a/d/e/m]: ").lower()

        custom_deny_message = None
        explanation = None
        review_decision = ReviewDecision.APPROVE

        # Handle the decision
        if decision == "a":
            # Approve
            review_decision = ReviewDecision.APPROVE
        elif decision == "d":
            # Deny
            review_decision = ReviewDecision.DENY
            custom_deny_message = input("Reason for denial (optional): ")
        elif decision == "e":
            # Explain
            review_decision = ReviewDecision.EXPLAIN
            # Generate explanation
            explanation = generate_command_explanation(command, self.config.model)
            print(f"\n{TermColor.CYAN}Explanation:{TermColor.RESET}")
            print(explanation)
            print("\nNow that you have an explanation:")
            print(f"  {TermColor.GREEN}(a)pprove{TermColor.RESET} - Execute the command")
            print(f"  {TermColor.RED}(d)eny{TermColor.RESET} - Reject the command")

            inner_decision = ""
            while inner_decision not in ["a", "d"]:
                inner_decision = input("Your choice [a/d]: ").lower()

            if inner_decision == "a":
                review_decision = ReviewDecision.APPROVE
            else:
                review_decision = ReviewDecision.DENY
                custom_deny_message = input("Reason for denial (optional): ")
        elif decision == "m":
            # Modify
            review_decision = ReviewDecision.MODIFY
            # Not fully implemented yet
            print("Modify functionality is not yet implemented. Denying command.")
            review_decision = ReviewDecision.DENY
            custom_deny_message = "User wanted to modify the command but this feature is not yet implemented"

        return CommandConfirmation(
            review=review_decision,
            custom_deny_message=custom_deny_message,
            apply_patch=apply_patch,
            explanation=explanation
        )

    def show_thinking_indicator(self):
        """Show a thinking indicator while waiting for a response"""
        dots = "." * (self.thinking_seconds % 4)
        sys.stdout.write(f"\rThinking{dots}    ")
        sys.stdout.flush()

    def send_message_to_agent(self, user_message=None):
        """
        Send a message to the agent
        
        Args:
            user_message: Optional user message to send
        """
        if user_message == self.initial_prompt:
            self.initial_image_paths = []
            # Don't print "You:" prefix
            print(f"\n{user_message}")

        # Send message to agent
        self.agent.send_message(user_message)

    def print_header(self):
        """Print the application header with version and model information"""
        header_color = TermColor.BRIGHT_CYAN
        accent_color = TermColor.BRIGHT_GREEN
        reset = TermColor.RESET

        # Create a boxed header
        box_width = 60
        border_top = f"{header_color}╭{'─' * (box_width - 1)}╮{reset}"
        border_bottom = f"{header_color}╰{'─' * (box_width - 1)}╯{reset}"

        # Print header
        print(border_top)

        # App name and version
        app_name = f"{header_color}│{reset} {accent_color}Codev CLI{reset} - Interactive AI Coding Agent"
        padding = box_width - len(app_name) + len(header_color) + len(reset) + len(accent_color) + len(reset)
        print(f"{app_name}{' ' * padding}{header_color}│{reset}")

        # Version info
        version_line = f"{header_color}│{reset} Version: {CLI_VERSION}"
        padding = box_width - len(version_line) + len(header_color) + len(reset)
        print(f"{version_line}{' ' * padding}{header_color}│{reset}")

        # Model info
        model_info = f"{header_color}│{reset} Model: {accent_color}{self.config.model}{reset}"
        padding = box_width - len(model_info) + len(header_color) + len(reset) + len(accent_color) + len(reset)
        print(f"{model_info}{' ' * padding}{header_color}│{reset}")

        # Approval policy info
        policy_color = POLICY_COLORS.get(self.approval_policy, TermColor.WHITE)
        policy_line = f"{header_color}│{reset} Approval Policy: {policy_color}{self.approval_policy}{reset}"
        padding = box_width - len(policy_line) + len(header_color) + len(reset) + len(policy_color) + len(reset)
        print(f"{policy_line}{' ' * padding}{header_color}│{reset}")

        # Working directory
        cwd_line = f"{header_color}│{reset} Working Directory: {short_cwd()}"
        if len(cwd_line) - len(header_color) - len(reset) > box_width - 4:
            # Truncate if too long
            display_cwd = short_cwd()
            max_cwd_len = box_width - 24  # Allow space for the label and ellipsis
            if len(display_cwd) > max_cwd_len:
                display_cwd = "..." + display_cwd[-(max_cwd_len - 3):]
            cwd_line = f"{header_color}│{reset} Working Directory: {display_cwd}"
        padding = box_width - len(cwd_line) + len(header_color) + len(reset)
        print(f"{cwd_line}{' ' * padding}{header_color}│{reset}")

        # Help info
        help_line = f"{header_color}│{reset} Type {accent_color}/help{reset} for available commands"
        padding = box_width - len(help_line) + len(header_color) + len(reset) + len(accent_color) + len(reset)
        print(f"{help_line}{' ' * padding}{header_color}│{reset}")
        
        # Input instructions
        input_line = f"{header_color}│{reset} Input with {accent_color}>{reset} prompt, press {accent_color}Enter twice{reset} to submit"
        padding = box_width - len(input_line) + len(header_color) + len(reset) + 2 * len(accent_color) + 2 * len(reset)
        print(f"{input_line}{' ' * padding}{header_color}│{reset}")
        
        print(border_bottom)
        print()

    def process_initial_prompt(self):
        """Process the initial prompt if provided"""
        if self.initial_prompt or self.initial_image_paths:
            content = self.initial_prompt or ""

            # Handle images
            if self.initial_image_paths:
                image_paths_str = ", ".join(self.initial_image_paths)
                print(f"{colored_text('You: ', 'bright_blue')}[Images attached: {image_paths_str}]")
                if not content:
                    content = "[Please analyze these images]"

            # Send to agent
            self.send_message_to_agent(content)

    def run(self):
        """Run the terminal chat interface"""
        self.print_header()

        # Process initial prompt if provided
        self.process_initial_prompt()

        # Enable readline support (if available)
        try:
            # Set basic command auto-completion
            def completer(text, state):
                commands = ["/help", "/model", "/approval", "/history",
                            "/clear", "/clearhistory", "/compact", "/exit", "/quit"]
                options = [cmd for cmd in commands if cmd.startswith(text)]
                if state < len(options):
                    return options[state]
                else:
                    return None

            readline.parse_and_bind("tab: complete")
            readline.set_completer(completer)

            # Add history functionality
            history_file = os.path.expanduser("~/.codev/chat_history")
            try:
                readline.read_history_file(history_file)
            except FileNotFoundError:
                pass

        except ImportError:
            logger.warning("readline module not available, some features will be limited")

        # Main input loop
        while not self.should_exit:
            try:
                # If we're loading, show thinking indicator
                if self.loading:
                    self.show_thinking_indicator()
                    self.thinking_seconds += 1
                    continue

                # Get user input
                user_input = self.get_user_input()

                # Check if user wants to exit
                if user_input is None:
                    print("\nExiting...")
                    self.should_exit = True
                    continue
                # Save to readline history (if available)
                try:
                    readline.add_history(user_input)
                    readline.write_history_file(history_file)
                except (NameError, FileNotFoundError):
                    pass
                # Handle special commands using the command handler
                if user_input.startswith("/"):
                    if self.command_handler.handle_command(user_input):
                        continue
                # Send message to the agent
                self.send_message_to_agent(user_input)
            except KeyboardInterrupt:
                print("\n\nUser interrupted.")
                if self.loading:
                    print("Cancelling current request...")
                    self.agent.cancel()
                else:
                    print("Exiting...")
                    self.should_exit = True
            except Exception as e:
                print(f"\n{TermColor.RED}Error: {str(e)}{TermColor.RESET}")
                logger.exception("Terminal chat error:")

        print("\nThank you for using Codev CLI. Goodbye!")

    def get_user_input(self):
        """
        Get user input with support for multi-line editing
        
        Returns:
            User input string, or None if user wants to exit
        """
        try:
            # Display prompt - just use ">" instead of "You:"
            print("> ", end="", flush=True)
            
            # Get input using the simple multi-line method
            user_input = self._get_simple_input()
            
            if user_input is None:
                return None
                
            # Check if user wants to exit
            if user_input.strip() in ['\\q', 'exit', 'quit']:
                print("\nExiting...")
                self.should_exit = True
                return None
            
            # Handle empty input
            if not user_input.strip():
                print("Empty input, please try again.")
                return self.get_user_input()
                
            # Save to history
            self._save_to_input_history(user_input)
            return user_input
        except KeyboardInterrupt:
            print("\nOperation interrupted.")
            if self.loading:
                print("Cancelling current request...")
                self.agent.cancel()
            else:
                print("Exiting...")
                self.should_exit = True
            return None
        except EOFError:
            print("\nExiting...")
            self.should_exit = True
            return None
            
    def _get_simple_input(self):
        """
        Get multi-line user input with improved code paste support
        
        This method implements a simple but effective multi-line input system:
        1. First line is entered directly with the ">" prompt
        2. Subsequent lines are collected without additional prompts
        3. Input is terminated when the user enters two empty lines in a row
        4. Code pasting is supported naturally - each line is treated as a separate input
        
        Returns:
            User input string or None if canceled
        """
        lines = []
        empty_line_count = 0
        
        # Get input lines until termination condition
        while True:
            try:
                # For the first line, prompt is already displayed in get_user_input
                # For subsequent lines, don't show any prompt to avoid confusion with pasted code
                if lines:
                    line = input()
                else:
                    line = input()
                
                # Check if the line is empty
                if not line.strip():
                    empty_line_count += 1
                    # Two consecutive empty lines means we're done
                    if empty_line_count >= 1:
                        break
                else:
                    empty_line_count = 0
                # Add the line to our buffer
                lines.append(line)
            except KeyboardInterrupt:
                print("\nInput canceled.")
                return None
        # If no valid input, return None
        if not any(line.strip() for line in lines):
            print("Empty input, please try again.")
            return self.get_user_input()
        # Join lines
        user_input = '\n'.join(lines)
        return user_input.strip()
        
    def _save_to_input_history(self, user_input):
        """
        Save input to history
        
        Args:
            user_input: User input to save
        """
        # Avoid duplicates in history
        if not self._input_history or self._input_history[-1] != user_input:
            self._input_history.append(user_input)
            # Keep history size reasonable
            if len(self._input_history) > 50:
                self._input_history = self._input_history[-50:]


if __name__ == '__main__':
    terminal = TerminalChat()
    terminal.send_message_to_agent("Write a Python quicksort script")
