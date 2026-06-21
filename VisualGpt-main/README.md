# Portable Visual AI Assistant

This project has been refactored into a portable backend that can be easily integrated into any other project.

## Project Structure
- `assistant.py`: Core logic for Gemini interaction. This can be imported as a class.
- `main.py`: A FastAPI implementation to run the assistant as a standalone service.
- `.env`: Environment variables (set your `GEMINI_API_KEY` here).
- `requirements.txt`: Python dependencies.

## Portable Usage

### Import as a Python Class
You can use the `VisualAIAssistant` class in any Python script:

```python
from assistant import VisualAIAssistant

# Initialize the assistant
ai = VisualAIAssistant(api_key="YOUR_GEMINI_API_KEY")

# Generate a response
query = "How does photosynthesis work visually?"
response = ai.generate_response(query)

# Response is a structured JSON:
# {
#   "type": "diagram", // diagram | chart | steps | image
#   "title": "Title of the visual",
#   "content": "Detailed text explanation",
#   "data": { ... } // data for rendering (e.g. mermaid code)
# }
```

### Run as an API Service
1. Install requirements: `pip install -r requirements.txt`
2. Run server: `python main.py` or `uvicorn main:app --reload`
3. Send POST requests to `http://localhost:8000/ask` with `{ "query": "your question" }`.

## Dependencies
- `google-generativeai`
- `fastapi`
- `uvicorn`
- `python-dotenv`
- `pydantic`
