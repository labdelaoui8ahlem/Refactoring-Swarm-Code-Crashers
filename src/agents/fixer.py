"""
Fixer Agent - Corrects code based on refactoring plans.
"""

import re
from typing import Dict
from src.utils.logger import log_experiment, ActionType
from src.utils.llm_client import LLMClient, LLMError, QuotaExhaustedError
from src.utils.file_tools import Tools


class FixerAgent:
    """Fixes code issues based on analysis."""
    
    def __init__(self, tools: Tools, llm_client: LLMClient):
        self.tools = tools
        self.llm = llm_client
        self.name = "Fixer_Agent"
    
    def _remove_test_code(self, code: str) -> str:
        """
        Remove any test code that the LLM might have included.
        
        Args:
            code: The code string to clean
            
        Returns:
            Code with test classes and test imports removed
        """
        lines = code.split('\n')
        clean_lines = []
        skip_until_dedent = False
        class_indent = 0
        
        for line in lines:
            # Skip test-related imports
            if re.match(r'^import\s+(unittest|pytest)', line):
                continue
            if re.match(r'^from\s+(unittest|pytest)', line):
                continue
            
            # Detect start of test class
            if re.match(r'^class\s+Test\w*.*:', line) or 'unittest.TestCase' in line:
                skip_until_dedent = True
                class_indent = len(line) - len(line.lstrip())
                continue
            
            # If we're skipping a test class, check for dedent
            if skip_until_dedent:
                current_indent = len(line) - len(line.lstrip())
                # Empty lines or lines with greater indent are part of the class
                if line.strip() == '' or current_indent > class_indent:
                    continue
                # If we hit a line with same or less indent and it's not empty, we're done
                skip_until_dedent = False
            
            # Skip standalone test functions
            if re.match(r'^def\s+test_\w+\s*\(', line):
                skip_until_dedent = True
                class_indent = 0
                continue
            
            # Skip if __name__ == '__main__' blocks that run unittest
            if "unittest.main()" in line or "pytest.main()" in line:
                continue
                
            clean_lines.append(line)
        
        # Remove trailing empty lines
        while clean_lines and clean_lines[-1].strip() == '':
            clean_lines.pop()
        
        return '\n'.join(clean_lines)
    
    def fix_file(self, filepath: str, analysis: Dict, iteration: int = 0) -> Dict:
        """
        Fix issues in a Python file.
        
        Args:
            filepath: Path to file to fix
            analysis: Analysis from Auditor agent
            iteration: Current iteration number (for tracking)
            
        Returns:
            Results of the fix attempt
            
        Raises:
            QuotaExhaustedError: If API quota is exhausted
        """
        # Read current code
        code = self.tools.read_file(filepath)
        
        # Create fix prompt
        prompt = f"""Fix this Python code. Return ONLY the corrected source code.

Code:
```python
{code}
```

Issues: {analysis.get('llm_analysis', 'Fix any bugs, add docstrings, follow PEP 8')}

Rules:
- ONLY fix the existing code, do NOT add new functions or classes
- Do NOT implement functions that are only referenced (like read_file if it's just called but not defined)
- Fix syntax errors, add exception handling, add docstrings, follow PEP 8
- NO tests, NO unittest, NO pytest code
- Keep original function names and structure
- Return only Python code, no markdown
"""
        
        # Get fixed code from LLM
        try:
            fixed_code = self.llm.generate(prompt, temperature=0.2)
        except QuotaExhaustedError:
            # Re-raise quota errors to stop immediately
            raise
        except LLMError as e:
            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=ActionType.FIX,
                details={
                    "file_fixed": filepath,
                    "iteration": iteration,
                    "input_prompt": prompt,
                    "output_response": str(e),
                    "error": str(e)
                },
                status="FAILURE"
            )
            return {
                "filepath": filepath,
                "fixed": False,
                "error": str(e)
            }
        
        # Clean up the response (remove markdown formatting if present)
        if "```python" in fixed_code:
            fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
        elif "```" in fixed_code:
            fixed_code = fixed_code.split("```")[1].split("```")[0].strip()
        
        # Remove any test code that might have been included
        fixed_code = self._remove_test_code(fixed_code)
        
        # Write the fixed code
        try:
            self.tools.write_file(filepath, fixed_code)
            
            # Run pylint on fixed code
            new_pylint = self.tools.run_pylint(filepath)
            
            # Log the fix
            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=ActionType.FIX,
                details={
                    "file_fixed": filepath,
                    "iteration": iteration,
                    "input_prompt": prompt,
                    "output_response": fixed_code,
                    "old_score": analysis.get('pylint_results', {}).get('score', 0),
                    "new_score": new_pylint.get('score', 0)
                },
                status="SUCCESS"
            )
            
            return {
                "filepath": filepath,
                "fixed": True,
                "new_pylint": new_pylint,
                "improved": new_pylint.get('score', 0) > analysis.get('pylint_results', {}).get('score', 0)
            }
        
        except Exception as e:
            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=ActionType.FIX,
                details={
                    "file_fixed": filepath,
                    "iteration": iteration,
                    "input_prompt": prompt,
                    "output_response": str(e),
                    "error": str(e)
                },
                status="FAILURE"
            )
            
            return {
                "filepath": filepath,
                "fixed": False,
                "error": str(e)
            }