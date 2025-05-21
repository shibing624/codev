# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Agent implementation for the Codev CLI
"""

import os
import json
import time
from enum import Enum
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass
from loguru import logger
from agentica import Agent, OpenAIChat

from codev.config import AppConfig
from codev.tools import ShellTool, FileTool


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
    patch: Optional[str] = None


@dataclass
class CommandConfirmation:
    """Response from user when confirming a command"""
    review: ReviewDecision
    custom_deny_message: Optional[str] = None
    apply_patch: Optional[ApplyPatchCommand] = None
    explanation: Optional[str] = None


class CodevAgent:
    """
    Agent that interacts with the user via the terminal
    """

    def __init__(
            self,
            config: 'AppConfig',
            approval_policy: str = "auto-edit",
            on_loading: Callable[[bool], None] = None,
            get_command_confirmation: Optional[Callable] = None,
            history_manager=None,
            instructions: Union[List[str], str, None] = None,
            debug: bool = False,
    ):
        """
        Initialize the agent
        
        Args:
            config: The application configuration
            approval_policy: The approval policy to use, 'auto-edit', 'full-auto', or 'suggest'
            get_command_confirmation: Callback to request confirmation for commands
            history_manager: Manager for conversation history
            instructions: Instructions for the agent
            debug: Enable debug mode
        """
        self.config = config
        self.model = config.model  # Store model from config for easy access
        self.approval_policy = approval_policy
        self.get_command_confirmation = get_command_confirmation
        self.history_manager = history_manager

        # Initialize state variables
        self.is_running = False
        self.should_cancel = False
        self.loading = False
        self.session_id = self._generate_session_id()

        # Initialize the agent
        # Create custom tools
        self.shell_tool = self._create_custom_shell_tool()
        self.file_tool = self._create_custom_file_tool()

        # Create system message with instructions
        system_message = "You are a powerful coding assistant that helps users with programming tasks."
        if self.approval_policy:
            system_message += f" The current approval policy is set to '{self.approval_policy}'."

        self.agent = Agent(
            model=OpenAIChat(id=self.config.model),
            system_prompt=system_message,
            instructions=instructions,
            add_history_to_messages=True,
            tools=[self.shell_tool.execute_command, self.file_tool.write, self.file_tool.read, self.file_tool.delete],
            show_tool_calls=debug,
            debug=debug,
        )
        # Initialize conversation history
        self.conversation_history = self.agent.memory.messages

    def _create_custom_shell_tool(self):
        """
        Create a custom shell tool for executing commands
        
        Returns:
            ShellTool instance
        """
        shell_tool = ShellTool()

        # Wrap the execute_command method to handle approval
        original_execute_command = shell_tool.execute_command

        def custom_execute_command(command, is_background=False):
            """
            Execute a command with approval handling
            
            Args:
                command: The command to execute
                is_background: Whether to run in background
                
            Returns:
                Command execution result
            """
            logger.debug(f"Executing command: {command} (background: {is_background})")

            # Check if we need to confirm
            if self.approval_policy != "full-auto" and self.get_command_confirmation:
                try:
                    # Convert command to list if it's a string
                    cmd_list = command if isinstance(command, list) else command.split()

                    # For synchronous operation, we need to handle the confirmation differently
                    if hasattr(self.get_command_confirmation, "__call__"):
                        confirmation = self.get_command_confirmation(cmd_list, None)
                    else:
                        # If the confirmation function is async, we can't call it directly
                        confirmation = CommandConfirmation(review=ReviewDecision.APPROVE)

                    if confirmation.review != ReviewDecision.APPROVE:
                        deny_message = confirmation.custom_deny_message or "Command not approved by user"
                        logger.info(f"Command denied: {deny_message}")
                        return deny_message

                    logger.info("Command approved")
                except Exception as e:
                    error_msg = f"Error during command confirmation: {str(e)}"
                    logger.error(error_msg)
                    return error_msg

            # Execute the command
            try:
                result = original_execute_command(command, is_background)

                # Add to history manager if available
                if self.history_manager:
                    self.history_manager.add_command(command, True)

                return result
            except Exception as e:
                error_msg = f"Error executing command: {str(e)}"
                logger.error(error_msg)

                # Add to history manager if available
                if self.history_manager:
                    self.history_manager.add_command(command, False, str(e))

                return error_msg

        # Replace the original method with our custom one
        shell_tool.execute_command = custom_execute_command

        return shell_tool

    def _create_custom_file_tool(self):
        """
        Create a custom file tool for file operations
        
        Returns:
            FileTool instance
        """
        file_tool = FileTool()

        # Get original methods
        original_write = file_tool.write
        original_read = file_tool.read
        original_delete = file_tool.delete

        # Custom write method with approval handling
        def custom_write(path: str, content: str, **kwargs):
            """
            Write to a file with approval handling
            
            Args:
                path: File path to write to
                content: Content to write
                
            Returns:
                Result message
            """
            logger.debug(f"Writing to file: {path}")

            # Check if we need to confirm
            if self.approval_policy != "full-auto" and self.approval_policy != "auto-edit" and self.get_command_confirmation:
                try:
                    # Create apply patch command for confirmation
                    apply_patch = ApplyPatchCommand(
                        file_path=path,
                        content=content
                    )

                    # For synchronous operation, we need to handle the confirmation differently
                    if hasattr(self.get_command_confirmation, "__call__"):
                        confirmation = self.get_command_confirmation(["edit", path], apply_patch)
                    else:
                        # If the confirmation function is async, we can't call it directly
                        confirmation = CommandConfirmation(review=ReviewDecision.APPROVE)

                    if confirmation.review != ReviewDecision.APPROVE:
                        deny_message = confirmation.custom_deny_message or "File edit not approved by user"
                        logger.info(f"File edit denied: {deny_message}")
                        return deny_message

                    logger.info("File edit approved")
                except Exception as e:
                    error_msg = f"Error during file edit confirmation: {str(e)}"
                    logger.error(error_msg)
                    return error_msg

            # Write the file
            try:
                result = original_write(path, content, **kwargs)

                # Add to history manager if available
                if self.history_manager:
                    operation = "create" if not os.path.exists(path) else "edit"
                    self.history_manager.add_file_edit(path, operation)

                return result
            except Exception as e:
                error_msg = f"Error writing file: {str(e)}"
                logger.error(error_msg)
                return error_msg

        # Custom read method
        def custom_read(path: str, **kwargs):
            """Read a file"""
            logger.debug(f"Reading file: {path}")
            try:
                return original_read(path, **kwargs)
            except Exception as e:
                error_msg = f"Error reading file: {str(e)}"
                logger.error(error_msg)
                return error_msg

        # Custom delete method with approval handling
        def custom_delete(path: str, **kwargs):
            """
            Delete a file with approval handling
            
            Args:
                path: File path to delete
                
            Returns:
                Result message
            """
            logger.debug(f"Deleting file: {path}")

            # Check if we need to confirm
            if self.approval_policy != "full-auto" and self.get_command_confirmation:
                try:
                    # For synchronous operation, we need to handle the confirmation differently
                    if hasattr(self.get_command_confirmation, "__call__"):
                        confirmation = self.get_command_confirmation(["delete", path], None)
                    else:
                        # If the confirmation function is async, we can't call it directly
                        confirmation = CommandConfirmation(review=ReviewDecision.APPROVE)

                    if confirmation.review != ReviewDecision.APPROVE:
                        deny_message = confirmation.custom_deny_message or "File deletion not approved by user"
                        logger.info(f"File deletion denied: {deny_message}")
                        return deny_message

                    logger.info("File deletion approved")
                except Exception as e:
                    error_msg = f"Error during file deletion confirmation: {str(e)}"
                    logger.error(error_msg)
                    return error_msg

            # Delete the file
            try:
                result = original_delete(path, **kwargs)

                # Add to history manager if available
                if self.history_manager:
                    self.history_manager.add_file_edit(path, "delete")

                return result
            except Exception as e:
                error_msg = f"Error deleting file: {str(e)}"
                logger.error(error_msg)
                return error_msg

        # Replace the original methods with our custom ones
        file_tool.write = custom_write
        file_tool.read = custom_read
        file_tool.delete = custom_delete

        return file_tool

    def _generate_session_id(self):
        """Generate a unique session ID"""
        return f"session_{int(time.time())}"

    def send_message(self, user_message: str, stream: bool = False):
        """
        Send a message to the agent and handle the response
        
        Args:
            user_message: The user's message
            stream: Whether to stream the response
            
        Returns:
            If stream=True, returns an iterator of response chunks
            If stream=False, returns the complete response
        """
        if not user_message:
            return None
        return self.agent.run(user_message, stream=stream)
            

    def cancel(self):
        """
        Cancel the current operation
        """
        logger.info("Cancelling current operation")
        self.should_cancel = True
