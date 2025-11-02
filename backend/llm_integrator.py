import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables FIRST
load_dotenv()

# Get key from environment
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    # Configure the module only if the key exists
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("Warning: GOOGLE_API_KEY not found. LLM suggestions will be disabled.")

# Define the prompt for the model
REFACTOR_PROMPT = """
You are an expert pair programmer. Your job is to analyze a piece of code and provide a safe, refactored version of it.
The user will provide a function that has been flagged for high cyclomatic complexity.

Please provide a refactored version of the code that improves readability and maintainability, and reduces complexity.

Here is the code:
---
{code_content}
---

Your suggestion:
"""

def get_llm_refactor_suggestion(code_content: str) -> str:
    """
    Sends code content to the generative AI model and gets a refactoring suggestion.
    """
    if not GOOGLE_API_KEY:
        return "LLM integration is not configured. (Missing GOOGLE_API_KEY)"

    try:
        # --- THIS IS THE FIX ---
        # Changed 'gemini-pro' to the newer 'gemini-1.5-flash'
        model = genai.GenerativeModel('gemini-1.5-flash')
        # --- END FIX ---
        
        prompt = REFACTOR_PROMPT.format(code_content=code_content)
        
        response = model.generate_content(prompt)
        
        # Return the refactored code snippet
        return response.text
    
    except Exception as e:
        print(f"Error communicating with Generative AI model: {e}")
        return f"Could not generate suggestion: {str(e)}"