# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description:
"""

import os
import sys
import time
from loguru import logger
import json
import subprocess
from typing import Dict, List, Optional
from openai import OpenAI

from codev.config import AppConfig, CLI_VERSION, OPENAI_BASE_URL
from codev.utils.agent_loop import ReviewDecision, CommandConfirmation, ApplyPatchCommand
from codev.format_command import format_command_for_display
from codev.approvals import generate_command_explanation, ApprovalPolicy
from codev.commands import CommandHandler, TermColor, COLOR_MAP, POLICY_COLORS
from codev.history_manager import HistoryManager


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
    Terminal-based chat interface for interacting with the AI assistant using OpenAI's Chat Completions API
    """

    def __init__(
            self,
            config: AppConfig = AppConfig(),
            prompt: Optional[str] = None,
            image_paths: Optional[List[str]] = None,
            approval_policy: ApprovalPolicy = "suggest",
            additional_writable_roots: List[str] = None,
            full_stdout: bool = False,
    ):
        """
        Initialize the terminal chat interface
        
        Args:
            config: Application configuration
            prompt: Initial prompt to send to the model
            image_paths: Paths to images to include with the prompt
            approval_policy: Approval policy for commands
            additional_writable_roots: Additional writable directories
            full_stdout: Whether to show full command output
        """
        self.config = config
        self.initial_prompt = prompt
        self.initial_image_paths = image_paths or []
        self.approval_policy = approval_policy
        self.additional_writable_roots = additional_writable_roots or []
        self.full_stdout = full_stdout

        self.conversation_history = []
        self.command_history = []
        self.file_edit_history = []
        self.loading = False
        self.thinking_seconds = 0
        self.should_exit = False
        self.current_stream = None
        
        # Initialize history manager
        self.history_manager = HistoryManager()
        
        # Initialize command handler
        self.command_handler = CommandHandler(self)

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=OPENAI_BASE_URL
        )

        # Define tools for the OpenAI API
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "run_terminal_cmd",
                    "description": "Run a terminal command on the user's system",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                                "description": "The terminal command to execute"
                            },
                            "is_background": {
                                "type": "boolean",
                                "description": "Whether the command should be run in the background"
                            }
                        },
                        "required": ["command"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "edit_file",
                    "description": "Edit a file or create a new one",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_file": {
                                "type": "string",
                                "description": "The path of the file to edit"
                            },
                            "code_edit": {
                                "type": "string",
                                "description": "The new content for the file"
                            }
                        },
                        "required": ["target_file", "code_edit"]
                    }
                }
            }
        ]

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

    def execute_tool_call(self, tool_call):
        """
        Execute a tool call from the AI
        
        Args:
            tool_call: The tool call to execute
            
        Returns:
            Result of the tool execution
        """
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)

        if function_name == "run_terminal_cmd":
            command = function_args.get("command", "")
            is_background = function_args.get("is_background", False)
            
            # Add command to in-memory history
            self.command_history.append(command)
            
            # Format command for display
            formatted_command = format_command_for_display(command)

            # Generate command explanation
            explanation = generate_command_explanation(command, self.config.model)

            # Determine if user confirmation is needed
            requires_approval = self.approval_policy != "full-auto"
            if self.approval_policy == "auto-edit":
                # In auto-edit mode, only shell commands need confirmation
                requires_approval = True

            if requires_approval:
                # Display command and request confirmation
                policy_color = POLICY_COLORS.get(self.approval_policy, TermColor.WHITE)
                policy_name = self.approval_policy.upper()
                print(f"\n{policy_color}[{policy_name}]{TermColor.RESET} {TermColor.CYAN}Recommended command:{TermColor.RESET}")
                print(f"{TermColor.BRIGHT_WHITE}{formatted_command}{TermColor.RESET}")
                
                if explanation:
                    print(f"{TermColor.YELLOW}Explanation: {explanation}{TermColor.RESET}")
                
                print("\nExecute this command? (y/n)")
                decision = input("> ").strip().lower()
                
                if decision != "y":
                    return "User cancelled the command execution."

            # Execute command
            print(f"\n{TermColor.GREEN}Executing command:{TermColor.RESET} {formatted_command}\n")
            
            try:
                if is_background:
                    # Run in background
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    result = f"Command started in the background, Command: `{command}`, PID: {process.pid}"
                    # Record to history manager
                    self.history_manager.add_command(command, True, result)
                    return result
                else:
                    # Capture output
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    stdout, stderr = process.communicate()
                    
                    # Determine output based on full_stdout setting
                    if self.full_stdout or len(stdout) < 1000:
                        output = stdout
                    else:
                        # If output is too long, truncate display
                        lines = stdout.split("\n")
                        if len(lines) > 15:
                            output = "\n".join(lines[:15])
                            output += f"\n... (truncated, total {len(lines)} lines)"
                        else:
                            output = stdout
                    
                    # If there are errors, include stderr
                    if process.returncode != 0 and stderr:
                        output += f"\nError: {stderr}"
                        
                    # Record to history manager
                    success = process.returncode == 0
                    self.history_manager.add_command(command, success, output)
                    
                    return output or "Command executed successfully (no output)"
            except Exception as e:
                error_msg = f"Error executing command: {str(e)}"
                # Record to history manager
                self.history_manager.add_command(command, False, error_msg)
                return error_msg

        elif function_name == "edit_file":
            target_file = function_args.get("target_file", "")
            code_edit = function_args.get("code_edit", "")
            
            # Add file edit to in-memory history
            self.file_edit_history.append(target_file)
            
            # Determine if user confirmation is required
            requires_approval = self.approval_policy == "suggest"
            
            if requires_approval:
                # Display edit and request confirmation
                policy_color = POLICY_COLORS.get(self.approval_policy, TermColor.WHITE)
                policy_name = self.approval_policy.upper()
                print(f"\n{policy_color}[{policy_name}]{TermColor.RESET} {TermColor.CYAN}Recommended file edit:{TermColor.RESET}")
                print(f"{TermColor.BRIGHT_WHITE}File: {target_file}{TermColor.RESET}")
                
                # Show edit preview
                print(f"\nPreview:")
                max_lines = 15
                lines = code_edit.split("\n")
                preview = "\n".join(lines[:max_lines])
                if len(lines) > max_lines:
                    preview += f"\n... (truncated, total {len(lines)} lines)"
                print(f"{TermColor.BRIGHT_WHITE}{preview}{TermColor.RESET}")
                
                print("\nApply this edit? (y/n)")
                decision = input("> ").strip().lower()
                
                if decision != "y":
                    return "User cancelled the file edit."
            
            # Apply edit
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)
                
                # Write to file
                with open(target_file, "w") as f:
                    f.write(code_edit)
                
                # Determine operation type (create or edit)
                operation = "create" if not os.path.exists(target_file) else "edit"
                
                # Record to history manager
                self.history_manager.add_file_edit(target_file, operation)
                
                return f"Successfully edited file: {target_file}"
            except Exception as e:
                error_msg = f"Error editing file: {str(e)}"
                # TODO: Consider recording failed edit attempts
                return error_msg
        
        return "Unsupported tool call."

    def handle_ai_message(self, message):
        """Display AI message and handle any tool calls"""
        if message.content:
            print(f"{colored_text('Assistant: ', 'bright_green')}{message.content}")

            # Add to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": message.content
            })

        # Handle any tool calls
        if message.tool_calls:
            for tool_call in message.tool_calls:
                # Add the tool call to conversation history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments
                        }
                    }]
                })

                # Execute the tool call
                result = self.execute_tool_call(tool_call)

                # Add the tool call result to conversation history
                self.conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

    def handle_streaming_response(self, stream):
        """
        Handle a streaming response from the OpenAI API
        
        Args:
            stream: The streaming response from OpenAI
        """
        # Variables to track the current message being built
        current_content = ""
        last_displayed_length = 0  # Track last displayed content length
        current_tool_calls = {}
        has_tool_calls = False  # Track if there are tool calls

        try:
            for chunk in stream:
                if self.should_exit:
                    print("\nResponse generation cancelled.")
                    break

                delta = chunk.choices[0].delta

                # Handle content updates
                if delta.content:
                    current_content += delta.content

                    # Calculate new content to display
                    new_content = current_content[last_displayed_length:]
                    last_displayed_length = len(current_content)

                    # Only update display if there's new content
                    if new_content:
                        if last_displayed_length == len(new_content):  # First display content
                            sys.stdout.write(colored_text("Assistant: ", "bright_green") + new_content)
                        else:  # Append content
                            sys.stdout.write(new_content)
                        sys.stdout.flush()

                # Handle tool call updates
                if delta.tool_calls:
                    has_tool_calls = True
                    for tc_delta in delta.tool_calls:
                        # Create tool call if it doesn't exist
                        if tc_delta.index not in current_tool_calls:
                            current_tool_calls[tc_delta.index] = {
                                "id": "",
                                "function": {"name": "", "arguments": ""}
                            }
                            # Print a newline if transitioning from content to tool calls
                            if current_content and tc_delta.index == 0:
                                print("\n")
                                
                            # Display tool call header when a new tool call is started
                            if tc_delta.function and tc_delta.function.name:
                                tool_name = tc_delta.function.name
                                print(f"\n{colored_text('Tool Call: ', 'bright_cyan')}{colored_text(tool_name, 'bright_white')}")

                        # Update tool call properties
                        if tc_delta.id:
                            current_tool_calls[tc_delta.index]["id"] = tc_delta.id

                        if tc_delta.function and tc_delta.function.name:
                            current_tool_calls[tc_delta.index]["function"]["name"] = tc_delta.function.name

                        if tc_delta.function and tc_delta.function.arguments:
                            # Display arguments as they come in
                            sys.stdout.write(tc_delta.function.arguments)
                            sys.stdout.flush()
                            current_tool_calls[tc_delta.index]["function"]["arguments"] += tc_delta.function.arguments

            # Create the final content message if not empty
            if current_content:
                print()  # Add newline after streaming
                # Add to conversation history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": current_content
                })

            # Process tool calls
            if current_tool_calls:
                # Convert dictionary to list
                tool_calls_list = []
                for idx in sorted(current_tool_calls.keys()):
                    tc = current_tool_calls[idx]

                    # Create a tool call object
                    tool_call = {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"]
                        }
                    }
                    tool_calls_list.append(tool_call)

                # Process each tool call
                for tool_call in tool_calls_list:
                    # Add the tool call to conversation history
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call]
                    })

                    # Create a simple object for executing tool call
                    class ToolCall:
                        def __init__(self, id, function_name, arguments):
                            self.id = id
                            self.function = type('obj', (object,), {
                                'name': function_name,
                                'arguments': arguments
                            })

                    # Execute tool call
                    tc_obj = ToolCall(
                        tool_call["id"],
                        tool_call["function"]["name"],
                        tool_call["function"]["arguments"]
                    )
                    
                    # Execute and display the result
                    print(f"\n{colored_text('Executing tool...', 'bright_yellow')}")
                    result = self.execute_tool_call(tc_obj)
                    print(f"\n{colored_text('Result:', 'bright_green')}")
                    print(result)

                    # Add the tool call result to conversation history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result
                    })

                # Only auto-start subsequent conversation when there's no content output, only tool calls
                if not current_content and has_tool_calls and not self.should_exit:
                    # Delay a bit to avoid abrupt experience
                    time.sleep(0.5)
                    print(f"\n{colored_text('Continuing conversation based on tool results...', 'bright_blue')}")
                    # Use an empty message to trigger subsequent conversation, let model respond to tool call results
                    self.send_message_to_model(None)

        except Exception as e:
            print(f"\n{colored_text(f'Error processing response: {str(e)}', 'bright_red')}")
            logger.exception("Error in handle_streaming_response:")
        finally:
            # Reset loading state
            self.loading = False
            self.current_stream = None

    def send_message_to_model(self, user_message=None):
        """
        Send a message to the OpenAI model
        
        Args:
            user_message: Optional user message to send
        """
        # If already loading, don't repeat send request
        if self.loading:
            return

        try:
            # Add user message to conversation history if provided
            if user_message:
                self.conversation_history.append({
                    "role": "user",
                    "content": user_message
                })

            # Set loading state
            self.loading = True
            self.thinking_seconds = 0  # Reset thinking time counter

            # Build system message
            system_message = {
                "role": "system",
                "content": "You are a powerful coding assistant that helps users with programming tasks."
            }

            if self.config.instructions:
                system_message["content"] += f" {self.config.instructions}"

            # Add information about approval policy
            system_message["content"] += f" The current approval policy is set to '{self.approval_policy}'."

            # Prepare messages for the API
            messages = [system_message] + self.conversation_history

            # Create streaming request
            self.current_stream = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                tools=self.tools,
                stream=True,
                max_tokens=4000,
                temperature=0.7,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )

            # Handle the streaming response
            self.handle_streaming_response(self.current_stream)

        except Exception as e:
            print(f"\n{TermColor.RED}Error: {str(e)}{TermColor.RESET}")
            logger.exception("Error sending message to model:")
            self.loading = False

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
                display_cwd = "..." + display_cwd[-(max_cwd_len-3):]
            cwd_line = f"{header_color}│{reset} Working Directory: {display_cwd}"
        padding = box_width - len(cwd_line) + len(header_color) + len(reset)
        print(f"{cwd_line}{' ' * padding}{header_color}│{reset}")
        
        # Help info
        help_line = f"{header_color}│{reset} Type {accent_color}/help{reset} for available commands"
        padding = box_width - len(help_line) + len(header_color) + len(reset) + len(accent_color) + len(reset)
        print(f"{help_line}{' ' * padding}{header_color}│{reset}")
        
        print(border_bottom)
        print()

    def process_initial_prompt(self):
        """Process the initial prompt if provided"""
        if self.initial_prompt or self.initial_image_paths:
            content = []

            # Handle text prompt
            if self.initial_prompt:
                content = self.initial_prompt
                print(f"{colored_text('You: ', 'bright_blue')}{self.initial_prompt}")

            # Handle images (would need to be implemented differently with OpenAI API)
            if self.initial_image_paths:
                image_paths_str = ", ".join(self.initial_image_paths)
                print(f"{colored_text('You: ', 'bright_blue')}[Images attached: {image_paths_str}]")
                # Note: For now, we'll just mention the images in the prompt
                if content:
                    content += f"\n[User included images: {image_paths_str}]"
                else:
                    content = f"[User included images: {image_paths_str}]"

            # Send to model
            self.send_message_to_model(content)

    def show_thinking_indicator(self):
        """Show a thinking indicator while waiting for a response"""
        dots = "." * (self.thinking_seconds % 4)
        sys.stdout.write(f"\rThinking{dots}    ")
        sys.stdout.flush()

    def run(self):
        """Run the terminal chat interface"""
        self.print_header()

        # Process initial prompt if provided
        self.process_initial_prompt()

        # Enable readline support (if available)
        try:
            import readline
            
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
            history_file = os.path.expanduser("~/.codev_history")
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
                    time.sleep(1)
                    continue

                # Get user input
                user_input = input(f"{TermColor.BRIGHT_BLUE}You:{TermColor.RESET} ")
                
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

                # Send message to the model
                self.send_message_to_model(user_input)

            except KeyboardInterrupt:
                print("\n\nUser interrupted.")
                if self.loading and self.current_stream:
                    print("Cancelling current request...")
                    # Note: The OpenAI Python library doesn't have a direct way to cancel streams
                    # We'll set our flags to stop processing
                    self.loading = False
                else:
                    print("Exiting...")
                    self.should_exit = True

            except Exception as e:
                print(f"\n{TermColor.RED}Error: {str(e)}{TermColor.RESET}")
                logger.exception("Terminal chat error:")

        print("\nThank you for using Codev CLI. Goodbye!")
