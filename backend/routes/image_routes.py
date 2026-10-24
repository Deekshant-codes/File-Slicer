import os
import tempfile
from pathlib import Path
from flask import Blueprint, request, jsonify
from backend.utils.file_helpers import (
    save_upload_file,
    register_processed_file,
    get_file_info
)
from backend.services.image_service import (
    compress_image,
    resize_image,
    convert_image,
    get_image_info
)

image_bp = Blueprint("image_bp", __name__)

def resolve_single_image(req):
    files = req.files.getlist("files")
    if not files and "file" in req.files:
        files = [req.files.get("file")]

    if files and files[0] and files[0].filename:
        info = save_upload_file(files[0])
        return info["path"], info["original_name"], info

    fid = None
    if req.is_json:
        data = req.get_json(silent=True) or {}
        fid = data.get("file_id")
    else:
        fid = req.form.get("file_id")

    if fid:
        info = get_file_info(fid)
        if info:
            return info["path"], info["original_name"], info

    return None, None, None

@image_bp.route("/image/compress", methods=["POST"])
@image_bp.route("/api/image/compress", methods=["POST"])
def api_compress_image():
    path, orig_name, orig_info = resolve_single_image(request)
    if not path:
        return jsonify({"success": False, "error": "No image file provided."}), 400

    data = request.get_json(silent=True) if request.is_json else request.form
    quality = int(data.get("quality", 75)) if data else 75
    max_w = int(data.get("max_width", 0)) if data and data.get("max_width") else None
    max_h = int(data.get("max_height", 0)) if data and data.get("max_height") else None

    original_size = Path(path).stat().st_size
    ext = Path(orig_name).suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name

        compress_image(path, tmp_path, quality=quality, max_width=max_w, max_height=max_h)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}_compressed{ext}", ext)

        savings_bytes = max(0, original_size - proc_info["size"])
        savings_percent = round((savings_bytes / original_size) * 100, 1) if original_size > 0 else 0
        new_meta = get_image_info(proc_info["path"])

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "original_size": original_size,
            "size": proc_info["size"],
            "savings_percent": savings_percent,
            "meta": new_meta,
            "message": f"Image compressed successfully ({savings_percent}% reduction)."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Image compression failed: {str(e)}"}), 500

@image_bp.route("/image/resize", methods=["POST"])
@image_bp.route("/api/image/resize", methods=["POST"])
def api_resize_image():
    path, orig_name, orig_info = resolve_single_image(request)
    if not path:
        return jsonify({"success": False, "error": "No image file provided."}), 400

    data = request.get_json(silent=True) if request.is_json else request.form
    width = int(data.get("width")) if data and data.get("width") else None
    height = int(data.get("height")) if data and data.get("height") else None
    scale = float(data.get("scale")) if data and data.get("scale") else None
    maintain_aspect = data.get("maintain_aspect", "true") in [True, "true", "True", 1, "1"] if data else True

    if not width and not height and not scale:
        return jsonify({"success": False, "error": "Please provide target dimensions or scale percentage."}), 400

    ext = Path(orig_name).suffix.lower()
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name

        resize_image(path, tmp_path, width=width, height=height, scale_percent=scale, maintain_aspect=maintain_aspect)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}_resized{ext}", ext)
        new_meta = get_image_info(proc_info["path"])

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "meta": new_meta,
            "message": f"Image resized to {new_meta['width']}x{new_meta['height']}px."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Image resizing failed: {str(e)}"}), 500

@image_bp.route("/image/convert", methods=["POST"])
@image_bp.route("/api/image/convert", methods=["POST"])
def api_convert_image():
    path, orig_name, orig_info = resolve_single_image(request)
    if not path:
        return jsonify({"success": False, "error": "No image file provided."}), 400

    data = request.get_json(silent=True) if request.is_json else request.form
    target_format = data.get("format", "png").lower().lstrip(".") if data else "png"
    out_ext = f".{target_format}"

    try:
        with tempfile.NamedTemporaryFile(suffix=out_ext, delete=False) as tmp:
            tmp_path = tmp.name

        convert_image(path, tmp_path, target_format=target_format)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}_converted{out_ext}", out_ext)
        new_meta = get_image_info(proc_info["path"])

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "meta": new_meta,
            "message": f"Image converted to {target_format.upper()} format."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Image conversion failed: {str(e)}"}), 500