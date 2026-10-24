import os
import tempfile
from pathlib import Path
from flask import Blueprint, request, jsonify
from backend.utils.file_helpers import (
    save_upload_file,
    register_processed_file,
    get_file_info
)
from backend.services.pdf_service import (
    merge_pdfs,
    split_pdf,
    compress_pdf,
    rotate_pdf,
    images_to_pdf
)
from backend.services.spreadsheet_service import (
    excel_to_csv,
    csv_to_excel
)
from backend.services.ppt_service import (
    pdf_to_ppt,
    ppt_to_pdf
)

pdf_bp = Blueprint("pdf_bp", __name__)

def resolve_file_paths(req, allowed_exts=None):
    file_paths = []
    original_names = []

    files = req.files.getlist("files")
    if not files and "file" in req.files:
        files = [req.files.get("file")]

    for f in files:
        if f and f.filename:
            info = save_upload_file(f)
            file_paths.append(info["path"])
            original_names.append(info["original_name"])

    file_ids = []
    if req.is_json:
        data = req.get_json(silent=True) or {}
        if "file_ids" in data:
            file_ids.extend(data["file_ids"])
        elif "file_id" in data:
            file_ids.append(data["file_id"])
    else:
        if "file_ids" in req.form:
            f_ids = req.form.getlist("file_ids")
            file_ids.extend(f_ids)
        elif "file_id" in req.form:
            file_ids.append(req.form.get("file_id"))

    for fid in file_ids:
        info = get_file_info(fid)
        if info:
            file_paths.append(info["path"])
            original_names.append(info["original_name"])

    return file_paths, original_names

@pdf_bp.route("/pdf/merge", methods=["POST"])
@pdf_bp.route("/api/pdf/merge", methods=["POST"])
def api_merge_pdf():
    paths, names = resolve_file_paths(request)
    if len(paths) < 2:
        return jsonify({"success": False, "error": "Please provide at least 2 PDF files to merge."}), 400

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        merge_pdfs(paths, tmp_path)
        first_name = names[0] if names else "merged.pdf"
        base_name = Path(first_name).stem.replace("_processed", "")
        proc_info = register_processed_file(tmp_path, f"{base_name}_merged.pdf", ".pdf")

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "mime_type": proc_info["mime_type"],
            "message": f"Successfully merged {len(paths)} PDF documents."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Merge failed: {str(e)}"}), 500

@pdf_bp.route("/pdf/split", methods=["POST"])
@pdf_bp.route("/api/pdf/split", methods=["POST"])
def api_split_pdf():
    paths, names = resolve_file_paths(request)
    if not paths:
        return jsonify({"success": False, "error": "No PDF file provided."}), 400

    pdf_path = paths[0]
    orig_name = names[0] if names else "document.pdf"
    
    data = request.get_json(silent=True) if request.is_json else request.form
    page_range = data.get("pages", "all") if data else "all"
    mode = data.get("mode", "extract_range") if data else "extract_range"

    try:
        ext = ".zip" if mode == "split_all_zip" else ".pdf"
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name

        split_pdf(pdf_path, page_range, tmp_path, mode=mode)
        base_name = Path(orig_name).stem
        download_title = f"{base_name}_split{ext}"
        proc_info = register_processed_file(tmp_path, download_title, ext)

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "mime_type": proc_info["mime_type"],
            "message": "PDF split completed successfully."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Split failed: {str(e)}"}), 400

@pdf_bp.route("/pdf/compress", methods=["POST"])
@pdf_bp.route("/api/pdf/compress", methods=["POST"])
def api_compress_pdf():
    paths, names = resolve_file_paths(request)
    if not paths:
        return jsonify({"success": False, "error": "No PDF file provided."}), 400

    pdf_path = paths[0]
    orig_name = names[0] if names else "document.pdf"
    original_size = Path(pdf_path).stat().st_size

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        compress_pdf(pdf_path, tmp_path)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}_compressed.pdf", ".pdf")

        savings_bytes = max(0, original_size - proc_info["size"])
        savings_percent = round((savings_bytes / original_size) * 100, 1) if original_size > 0 else 0

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "original_size": original_size,
            "size": proc_info["size"],
            "savings_percent": savings_percent,
            "message": f"PDF compressed successfully ({savings_percent}% reduction)."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Compression failed: {str(e)}"}), 500

@pdf_bp.route("/pdf/rotate", methods=["POST"])
@pdf_bp.route("/api/pdf/rotate", methods=["POST"])
def api_rotate_pdf():
    paths, names = resolve_file_paths(request)
    if not paths:
        return jsonify({"success": False, "error": "No PDF file provided."}), 400

    pdf_path = paths[0]
    orig_name = names[0] if names else "document.pdf"

    data = request.get_json(silent=True) if request.is_json else request.form
    angle = int(data.get("angle", 90)) if data else 90
    pages = data.get("pages", "all") if data else "all"

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        rotate_pdf(pdf_path, pages, angle, tmp_path)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}_rotated.pdf", ".pdf")

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "message": f"PDF rotated by {angle}° successfully."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Rotation failed: {str(e)}"}), 400

@pdf_bp.route("/pdf/images-to-pdf", methods=["POST"])
@pdf_bp.route("/api/pdf/images-to-pdf", methods=["POST"])
def api_images_to_pdf():
    paths, names = resolve_file_paths(request)
    if not paths:
        return jsonify({"success": False, "error": "No image files provided."}), 400

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        images_to_pdf(paths, tmp_path)
        first_name = names[0] if names else "converted.pdf"
        base_name = Path(first_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}_images.pdf", ".pdf")

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "message": f"Converted {len(paths)} images into a single PDF document."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Image to PDF conversion failed: {str(e)}"}), 500

@pdf_bp.route("/pdf/excel-to-csv", methods=["POST"])
@pdf_bp.route("/api/pdf/excel-to-csv", methods=["POST"])
def api_excel_to_csv():
    paths, names = resolve_file_paths(request)
    if not paths:
        return jsonify({"success": False, "error": "No Excel file provided."}), 400

    excel_path = paths[0]
    orig_name = names[0] if names else "spreadsheet.xlsx"

    data = request.get_json(silent=True) if request.is_json else request.form
    sheet_name = data.get("sheet_name") if data else None

    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name

        _, used_sheet = excel_to_csv(excel_path, tmp_path, sheet_name=sheet_name)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}_{used_sheet}.csv", ".csv")

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "sheet_used": used_sheet,
            "size": proc_info["size"],
            "message": f"Excel converted to CSV (Sheet: '{used_sheet}')."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Excel to CSV conversion failed: {str(e)}"}), 500

@pdf_bp.route("/pdf/csv-to-excel", methods=["POST"])
@pdf_bp.route("/api/pdf/csv-to-excel", methods=["POST"])
def api_csv_to_excel():
    paths, names = resolve_file_paths(request)
    if not paths:
        return jsonify({"success": False, "error": "No CSV file provided."}), 400

    csv_path = paths[0]
    orig_name = names[0] if names else "data.csv"

    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        csv_to_excel(csv_path, tmp_path)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}_converted.xlsx", ".xlsx")

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "message": "CSV converted to Excel workbook successfully."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"CSV to Excel conversion failed: {str(e)}"}), 500

@pdf_bp.route("/pdf/to-ppt", methods=["POST"])
@pdf_bp.route("/api/pdf/to-ppt", methods=["POST"])
def api_pdf_to_ppt():
    paths, names = resolve_file_paths(request)
    if not paths:
        return jsonify({"success": False, "error": "No PDF file provided."}), 400

    pdf_path = paths[0]
    orig_name = names[0] if names else "presentation.pdf"

    try:
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as tmp:
            tmp_path = tmp.name

        pdf_to_ppt(pdf_path, tmp_path)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}.pptx", ".pptx")

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "message": "PDF converted to PowerPoint presentation successfully."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"PDF to PowerPoint conversion failed: {str(e)}"}), 500

@pdf_bp.route("/pdf/ppt-to-pdf", methods=["POST"])
@pdf_bp.route("/api/pdf/ppt-to-pdf", methods=["POST"])
def api_ppt_to_pdf():
    paths, names = resolve_file_paths(request)
    if not paths:
        return jsonify({"success": False, "error": "No PowerPoint presentation provided."}), 400

    ppt_path = paths[0]
    orig_name = names[0] if names else "presentation.pptx"

    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name

        ppt_to_pdf(ppt_path, tmp_path)
        base_name = Path(orig_name).stem
        proc_info = register_processed_file(tmp_path, f"{base_name}.pdf", ".pdf")

        return jsonify({
            "success": True,
            "file_id": proc_info["file_id"],
            "download_name": proc_info["original_name"],
            "size": proc_info["size"],
            "message": "PowerPoint presentation converted to PDF successfully."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"PowerPoint to PDF conversion failed: {str(e)}"}), 500