import argparse
import os
import threading
import time
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from logger import logger
from registry import get_npc_engine
from compile_npc import compile_npc_html
from server_openai import openai_blueprint
import on_demand

app = Flask(__name__)
CORS(app)

app.register_blueprint(openai_blueprint)

LAST_ACTIVITY = [time.monotonic()]

@app.before_request
@app.teardown_request
def mark_activity(*_):
    LAST_ACTIVITY[0] = time.monotonic()

@app.route("/<npc_name>/chat/", methods=["GET"])
def chat_html(npc_name):
    try:
        logger.info(f"[server.py][chat_html] Compiling HTML interface for NPC: '{npc_name}'")
        html_content = compile_npc_html(npc_name)
        response = make_response(html_content)
        response.headers['Content-Type'] = 'text/html'
        return response
        
    except Exception as server_crash:
        # exc_info=True automatically captures and formats the full traceback in the log file
        logger.error(
            f"[server.py][chat_html] CRITICAL ERROR compiling HTML for NPC '{npc_name}'. "
            f"Exception: {str(server_crash)}", 
            exc_info=True
        )
        # Return a generic error to the client to avoid leaking internal paths/stack traces
        return jsonify({"error": "Internal Server Error: Failed to compile chat interface."}), 500


@app.route("/api/chat/<npc_name>", methods=["POST"])
def chat(npc_name):
    try:
        logger.info(f"[server.py][chat] Incoming chat request for NPC: '{npc_name}'")
        
        engine = get_npc_engine(npc_name)
        if not engine:
            logger.warning(f"[server.py][chat] NPC profile '{npc_name}' not found on disk.")
            return jsonify({"error": f"NPC profile '{npc_name}' not found on disk"}), 404
        
        data = request.get_json() or {}
        message = data.get("message", "")
        
        if not message:
            logger.warning(f"[server.py][chat] Missing mandatory 'message' field in request.")
            return jsonify({"error": "The field 'message' is mandatory"}), 400
        
        # Log a snippet of the message to avoid flooding logs with massive payloads
        msg_preview = message[:100] + "..." if len(message) > 100 else message
        logger.info(f"[server.py][chat] Processing message: '{msg_preview}'")
        
        result = engine.process_messages(message)
        return jsonify(result)
        
    except Exception as server_crash:
        # exc_info=True ensures the traceback is written to the rotating log file
        logger.error(
            f"[server.py][chat] CRITICAL ERROR processing chat for NPC '{npc_name}'. "
            f"Exception: {str(server_crash)}",
            exc_info=True
        )
        return jsonify({
            "error": "Internal Server Error",
            "details": "An unexpected error occurred while processing the request."
        }), 500


def parse_args():
    parser = argparse.ArgumentParser(description="NPC-Forge server")
    parser.add_argument("--unix", help="Serve on this Unix socket path instead of TCP")
    parser.add_argument(
        "--idle-seconds", type=int, default=0, help="Exit after this many idle seconds (0: never)"
    )
    parser.add_argument("--preload", action="append", default=[], help="NPC to load at start")
    return parser.parse_args()

def socket_inode(path):
    try:
        return os.stat(path).st_ino
    except OSError:
        return None

def exit_when_idle(idle_seconds, path):
    """Stops the server after idle_seconds without requests, removing only its own socket."""
    own_inode = None
    while time.monotonic() - LAST_ACTIVITY[0] <= idle_seconds:
        time.sleep(0.5)
        own_inode = own_inode or socket_inode(path)
    if own_inode is not None and socket_inode(path) == own_inode:
        os.unlink(path)
    logger.info(f"[server.py][exit_when_idle] Idle for {idle_seconds}s, stopping")
    os._exit(0)

def serve_unix(path, idle_seconds, preload):
    if on_demand.is_server_live(path):
        logger.info(f"[server.py][serve_unix] A server is already running on {path}")
        return
    on_demand.prepare_socket_folder(path)
    os.umask(0o077)
    if idle_seconds > 0:
        threading.Thread(target=exit_when_idle, args=(idle_seconds, path), daemon=True).start()
    for npc_name in preload:
        threading.Thread(target=get_npc_engine, args=(npc_name,), daemon=True).start()
    logger.info(f"[server.py][serve_unix] Starting NPC-Forge Flask Server on unix://{path}")
    app.run(host=f"unix://{path}", debug=False)

if __name__ == "__main__":
    args = parse_args()
    if args.unix:
        serve_unix(args.unix, args.idle_seconds, args.preload)
    else:
        logger.info("[server.py][main] Starting NPC-Forge Flask Server on http://127.0.0.1:5000")

        # Note: For production deployment, it is highly recommended to use a WSGI
        # server like Gunicorn or Waitress instead of the built-in Flask development server.
        # Example: gunicorn -w 4 -b 127.0.0.1:5000 server:app
        app.run(host="127.0.0.1", port=5000, debug=False)
