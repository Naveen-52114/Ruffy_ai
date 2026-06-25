import os
import json
import re
import urllib.parse
import requests
from flask import Flask, render_template, request, jsonify, send_from_directory
import google.generativeai as genai

app = Flask(__name__)

# Hardcoded API key provided by user

API_KEY = "AIzaSyCDCqnN0QYlXw54dKCiY13sx4NgSJgMMuk"
genai.configure(api_key=API_KEY)

FIREBASE_URL = "https://kecnotes-13af0-default-rtdb.asia-southeast1.firebasedatabase.app"

def sanitize_user_id(user_id):
    if not user_id: return "anonymous"
    return re.sub(r'[.#$\[\]]', '_', str(user_id))

def get_history(user_id="anonymous", chat_id="default"):
    safe_id = sanitize_user_id(user_id)
    safe_chat_id = sanitize_user_id(chat_id)
    try:
        r = requests.get(f"{FIREBASE_URL}/chat_history/{safe_id}/{safe_chat_id}.json")
        data = r.json()
        if data and isinstance(data, list):
            formatted_history = []
            for item in data:
                parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in item.get("parts", [])]
                formatted_history.append({
                    "role": item.get("role"),
                    "parts": parts
                })
            return formatted_history
    except Exception as e:
        print(f"Error loading history from Firebase: {e}")
    return []

def save_history(history, user_id="anonymous", chat_id="default"):
    safe_id = sanitize_user_id(user_id)
    safe_chat_id = sanitize_user_id(chat_id)
    serialized = []
    for content in history:
        parts = []
        for part in content.parts:
            if hasattr(part, 'text'):
                parts.append({"text": part.text})
        serialized.append({
            "role": content.role,
            "parts": parts
        })
    try:
        requests.put(f"{FIREBASE_URL}/chat_history/{safe_id}/{safe_chat_id}.json", json=serialized)
    except Exception as e:
        print(f"Error saving to firebase: {e}")

# Use gemini-2.5-flash
model = genai.GenerativeModel('gemini-2.5-flash')

# ─── ImageGen (VisualAI) Setup ─────────────────────────────────────────────────
IMAGEGEN_API_KEY = "AIzaSyBKvO6u3UFt55zKR1z6roWqQgRu56KybHg"

IMAGEGEN_SYSTEM_PROMPT = """
You are a visual assistant that generates Mermaid diagrams, charts, and images along with detailed textual explanations.

For every request, you must provide:
1. A clear, helpful TITLE.
2. A DETAILED TEXTUAL EXPLANATION (the 'content' field) that explains the concept or visual in depth.
3. A VISUAL REPRESENTATION (in the 'data' field).

You MUST return ONLY valid JSON.
Your JSON output MUST exactly match this structure:
{
  "type": "diagram",
  "title": "A short descriptive title",
  "content": "A detailed, multi-paragraph text explanation. Use markdown for formatting.",
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

def _extract_json(text):
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    json_match = re.search(r'(\{.*\})', text, re.DOTALL)
    if json_match:
        return json_match.group(1)
    return text

def generate_imagegen_response(query):
    content_text = ""
    error_log = []
    
    # Configure with ImageGen API key
    genai.configure(api_key=IMAGEGEN_API_KEY)
    
    # Strategy 1: gemini-2.5-flash with system_instruction
    try:
        ig_model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            system_instruction=IMAGEGEN_SYSTEM_PROMPT
        )
        response = ig_model.generate_content(query)
        content_text = response.text
    except Exception as e:
        error_log.append(f"gemini-2.5-flash failed: {str(e)}")

    # Strategy 2: gemini-1.5-flash fallback
    if not content_text:
        try:
            ig_model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                system_instruction=IMAGEGEN_SYSTEM_PROMPT
            )
            response = ig_model.generate_content(query)
            content_text = response.text
        except Exception as e:
            error_log.append(f"gemini-1.5-flash failed: {str(e)}")

    # Strategy 3: gemini-pro fallback (no system_instruction)
    if not content_text:
        try:
            ig_model = genai.GenerativeModel('gemini-pro')
            response = ig_model.generate_content(f"{IMAGEGEN_SYSTEM_PROMPT}\n\nUser Query: {query}")
            content_text = response.text
        except Exception as e:
            error_log.append(f"gemini-pro failed: {str(e)}")
    
    # Restore main API key
    genai.configure(api_key=API_KEY)

    if not content_text:
        return {
            "type": "steps",
            "title": "API Error",
            "content": "All attempts to connect to Gemini for ImageGen failed.",
            "data": {"stepsArray": error_log}
        }

    try:
        json_str = _extract_json(content_text)
        result = json.loads(json_str)
        if "type" not in result or "title" not in result:
            raise ValueError("Missing required JSON fields")
        if result["type"] == "image" and "data" in result and "prompt" in result["data"]:
            prompt_encoded = urllib.parse.quote(result["data"]["prompt"])
            result["data"]["image_url"] = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=800&height=600&nologo=true"
        return result
    except Exception as e:
        return {
            "type": "steps",
            "title": "Response Formatting Error",
            "content": "Received a response but couldn't format it. Here is the raw text:",
            "data": {"stepsArray": [content_text]}
        }
# ──────────────────────────────────────────────────────────────────────────────

# Load predefined static visual content
def load_all_visual_data():
    data = []
    try:
        for filename in os.listdir("."):
            if filename.endswith(".json") and filename not in ["package-lock.json", "package.json"]:
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        content = json.load(f)
                        if "keyword" in content or "keywords" in content:
                            data.append(content)
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
    except Exception as e:
        print(f"Error reading root directory: {e}")
    return data

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/<path:filename>")
def serve_root_file(filename):
    # Serve any file from the project root (logo, intro video, etc.)
    return send_from_directory(".", filename)

@app.route("/videos/<path:filename>")
def serve_video(filename):
    # Backward compatibility for /videos/ path
    return send_from_directory(".", filename)

@app.route("/api/history", methods=["GET", "DELETE"])
def api_history():
    user_id = request.args.get("user_id", "anonymous")
    chat_id = request.args.get("chat_id")
    safe_id = sanitize_user_id(user_id)
    
    if request.method == "DELETE":
        try:
            delete_all = request.args.get("delete_all")
            if delete_all == "true":
                requests.delete(f"{FIREBASE_URL}/chat_history/{safe_id}.json")
            elif chat_id:
                safe_chat_id = sanitize_user_id(chat_id)
                requests.delete(f"{FIREBASE_URL}/chat_history/{safe_id}/{safe_chat_id}.json")
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    if not chat_id:
        # Get a list of all chat sessions for the sidebar
        try:
            r = requests.get(f"{FIREBASE_URL}/chat_history/{safe_id}.json")
            all_chats_data = r.json()
            summaries = []
            if all_chats_data and isinstance(all_chats_data, dict):
                # Sort chats by key (which are timestamps from frontend)
                for c_id in sorted(all_chats_data.keys(), reverse=True):
                    chat_messages = all_chats_data[c_id]
                    if isinstance(chat_messages, list) and len(chat_messages) > 0:
                        # Find the first user message for the title
                        first_user_msg = next((m for m in chat_messages if m.get("role") == "user"), None)
                        title = "New Chat"
                        if first_user_msg:
                            parts = first_user_msg.get("parts", [])
                            if parts:
                                title = parts[0].get("text", "New Chat") if isinstance(parts[0], dict) else str(parts[0])
                        
                        summaries.append({
                            "chat_id": c_id,
                            "title": title[:40] + ("..." if len(title) > 40 else "")
                        })
            return jsonify({"chats": summaries})
        except:
            return jsonify({"chats": []})
            
    return jsonify({"history": get_history(user_id, chat_id)})

@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "").strip()
    visual_mode = data.get("visual_mode", False)
    user_id = data.get("user_id", "anonymous")
    chat_id = data.get("chat_id", "default")
    
    if not user_message:
        return jsonify({"error": "Empty message"}), 400
        
    # Visual Mode Logic: Serve specific step-by-step components if matches
    if visual_mode:
        visual_data_list = load_all_visual_data()  # Reload fresh every time
        for v_data in visual_data_list:
            keywords = []
            if "keywords" in v_data and isinstance(v_data["keywords"], list):
                keywords.extend([str(k).lower() for k in v_data["keywords"]])
            if "keyword" in v_data and isinstance(v_data["keyword"], str):
                keywords.append(v_data["keyword"].lower())
            
            matched = False
            user_msg_lower = user_message.lower()
            
            for kw in keywords:
                if kw in user_msg_lower:
                    matched = True
                    break
            
            # backward compatibility for old "convolution" hardcoded check on CNN
            if "convolution" in user_msg_lower and (v_data.get("title", "") == "Convolutional Neural Network Architecture" or v_data.get("keyword") == "cnn architecture"):
                matched = True

            if matched:
                title = v_data.get("title") or v_data.get("topic") or "Visual Content"
                
                desc_obj = v_data.get("description", "")
                if isinstance(desc_obj, dict):
                    description = desc_obj.get("detailed") or desc_obj.get("short") or ""
                else:
                    description = desc_obj or ""
                
                # --- Deep-extract ALL useful content from the entire JSON ---
                skip_keys = {"keywords", "keyword", "title", "topic", "description", "steps"}
                
                def extract_all(obj, depth=0):
                    """Recursively extract all content from nested dicts/lists."""
                    parts = []
                    if isinstance(obj, dict):
                        for key, val in obj.items():
                            if key in skip_keys and depth == 0:
                                continue
                            nice_key = key.replace("_", " ").title()
                            if isinstance(val, str):
                                parts.append(f"**{nice_key}:** {val}")
                            elif isinstance(val, list):
                                items = []
                                for item in val:
                                    if isinstance(item, str):
                                        items.append(f"- {item}")
                                    elif isinstance(item, dict):
                                        sub = extract_all(item, depth + 1)
                                        if sub:
                                            items.append(sub)
                                if items:
                                    parts.append(f"**{nice_key}:**\n" + "\n".join(items))
                            elif isinstance(val, dict):
                                sub = extract_all(val, depth + 1)
                                if sub:
                                    parts.append(f"### {nice_key}\n{sub}")
                    elif isinstance(obj, list):
                        for item in obj:
                            sub = extract_all(item, depth + 1)
                            if sub:
                                parts.append(sub)
                    return "\n\n".join(parts)
                
                extra_content = extract_all(v_data)
                if extra_content:
                    description += "\n\n" + extra_content
                
                # Collect steps if present
                steps = v_data.get("steps", [])
                
                # Find videos from anywhere in the JSON
                main_video = None
                if isinstance(desc_obj, dict) and "video" in desc_obj:
                    main_video = desc_obj["video"]
                
                # Also scan for video fields in nested objects if no main_video or no steps
                def find_videos(obj, found=None):
                    if found is None:
                        found = []
                    if isinstance(obj, dict):
                        if "video" in obj and isinstance(obj["video"], str):
                            found.append(obj["video"])
                        for val in obj.values():
                            find_videos(val, found)
                    elif isinstance(obj, list):
                        for item in obj:
                            find_videos(item, found)
                    return found
                
                # If no steps, auto-create steps from nested sections that have videos
                if not steps:
                    all_videos = find_videos(v_data)
                    step_num = 1
                    for key, val in v_data.items():
                        if key in skip_keys or not isinstance(val, dict):
                            continue
                        section_title = key.replace("_", " ").title()
                        section_desc = val.get("description") or val.get("definition") or val.get("summary") or ""
                        section_video = val.get("video")
                        if isinstance(val.get("formula"), dict):
                            section_desc += f"\n\n**Formula:** {val['formula'].get('expression', '')}"
                            params = val['formula'].get('parameters', {})
                            if params:
                                section_desc += "\n" + "\n".join(f"- {k} = {v}" for k, v in params.items() if k != 'video')
                            if not section_video and 'video' in params:
                                section_video = params['video']
                        elif isinstance(val.get("formula"), str):
                            section_desc += f"\n\n**Formula:** {val['formula']}"
                        steps.append({
                            "step": step_num,
                            "title": section_title,
                            "explanation": section_desc,
                            "video": section_video
                        })
                        step_num += 1
                
                # Only set main_video if steps don't already have videos
                step_has_video = any(s.get("video") for s in steps)
                if not main_video and not step_has_video:
                    all_vids = find_videos(v_data)
                    if all_vids:
                        main_video = all_vids[0]
                
                return jsonify({
                    "type": "visual",
                    "title": title,
                    "description": description,
                    "video": main_video,
                    "steps": steps
                })
            
    # Fallback to LLM
    try:
        # Start a per-request session using this user's history
        history = get_history(user_id, chat_id)
        chat_session = model.start_chat(history=history)
        
        response = chat_session.send_message(user_message)
        # Save history after receiving a response
        save_history(chat_session.history, user_id, chat_id)
        return jsonify({
            "type": "text",
            "response": response.text
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/imagegen", methods=["POST"])
def imagegen():
    data = request.json
    query = data.get("message", "").strip()
    if not query:
        return jsonify({"error": "Empty message"}), 400
    result = generate_imagegen_response(query)
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
