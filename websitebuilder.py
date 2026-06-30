import os
import json
import webbrowser
import platform
import subprocess
from flask import Flask, request, jsonify, send_file, send_from_directory
from google import genai
from google.genai import types

system = platform.system()
app = Flask(__name__)

def run_terminal(command):
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True
    )
    return result.stdout

@app.route("/")
def home():
    return send_file("bot.html")

@app.route('/website/<path:filename>')
def serve_website_files(filename):
    return send_from_directory('website', filename)

@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        api_key = data.get("api_key", "")

        if not api_key:
            return jsonify({"success": False, "message": "API key is required"})

        if not prompt:
            return jsonify({"success": False, "message": "Prompt context is empty"})

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                system_instruction=f"""
You are an incremental website builder. 
The user is giving you a sequence of instructions. Build, expand, or adjust the code according to the overall sequence history.

Return ONLY a JSON array containing action objects. Do not wrap your answer in markdown.

Allowed format:
[
    {{
        "action": "create_file",
        "filename": "website/index.html",
        "content": "<html>...entire updated code here...</html>"
    }},
    {{
        "action": "open_web",
        "url": "http://127.0.0.1:5005/website/index.html"
    }}
]

Rules:
1. Return strict JSON data only.
2. If modifying a website, overwrite the exact file inside 'website/' folder with the FULL newly changed code.
3. Use port 5005 for 'open_web' actions.
4. Operating System: {system}
"""
            )
        )

        reply = response.text.strip()
        logs = []

        try:
            jsond = json.loads(reply)
            actions = [jsond] if isinstance(jsond, dict) else jsond

            for item in actions:
                action = item.get("action")

                if action == "create_file":
                    result = create_file(item["filename"], item["content"])
                    logs.append(result)
                    
                elif action == "run_terminal":
                    logs.append(run_terminal(item["command"]))

                elif action == "open_web":
                    webbrowser.open(item["url"])
                    logs.append(f"Opened {item['url']}")

                else:
                    logs.append(f"Unknown action: {action}")

        except json.JSONDecodeError as e:
            return jsonify({
                "success": False,
                "message": f"Invalid JSON returned by model: {e}",
                "raw_response": reply
            })

        return jsonify({
            "success": True,
            "reply": reply,
            "logs": logs
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


def create_file(filename, content):
    try:
        filename = os.path.normpath(filename)
        folder = os.path.dirname(filename)

        if folder:
            os.makedirs(folder, exist_ok=True)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)

        return f"Created {filename}"
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5005, debug=True)