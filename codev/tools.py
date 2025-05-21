# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""

import os
import subprocess
import time
from loguru import logger


class ShellTool:
    """Custom shell tool for executing commands"""

    def __init__(self):
        """Initialize the shell tool"""
        self.name = "shell"
        self.description = "Execute shell commands"

    def execute_command(self, command, is_background=False):
        """
        Execute a shell command

        Args:
            command: The command to execute
            is_background: Whether to run the command in the background

        Returns:
            The command output
        """
        try:
            logger.info(f"Executing command: `{command}`")
            # Execute the command
            if is_background:
                # Run in background
                process = subprocess.Popen(
                    command,
                    shell=True if isinstance(command, str) else False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                result = f"Command running in background (PID: {process.pid})"
            else:
                # Run with timeout
                process = subprocess.Popen(
                    command,
                    shell=True if isinstance(command, str) else False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                try:
                    import threading
                    
                    # Use a timeout mechanism
                    def kill_process():
                        if process.poll() is None:  # Process still running
                            process.kill()
                    
                    # Start timer for timeout
                    timer = threading.Timer(300, kill_process)
                    timer.start()
                    
                    # Wait for process to complete
                    stdout, stderr = process.communicate()
                    
                    # Cancel timer if process completed
                    timer.cancel()
                    
                    exit_code = process.returncode
                    stdout_text = stdout.decode('utf-8', errors='replace')
                    stderr_text = stderr.decode('utf-8', errors='replace')

                    result = stdout_text
                    if exit_code != 0 and stderr_text:
                        result += f"\nError (code {exit_code}): {stderr_text}"
                except Exception as timeout_error:
                    try:
                        process.terminate()
                        time.sleep(0.1)
                        if process.poll() is None:
                            process.kill()
                    except:
                        pass
                    result = "Command execution timed out or error occurred"
            logger.info(f"Command output: \n```{result}```")
            return result
        except Exception as e:
            error_msg = f"Error executing command: {str(e)}"
            logger.error(error_msg)
            return error_msg


class FileTool:
    """Custom file tool for file operations"""

    def __init__(self):
        """Initialize the file tool"""
        self.name = "file"
        self.description = "Perform file operations (read, write, delete)"

    def read(self, path: str, **kwargs):
        """
        Read a file

        Args:
            path: Path to the file

        Returns:
            The file content
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"Successfully read file: {path}")
            return content
        except Exception as e:
            error_msg = f"Error reading file: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def write(self, path: str, content: str, **kwargs):
        """
        Write to a file

        Args:
            path: Path to the file
            content: Content to write

        Returns:
            Success message
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Successfully wrote to file: {path}")
            return f"Successfully wrote to {path}"
        except Exception as e:
            error_msg = f"Error writing file: {str(e)}"
            logger.error(error_msg)
            return error_msg

    def delete(self, path: str, **kwargs):
        """
        Delete a file

        Args:
            path: Path to the file

        Returns:
            Success message
        """
        try:
            os.remove(path)
            logger.info(f"Successfully deleted file: {path}")
            return f"Successfully deleted {path}"
        except Exception as e:
            error_msg = f"Error deleting file: {str(e)}"
            logger.error(error_msg)
            return error_msg

