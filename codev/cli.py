#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import argparse

from codev.chat_terminal import TerminalChat
from codev.config import load_config
from codev.utils.models import get_available_models


def main():
    """
    Main entry point for the Codex CLI application
    """
    parser = argparse.ArgumentParser(description="Codex CLI - A command-line interface for code generation with AI")
    parser.add_argument("--model", type=str, help="The model to use for generation")
    parser.add_argument("--prompt", type=str, help="Initial prompt to send to the model")
    parser.add_argument("--image", action="append", help="Image file paths to include with the prompt")
    parser.add_argument("--approval-policy", type=str, choices=["suggest", "auto-edit", "full-auto"],
                        default="suggest", help="Approval policy for commands")
    parser.add_argument("--writable", action="append", help="Additional writable directories")
    parser.add_argument("--full-stdout", action="store_true", help="Show full stdout for commands")
    parser.add_argument("--notify", action="store_true", help="Enable desktop notifications")
    parser.add_argument("--config", type=str, help="Path to config file")

    args = parser.parse_args()

    # Load the configuration
    config_path = args.config
    config = load_config(config_path)

    # Override config with command line arguments
    if args.model:
        config.model = args.model
    if args.notify:
        config.notify = True

    # Verify model availability - but don't block execution if this fails
    try:
        available_models = get_available_models()
        if available_models and config.model not in available_models:
            print(f"Warning: model '{config.model}' is not in the list of available models returned by OpenAI.")
    except Exception as e:
        print(f"Warning: Failed to retrieve available models: {str(e)}")

    # Set up additional writable roots
    additional_writable_roots = args.writable or []

    # Initialize and run the terminal chat
    terminal = TerminalChat(
        config=config,
        prompt=args.prompt,
        image_paths=args.image,
        approval_policy=args.approval_policy or "suggest",
        additional_writable_roots=additional_writable_roots,
        full_stdout=args.full_stdout
    )

    try:
        terminal.run()
    except KeyboardInterrupt:
        print("\nExiting Codex CLI...")
        sys.exit(0)


if __name__ == "__main__":
    main()
