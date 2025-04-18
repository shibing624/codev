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


# Terminal colors
class TermColor:
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
        self.loading = False
        self.thinking_seconds = 0
        self.should_exit = False
        self.current_stream = None

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
        Execute a tool call from the AI assistant
        
        Args:
            tool_call: The tool call to execute
            
        Returns:
            Tool call result
        """
        function_name = tool_call.function.name

        try:
            arguments = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse tool call arguments: {tool_call.function.arguments}")
            return "Error: Failed to parse tool call arguments"

        if function_name == "run_terminal_cmd":
            command = arguments.get("command", "")
            is_background = arguments.get("is_background", False)

            # Display the command info
            bg_info = " (background)" if is_background else ""
            print(colored_text(f"Running command{bg_info}: {command}", "bright_yellow"))

            # Check if we need to confirm this command
            if self.approval_policy != "full-auto":
                # Parse command into list if it's a string
                cmd_list = command.split() if isinstance(command, str) else command

                # Get confirmation from user
                confirmation = self.get_command_confirmation(cmd_list, None)

                if confirmation.review != ReviewDecision.APPROVE:
                    # Command was denied
                    deny_message = confirmation.custom_deny_message or "Command not approved by user"
                    print(colored_text(f"Command denied: {deny_message}", "bright_red"))
                    return deny_message

            # Run the command
            try:
                if is_background:
                    # Run in background (non-blocking)
                    subprocess.Popen(
                        command if isinstance(command, str) else command.split(),
                        shell=isinstance(command, str),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    result = f"Command running in background, command: {command}"
                else:
                    # Run blocking with timeout
                    proc = subprocess.run(
                        command if isinstance(command, str) else command.split(),
                        shell=isinstance(command, str),
                        capture_output=True,
                        text=True,
                        timeout=300  # 5 minute timeout
                    )
                    result = f"Command: {command}\n" + proc.stdout + "\n" + proc.stderr

                # Display result
                print(colored_text("Result:", "bright_magenta"))
                if not self.full_stdout and len(result.split("\n")) > 10:
                    lines = result.split("\n")
                    print("\n".join(lines[:10]))
                    print(colored_text(f"... and {len(lines) - 10} more lines (use --full-stdout to see all)",
                                       "bright_black"))
                else:
                    print(result)

                return result

            except Exception as e:
                error_result = f"Error executing command: {str(e)}"
                print(colored_text(error_result, "bright_red"))
                return error_result

        elif function_name == "edit_file":
            target_file = arguments.get("target_file", "")
            code_edit = arguments.get("code_edit", "")

            # Display file edit info
            print(colored_text(f"Editing file: {target_file}", "bright_yellow"))

            # Check if we need to confirm this edit
            if self.approval_policy != "full-auto" and self.approval_policy != "auto-edit":
                # Create an ApplyPatchCommand
                apply_patch = ApplyPatchCommand(
                    file_path=target_file,
                    content=code_edit
                )

                # Get confirmation from user
                confirmation = self.get_command_confirmation(["edit", target_file], apply_patch)

                if confirmation.review != ReviewDecision.APPROVE:
                    # Edit was denied
                    deny_message = confirmation.custom_deny_message or "File edit not approved by user"
                    print(colored_text(f"Edit denied: {deny_message}", "bright_red"))
                    return deny_message

            # Apply the edit
            try:
                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)

                # Write the file
                with open(target_file, "w") as f:
                    f.write(code_edit)

                result = f"Successfully wrote to {target_file}"
                print(colored_text(result, "bright_green"))
                return result

            except Exception as e:
                error_result = f"Error editing file: {str(e)}"
                print(colored_text(error_result, "bright_red"))
                return error_result

        else:
            return f"Unknown tool call: {function_name}"

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
        """Handle a streaming response from the OpenAI API"""
        # Variables to track the current message being built
        current_content = ""
        last_displayed_length = 0  # 跟踪上次显示的内容长度
        current_tool_calls = {}
        has_tool_calls = False  # 跟踪是否有工具调用

        try:
            for chunk in stream:
                if self.should_exit:
                    break

                delta = chunk.choices[0].delta

                # Handle content updates
                if delta.content:
                    current_content += delta.content

                    # 计算需要显示的新内容
                    new_content = current_content[last_displayed_length:]
                    last_displayed_length = len(current_content)

                    # 只有在有新内容时才更新显示
                    if new_content:
                        if last_displayed_length == len(new_content):  # 第一次显示内容
                            sys.stdout.write(colored_text("Assistant: ", "bright_green") + new_content)
                        else:  # 追加内容
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

                        # Update tool call properties
                        if tc_delta.id:
                            current_tool_calls[tc_delta.index]["id"] = tc_delta.id

                        if tc_delta.function and tc_delta.function.name:
                            current_tool_calls[tc_delta.index]["function"]["name"] = tc_delta.function.name

                        if tc_delta.function and tc_delta.function.arguments:
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
                from openai.types.chat import ChatCompletionMessageToolCall

                # Convert dictionary to list
                tool_calls_list = []
                for idx in sorted(current_tool_calls.keys()):
                    tc = current_tool_calls[idx]

                    # 创建一个工具调用对象 - 使用正确的方式创建
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

                    # 创建一个简单的对象用于执行工具调用
                    class ToolCall:
                        def __init__(self, id, function_name, arguments):
                            self.id = id
                            self.function = type('obj', (object,), {
                                'name': function_name,
                                'arguments': arguments
                            })

                    # 执行工具调用
                    tc_obj = ToolCall(
                        tool_call["id"],
                        tool_call["function"]["name"],
                        tool_call["function"]["arguments"]
                    )
                    result = self.execute_tool_call(tc_obj)

                    # Add the tool call result to conversation history
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result
                    })

                # 只有当没有内容输出，只有工具调用时，才自动发起后续对话
                if not current_content and has_tool_calls and not self.should_exit:
                    # 延迟一点时间，避免用户体验突兀
                    time.sleep(0.5)
                    # 使用一个空消息触发后续对话，让模型回应工具调用的结果
                    self.send_message_to_model(None)

        except Exception as e:
            print(f"\n{TermColor.RED}Error in stream processing: {str(e)}{TermColor.RESET}")
            logger.exception("Error processing stream:")
        finally:
            self.loading = False
            self.current_stream = None

    def send_message_to_model(self, user_message=None):
        """
        Send a message to the OpenAI model
        
        Args:
            user_message: Optional user message to send
        """
        # 如果已经在加载中，就不要重复发送请求
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
            self.thinking_seconds = 0  # 重置思考时间计数器

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
        """Print the terminal chat header"""
        cwd = short_cwd()
        policy_color = POLICY_COLORS.get(self.approval_policy, TermColor.WHITE)

        print(f"{TermColor.BRIGHT_CYAN}────────────────────────────────────────────────{TermColor.RESET}")
        print(f"{TermColor.BRIGHT_WHITE}Codev CLI v{CLI_VERSION}{TermColor.RESET}")
        print(f"{TermColor.BRIGHT_WHITE}Directory: {cwd}{TermColor.RESET}")
        print(f"{TermColor.BRIGHT_WHITE}Model: {self.config.model}{TermColor.RESET}")
        print(f"{TermColor.BRIGHT_WHITE}Approval Policy: {policy_color}{self.approval_policy}{TermColor.RESET}")
        print(f"{TermColor.BRIGHT_CYAN}────────────────────────────────────────────────{TermColor.RESET}")
        print(f"{TermColor.BRIGHT_BLACK}Type your message and press Enter. Use Ctrl+C or '/exit' to exit.{TermColor.RESET}")
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

                # Check for special commands
                if user_input.lower() in ["/exit", "/quit"]:
                    self.should_exit = True
                    continue
                elif user_input.lower() == "/clear":
                    os.system("clear" if os.name == "posix" else "cls")
                    self.print_header()
                    continue

                # Send message to the model
                self.send_message_to_model(user_input)

            except KeyboardInterrupt:
                print("\n\nInterrupted by user.")
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
                logger.exception("Error in terminal chat:")

        print("\nThank you for using Codev CLI. Goodbye!")
