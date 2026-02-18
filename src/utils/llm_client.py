"""
LLM client wrapper for Groq API using langchain-groq.
"""

import os
import time
import re
from typing import Optional
from langchain_groq import ChatGroq

class LLMError(Exception):
    """Exception raised when LLM API call fails."""


class QuotaExhaustedError(LLMError):
    """Exception raised when API quota is exhausted."""


class LLMClient:
    """Wrapper for Groq API using LangChain."""
    
    # Class variable to track last request time (shared across instances)
    _last_request_time = 0
    
    # Groq is very fast. We set a small buffer to avoid hammering the API 
    # instantly in a tight loop, but we rely mostly on the 429 retry logic.
    _min_request_interval = 1.0
    
    def __init__(self, model_name: str = "llama-3.3-70b-versatile", max_retries: int = 3, retry_delay: float = 20.0):
        """
        Initialize the LLM client for Groq.
        
        Args:
            model_name: Name of the model (default: llama-3.1-8b-instant)
            max_retries: Maximum number of retries on rate limit errors
            retry_delay: Default delay in seconds between retries (Groq resets quickly)
        """
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        self.model_name = model_name
        
        # Initialize Groq Client
        self.model = ChatGroq(
            model_name=model_name,
            groq_api_key=api_key,
            temperature=0.7,
            max_retries=max_retries
        )
        self.max_retries = max_retries
        self.retry_delay = retry_delay
    
    def _wait_for_rate_limit(self):
        """Wait if needed to respect local pacing."""
        current_time = time.time()
        time_since_last = current_time - LLMClient._last_request_time
        
        if time_since_last < LLMClient._min_request_interval:
            wait_time = LLMClient._min_request_interval - time_since_last
            time.sleep(wait_time)
        
        LLMClient._last_request_time = time.time()
    
    def _extract_retry_delay(self, error_message: str) -> float:
        """Extract retry delay from error message if available."""
        # Regex to find "try again in X seconds" or "retry after X"
        match = re.search(r'try again in (\d+\.?\d*)s', error_message)
        if match:
            return float(match.group(1))
        match = re.search(r'after (\d+\.?\d*)s', error_message)
        if match:
            return float(match.group(1))
        return self.retry_delay
    
    def generate(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Generate a response with automatic retry for Groq Rate Limits.
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Wait for local pacing
                self._wait_for_rate_limit()
                
                # Update temperature for this request
                self.model.temperature = temperature
                
                # Invoke the model
                response = self.model.invoke(prompt)
                return response.content
            
            except Exception as e:
                error_str = str(e).lower()
                last_error = e
                
                # Check for Rate Limit (429)
                if '429' in error_str or 'rate limit' in error_str:
                    # Groq limits usually reset every minute.
                    
                    if attempt < self.max_retries:
                        # Try to find specific wait time in error, otherwise use default
                        delay = self._extract_retry_delay(error_str)
                        
                        # If default is used, apply progressive backoff (20s, 40s, 60s)
                        if delay == self.retry_delay:
                            delay = self.retry_delay * (attempt + 1)
                            
                        print(f"      [Groq] Rate limit hit. Cooling down for {delay:.1f}s... (Attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        raise QuotaExhaustedError("Groq API rate limit exceeded after retries.")
                
                # Handle other API errors immediately
                print(f"      Groq API Error: {str(e)}")
                break
        
        raise LLMError(f"Error generating response: {str(last_error)}")
    