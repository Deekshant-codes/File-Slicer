import io
from flask import Blueprint, request, jsonify, send_file
from pathlib import Path
from backend.utils.file_helpers import (
    save_upload_file,
    get_file_info,
    delete_file,
    clean_old_files
)
from backend.services.pdf_service import get_pdf_info, generate_pdf_thumbnail
from backend.services.image_service import get_image_info
from backend.services.spreadsheet_service import preview_tabular_file

upload_bp = Blueprint("upload_bp", __name__)

@upload_bp.route("/upload", methods=["POST"])
@upload_bp.route("/api/upload", methods=["POST"])
def upload_files():
    clean_old_files()
    if "files" not in request.files and "file" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400

    uploaded_files = request.files.getlist("files")
    if not uploaded_files or (len(uploaded_files) == 1 and not uploaded_files[0].filename):
        uploaded_files = [request.files.get("file")]

    results = []
    for f in uploaded_files:
        if not f or not f.filename:
            continue
        try:
            info = save_upload_file(f)
            ext = info["ext"]
            meta = {}
            if ext == ".pdf":
                try:
                    meta = get_pdf_info(info["path"])
                except Exception as e:
                    meta = {"error": f"Unable to read PDF: {str(e)}"}
            elif ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"]:
                try:
                    meta = get_image_info(info["path"])
                except Exception as e:
                    meta = {"error": f"Unable to inspect image: {str(e)}"}
            elif ext in [".xlsx", ".xls", ".csv"]:
                try:
                    meta = preview_tabular_file(info["path"])
                except Exception as e:
                    meta = {"error": f"Unable to parse table: {str(e)}"}

            results.append({
                "file_id": info["file_id"],
                "original_name": info["original_name"],
                "size": info["size"],
                "mime_type": info["mime_type"],
                "ext": info["ext"],
                "meta": meta
            })
        except Exception as e:
            return jsonify({"success": False, "error": f"Upload failed for {f.filename}: {str(e)}"}), 500

    return jsonify({
        "success": True,
        "files": results,
        "count": len(results)
    })

@upload_bp.route("/info/<file_id>", methods=["GET"])
@upload_bp.route("/api/info/<file_id>", methods=["GET"])
def file_details(file_id):
    info = get_file_info(file_id)
    if not info:
        return jsonify({"success": False, "error": "File not found or expired"}), 404
    
    meta = {}
    ext = info["ext"]
    if ext == ".pdf":
        try:
            meta = get_pdf_info(info["path"])
        except Exception:
            pass
    elif ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"]:
        try:
            meta = get_image_info(info["path"])
        except Exception:
            pass
    elif ext in [".xlsx", ".xls", ".csv"]:
        try:
            meta = preview_tabular_file(info["path"])
        except Exception:
            pass

    return jsonify({
        "success": True,
        "file_id": info["file_id"],
        "original_name": info["original_name"],
        "size": info["size"],
        "mime_type": info["mime_type"],
        "ext": info["ext"],
        "meta": meta
    })

@upload_bp.route("/preview/<file_id>", methods=["GET"])
@upload_bp.route("/api/preview/<file_id>", methods=["GET"])
def preview_file(file_id):
    info = get_file_info(file_id)
    if not info:
        return jsonify({"success": False, "error": "File not found"}), 404

    page = request.args.get("page", 0, type=int)
    ext = info["ext"]

    if ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".ico"]:
        return send_file(info["path"], mimetype=info["mime_type"])

    if ext == ".pdf":
        thumb_bytes = generate_pdf_thumbnail(info["path"], page_number=page)
        if thumb_bytes:
            return send_file(io.BytesIO(thumb_bytes), mimetype="image/jpeg")

    return send_file(info["path"], mimetype=info["mime_type"])

@upload_bp.route("/download/<file_id>", methods=["GET"])
@upload_bp.route("/api/download/<file_id>", methods=["GET"])
def download_file(file_id):
    info = get_file_info(file_id)
    if not info:
        return jsonify({"success": False, "error": "File expired or not found"}), 404

    custom_name = request.args.get("filename", info["original_name"])
    return send_file(
        info["path"],
        as_attachment=True,
        download_name=custom_name,
        mimetype=info["mime_type"]
    )

@upload_bp.route("/cleanup/<file_id>", methods=["POST", "DELETE"])
@upload_bp.route("/api/cleanup/<file_id>", methods=["POST", "DELETE"])
def cleanup_file(file_id):
    success = delete_file(file_id)
    return jsonify({"success": success})
