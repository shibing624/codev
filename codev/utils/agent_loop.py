#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from loguru import logger
from openai import OpenAI

from codev.config import AppConfig, OPENAI_BASE_URL


class ReviewDecision(Enum):
    """Enumeration of possible review decisions"""
    APPROVE = "approve"
    DENY = "deny"
    EXPLAIN = "explain"
    MODIFY = "modify"


@dataclass
class ApplyPatchCommand:
    """Represents a patch to be applied to a file"""
    file_path: str
    content: str


@dataclass
class CommandConfirmation:
    """Response from user when confirming a command"""
    review: ReviewDecision
    custom_deny_message: Optional[str] = None
    apply_patch: Optional[ApplyPatchCommand] = None
    explanation: Optional[str] = None


class AgentLoop:
    """
    Manages the interaction loop with the AI agent.
    Handles sending messages, receiving responses, and processing tool calls.
    """

    def __init__(self,
                 model: str,
                 config: AppConfig,
                 instructions: Optional[str] = None,
                 approval_policy: str = "suggest",
                 additional_writable_roots: List[str] = None,
                 on_item: Callable[[Dict[str, Any]], None] = None,
                 on_loading: Callable[[bool], None] = None,
                 on_last_response_id: Callable[[Optional[str]], None] = None,
                 get_command_confirmation: Optional[Callable] = None):
        """
        Initialize the agent loop
        
        Args:
            model: The model to use for generation
            config: The application configuration
            instructions: Custom instructions for the model
            approval_policy: The policy for approving commands ("suggest", "auto-edit", "full-auto")
            additional_writable_roots: Additional directories that can be written to
            on_item: Callback for when a new response item is received
            on_loading: Callback for when loading state changes
            on_last_response_id: Callback for when the last response ID changes
            get_command_confirmation: Callback to request confirmation for commands
        """
        self.model = model
        self.config = config
        self.instructions = instructions
        self.approval_policy = approval_policy
        self.additional_writable_roots = additional_writable_roots or []
        self.on_item = on_item
        self.on_loading = on_loading
        self.on_last_response_id = on_last_response_id
        self.get_command_confirmation = get_command_confirmation

        self.conversation_history = []
        self.is_running = False
        self.should_cancel = False

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=OPENAI_BASE_URL
        )

    def add_system_message(self, content: str):
        """Add a system message to the conversation history"""
        message = {
            "id": f"system-{time.time()}",
            "type": "message",
            "role": "system",
            "content": [{"type": "text", "text": content}]
        }

        if self.on_item:
            self.on_item(message)

        self.conversation_history.append({
            "role": "system",
            "content": content
        })

    def add_user_message(self, content: str, images: List[str] = None):
        """Add a user message to the conversation history"""
        message_content = []

        # Add text content
        if content:
            message_content.append({
                "type": "text",
                "text": content
            })

        # Add image content if provided
        if images and len(images) > 0:
            for image_path in images:
                if os.path.exists(image_path):
                    with open(image_path, "rb") as img_file:
                        import base64
                        # Convert image to base64
                        image_data = base64.b64encode(img_file.read()).decode('utf-8')
                        # Determine image type from file extension
                        image_type = os.path.splitext(image_path)[1][1:]  # Remove the '.'
                        if image_type.lower() in ['jpg', 'jpeg']:
                            mime_type = 'image/jpeg'
                        elif image_type.lower() == 'png':
                            mime_type = 'image/png'
                        else:
                            mime_type = f'image/{image_type}'

                        message_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            }
                        })

        message = {
            "id": f"user-{time.time()}",
            "type": "message",
            "role": "user",
            "content": message_content
        }

        if self.on_item:
            self.on_item(message)

        # Add to OpenAI conversation format
        self.conversation_history.append({
            "role": "user",
            "content": message_content
        })

    def run(self, input_items: List[Dict[str, Any]], last_response_id: str = None):
        """
        Run the agent loop with the given input items
        
        Args:
            input_items: List of input items to process
            last_response_id: ID of the last response
        """
        if self.is_running:
            logger.warning("Agent is already running")
            return

        self.is_running = True
        self.should_cancel = False

        # Process input items
        for item in input_items:
            if item.get("type") == "message":
                content = item.get("content", "")
                if isinstance(content, list):
                    # Extract text content
                    text_content = ""
                    image_paths = []

                    for part in content:
                        if part.get("type") == "text":
                            text_content += part.get("text", "")
                        elif part.get("type") == "image_url":
                            image_url = part.get("image_url", {}).get("url", "")
                            if image_url.startswith("file://"):
                                image_paths.append(image_url[7:])  # Remove file:// prefix

                    self.add_user_message(text_content, image_paths)
                else:
                    self.add_user_message(content)

        # Update loading state
        if self.on_loading:
            self.on_loading(True)

        try:
            # Check if API key is set
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                self.add_system_message("Error: OPENAI_API_KEY environment variable not set")
                return

            # Build the system message
            system_message = {
                "role": "system",
                "content": "You are a powerful coding assistant that helps users with programming tasks."
            }

            if self.instructions:
                system_message["content"] += f" {self.instructions}"

            # Add information about approval policy
            system_message["content"] += f" The current approval policy is set to '{self.approval_policy}'."

            # Prepare messages for the OpenAI API
            messages = [system_message] + self.conversation_history

            # Define tools for the API
            tools = [
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

            # Create a single message ID for the entire stream
            message_id = f"assistant-{time.time()}"
            accumulated_message = ""
            last_sent_message = ""  # Track the last message sent to prevent duplicates

            # Make streaming request using OpenAI's Python client
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                stream=True,
                max_tokens=4000,
                temperature=0.7,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )

            # Process the streaming response
            tool_calls = []
            for chunk in response:
                if self.should_cancel:
                    break

                # Extract content if present
                delta = chunk.choices[0].delta

                # Handle content updates
                if hasattr(delta, 'content') and delta.content is not None:
                    accumulated_message += delta.content

                    # Only update if the message has actually changed to avoid spamming the terminal
                    if accumulated_message != last_sent_message:
                        # Create a message item to show streaming text
                        message_item = {
                            "id": message_id,
                            "type": "message",
                            "role": "assistant",
                            "content": [{"type": "text", "text": accumulated_message}]
                        }

                        if self.on_item:
                            self.on_item(message_item)

                        last_sent_message = accumulated_message

                # Handle tool calls
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        tc_index = tc_delta.index

                        # Initialize tool call if it doesn't exist
                        while len(tool_calls) <= tc_index:
                            tool_calls.append({
                                "id": "",
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": ""
                                }
                            })

                        # Update tool call ID
                        if tc_delta.id:
                            tool_calls[tc_index]["id"] = tc_delta.id

                        # Update function name
                        if tc_delta.function and tc_delta.function.name:
                            tool_calls[tc_index]["function"]["name"] = tc_delta.function.name

                        # Update function arguments
                        if tc_delta.function and tc_delta.function.arguments:
                            tool_calls[tc_index]["function"]["arguments"] += tc_delta.function.arguments

            # Add the final response to conversation history
            if accumulated_message:
                # Add assistant message to conversation history for continuity
                self.conversation_history.append({
                    "role": "assistant",
                    "content": accumulated_message
                })

            # Process any tool calls after streaming is complete
            if tool_calls and not self.should_cancel:
                for tool_call in tool_calls:
                    function_name = tool_call["function"]["name"]

                    try:
                        arguments = json.loads(tool_call["function"]["arguments"])
                    except json.JSONDecodeError:
                        arguments = {}
                        logger.error(f"Failed to parse tool call arguments: {tool_call['function']['arguments']}")

                    # Process different tool calls
                    if function_name == "run_terminal_cmd":
                        command = arguments.get("command", "")
                        is_background = arguments.get("is_background", False)

                        # Display the tool call
                        tool_call_item = {
                            "id": f"tool-call-{time.time()}",
                            "type": "tool_call",
                            "tool_call": {
                                "id": tool_call["id"],
                                "type": "function",
                                "function": {
                                    "name": function_name,
                                    "arguments": arguments
                                }
                            }
                        }

                        if self.on_item:
                            self.on_item(tool_call_item)

                        # Check if we need to confirm this command
                        if self.approval_policy != "full-auto" and self.get_command_confirmation:
                            # Parse command into list if it's a string
                            cmd_list = command.split() if isinstance(command, str) else command

                            # Get confirmation from user
                            confirmation = self.get_command_confirmation(cmd_list, None)

                            if confirmation.review == ReviewDecision.APPROVE:
                                # Run the command
                                import subprocess
                                try:
                                    if is_background:
                                        # Run in background (non-blocking)
                                        subprocess.Popen(
                                            cmd_list,
                                            shell=True if isinstance(command, str) else False,
                                            stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE
                                        )
                                        result = "Command running in background"
                                    else:
                                        # Run blocking with timeout
                                        proc = subprocess.run(
                                            cmd_list,
                                            shell=True if isinstance(command, str) else False,
                                            capture_output=True,
                                            text=True,
                                            timeout=300  # 5 minute timeout
                                        )
                                        result = proc.stdout + "\n" + proc.stderr

                                    # Return success result
                                    tool_result_item = {
                                        "id": f"tool-result-{time.time()}",
                                        "type": "tool_result",
                                        "tool_call_id": tool_call["id"],
                                        "content": result
                                    }

                                    if self.on_item:
                                        self.on_item(tool_result_item)

                                except Exception as e:
                                    # Return error result
                                    error_result = f"Error executing command: {str(e)}"
                                    tool_result_item = {
                                        "id": f"tool-error-{time.time()}",
                                        "type": "tool_result",
                                        "tool_call_id": tool_call["id"],
                                        "content": error_result
                                    }

                                    if self.on_item:
                                        self.on_item(tool_result_item)
                            else:
                                # Command was denied
                                deny_message = confirmation.custom_deny_message or "Command not approved by user"
                                tool_result_item = {
                                    "id": f"tool-denied-{time.time()}",
                                    "type": "tool_result",
                                    "tool_call_id": tool_call["id"],
                                    "content": deny_message
                                }

                                if self.on_item:
                                    self.on_item(tool_result_item)
                        else:
                            # Auto-approve in full-auto mode
                            import subprocess
                            try:
                                if is_background:
                                    # Run in background (non-blocking)
                                    subprocess.Popen(
                                        command,
                                        shell=True if isinstance(command, str) else False,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE
                                    )
                                    result = "Command running in background"
                                else:
                                    # Run blocking with timeout
                                    proc = subprocess.run(
                                        command,
                                        shell=True if isinstance(command, str) else False,
                                        capture_output=True,
                                        text=True,
                                        timeout=300  # 5 minute timeout
                                    )
                                    result = proc.stdout + "\n" + proc.stderr

                                # Return success result
                                tool_result_item = {
                                    "id": f"tool-result-{time.time()}",
                                    "type": "tool_result",
                                    "tool_call_id": tool_call["id"],
                                    "content": result
                                }

                                if self.on_item:
                                    self.on_item(tool_result_item)

                            except Exception as e:
                                # Return error result
                                error_result = f"Error executing command: {str(e)}"
                                tool_result_item = {
                                    "id": f"tool-error-{time.time()}",
                                    "type": "tool_result",
                                    "tool_call_id": tool_call["id"],
                                    "content": error_result
                                }

                                if self.on_item:
                                    self.on_item(tool_result_item)

                    elif function_name == "edit_file":
                        target_file = arguments.get("target_file", "")
                        code_edit = arguments.get("code_edit", "")

                        # Display the tool call
                        tool_call_item = {
                            "id": f"tool-call-{time.time()}",
                            "type": "tool_call",
                            "tool_call": {
                                "id": tool_call["id"],
                                "type": "function",
                                "function": {
                                    "name": function_name,
                                    "arguments": arguments
                                }
                            }
                        }

                        if self.on_item:
                            self.on_item(tool_call_item)

                        # Check if we need to confirm this edit
                        if self.approval_policy != "full-auto" and self.approval_policy != "auto-edit" and self.get_command_confirmation:
                            # Create an ApplyPatchCommand
                            apply_patch = ApplyPatchCommand(
                                file_path=target_file,
                                content=code_edit
                            )

                            # Get confirmation from user
                            confirmation = self.get_command_confirmation(["edit", target_file], apply_patch)

                            if confirmation.review == ReviewDecision.APPROVE:
                                # Apply the edit
                                try:
                                    # Create directory if it doesn't exist
                                    os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)

                                    # Write the file
                                    with open(target_file, "w") as f:
                                        f.write(code_edit)

                                    result = f"Successfully wrote to {target_file}"

                                    tool_result_item = {
                                        "id": f"tool-result-{time.time()}",
                                        "type": "tool_result",
                                        "tool_call_id": tool_call["id"],
                                        "content": result
                                    }

                                    if self.on_item:
                                        self.on_item(tool_result_item)

                                except Exception as e:
                                    error_result = f"Error editing file: {str(e)}"
                                    tool_result_item = {
                                        "id": f"tool-error-{time.time()}",
                                        "type": "tool_result",
                                        "tool_call_id": tool_call["id"],
                                        "content": error_result
                                    }

                                    if self.on_item:
                                        self.on_item(tool_result_item)
                            else:
                                # Edit was denied
                                deny_message = confirmation.custom_deny_message or "File edit not approved by user"
                                tool_result_item = {
                                    "id": f"tool-denied-{time.time()}",
                                    "type": "tool_result",
                                    "tool_call_id": tool_call["id"],
                                    "content": deny_message
                                }

                                if self.on_item:
                                    self.on_item(tool_result_item)
                        else:
                            # Auto-approve in full-auto or auto-edit mode
                            try:
                                # Create directory if it doesn't exist
                                os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)

                                # Write the file
                                with open(target_file, "w") as f:
                                    f.write(code_edit)

                                result = f"Successfully wrote to {target_file}"

                                tool_result_item = {
                                    "id": f"tool-result-{time.time()}",
                                    "type": "tool_result",
                                    "tool_call_id": tool_call["id"],
                                    "content": result
                                }

                                if self.on_item:
                                    self.on_item(tool_result_item)

                            except Exception as e:
                                error_result = f"Error editing file: {str(e)}"
                                tool_result_item = {
                                    "id": f"tool-error-{time.time()}",
                                    "type": "tool_result",
                                    "tool_call_id": tool_call["id"],
                                    "content": error_result
                                }

                                if self.on_item:
                                    self.on_item(tool_result_item)

            # Store the response ID for continuing the conversation
            if self.on_last_response_id:
                self.on_last_response_id(message_id)

        except Exception as e:
            # Handle any exceptions during processing
            error_message = f"Error in agent loop: {str(e)}"
            logger.error(error_message)
            self.add_system_message(error_message)

        finally:
            # Update loading state
            if self.on_loading:
                self.on_loading(False)

            self.is_running = False

    def cancel(self):
        """Cancel the currently running agent loop"""
        self.should_cancel = True

    def terminate(self):
        """Terminate the agent loop"""
        self.cancel()
        self.is_running = False
