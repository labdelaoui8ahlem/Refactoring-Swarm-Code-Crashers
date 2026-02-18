"""
Orchestrator - Manages the multi-agent refactoring workflow.
"""

import os
import shutil
from typing import List, Dict
from src.agents.auditor import AuditorAgent
from src.agents.fixer import FixerAgent
from src.agents.judge import JudgeAgent
from src.utils.file_tools import Tools
from src.utils.llm_client import LLMClient, QuotaExhaustedError


class RefactoringOrchestrator:
    """Orchestrates the refactoring swarm workflow."""
    
    def __init__(self, tools: Tools, llm_client: LLMClient, max_iterations: int = 10):
        self.tools = tools
        self.llm = llm_client
        self.max_iterations = max_iterations
        
        # Initialize agents
        self.auditor = AuditorAgent(tools, llm_client)
        self.fixer = FixerAgent(tools, llm_client)
        self.judge = JudgeAgent(tools, llm_client)
    
    def run(self, target_dir: str = ".") -> Dict:
        """
        Execute the refactoring workflow.
        Each iteration: fix all pending files, test all, repeat until all pass.
        
        Args:
            target_dir: Directory containing code to refactor
            
        Returns:
            Summary of the refactoring process
        """
        print(f"Starting Refactoring Swarm on {target_dir}")
        
        # Step 1: Auditor analyzes all files
        print("\nPhase 1: Code Analysis")
        try:
            analyses = self.auditor.create_refactoring_plan(target_dir)
        except QuotaExhaustedError as e:
            print(f"\n{'='*60}")
            print(f"  ERROR: {str(e)}")
            print(f"{'='*60}")
            return {"status": "quota_exhausted", "files_processed": 0}
        
        if not analyses:
            print("No Python files found to analyze")
            return {"status": "no_files", "files_processed": 0}
        
        print(f"   Found {len(analyses)} Python files")
        
        # Separate files that need fixing from those already good
        pending = {}  # filepath -> analysis
        results = {}  # filepath -> result
        
        for analysis in analyses:
            filepath = analysis['filepath']
            if not analysis.get('needs_refactoring', False):
                print(f"   {filepath} - Already good quality")
                results[filepath] = {
                    "filepath": filepath,
                    "status": "no_fix_needed",
                    "validated": True,
                    "iterations": 0,
                    "final_score": analysis.get('pylint_results', {}).get('score', 10.0)
                }
            else:
                pending[filepath] = analysis
        
        if not pending:
            print("\n   All files already pass quality checks!")
            self._cleanup_tests(target_dir)
            return self._build_summary(results, target_dir)
        
        # Step 2: Iterative batch fixing
        print(f"\nPhase 2: Code Fixing ({len(pending)} files need work)")
        
        try:
            for iteration in range(1, self.max_iterations + 1):
                if not pending:
                    break
                    
                print(f"\n--- Iteration {iteration}/{self.max_iterations} ---")
                print(f"   Files remaining: {len(pending)}")
                
                # Fix all pending files
                for filepath, analysis in list(pending.items()):
                    print(f"\n   Fixing: {filepath}")
                    fix_result = self.fixer.fix_file(filepath, analysis, iteration)
                    
                    if not fix_result.get('fixed', False):
                        print(f"      Fix failed: {fix_result.get('error', 'Unknown')}")
                        results[filepath] = {
                            "filepath": filepath,
                            "status": "fix_failed",
                            "validated": False,
                            "iterations": iteration
                        }
                        del pending[filepath]
                
                # Test all pending files
                failed_this_round = []
                for filepath, analysis in list(pending.items()):
                    print(f"\n   Testing: {filepath}")
                    validation = self.judge.validate_code(filepath)
                    
                    if validation.get('validated', False):
                        print(f"      ✓ Tests passed!")
                        results[filepath] = {
                            "filepath": filepath,
                            "status": "success",
                            "validated": True,
                            "improved": True,
                            "iterations": iteration
                        }
                        del pending[filepath]
                    else:
                        print(f"      ✗ Tests failed")
                        # Add feedback for next iteration
                        feedback = self.judge.get_failure_feedback(validation)
                        analysis['llm_analysis'] = f"{analysis.get('llm_analysis', '')}\n\nTest failure:\n{feedback}"
                        failed_this_round.append(filepath)
                
                if not failed_this_round:
                    print(f"\n   All files passed!")
                    break
                    
        except QuotaExhaustedError as e:
            print(f"\n{'='*60}")
            print(f"  ERROR: {str(e)}")
            print(f"{'='*60}")
            # Mark remaining as not validated
            for filepath in pending:
                results[filepath] = {
                    "filepath": filepath,
                    "status": "quota_exhausted",
                    "validated": False
                }
            self._cleanup_tests(target_dir)
            return self._build_summary(results, target_dir)
        
        # Mark any remaining files as max_iterations reached
        for filepath in pending:
            results[filepath] = {
                "filepath": filepath,
                "status": "max_iterations",
                "validated": False,
                "iterations": self.max_iterations
            }
        
        self._cleanup_tests(target_dir)
        return self._build_summary(results, target_dir)
    
    def _build_summary(self, results: Dict, target_dir: str) -> Dict:
        """Build final summary from results."""
        result_list = list(results.values())
        total_files = len(result_list)
        successful = sum(1 for r in result_list if r.get('validated', False))
        improved = sum(1 for r in result_list if r.get('improved', False))
        
        print("\n" + "="*60)
        print(f"  Refactoring Complete!")
        print(f"   Files processed: {total_files}")
        print(f"   Successfully validated: {successful}/{total_files}")
        print(f"   Quality improved: {improved}")
        print("="*60)
        
        return {
            "status": "complete",
            "total_files": total_files,
            "successful": successful,
            "improved": improved,
            "results": result_list
        }
    
    def _cleanup_tests(self, target_dir: str):
        """Remove generated tests folder after refactoring."""
        tests_dir = self.tools.working_dir / target_dir / 'tests'
        if tests_dir.exists():
            try:
                shutil.rmtree(tests_dir)
                print(f"\n   Cleaned up: {tests_dir}")
            except Exception as e:
                print(f"\n   Warning: Could not clean up tests: {e}")