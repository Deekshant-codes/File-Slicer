import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, jsonify, request
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

    upload_folder = os.path.join(os.path.dirname(__file__), "uploads")
    processed_folder = os.path.join(os.path.dirname(__file__), "processed")
    os.makedirs(upload_folder, exist_ok=True)
    os.makedirs(processed_folder, exist_ok=True)

    app.config["UPLOAD_FOLDER"] = upload_folder
    app.config["PROCESSED_FOLDER"] = processed_folder

    from backend.routes.upload_routes import upload_bp
    from backend.routes.image_routes import image_bp
    from backend.routes.pdf_routes import pdf_bp

    app.register_blueprint(upload_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(pdf_bp)

    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({"status": "healthy"}), 200

    print("--- REGISTERED FLASK ROUTES ---")
    for rule in app.url_map.iter_rules():
        print(f"{list(rule.methods - {'HEAD', 'OPTIONS'})} {rule.rule}")
    print("--------------------------------")

    @app.errorhandler(413)
    def file_too_large(e):
        return jsonify({"success": False, "error": "File exceeds maximum size limit (100MB)."}), 413

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"success": False, "error": f"API route not found: {request.path}"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"success": False, "error": "An internal server error occurred during processing."}), 500

    return app

if __name__ == "__main__":
    app = create_app()
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", 5000))

    try:
        from waitress import serve
        print(f"Starting File Slicer Flask backend on http://{host}:{port} via Waitress WSGI")
        serve(app, host=host, port=port)
    except ImportError:
        print(f"Starting File Slicer Flask backend on http://{host}:{port} via Flask dev server")
        app.run(host=host, port=port, debug=False)
