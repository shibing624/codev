# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Agent loop implementation for handling interactions with AI assistants
"""
import os
import json
import time
import asyncio
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Set
from dataclasses import dataclass
from loguru import logger
from openai import OpenAI, OpenAIError

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
    patch: Optional[str] = None


@dataclass
class CommandConfirmation:
    """Response from user when confirming a command"""
    review: ReviewDecision
    custom_deny_message: Optional[str] = None
    apply_patch: Optional[ApplyPatchCommand] = None
    explanation: Optional[str] = None


# Constants for patch operations and formats
PATCH_PREFIX = "*** Begin Patch\n"
PATCH_SUFFIX = "\n*** End Patch"
ADD_FILE_PREFIX = "*** Add File: "
DELETE_FILE_PREFIX = "*** Delete File: "
MOVE_FILE_TO_PREFIX = "*** Move File To: "
UPDATE_FILE_PREFIX = "*** Update File: "
END_OF_FILE_PREFIX = "*** End of File"
HUNK_ADD_LINE_PREFIX = "+"

# Wait time before retrying after rate limit errors (ms)
RATE_LIMIT_RETRY_WAIT_MS = int(os.environ.get("OPENAI_RATE_LIMIT_RETRY_WAIT_MS", "2500"))


class ActionType(Enum):
    """Enumeration of possible patch action types"""
    ADD = "add"
    DELETE = "delete"
    UPDATE = "update"


class Chunk:
    """Represents a chunk of changes in a file patch"""

    def __init__(self, orig_index: int, del_lines: List[str], ins_lines: List[str]):
        self.orig_index = orig_index
        self.del_lines = del_lines
        self.ins_lines = ins_lines


class PatchAction:
    """Represents an action to be performed on a file"""

    def __init__(self, action_type: ActionType, new_file: Optional[str] = None,
                 move_path: Optional[str] = None):
        self.type = action_type
        self.new_file = new_file
        self.chunks = []
        self.move_path = move_path


class Patch:
    """Represents a collection of patch actions to be applied"""

    def __init__(self):
        self.actions = {}


class DiffError(Exception):
    """Error raised when a patch cannot be properly applied"""
    pass


class Parser:
    """
    Parser for patches that converts patch text into structured operations
    Based on the TypeScript implementation for consistency
    """

    def __init__(self, current_files: Dict[str, str], lines: List[str]):
        """
        Initialize the parser
        
        Args:
            current_files: Dictionary of current file contents
            lines: Lines of the patch text
        """
        self.current_files = current_files
        self.lines = lines
        self.index = 0
        self.patch = Patch()
        self.fuzz = 0

    def is_done(self, prefixes: Optional[List[str]] = None) -> bool:
        """Check if parsing is complete or at a section boundary"""
        if self.index >= len(self.lines):
            return True
        if prefixes and any(self.lines[self.index].startswith(p.strip()) for p in prefixes):
            return True
        return False

    def startswith(self, prefix) -> bool:
        """Check if current line starts with a prefix"""
        prefixes = [prefix] if isinstance(prefix, str) else prefix
        return any(self.lines[self.index].startswith(p) for p in prefixes)

    def read_str(self, prefix="", return_everything=False) -> str:
        """Read a string from the current line with optional prefix"""
        if self.index >= len(self.lines):
            raise DiffError(f"Index: {self.index} >= {len(self.lines)}")

        if self.lines[self.index].startswith(prefix):
            text = self.lines[self.index] if return_everything else self.lines[self.index][len(prefix):]
            self.index += 1
            return text
        return ""

    def parse(self) -> None:
        """Parse the patch text into structured operations"""
        while not self.is_done([PATCH_SUFFIX]):
            path = self.read_str(UPDATE_FILE_PREFIX)
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Update File Error: Duplicate Path: {path}")
                if path not in self.current_files:
                    raise DiffError(f"Update File Error: Missing File: {path}")

                move_to = self.read_str(MOVE_FILE_TO_PREFIX)
                text = self.current_files[path]
                action = self.parse_update_file(text)
                action.move_path = move_to if move_to else None
                self.patch.actions[path] = action
                continue

            path = self.read_str(DELETE_FILE_PREFIX)
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Delete File Error: Duplicate Path: {path}")
                if path not in self.current_files:
                    raise DiffError(f"Delete File Error: Missing File: {path}")

                self.patch.actions[path] = PatchAction(ActionType.DELETE)
                continue

            path = self.read_str(ADD_FILE_PREFIX)
            if path:
                if path in self.patch.actions:
                    raise DiffError(f"Add File Error: Duplicate Path: {path}")
                if path in self.current_files:
                    raise DiffError(f"Add File Error: File already exists: {path}")

                self.patch.actions[path] = self.parse_add_file()
                continue

            raise DiffError(f"Unknown Line: {self.lines[self.index]}")

        if not self.startswith(PATCH_SUFFIX.strip()):
            raise DiffError("Missing End Patch")

        self.index += 1

    def parse_update_file(self, text: str) -> PatchAction:
        """Parse update file action"""
        action = PatchAction(ActionType.UPDATE)
        file_lines = text.split("\n")
        index = 0

        while not self.is_done([
            PATCH_SUFFIX,
            UPDATE_FILE_PREFIX,
            DELETE_FILE_PREFIX,
            ADD_FILE_PREFIX,
            END_OF_FILE_PREFIX,
        ]):
            def_str = self.read_str("@@ ")
            section_str = ""

            if not def_str and self.lines[self.index] == "@@":
                section_str = self.lines[self.index]
                self.index += 1

            if not (def_str or section_str or index == 0):
                raise DiffError(f"Invalid Line:\n{self.lines[self.index]}")

            if def_str.strip():
                found = False
                if not any(s == def_str for s in file_lines[:index]):
                    for i in range(index, len(file_lines)):
                        if file_lines[i] == def_str:
                            index = i + 1
                            found = True
                            break

                if not found and not any(s.strip() == def_str.strip() for s in file_lines[:index]):
                    for i in range(index, len(file_lines)):
                        if file_lines[i].strip() == def_str.strip():
                            index = i + 1
                            self.fuzz += 1
                            found = True
                            break

            next_chunk_context, chunks, end_patch_index, eof = self.peek_next_section(self.lines, self.index)
            new_index, fuzz = self.find_context(file_lines, next_chunk_context, index, eof)

            if new_index == -1:
                ctx_text = "\n".join(next_chunk_context)
                if eof:
                    raise DiffError(f"Invalid EOF Context {index}:\n{ctx_text}")
                else:
                    raise DiffError(f"Invalid Context {index}:\n{ctx_text}")

            self.fuzz += fuzz
            for ch in chunks:
                ch.orig_index += new_index
                action.chunks.append(ch)

            index = new_index + len(next_chunk_context)
            self.index = end_patch_index

        return action

    def parse_add_file(self) -> PatchAction:
        """Parse add file action"""
        lines = []
        while not self.is_done([
            PATCH_SUFFIX,
            UPDATE_FILE_PREFIX,
            DELETE_FILE_PREFIX,
            ADD_FILE_PREFIX,
        ]):
            s = self.read_str()
            if not s.startswith(HUNK_ADD_LINE_PREFIX):
                raise DiffError(f"Invalid Add File Line: {s}")
            lines.append(s[1:])

        return PatchAction(ActionType.ADD, new_file="\n".join(lines))

    @staticmethod
    def find_context_core(lines: List[str], context: List[str], start: int) -> Tuple[int, int]:
        """Find context in lines starting from start position"""
        if not context:
            return start, 0

        for i in range(start, len(lines)):
            if "\n".join(lines[i:i + len(context)]) == "\n".join(context):
                return i, 0

        for i in range(start, len(lines)):
            if "\n".join([s.rstrip() for s in lines[i:i + len(context)]]) == "\n".join([s.rstrip() for s in context]):
                return i, 1

        for i in range(start, len(lines)):
            if "\n".join([s.strip() for s in lines[i:i + len(context)]]) == "\n".join([s.strip() for s in context]):
                return i, 100

        return -1, 0

    @staticmethod
    def find_context(lines: List[str], context: List[str], start: int, eof: bool) -> Tuple[int, int]:
        """Find context in lines with EOF awareness"""
        if eof:
            new_index, fuzz = Parser.find_context_core(lines, context, len(lines) - len(context))
            if new_index != -1:
                return new_index, fuzz

            new_index, fuzz = Parser.find_context_core(lines, context, start)
            return new_index, fuzz + 10000

        return Parser.find_context_core(lines, context, start)

    @staticmethod
    def peek_next_section(lines: List[str], initial_index: int) -> Tuple[List[str], List[Chunk], int, bool]:
        """Peek ahead to get the next section of the patch"""
        index = initial_index
        old = []
        del_lines = []
        ins_lines = []
        chunks = []
        mode = "keep"

        while index < len(lines):
            s = lines[index]
            if any(s.startswith(p.strip()) for p in [
                "@@",
                PATCH_SUFFIX,
                UPDATE_FILE_PREFIX,
                DELETE_FILE_PREFIX,
                ADD_FILE_PREFIX,
                END_OF_FILE_PREFIX,
            ]):
                break

            if s == "***":
                break

            if s.startswith("***"):
                raise DiffError(f"Invalid Line: {s}")

            index += 1
            last_mode = mode
            line = s

            if line[0] == HUNK_ADD_LINE_PREFIX:
                mode = "add"
            elif line[0] == "-":
                mode = "delete"
            elif line[0] == " ":
                mode = "keep"
            else:
                # Tolerate invalid lines missing leading whitespace
                mode = "keep"
                line = " " + line

            line = line[1:]
            if mode == "keep" and last_mode != mode:
                if ins_lines or del_lines:
                    chunks.append(Chunk(len(old) - len(del_lines), del_lines.copy(), ins_lines.copy()))
                del_lines = []
                ins_lines = []

            if mode == "delete":
                del_lines.append(line)
                old.append(line)
            elif mode == "add":
                ins_lines.append(line)
            else:
                old.append(line)

        if ins_lines or del_lines:
            chunks.append(Chunk(len(old) - len(del_lines), del_lines.copy(), ins_lines.copy()))

        if index < len(lines) and lines[index] == END_OF_FILE_PREFIX:
            index += 1
            return old, chunks, index, True

        return old, chunks, index, False


def write_file(p: str, content: str) -> None:
    """Write content to a file, creating directories as needed"""
    import os.path

    if os.path.isabs(p):
        raise DiffError("We do not support absolute paths.")

    parent = os.path.dirname(p)
    if parent != ".":
        os.makedirs(parent, exist_ok=True)

    with open(p, "w", encoding="utf-8") as f:
        f.write(content)


def remove_file(p: str) -> None:
    """Remove a file"""
    import os
    os.unlink(p)


class AgentLoop:
    """
    Manages the interaction loop with the AI agent.
    Handles sending messages, receiving responses, and processing tool calls.
    """

    def __init__(
            self,
            model: str,
            config: AppConfig,
            instructions: Optional[str] = None,
            approval_policy: str = "suggest",
            additional_writable_roots: List[str] = None,
            on_item: Callable[[Dict[str, Any]], None] = None,
            on_loading: Callable[[bool], None] = None,
            on_last_response_id: Callable[[Optional[str]], None] = None,
            get_command_confirmation: Optional[Callable] = None
    ):
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
        # Track generations to ignore stale events
        self.generation = 0
        # Track pending abort tool calls
        self.pending_aborts: Set[str] = set()
        # Abort controller for in-progress tool calls
        self.exec_abort_controller = None
        # Reference to the current stream for cancellation
        self.current_stream = None
        # Session ID for tracking
        self.session_id = self._generate_session_id()

        # Initialize OpenAI client
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
            base_url=OPENAI_BASE_URL
        )

    def _generate_session_id(self) -> str:
        """Generate a unique session ID"""
        import uuid
        return uuid.uuid4().hex

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

        # Print the system message to terminal
        print(f"\n[System] {content}")

    def add_user_message(self, content: str, images: List[str] = None):
        """
        Add a user message to the conversation history
        
        Args:
            content: The text content of the message
            images: Optional list of image paths to include
        """
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
                    try:
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
                    except Exception as e:
                        print(f"\n[Error] Failed to load image {image_path}: {str(e)}")
                        logger.error(f"Failed to load image {image_path}: {str(e)}")

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
            "content": message_content if images else content
        })

        # Print user message to terminal
        print(f"\n[User] {content}")
        if images:
            print(f"[Attached {len(images)} image(s)]")

    async def handle_function_call(self, tool_call):
        """
        Process a tool call from the AI
        
        Args:
            tool_call: The tool call to process
            
        Returns:
            List of response input items
        """
        # If the agent has been canceled, don't process this tool call
        if self.should_cancel:
            return []

        # Extract function details from the tool call
        function_name = tool_call.get("function", {}).get("name", "")
        function_arguments = tool_call.get("function", {}).get("arguments", "{}")
        call_id = tool_call.get("id", "")

        # Print tool call to terminal
        print(f"\n[Tool Call] Function: {function_name}")

        # Parse arguments
        try:
            args = json.loads(function_arguments)
            print(f"[Arguments] {json.dumps(args, indent=2)}")
        except json.JSONDecodeError:
            error_msg = f"Invalid arguments for function call: {function_arguments}"
            print(f"[Error] {error_msg}")
            logger.error(error_msg)
            return [{
                "type": "function_call_output",
                "call_id": call_id,
                "output": f"Invalid arguments: {function_arguments}"
            }]

        # Initialize default output
        output_item = {
            "type": "function_call_output",
            "call_id": call_id,
            "output": "No function found"
        }

        # Process different tool calls
        if function_name in ["shell", "run_terminal_cmd", "container.exec"]:
            command = args.get("command", "")
            is_background = args.get("is_background", False)
            workdir = args.get("workdir", None)

            # Prepare command for execution
            cmd_list = command if isinstance(command, list) else command.split()

            # Check if we need to confirm
            if self.approval_policy != "full-auto" and self.get_command_confirmation:
                print("\n[Approval] Requesting command confirmation...")
                try:
                    confirmation = await self.get_command_confirmation(cmd_list, None)

                    if confirmation.review != ReviewDecision.APPROVE:
                        deny_message = confirmation.custom_deny_message or "Command not approved by user"
                        print(f"[Denied] {deny_message}")
                        output_item["output"] = deny_message
                        return [output_item]
                    print("[Approved] Command execution authorized")
                except Exception as e:
                    error_msg = f"Error during command confirmation: {str(e)}"
                    print(f"[Error] {error_msg}")
                    logger.error(error_msg)
                    output_item["output"] = f"Error confirming command: {str(e)}"
                    return [output_item]

            # Execute the command
            try:
                import subprocess

                print(f"\n[Executing] {'(Background) ' if is_background else ''}{command}")
                if workdir:
                    print(f"[Working Directory] {workdir}")

                # Create a new abort controller for this execution
                self.exec_abort_controller = asyncio.create_task(self._create_abort_controller())

                if is_background:
                    # Run in background
                    process = subprocess.Popen(
                        command,
                        shell=True if isinstance(command, str) else False,
                        cwd=workdir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    output_text = f"Command running in background (PID: {process.pid})"
                    print(f"[Background] {output_text}")
                else:
                    # Run with timeout
                    process = await asyncio.create_subprocess_shell(
                        command if isinstance(command, str) else " ".join(command),
                        cwd=workdir,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )

                    try:
                        print("[Waiting] Command execution in progress...")
                        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
                        exit_code = process.returncode
                        stdout_text = stdout.decode('utf-8', errors='replace')
                        stderr_text = stderr.decode('utf-8', errors='replace')

                        output_text = stdout_text
                        if exit_code != 0 and stderr_text:
                            output_text += f"\nError (code {exit_code}): {stderr_text}"
                            print(f"[Exit Code] {exit_code}")
                            print(f"[Error] {stderr_text}")
                        else:
                            print(f"[Success] Command completed (Exit Code: {exit_code})")

                        # Print up to 20 lines of stdout to the terminal
                        lines = stdout_text.splitlines()
                        if lines:
                            print("\n[Output]")
                            for i, line in enumerate(lines[:20]):
                                print(line)
                            if len(lines) > 20:
                                print(f"... and {len(lines) - 20} more lines")
                    except asyncio.TimeoutError:
                        try:
                            print("[Timeout] Command execution timed out, terminating...")
                            process.terminate()
                            await asyncio.sleep(0.1)
                            if process.returncode is None:
                                process.kill()
                                print("[Killed] Process forcefully terminated")
                        except:
                            pass
                        output_text = "Command execution timed out after 300 seconds"

                output_item["output"] = json.dumps({
                    "output": output_text,
                    "metadata": {
                        "exit_code": 0 if is_background else (exit_code if 'exit_code' in locals() else 1),
                        "duration_seconds": 0 if is_background else 300
                    }
                })

            except Exception as e:
                error_msg = f"Error executing command: {str(e)}"
                print(f"[Error] {error_msg}")
                logger.error(error_msg)
                output_item["output"] = json.dumps({
                    "output": f"Error executing command: {str(e)}",
                    "metadata": {"exit_code": 1}
                })

            finally:
                # Clear the abort controller
                self.exec_abort_controller = None

        elif function_name == "edit_file":
            target_file = args.get("target_file", "")
            code_edit = args.get("code_edit", "")

            print(f"\n[Edit File] {target_file}")

            # Check if this is a patch operation
            is_patch = code_edit.startswith(PATCH_PREFIX) and code_edit.endswith(PATCH_SUFFIX)
            if is_patch:
                print("[Patch] Processing patch operation")
            else:
                print("[Direct Edit] Writing file directly")

            # Create apply patch command
            apply_patch = ApplyPatchCommand(
                file_path=target_file,
                content=code_edit,
                patch=code_edit if is_patch else None
            )

            # Check if we need to confirm
            if self.approval_policy != "full-auto" and self.approval_policy != "auto-edit" and self.get_command_confirmation:
                print("\n[Approval] Requesting file edit confirmation...")
                try:
                    confirmation = await self.get_command_confirmation(["edit", target_file], apply_patch)

                    if confirmation.review != ReviewDecision.APPROVE:
                        deny_message = confirmation.custom_deny_message or "File edit not approved by user"
                        print(f"[Denied] {deny_message}")
                        output_item["output"] = deny_message
                        return [output_item]
                    print("[Approved] File edit authorized")
                except Exception as e:
                    error_msg = f"Error during file edit confirmation: {str(e)}"
                    print(f"[Error] {error_msg}")
                    logger.error(error_msg)
                    output_item["output"] = f"Error confirming file edit: {str(e)}"
                    return [output_item]

            # Apply the edit
            try:
                if is_patch:
                    # Apply patch using the improved patch handling
                    result = process_patch(
                        code_edit,
                        open_file,
                        write_file,
                        remove_file
                    )
                    output_item["output"] = result
                else:
                    # Direct file edit
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(os.path.abspath(target_file)), exist_ok=True)

                    # Write the file
                    with open(target_file, "w", encoding="utf-8") as f:
                        f.write(code_edit)

                    success_msg = f"Successfully wrote to {target_file}"
                    print(f"[Success] {success_msg}")
                    output_item["output"] = success_msg
            except Exception as e:
                error_msg = f"Error editing file: {str(e)}"
                print(f"[Error] {error_msg}")
                logger.error(error_msg)
                output_item["output"] = f"Error editing file: {str(e)}"

        return [output_item]

    async def _create_abort_controller(self):
        """Create an abort controller that can be used to cancel operations"""
        controller = asyncio.Event()
        return controller

    async def run(self, input_items: List[Dict[str, Any]], last_response_id: str = None):
        """
        Run the agent loop with the given input items
        
        Args:
            input_items: List of input items to process
            last_response_id: ID of the last response
        """
        if self.is_running:
            print("\n[Warning] Agent is already running")
            logger.warning("Agent is already running")
            return

        self.is_running = True
        self.should_cancel = False

        # Increment generation to ignore stray events
        self.generation += 1
        this_generation = self.generation

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

        print("\n[Agent] Processing request...")

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

            print(f"\n[Model] Using {self.model}")
            print(f"[Policy] Approval Policy: {self.approval_policy}")

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
                                },
                                "workdir": {
                                    "type": "string",
                                    "description": "The working directory for the command"
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
                                    "description": "The new content for the file or a patch in the format '*** Begin Patch\\n...'"
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

            print("\n[Processing] Sending request to model...")

            # Prepare for retry in case of API errors
            MAX_RETRIES = 2

            for attempt in range(MAX_RETRIES):
                try:
                    # Make streaming request using OpenAI's Python client
                    print("[Stream] Starting response stream...")
                    self.current_stream = self.client.chat.completions.create(
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
                    print("\n[Response]")
                    for chunk in self.current_stream:
                        # Check if we should cancel
                        if self.should_cancel or this_generation != self.generation:
                            print("[Canceled] Response generation canceled")
                            break

                        # Extract content if present
                        delta = chunk.choices[0].delta

                        # Handle content updates
                        if hasattr(delta, 'content') and delta.content is not None:
                            accumulated_message += delta.content
                            print(delta.content, end="", flush=True)

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
                                    print(f"\n\n[Tool Call] {tc_delta.function.name}")

                                # Update function arguments
                                if tc_delta.function and tc_delta.function.arguments:
                                    tool_calls[tc_index]["function"]["arguments"] += tc_delta.function.arguments
                                    print(tc_delta.function.arguments, end="", flush=True)

                    print("\n")  # Add newline after response

                    # Add the final response to conversation history
                    if accumulated_message:
                        # Add assistant message to conversation history for continuity
                        self.conversation_history.append({
                            "role": "assistant",
                            "content": accumulated_message
                        })

                    # Process any tool calls after streaming is complete
                    if tool_calls and not self.should_cancel and this_generation == self.generation:
                        for tool_call in tool_calls:
                            # Add the tool call to conversation history
                            self.conversation_history.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [tool_call]
                            })

                            # Process the tool call
                            results = await self.handle_function_call(tool_call)

                            for result in results:
                                # Add the tool call result to conversation history
                                self.conversation_history.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call["id"],
                                    "content": result["output"]
                                })

                                # Create a result item to show the output
                                tool_result_item = {
                                    "id": f"tool-result-{time.time()}",
                                    "type": "tool_result",
                                    "tool_call_id": tool_call["id"],
                                    "content": result["output"]
                                }

                                if self.on_item:
                                    self.on_item(tool_result_item)

                    # If we reached here, break the retry loop
                    break

                except OpenAIError as e:
                    if attempt < MAX_RETRIES - 1:
                        print(f"\n[Retry] OpenAI request timed out (attempt {attempt + 1}/{MAX_RETRIES}), retrying...")
                        logger.warning(f"OpenAI request timed out (attempt {attempt + 1}/{MAX_RETRIES}), retrying...")
                        await asyncio.sleep(1)  # Wait briefly before retrying
                    else:
                        print("\n[Error] Max retries reached for OpenAI API timeout")
                        logger.error("Max retries reached for OpenAI API timeout")
                        self.add_system_message("Error: OpenAI API timed out after multiple attempts.")

                except Exception as e:
                    error_msg = f"Error in agent loop: {str(e)}"
                    print(f"\n[Error] {error_msg}")
                    logger.error(error_msg)
                    if attempt < MAX_RETRIES - 1 and isinstance(e, (ConnectionError, TimeoutError)):
                        print(f"[Retry] Connection error, retrying (attempt {attempt + 1}/{MAX_RETRIES})...")
                        logger.warning(f"Connection error, retrying (attempt {attempt + 1}/{MAX_RETRIES})...")
                        await asyncio.sleep(1)
                    else:
                        self.add_system_message(f"Error: {str(e)}")
                        break

            # Store the response ID for continuing the conversation
            if self.on_last_response_id:
                self.on_last_response_id(message_id)

            print("\n[Complete] Processing completed")

        except Exception as e:
            # Handle any exceptions during processing
            error_message = f"Error in agent loop: {str(e)}"
            print(f"\n[Error] {error_message}")
            logger.error(error_message)
            self.add_system_message(error_message)

        finally:
            # Update loading state
            if self.on_loading:
                self.on_loading(False)

            self.is_running = False
            self.current_stream = None
            print("\n[Ready] Agent ready for next request")

    def cancel(self):
        """Cancel the currently running agent loop"""
        print("\n[Cancel] Canceling current operation...")
        self.should_cancel = True
        self.generation += 1  # Increment to ignore ongoing events

        # Cancel the current stream if possible
        if self.current_stream:
            try:
                # OpenAI's Python client doesn't have a direct way to cancel streams
                # We rely on the generation counter to ignore future events
                print("[Cancel] Stopping response stream")
                pass
            except:
                pass

        # Cancel any running tool executions
        if self.exec_abort_controller:
            try:
                print("[Cancel] Aborting current tool execution")
                self.exec_abort_controller.set()
            except:
                pass

        print("[Cancel] Operation canceled")

    def terminate(self):
        """Terminate the agent loop completely"""
        print("\n[Terminate] Terminating agent loop")
        self.cancel()
        self.is_running = False
        print("[Terminate] Agent loop terminated")


# High-level helpers for patch processing
def text_to_patch(text: str, orig: Dict[str, str]) -> Tuple[Patch, int]:
    """
    Convert patch text to structured Patch object
    
    Args:
        text: The patch text
        orig: Dictionary of original file contents
        
    Returns:
        Tuple of Patch object and fuzz factor
    """
    lines = text.strip().split("\n")
    if (len(lines) < 2 or
            not (lines[0] or "").startswith(PATCH_PREFIX.strip()) or
            lines[-1] != PATCH_SUFFIX.strip()):
        raise DiffError("Invalid patch text")

    parser = Parser(orig, lines)
    parser.index = 1
    parser.parse()
    return parser.patch, parser.fuzz


def identify_files_needed(text: str) -> List[str]:
    """
    Identify files needed for the patch
    
    Args:
        text: The patch text
        
    Returns:
        List of file paths needed
    """
    lines = text.strip().split("\n")
    result = set()

    for line in lines:
        if line.startswith(UPDATE_FILE_PREFIX):
            result.add(line[len(UPDATE_FILE_PREFIX):])
        if line.startswith(DELETE_FILE_PREFIX):
            result.add(line[len(DELETE_FILE_PREFIX):])

    return list(result)


def identify_files_added(text: str) -> List[str]:
    """
    Identify files to be added by the patch
    
    Args:
        text: The patch text
        
    Returns:
        List of file paths to be added
    """
    lines = text.strip().split("\n")
    result = set()

    for line in lines:
        if line.startswith(ADD_FILE_PREFIX):
            result.add(line[len(ADD_FILE_PREFIX):])

    return list(result)


def get_updated_file(text: str, action: PatchAction, path: str) -> str:
    """
    Apply patches to get updated file content
    
    Args:
        text: Original file content
        action: Patch action to apply
        path: File path for error reporting
        
    Returns:
        Updated file content
    """
    if action.type != ActionType.UPDATE:
        raise ValueError("Expected UPDATE action")

    orig_lines = text.split("\n")
    dest_lines = []
    orig_index = 0

    for chunk in action.chunks:
        if chunk.orig_index > len(orig_lines):
            raise DiffError(
                f"{path}: chunk.orig_index {chunk.orig_index} > len(lines) {len(orig_lines)}"
            )

        if orig_index > chunk.orig_index:
            raise DiffError(
                f"{path}: orig_index {orig_index} > chunk.orig_index {chunk.orig_index}"
            )

        dest_lines.extend(orig_lines[orig_index:chunk.orig_index])
        delta = chunk.orig_index - orig_index
        orig_index += delta

        # Add inserted lines
        if chunk.ins_lines:
            dest_lines.extend(chunk.ins_lines)

        orig_index += len(chunk.del_lines)

    dest_lines.extend(orig_lines[orig_index:])
    return "\n".join(dest_lines)


def patch_to_commit(patch: Patch, orig: Dict[str, str]) -> Dict[str, Dict]:
    """
    Convert patch to commit format
    
    Args:
        patch: Patch object
        orig: Dictionary of original file contents
        
    Returns:
        Dictionary representing changes to apply
    """
    commit = {"changes": {}}

    for path_key, action in patch.actions.items():
        if action.type == ActionType.DELETE:
            commit["changes"][path_key] = {
                "type": "delete",
                "old_content": orig.get(path_key)
            }
        elif action.type == ActionType.ADD:
            commit["changes"][path_key] = {
                "type": "add",
                "new_content": action.new_file or ""
            }
        elif action.type == ActionType.UPDATE:
            new_content = get_updated_file(orig[path_key], action, path_key)
            commit["changes"][path_key] = {
                "type": "update",
                "old_content": orig[path_key],
                "new_content": new_content,
                "move_path": action.move_path
            }

    return commit


def load_files(paths: List[str], open_fn: Callable[[str], str]) -> Dict[str, str]:
    """
    Load multiple files using the provided open function
    
    Args:
        paths: List of file paths to load
        open_fn: Function to open and read files
        
    Returns:
        Dictionary mapping file paths to their contents
    """
    orig = {}
    for p in paths:
        try:
            orig[p] = open_fn(p)
        except Exception:
            # Convert any file read error to DiffError
            raise DiffError(f"File not found: {p}")

    return orig


def apply_commit(commit: Dict[str, Dict], write_fn: Callable[[str, str], None],
                 remove_fn: Callable[[str], None]) -> None:
    """
    Apply changes in a commit
    
    Args:
        commit: Commit dictionary with changes
        write_fn: Function to write files
        remove_fn: Function to remove files
    """
    for p, change in commit["changes"].items():
        if change["type"] == "delete":
            remove_fn(p)
        elif change["type"] == "add":
            write_fn(p, change.get("new_content", ""))
        elif change["type"] == "update":
            if change.get("move_path"):
                write_fn(change["move_path"], change.get("new_content", ""))
                remove_fn(p)
            else:
                write_fn(p, change.get("new_content", ""))


def process_patch(text: str, open_fn: Callable[[str], str],
                  write_fn: Callable[[str, str], None],
                  remove_fn: Callable[[str], None]) -> str:
    """
    Process a patch and apply it to the filesystem
    
    Args:
        text: Patch text
        open_fn: Function to open and read files
        write_fn: Function to write files
        remove_fn: Function to remove files
        
    Returns:
        Result message
    """
    if not text.startswith(PATCH_PREFIX):
        raise DiffError("Patch must start with *** Begin Patch\\n")

    paths = identify_files_needed(text)
    orig = load_files(paths, open_fn)
    patch, _ = text_to_patch(text, orig)
    commit = patch_to_commit(patch, orig)
    apply_commit(commit, write_fn, remove_fn)

    print("Successfully applied patch")
    return "Successfully applied patch"


# Default filesystem implementations
def open_file(p: str) -> str:
    """Open and read a file"""
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write_file(p: str, content: str) -> None:
    """Write content to a file, creating directories as needed"""
    import os.path

    if os.path.isabs(p):
        raise DiffError("We do not support absolute paths.")

    parent = os.path.dirname(p)
    if parent != ".":
        os.makedirs(parent, exist_ok=True)

    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
