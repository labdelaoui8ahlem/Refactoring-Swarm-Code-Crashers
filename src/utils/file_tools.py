"""
Tools for the Refactoring Swarm agents.
Provides safe file operations, code analysis, and testing capabilities.
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class Tools:
    """Collection of tools that agents can use."""
    
    def __init__(self, working_dir: str = "."):
        self.working_dir = Path(working_dir).resolve()
        if not self.working_dir.exists():
            raise ValueError(f"Working directory does not exist: {working_dir}")
    
    def _is_safe_path(self, filepath: Path) -> bool:
        """Ensure file operations stay within working directory."""
        try:
            filepath = filepath.resolve()
            return filepath.is_relative_to(self.working_dir)
        except (ValueError, OSError):
            return False
    
    def read_file(self, filepath: str) -> str:
        """
        Safely read a file from the working directory.
        
        Args:
            filepath: Path to file (relative to working directory)
            
        Returns:
            File contents as string
            
        Raises:
            ValueError: If path is outside working directory
            FileNotFoundError: If file doesn't exist
        """
        full_path = self.working_dir / filepath
        
        if not self._is_safe_path(full_path):
            raise ValueError(f"Access denied: {filepath} is outside working directory")
        
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def write_file(self, filepath: str, content: str) -> None:
        """
        Safely write a file to the working directory.
        
        Args:
            filepath: Path to file (relative to working directory)
            content: Content to write
            
        Raises:
            ValueError: If path is outside working directory
        """
        full_path = self.working_dir / filepath
        
        if not self._is_safe_path(full_path):
            raise ValueError(f"Access denied: {filepath} is outside working directory")
        
        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def list_python_files(self, directory: str = ".") -> List[str]:
        """
        List all Python files in a directory within working directory.
        
        Args:
            directory: Directory to search (relative to working directory)
            
        Returns:
            List of Python file paths
        """
        search_dir = self.working_dir / directory
        
        if not self._is_safe_path(search_dir):
            raise ValueError(f"Access denied: {directory} is outside working directory")
        
        python_files = []
        for root, _, files in os.walk(search_dir):
            for file in files:
                if file.endswith('.py'):
                    rel_path = Path(root) / file
                    python_files.append(str(rel_path.relative_to(self.working_dir)))
        
        return python_files
    
    def run_pylint(self, filepath: str) -> Dict[str, any]:
        """
        Run pylint analysis on a Python file.
        
        Args:
            filepath: Path to Python file (relative to working directory)
            
        Returns:
            Dictionary with score and issues
        """
        full_path = self.working_dir / filepath
        
        if not self._is_safe_path(full_path):
            raise ValueError(f"Access denied: {filepath} is outside working directory")
        
        try:
            result = subprocess.run(
                ['pylint', str(full_path), '--output-format=json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse JSON output
            if result.stdout:
                issues = json.loads(result.stdout)
            else:
                issues = []
            
            # Extract score from stderr (pylint outputs score there)
            score = 0.0
            for line in result.stderr.split('\n'):
                if 'rated at' in line.lower():
                    try:
                        score = float(line.split('rated at')[1].split('/')[0].strip())
                    except:
                        pass
            
            return {
                "score": score,
                "issues": issues,
                "issue_count": len(issues)
            }
        
        except subprocess.TimeoutExpired:
            return {"score": 0.0, "issues": [], "error": "Timeout"}
        except Exception as e:
            return {"score": 0.0, "issues": [], "error": str(e)}
    
    def run_pytest(self, filepath: str) -> Dict[str, any]:
        """
        Run pytest on a Python test file.
        
        Args:
            filepath: Path to test file (relative to working directory)
            
        Returns:
            Dictionary with test results
        """
        full_path = self.working_dir / filepath
        
        if not self._is_safe_path(full_path):
            raise ValueError(f"Access denied: {filepath} is outside working directory")
        
        try:
            # Get the directory containing the test file
            test_dir = full_path.parent
            # The source files are one level up from tests/ folder
            source_dir = test_dir.parent
            
            # Set PYTHONPATH to include the source directory
            env = os.environ.copy()
            pythonpath = str(source_dir)
            if 'PYTHONPATH' in env:
                pythonpath = pythonpath + os.pathsep + env['PYTHONPATH']
            env['PYTHONPATH'] = pythonpath
            
            result = subprocess.run(
                ['pytest', str(full_path), '-v', '--tb=short'],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(source_dir),  # Run from source directory
                env=env
            )
            
            passed = result.returncode == 0
            
            return {
                "passed": passed,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            return {"passed": False, "error": "Timeout"}
        except Exception as e:
            return {"passed": False, "error": str(e)}
    
