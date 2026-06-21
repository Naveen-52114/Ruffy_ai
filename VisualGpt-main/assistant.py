import os
import json
import re
import urllib.parse
from typing import Dict, Any, List
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class VisualAIAssistant:
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        
        self.SYSTEM_PROMPT = """
You are a visual assistant that generates Mermaid diagrams, charts, and images along with detailed textual explanations.

For every request, you must provide:
1. A clear, helpful TITLE.
2. A DETAILED TEXTUAL EXPLANATION (the 'content' field) that explains the concept or visual in depth.
3. A VISUAL REPRESENTATION (in the 'data' field).

You MUST return ONLY valid JSON.
Your JSON output MUST exactly match this structure:
{
  "type": "diagram", // can be diagram | chart | steps | image
  "title": "A short descriptive title",
  "content": "A detailed, multi-paragraph text explanation of the topic. Use markdown for formatting.",
  "data": {} 
}

Rules for 'data' based on type:
- "chart": {"type": "bar", "labels": ["A", "B"], "datasets": [{"label": "Series", "data": [10, 20]}]}
- "steps": {"stepsArray": ["Step 1", "Step 2", "Step 3"]}
- "image": {"prompt": "Detailed description for image generation"}
- "diagram": {"mermaid": "graph TD; A[Start] --> B[End];"}

Rules for Mermaid diagrams:
* Use simple syntax: graph TD;
* DO NOT use labels inside arrows (no |text|)
* Use ONLY simple boxes [Text] and arrows -->
* Keep labels SHORT and use ONLY alphanumeric characters and spaces.
* DO NOT use parentheses (), braces {}, or brackets [] inside the label text.
* Keep the mermaid code on ONE LINE.
"""

    def _extract_json(self, text: str) -> str:
        """Robustly extract JSON from AI response, handling markdown blocks."""
        # Try to find JSON block in markdown
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
        
        # Try to find any {} block
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            return json_match.group(1)
            
        return text

    def generate_response(self, query: str) -> Dict[str, Any]:
        if not self.api_key:
            return {
                "type": "steps",
                "title": "Config Error",
                "content": "Gemini API key is missing.",
                "data": {"stepsArray": ["Please set GEMINI_API_KEY in your environment."]}
            }
            
        content_text = ""
        error_log = []

        # Strategy 1: Modern 1.5-flash with system_instruction
        try:
            model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=self.SYSTEM_PROMPT
            )
            response = model.generate_content(query)
            content_text = response.text
        except Exception as e:
            error_log.append(f"1.5-flash failed: {str(e)}")

        # Strategy 2: Fallback to gemini-pro (1.0) if 1.5 failed
        if not content_text:
            try:
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content(f"{self.SYSTEM_PROMPT}\n\nUser Query: {query}")
                content_text = response.text
            except Exception as e:
                error_log.append(f"gemini-pro failed: {str(e)}")

        # Strategy 3: Dynamic model selection
        if not content_text:
            try:
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                for m_name in available_models:
                    try:
                        model = genai.GenerativeModel(m_name)
                        response = model.generate_content(f"{self.SYSTEM_PROMPT}\n\nUser Query: {query}")
                        content_text = response.text
                        if content_text: break
                    except:
                        continue
            except Exception as e:
                error_log.append(f"Dynamic fallback failed: {str(e)}")

        if not content_text:
            return {
                "type": "steps",
                "title": "API Error",
                "content": "All attempts to connect to Gemini failed.",
                "data": {"stepsArray": error_log}
            }
            
        try:
            # Robust JSON parsing
            json_str = self._extract_json(content_text)
            result = json.loads(json_str)
            
            # Enforce exactly the required schema
            if "type" not in result or "title" not in result:
                 raise ValueError("Missing required JSON fields")
                
            # Add real image generation URL if the type is image
            if result["type"] == "image" and "data" in result and "prompt" in result["data"]:
                prompt_encoded = urllib.parse.quote(result["data"]["prompt"])
                result["data"]["image_url"] = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=800&height=600&nologo=true"
                
            return result
            
        except Exception as e:
            print("Parsing Error:", str(e))
            return {
                "type": "steps",
                "title": "Response Formatting Error",
                "content": "I received a response but couldn't format it. Here is the raw text:",
                "data": {"stepsArray": [content_text]}
            }
