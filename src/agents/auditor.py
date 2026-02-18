"""
Auditor Agent - Analyzes code and creates refactoring plans.
"""

from typing import Dict, List
from src.utils.logger import log_experiment, ActionType
from src.utils.llm_client import LLMClient, LLMError, QuotaExhaustedError
from src.utils.file_tools import Tools


class AuditorAgent:
    """Analyzes Python code and produces refactoring plans."""
    
    def __init__(self, tools: Tools, llm_client: LLMClient):
        self.tools = tools
        self.llm = llm_client
        self.name = "Auditor_Agent"
    
    def analyze_file(self, filepath: str) -> Dict:
        """
        Analyze a single Python file.
        
        Args:
            filepath: Path to Python file
            
        Returns:
            Analysis results with issues and recommendations
            
        Raises:
            QuotaExhaustedError: If API quota is exhausted
        """
        # Read the file
        code = self.tools.read_file(filepath)
        
        # Run pylint
        pylint_results = self.tools.run_pylint(filepath)
        
        # Create analysis prompt
        prompt = f"""Analyze this Python code and list issues to fix.

Code:
```python
{code}
```

Pylint Score: {pylint_results.get('score', 'N/A')}

Identify: syntax errors, logic bugs, missing exception handling, missing docstrings, PEP 8 issues.
ONLY analyze existing code - do NOT suggest adding new functions or implementing referenced functions.
DO NOT suggest adding tests.

Format:
- Issue: [description] | Fix: [solution]
"""
        
        # Get LLM analysis
        try:
            response = self.llm.generate(prompt, temperature=0.3)
        except QuotaExhaustedError:
            # Re-raise quota errors to stop immediately
            raise
        except LLMError as e:
            log_experiment(
                agent_name=self.name,
                model_used=self.llm.model_name,
                action=ActionType.ANALYSIS,
                details={
                    "file_analyzed": filepath,
                    "input_prompt": prompt,
                    "output_response": str(e),
                    "error": str(e)
                },
                status="FAILURE"
            )
            # Still mark as needing refactoring - we just couldn't analyze it
            # Use pylint results to determine if refactoring is needed
            needs_refactoring = (
                pylint_results.get('score', 0) < 7.0 or 
                len(pylint_results.get('issues', [])) > 0 or
                'error' in pylint_results
            )
            return {
                "filepath": filepath,
                "pylint_results": pylint_results,
                "llm_analysis": f"LLM error: {str(e)} - Please check your API quota.",
                "needs_refactoring": needs_refactoring,
                "error": str(e)
            }
        
        # Log the interaction
        log_experiment(
            agent_name=self.name,
            model_used=self.llm.model_name,
            action=ActionType.ANALYSIS,
            details={
                "file_analyzed": filepath,
                "input_prompt": prompt,
                "output_response": response,
                "pylint_score": pylint_results.get('score', 0.0),
                "issues_found": len(pylint_results.get('issues', []))
            },
            status="SUCCESS"
        )
        
        return {
            "filepath": filepath,
            "pylint_results": pylint_results,
            "llm_analysis": response,
            "needs_refactoring": (
                pylint_results.get('score', 0) < 7.0 or 
                len(pylint_results.get('issues', [])) > 0 or
                'error' in pylint_results
            )
        }
    
    def create_refactoring_plan(self, target_dir: str = ".") -> List[Dict]:
        """
        Create a refactoring plan for all Python files in target directory.
        
        Args:
            target_dir: Directory to analyze
            
        Returns:
            List of file analyses
            
        Raises:
            QuotaExhaustedError: If API quota is exhausted
        """
        python_files = self.tools.list_python_files(target_dir)
        
        if not python_files:
            return []
        
        analyses = []
        for filepath in python_files:
            try:
                analysis = self.analyze_file(filepath)
                analyses.append(analysis)
            except QuotaExhaustedError:
                # Re-raise quota errors to stop immediately
                raise
            except Exception as e:
                log_experiment(
                    agent_name=self.name,
                    model_used=self.llm.model_name,
                    action=ActionType.ANALYSIS,
                    details={
                        "file_analyzed": filepath,
                        "input_prompt": f"Attempted to analyze {filepath}",
                        "output_response": f"Error: {str(e)}",
                        "error": str(e)
                    },
                    status="FAILURE"
                )
        
        return analyses