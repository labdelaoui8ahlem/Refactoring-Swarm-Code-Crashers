#!/usr/bin/env python3
"""
Refactoring Swarm - Main Entry Point
A multi-agent system for automated code refactoring.

Usage:
    python main.py --target_dir <directory>
"""

import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

from src.utils.file_tools import Tools
from src.utils.llm_client import LLMClient
from src.orchestrator import RefactoringOrchestrator
from src.utils.logger import log_experiment


def main():
    """Main entry point for the Refactoring Swarm."""

    # Load environment variables
    load_dotenv()

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Refactoring Swarm - Automated code refactoring with LLM agents"
    )
    parser.add_argument(
        "--target_dir",
        type=str,
        required=True,
        help="Directory containing Python code to refactor"
    )
    parser.add_argument(
        "--max_iterations",
        type=int,
        default=10,
        help="Maximum iterations per file (default: 10)"
    )

    args = parser.parse_args()

    # Validate target directory
    target_path = Path(args.target_dir)
    if not target_path.exists():
        print(f"Error: Target directory '{args.target_dir}' does not exist")
        sys.exit(1)

    # ---- Startup event log ----
    log_experiment("System", "UNKNOWN", "STARTUP", f"Target: {args.target_dir}", "INFO")

    print("=" * 60)
    print("Refactoring Swarm - Multi-Agent Code Refactoring System")
    print("=" * 60)
    print(f"Target Directory : {args.target_dir}")
    print(f"Max Iterations   : {args.max_iterations}")
    print("=" * 60)

    try:
        # Initialize tools with target directory (work directly on files)
        tools = Tools(working_dir=args.target_dir)
        print(f"\nWorking directly on files in: {args.target_dir}")

        # Initialize LLM client
        print("Connecting to LLM...")
        llm_client = LLMClient(model_name="llama-3.3-70b-versatile")

        # Create orchestrator
        orchestrator = RefactoringOrchestrator(
            tools=tools,
            llm_client=llm_client,
            max_iterations=args.max_iterations
        )

        # Run the refactoring process
        results = orchestrator.run(target_dir=".")

        # Exit with appropriate code
        if results.get("status") == "complete":
            if results.get("successful", 0) > 0:
                print("\nRefactoring completed successfully")
                sys.exit(0)
            else:
                print("\nRefactoring completed but no files were validated")
                sys.exit(1)
        else:
            print("\nRefactoring failed")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(130)

    except Exception as e:
        print(f"\nFatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
