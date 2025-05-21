# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: CLI entry point for the application
"""
import os
import sys
import argparse
from loguru import logger

from codev.config import load_config, CLI_VERSION, ROOT_DIR
from codev.terminal_chat import TerminalChat


def main():
    """Main entry point for the CLI"""
    parser = argparse.ArgumentParser(description="Codev CLI - AI-powered coding assistant")
    parser.add_argument("--prompt", "-p", type=str, help="Initial prompt to send to the model")
    parser.add_argument("--model", "-m", type=str, help="Model to use (e.g., gpt-4o, gpt-4-turbo)")
    parser.add_argument("--config", "-c", type=str, help="Path to configuration file")
    parser.add_argument("--image", "-i", action='append',
                        help="Path to image file to include with the prompt (can be used multiple times)")
    parser.add_argument("--approval", "-a", type=str, choices=["suggest", "auto-edit", "full-auto"],
                        default="suggest", help="Approval policy for commands")
    parser.add_argument("--full-stdout", "-f", action="store_true", help="Show full command output")
    parser.add_argument("--version", "-v", action="store_true", help="Show version information")

    args = parser.parse_args()

    # Show version and exit if requested
    if args.version:
        print(f"Codev CLI v{CLI_VERSION}")
        sys.exit(0)

    # Configure logging
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    logger.add(os.path.join(ROOT_DIR, "codev_cli.log"), rotation="10 MB")

    # Load configuration
    config = load_config(args.config)

    # Override model if specified
    if args.model:
        config.model = args.model

    # Run terminal chat
    m = TerminalChat(
        config=config,
        prompt=args.prompt,
        image_paths=args.image,
        approval_policy=args.approval,
        full_stdout=args.full_stdout
    )
    m.run()


if __name__ == "__main__":
    main()
