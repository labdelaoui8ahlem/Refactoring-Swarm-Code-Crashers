"""
Judge Agent - Validates code with tests.
"""

import os
from typing import Dict, Optional
from src.utils.logger import log_experiment, ActionType
from src.utils.llm_client import LLMClient, LLMError, QuotaExhaustedError
from src.utils.file_tools import Tools


class JudgeAgent:
    """Validates code by running tests."""
    
    def __init__(self, tools: Tools, llm_client: LLMClient):
        self.tools = tools
        self.llm = llm_client
        self.name = "Judge_Agent"
    
    def generate_tests(self, filepath: str) -> Optional[str]:
        """
        Generate unit tests for a Python file.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            Path to generated test file, or None if failed
            
        Raises:
            QuotaExhaustedError: If API quota is exhausted
        """
        # Read the code
        code = self.tools.read_file(filepath)
        
        # Get the module name for imports
        filename = os.path.basename(filepath)
        module_name = filename.replace('.py', '')
        
        # Create test generation prompt
        prompt = f"""Generate pytest tests for this code.

Module: {module_name}
Code:
```python
{code}
```

Start with these exact lines:
import pytest
import sys
sys.path.insert(0, '..')
from {module_name} import <functions>

Rules:
- Use def test_* functions (not unittest)
- Use pytest.raises() for exceptions
- Use pytest.approx() for float comparisons
- Add brief docstrings
- Return only Python code, no markdown
"""
        
        # Generate tests
        try:
            test_code = self.llm.generate(prompt, temperature=0.3)
        except QuotaExhaustedError:
            # Re-raise quota errors to stop immediately
            raise
        except LLMError as e:
            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=ActionType.GENERATION,
                details={
                    "source_file": filepath,
                    "input_prompt": prompt,
                    "output_response": str(e),
                    "error": str(e)
                },
                status="FAILURE"
            )
            return None
        
        # Clean up response
        if "```python" in test_code:
            test_code = test_code.split("```python")[1].split("```")[0].strip()
        elif "```" in test_code:
            test_code = test_code.split("```")[1].split("```")[0].strip()
        
        # Create test file path in tests/ subfolder
        # Use the working_dir from tools to get absolute paths
        # e.g., code_bugs/bad_style.py -> code_bugs/tests/test_bad_style.py
        dir_path = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        test_filename = 'test_' + filename
        
        # Create tests subfolder path (relative to working_dir)
        tests_dir = os.path.join(dir_path, 'tests') if dir_path else 'tests'
        test_filepath = os.path.join(tests_dir, test_filename)
        
        # Get absolute path using tools.working_dir
        abs_tests_dir = self.tools.working_dir / tests_dir
        
        # Ensure tests directory exists
        os.makedirs(abs_tests_dir, exist_ok=True)
        
        # Create __init__.py in tests folder for imports to work
        init_file = abs_tests_dir / '__init__.py'
        if not init_file.exists():
            with open(init_file, 'w') as f:
                f.write('# Test package\n')
        
        # Write test file
        try:
            self.tools.write_file(test_filepath, test_code)
            
            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=ActionType.GENERATION,
                details={
                    "source_file": filepath,
                    "test_file": test_filepath,
                    "input_prompt": prompt,
                    "output_response": test_code
                },
                status="SUCCESS"
            )
            
            return test_filepath
        
        except Exception as e:
            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=ActionType.GENERATION,
                details={
                    "source_file": filepath,
                    "input_prompt": prompt,
                    "output_response": str(e),
                    "error": str(e)
                },
                status="FAILURE"
            )
            return None
    
    def validate_code(self, filepath: str, test_filepath: Optional[str] = None) -> Dict:
        """
        Validate code by running tests.
        
        Args:
            filepath: Path to code file
            test_filepath: Path to test file (will generate if None)
            
        Returns:
            Validation results
        """
        # Generate tests if not provided
        if test_filepath is None:
            test_filepath = self.generate_tests(filepath)
        
        if test_filepath is None:
            return {
                "filepath": filepath,
                "validated": False,
                "error": "Could not generate tests"
            }
        
        # Run tests
        test_results = self.tools.run_pytest(test_filepath)
        
        # Log validation
        log_experiment(
            agent_name=self.name,
            model_used=self.llm.model_name,
            action=ActionType.DEBUG if not test_results.get('passed') else ActionType.ANALYSIS,
            details={
                "file_validated": filepath,
                "test_file": test_filepath,
                "input_prompt": f"Running tests for {filepath}",
                "output_response": f"Tests {'passed' if test_results.get('passed') else 'failed'}\n{test_results.get('stdout', '')}",
                "tests_passed": test_results.get('passed', False)
            },
            status="SUCCESS" if test_results.get('passed') else "FAILURE"
        )
        
        return {
            "filepath": filepath,
            "test_filepath": test_filepath,
            "validated": test_results.get('passed', False),
            "test_results": test_results
        }
    
    def get_failure_feedback(self, validation_result: Dict) -> str:
        """
        Generate feedback for failed tests.
        
        Args:
            validation_result: Results from validate_code
            
        Returns:
            Feedback string for the Fixer agent
        """
        test_results = validation_result.get('test_results', {})
        
        feedback = f"""Test Failure Report for {validation_result.get('filepath')}:

STDOUT:
{test_results.get('stdout', 'No output')}

STDERR:
{test_results.get('stderr', 'No errors')}

Please fix the code to pass these tests.
"""
        return feedback