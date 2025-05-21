# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description:
"""
import os
import json
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger

from codev.commands import TermColor
from codev.config import ROOT_DIR


class HistoryManager:
    """History record manager, handles storage and retrieval of command and file edit history"""

    def __init__(self, history_file: str = os.path.join(ROOT_DIR, "history.json")):
        """
        Initialize history record manager
        
        Args:
            history_file: History record file path
        """
        self.history_file = history_file
        self.backup_dir = os.path.join(os.path.dirname(self.history_file), "backups")
        self.command_history: List[Dict[str, Any]] = []
        self.file_edit_history: List[Dict[str, Any]] = []
        self.session_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Ensure history and backup directories exist
        os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)

        # Load history records
        self.load_history()

    def create_backup(self) -> None:
        """Create a backup of the history file"""
        if not os.path.exists(self.history_file):
            return

        try:
            # Create timestamped backup filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(self.backup_dir, f"history_{timestamp}.json")

            # Copy the current history file to the backup location
            shutil.copy2(self.history_file, backup_file)

            # Clean up old backups (keep at most 10)
            self._cleanup_old_backups()
        except Exception as e:
            logger.error(f"Failed to create history backup: {str(e)}")

    def _cleanup_old_backups(self) -> None:
        """Keep only the 10 most recent backups"""
        try:
            backup_files = [os.path.join(self.backup_dir, f) for f in os.listdir(self.backup_dir)
                            if f.startswith("history_") and f.endswith(".json")]

            # Sort by modification time (oldest first)
            backup_files.sort(key=lambda x: os.path.getmtime(x))

            # If we have more than 10 backups, remove the oldest ones
            if len(backup_files) > 10:
                for old_file in backup_files[:-10]:
                    os.remove(old_file)
                    logger.debug(f"Removed old history backup: {old_file}")
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {str(e)}")

    def load_history(self) -> None:
        """Load history record file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.command_history = data.get('commands', [])
                    self.file_edit_history = data.get('files', [])

                logger.debug(f"History records loaded: {len(self.command_history)} commands, "
                             f"{len(self.file_edit_history)} file edits")

                # Create a backup when loading (ensures we have a backup even if the file gets corrupted)
                self.create_backup()
        except Exception as e:
            logger.error(f"Failed to load history records: {str(e)}")
            # Try to restore from backup if loading fails
            self._restore_from_backup()

    def _restore_from_backup(self) -> bool:
        """Attempt to restore history from the most recent backup"""
        try:
            backup_files = [os.path.join(self.backup_dir, f) for f in os.listdir(self.backup_dir)
                            if f.startswith("history_") and f.endswith(".json")]

            if not backup_files:
                logger.warning("No backup files found to restore from")
                # Initialize empty history
                self.command_history = []
                self.file_edit_history = []
                return False

            # Sort by modification time (newest first)
            backup_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            latest_backup = backup_files[0]

            # Load from the most recent backup
            with open(latest_backup, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.command_history = data.get('commands', [])
                self.file_edit_history = data.get('files', [])

            logger.info(f"Restored history from backup: {latest_backup}")
            # Copy the backup to the main history file
            shutil.copy2(latest_backup, self.history_file)
            return True
        except Exception as e:
            logger.error(f"Failed to restore from backup: {str(e)}")
            # Initialize empty history as last resort
            self.command_history = []
            self.file_edit_history = []
            return False

    def save_history(self) -> None:
        """Save history records to file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'commands': self.command_history,
                    'files': self.file_edit_history
                }, f, ensure_ascii=False, indent=2)

            # Create periodic backup (every 10 saves)
            if hash(str(self.command_history) + str(self.file_edit_history)) % 10 == 0:
                self.create_backup()
        except Exception as e:
            logger.error(f"Failed to save history records: {str(e)}")

    def add_command(self, command: str, success: bool = True, output: Optional[str] = None) -> None:
        """
        Add command to history records
        
        Args:
            command: Executed command
            success: Whether the command was successfully executed
            output: Command output (optional)
        """
        self.command_history.append({
            'command': command,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'success': success,
            'output_summary': output[:100] + '...' if output and len(output) > 100 else output
        })
        self.save_history()

    def add_file_edit(self, file_path: str, operation: str = 'edit') -> None:
        """
        Add file edit to history records
        
        Args:
            file_path: Path of the edited file
            operation: Operation type (edit, create, delete, etc.)
        """
        self.file_edit_history.append({
            'file': file_path,
            'operation': operation,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        self.save_history()

    def clear_history(self, session_only: bool = False) -> None:
        """
        Clear history records
        
        Args:
            session_only: If True, only clear history records from the current session
        """
        # Create backup before clearing
        self.create_backup()

        if session_only:
            # Only clear history records from the current session
            session_time = self.session_start_time
            self.command_history = [cmd for cmd in self.command_history
                                    if cmd.get('timestamp', '') < session_time]
            self.file_edit_history = [edit for edit in self.file_edit_history
                                      if edit.get('timestamp', '') < session_time]
        else:
            # Clear all history records
            self.command_history = []
            self.file_edit_history = []

        self.save_history()

    def get_session_commands(self) -> List[str]:
        """Get list of commands from the current session"""
        session_time = self.session_start_time
        return [cmd['command'] for cmd in self.command_history
                if cmd.get('timestamp', '') >= session_time]

    def get_session_files(self) -> List[str]:
        """Get list of files edited in the current session"""
        session_time = self.session_start_time
        return [edit['file'] for edit in self.file_edit_history
                if edit.get('timestamp', '') >= session_time]

    def show_history(self, limit: int = 20, session_only: bool = True) -> None:
        """
        Display history records
        
        Args:
            limit: Maximum number of entries to display
            session_only: If True, only display history records from the current session
        """
        print(f"\n{TermColor.CYAN}History Records:{TermColor.RESET}")

        # Filter and sort command history
        if session_only:
            session_time = self.session_start_time
            cmds = [cmd for cmd in self.command_history if cmd.get('timestamp', '') >= session_time]
            files = [edit for edit in self.file_edit_history if edit.get('timestamp', '') >= session_time]
        else:
            cmds = self.command_history
            files = self.file_edit_history

        # Sort by time (for string timestamps)
        cmds = sorted(cmds, key=lambda x: x.get('timestamp', ''), reverse=True)
        files = sorted(files, key=lambda x: x.get('timestamp', ''), reverse=True)

        # Limit quantity
        cmds = cmds[:limit]
        files = files[:limit]

        # Display command history
        print(f"\n{TermColor.YELLOW}Command History:{TermColor.RESET}")
        if cmds:
            for i, cmd in enumerate(cmds, 1):
                timestamp = cmd.get('timestamp', 'Unknown time')
                status = TermColor.GREEN + "✓" + TermColor.RESET if cmd.get('success',
                                                                            True) else TermColor.RED + "✗" + TermColor.RESET
                print(f"{i}. [{timestamp}] {status} {cmd['command']}")
        else:
            print("No command history records")

        # Display file edit history
        print(f"\n{TermColor.YELLOW}File Edit History:{TermColor.RESET}")
        if files:
            for i, edit in enumerate(files, 1):
                timestamp = edit.get('timestamp', 'Unknown time')
                operation = edit.get('operation', 'edit')
                op_color = {
                    'edit': TermColor.BLUE,
                    'create': TermColor.GREEN,
                    'delete': TermColor.RED
                }.get(operation, TermColor.WHITE)

                print(f"{i}. [{timestamp}] {op_color}{operation}{TermColor.RESET} {edit['file']}")
        else:
            print("No file edit history records")

        if session_only and (len(self.command_history) > len(cmds) or len(self.file_edit_history) > len(files)):
            print(
                f"\n{TermColor.BRIGHT_BLACK}Note: Only showing history records from the current session. Use '/history all' to view complete history.{TermColor.RESET}")

        if limit and (len(cmds) >= limit or len(files) >= limit):
            print(
                f"\n{TermColor.BRIGHT_BLACK}Note: Display limited to a maximum of {limit} entries. Use '/history all full' to view all history.{TermColor.RESET}")

        # Show backup info
        backup_count = len([f for f in os.listdir(self.backup_dir) if f.startswith("history_") and f.endswith(".json")])
        if backup_count > 0:
            print(
                f"\n{TermColor.BRIGHT_BLACK}Note: {backup_count} history backups available in {self.backup_dir}{TermColor.RESET}")
