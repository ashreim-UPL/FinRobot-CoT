import os
import json
import logging
from flask import Flask, request, Response, stream_with_context, send_from_directory, jsonify, render_template
from flask_cors import CORS
import subprocess  # For running the orchestrator script
import traceback   # For formatting and logging error tracebacks


app = Flask(__name__)
CORS(app)

APP_DIR = os.path.dirname(os.path.abspath(__file__))
ORCHESTRATOR_SCRIPT = os.path.join(APP_DIR, "annual_report_generator.py")
REPORT_DIR = os.path.join(APP_DIR, "report")
OAI_CONFIG_PATH = os.path.join(APP_DIR, "OAI_CONFIG_LIST.json")

# --- Logging ---
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

def get_available_models():
    """Return only models with non-empty API keys from OAI_CONFIG_LIST.json"""
    try:
        if not os.path.exists(OAI_CONFIG_PATH):
            app.logger.error(f"OAI_CONFIG_LIST.json not found at {OAI_CONFIG_PATH}")
            return {}
        with open(OAI_CONFIG_PATH, 'r') as f:
            config_list = json.load(f)
        # Only include models with a non-empty api_key
        filtered_models = {}
        for idx, entry in enumerate(config_list):
            model = entry.get("model", "").strip()
            api_key = entry.get("api_key", "").strip()
            if model and api_key:
                filtered_models[str(idx)] = model
        return filtered_models
    except Exception as e:
        app.logger.error(f"Error loading models: {str(e)}")
        return {}

def register_api_keys():
    """Register API keys from OAI_CONFIG_LIST.json"""
    try:
        with open(OAI_CONFIG_PATH, 'r') as f:
            config_list = json.load(f)
            
        for entry in config_list:
            if "api_key" in entry:
                os.environ["OPENAI_API_KEY"] = entry["api_key"]
                app.logger.info("Registered OpenAI API key from OAI_CONFIG_LIST")
                break  # Use first valid key
    except Exception as e:
        app.logger.error(f"Error registering API keys: {str(e)}")

def get_report_files():
    """Get list of files in report directory"""
    try:
        if not os.path.exists(REPORT_DIR):
            os.makedirs(REPORT_DIR)
            return []
        
        files = []
        for filename in os.listdir(REPORT_DIR):
            file_path = os.path.join(REPORT_DIR, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append({
                    'name': filename,
                    'size': stat.st_size,
                    'modified': stat.st_mtime,
                    'url': f'/report/{filename}'
                })
        
        files.sort(key=lambda x: x['modified'], reverse=True)
        return files
    except Exception as e:
        app.logger.error(f"Error getting report files: {str(e)}")
        return []

# Initialize on app start
register_api_keys()

# --- Routes ---
@app.route("/available_models")
def available_models():
    """Return available LLM models from OAI_CONFIG_LIST.json"""
    return jsonify(get_available_models())

@app.route("/report_files")
def report_files():
    """Return list of files in report directory"""
    return jsonify(get_report_files())

@app.route("/report/<path:filename>")
def reports(filename):
    """Serve report files"""
    return send_from_directory(REPORT_DIR, filename)

@app.route("/")
def index():
    return render_template("finrobot.html")

@app.route("/stream")
def stream():
    """Stream analysis results via SSE"""
    company = request.args.get("company", "")
    year = request.args.get("year", "2024")
    target_model = request.args.get("target_model", "gpt-4.1-nano-2025-04-14")
    report_type = request.args.get("report_type", "kpi_bullet_insights")
    verbose = request.args.get("verbose", "false").lower() == "true"
    
    if not company:
        return Response("Company parameter required", status=400)
    
    # Check API key
    if "OPENAI_API_KEY" not in os.environ:
        return Response("OpenAI API key not configured", status=500)
    
    if not os.path.exists(ORCHESTRATOR_SCRIPT):
        return Response("Orchestrator script not found", status=500)

    cmd = [
        "python", "-u", ORCHESTRATOR_SCRIPT,
        company,
        "--year", year,
        "--target_model", target_model,
        "--report_type", report_type
    ]
    if verbose:
        cmd.append("--verbose")
    
    # Pass environment with API key
    env = os.environ.copy()
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=APP_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            encoding='utf-8',
            errors="replace", 
            env=env
        )
    except Exception as e:
        error_msg = f"Subprocess failed to start: {str(e)}\n{traceback.format_exc()}"
        app.logger.error(error_msg)
        return Response(error_msg, status=500)
    
    import io
    def generate():
        def format_sse(data: dict) -> str:
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

        for line in iter(process.stdout.readline, ''):
            try:
                line = line.strip()
                if not line:
                    continue
                log_event = json.loads(line)
                yield format_sse(log_event)
            except json.JSONDecodeError:
                yield format_sse({"event_type": "log", "data": {"message": line}})
            except UnicodeDecodeError:
                # unlikely if stream is already utf-8, but safe
                safe_line = line.encode("utf-8", errors="replace").decode()
                yield format_sse({"event_type": "log", "data": {"message": safe_line}})

        stderr_output = process.stderr.read()
        if stderr_output:
            yield format_sse({"event_type": "pipeline_error", "data": {"error": stderr_output}})

        process.wait()
        yield format_sse({"event_type": "pipeline_complete", "data": {"exit_code": process.returncode}})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

if __name__ == "__main__":
    print(ORCHESTRATOR_SCRIPT)
    app.run(debug=True, port=5000, use_reloader=False)

