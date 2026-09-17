"""
app.py
======
Flask web application for Excel-to-PDF bill generation.
Dynamically detects fields, variables, and layout from uploaded Demo PDFs
(using DEMONEWPDF.pdf as the master template), validates Excel column mappings,
reports warnings for unmapped items, and generates 1 PDF per Excel record.
"""

import os
import uuid
import json
import re

from flask import Flask, render_template, request, send_file, jsonify, session, redirect, url_for

import config
import excel_reader
import billing_engine
import pdf_generator
import template_detector
import mapping_engine
import auth_manager
import direct_bill_service
from utils.file_utils import safe_customer_id, zip_directory, build_bill_filename, extract_billing_month_tag

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "billing_portal_auth_secret_session_key_2026")
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH_MB * 1024 * 1024

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)

DEFAULT_MASTER_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DEMONEWPDF.pdf")
if not os.path.exists(DEFAULT_MASTER_TEMPLATE):
    DEFAULT_MASTER_TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.pdf")


def _allowed_file(filename: str, allowed_extensions: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


@app.route("/")
def index():
    if request.args.get("preview") == "1" and request.remote_addr in ("127.0.0.1", "::1"):
        session["authenticated"] = True
        session["user"] = "Admin"
    if not session.get("authenticated"):
        return redirect(url_for("login_page"))
    master_name = os.path.basename(DEFAULT_MASTER_TEMPLATE)
    return render_template("index.html", master_template_name=master_name)


@app.route("/login")
def login_page():
    if session.get("authenticated"):
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    if auth_manager.check_credentials(username, password):
        session["authenticated"] = True
        session["user"] = "Admin"
        return jsonify({"success": True, "message": "Login successful."})
    return jsonify({"success": False, "error": "Invalid username or password. Please try again."}), 401


@app.route("/api/verify-pin", methods=["POST"])
def api_verify_pin():
    data = request.get_json(force=True, silent=True) or {}
    pin = data.get("pin", "")
    if auth_manager.verify_pin(pin):
        return jsonify({"success": True, "message": "PIN verified successfully."})
    return jsonify({"success": False, "error": "Invalid security PIN. Please enter the correct 6-digit PIN."}), 400


@app.route("/api/reset-password", methods=["POST"])
def api_reset_password():
    data = request.get_json(force=True, silent=True) or {}
    pin = data.get("pin", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")
    success, msg = auth_manager.update_password(pin, new_password, confirm_password)
    if success:
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "error": msg}), 400


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/download-template")
@app.route("/api/download-template")
def download_template():
    """
    Downloads an Excel template containing ONLY the header row
    fetched directly from Bimonthly_Bills_2021_to_August_2026.xlsx.
    """
    if not session.get("authenticated"):
        return redirect(url_for("login_page"))

    headers = excel_reader.get_template_headers()
    excel_stream = excel_reader.generate_header_template_excel(headers)

    return send_file(
        excel_stream,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="Consumer_Data_Template.xlsx",
    )


@app.route("/api/generate-direct-bill", methods=["POST"])
def api_generate_direct_bill():
    """
    Direct input billing endpoint. Validates user form data, calculates bill,
    runs pre-flight verification, and generates the PDF.
    """
    if not session.get("authenticated"):
        return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401

    payload = request.get_json(force=True, silent=True) or {}
    try:
        result = direct_bill_service.process_direct_bill(payload, template_path=DEFAULT_MASTER_TEMPLATE)
        return jsonify(result)
    except direct_bill_service.DirectBillValidationError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Failed to generate bill: {exc}"}), 500




@app.route("/inspect_mapping", methods=["POST"])
def inspect_mapping():
    """
    Analyzes an Excel workbook against the uploaded (or default) master Demo PDF template.
    Returns detected template details, mapped columns, and warnings.
    """
    if not session.get("authenticated"):
        return jsonify({"error": "Authentication required. Please log in."}), 401

    excel_file = request.files.get("excel_file")
    template_file = request.files.get("template_pdf")

    if not excel_file or excel_file.filename == "":
        return jsonify({"error": "Please upload an Excel file."}), 400

    if not _allowed_file(excel_file.filename, config.ALLOWED_EXCEL_EXTENSIONS):
        return jsonify({"error": "Consumer data must be a .xlsx or .xls file."}), 400

    job_id = uuid.uuid4().hex[:10]
    temp_dir = os.path.join(config.UPLOAD_FOLDER, f"temp_{job_id}")
    os.makedirs(temp_dir, exist_ok=True)

    excel_path = os.path.join(temp_dir, "data.xlsx")
    excel_file.save(excel_path)

    if template_file and template_file.filename != "" and _allowed_file(template_file.filename, config.ALLOWED_PDF_EXTENSIONS):
        template_path = os.path.join(temp_dir, "template.pdf")
        template_file.save(template_path)
    else:
        template_path = DEFAULT_MASTER_TEMPLATE

    try:
        ts = template_detector.detect_template_structure(template_path)
        if template_file and template_file.filename != "":
            ts.template_name = template_file.filename
        report = mapping_engine.analyze_mapping(excel_path, ts)

        return jsonify({
            "template_name": ts.template_name,
            "layout_type": ts.layout_type,
            "page_count": ts.page_count,
            "total_template_fields": len(ts.fields),
            "total_records": report.total_records,
            "mapped_fields_count": len(report.mapped_fields),
            "mapped_fields": report.mapped_fields,
            "unmapped_excel_columns": report.unmapped_excel_columns,
            "unmapped_pdf_variables": report.unmapped_pdf_variables,
            "warnings": report.warnings,
            "errors": report.errors,
            "is_valid": report.is_valid,
        })
    except Exception as exc:
        return jsonify({"error": f"Error analyzing template and mapping: {exc}"}), 500


@app.route("/preview", methods=["POST"])
def preview():
    """
    Generates a preview PDF for the first consumer record in the uploaded Excel file.
    """
    if not session.get("authenticated"):
        return jsonify({"error": "Authentication required. Please log in."}), 401

    excel_file = request.files.get("excel_file")
    template_file = request.files.get("template_pdf")

    if not excel_file or excel_file.filename == "":
        return jsonify({"error": "Please upload an Excel file."}), 400

    if not _allowed_file(excel_file.filename, config.ALLOWED_EXCEL_EXTENSIONS):
        return jsonify({"error": "Consumer data must be a .xlsx or .xls file."}), 400

    job_id = uuid.uuid4().hex[:10]
    preview_dir = os.path.join(config.OUTPUT_FOLDER, f"preview_{job_id}")
    os.makedirs(preview_dir, exist_ok=True)

    excel_path = os.path.join(preview_dir, "data.xlsx")
    excel_file.save(excel_path)

    if template_file and template_file.filename != "" and _allowed_file(template_file.filename, config.ALLOWED_PDF_EXTENSIONS):
        template_path = os.path.join(preview_dir, "template.pdf")
        template_file.save(template_path)
    else:
        template_path = DEFAULT_MASTER_TEMPLATE

    try:
        consumers = excel_reader.read_consumers(excel_path)
        if not consumers:
            return jsonify({"error": "No usable rows found in the Excel file."}), 400

        consumer = consumers[0]
        bill = billing_engine.compute_bill(consumer)
        history = excel_reader.build_consumption_history(consumers)

        ts = template_detector.detect_template_structure(template_path)
        preview_pdf_path = os.path.join(preview_dir, "Preview_Bill.pdf")

        pdf_generator.generate_bill_pdf(
            template_path, consumer, bill, preview_pdf_path,
            consumption_history=history, template_structure=ts
        )

        return send_file(
            preview_pdf_path,
            mimetype="application/pdf",
            as_attachment=False,
            download_name="Preview_Bill.pdf",
        )
    except Exception as exc:
        return jsonify({"error": f"Failed to generate preview: {exc}"}), 500


@app.route("/api/generate-bill-direct", methods=["POST"])
@app.route("/api/generate-direct-bill", methods=["POST"])
def generate_bill_direct():
    if not session.get("authenticated"):
        return jsonify({"error": "Authentication required. Please log in."}), 401

    payload = request.get_json(silent=True)
    if not payload:
        payload = request.form.to_dict()

    if not payload:
        return jsonify({"error": "No input data provided."}), 400

    try:
        result = direct_bill_service.process_direct_bill(payload, template_path=DEFAULT_MASTER_TEMPLATE)
        return jsonify(result), 200
    except direct_bill_service.DirectBillValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Failed to generate bill: {str(exc)}"}), 500


@app.route("/api/preview-bill/<bill_id>", methods=["GET"])
def preview_direct_bill(bill_id):
    if not session.get("authenticated"):
        return jsonify({"error": "Authentication required."}), 401

    clean_id = re.sub(r"[^\w\-]", "", bill_id)
    bill_dir = os.path.join(config.OUTPUT_FOLDER, f"direct_{clean_id}")
    if not os.path.exists(bill_dir):
        return jsonify({"error": "Bill session not found."}), 404

    # 1. Check if specific filename was requested
    req_filename = request.args.get("filename")
    if req_filename:
        safe_name = os.path.basename(req_filename)
        target_path = os.path.join(bill_dir, safe_name)
        if os.path.exists(target_path):
            return send_file(
                target_path,
                mimetype="application/pdf",
                as_attachment=False,
                download_name=safe_name,
            )

    # 2. Check if index was requested
    pdf_files = sorted([f for f in os.listdir(bill_dir) if f.lower().endswith(".pdf")])
    if not pdf_files:
        return jsonify({"error": "No bill PDF found for this session."}), 404

    idx_str = request.args.get("index")
    target_file = pdf_files[0]
    if idx_str is not None:
        try:
            idx = int(idx_str)
            if 0 <= idx < len(pdf_files):
                target_file = pdf_files[idx]
        except ValueError:
            pass

    file_path = os.path.join(bill_dir, target_file)
    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=False,
        download_name=target_file,
    )


@app.route("/api/download-bill/<bill_id>", methods=["GET"])
def download_direct_bill(bill_id):
    if not session.get("authenticated"):
        return jsonify({"error": "Authentication required."}), 401

    clean_id = re.sub(r"[^\w\-]", "", bill_id)
    bill_dir = os.path.join(config.OUTPUT_FOLDER, f"direct_{clean_id}")
    if not os.path.exists(bill_dir):
        return jsonify({"error": "Bill session not found."}), 404

    # 1. Check if specific filename was requested
    req_filename = request.args.get("filename")
    if req_filename:
        safe_name = os.path.basename(req_filename)
        target_path = os.path.join(bill_dir, safe_name)
        if os.path.exists(target_path):
            return send_file(
                target_path,
                mimetype="application/pdf",
                as_attachment=True,
                download_name=safe_name,
            )

    # 2. Check if index was requested
    pdf_files = sorted([f for f in os.listdir(bill_dir) if f.lower().endswith(".pdf")])
    if not pdf_files:
        return jsonify({"error": "No bill PDF found for this session."}), 404

    idx_str = request.args.get("index")
    target_file = pdf_files[0]
    if idx_str is not None:
        try:
            idx = int(idx_str)
            if 0 <= idx < len(pdf_files):
                target_file = pdf_files[idx]
        except ValueError:
            pass

    file_path = os.path.join(bill_dir, target_file)
    return send_file(
        file_path,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=target_file,
    )


@app.route("/api/download-direct-batch-zip/<batch_id>", methods=["GET"])
def download_direct_batch_zip(batch_id):
    if not session.get("authenticated"):
        return jsonify({"error": "Authentication required."}), 401

    clean_id = re.sub(r"[^\w\-]", "", batch_id)
    zip_path = os.path.join(config.OUTPUT_FOLDER, f"{clean_id}.zip")
    if not os.path.exists(zip_path):
        return jsonify({"error": "Batch ZIP archive not found."}), 404

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"Electricity_Bills_Batch_{clean_id}.zip",
    )


@app.route("/generate", methods=["POST"])
def generate():
    if not session.get("authenticated"):
        return jsonify({"error": "Authentication required. Please log in."}), 401

    template_file = request.files.get("template_pdf")
    excel_file = request.files.get("excel_file")

    if not excel_file or excel_file.filename == "":
        return jsonify({"error": "Please upload an Excel file."}), 400

    if not _allowed_file(excel_file.filename, config.ALLOWED_EXCEL_EXTENSIONS):
        return jsonify({"error": "Consumer data must be a .xlsx or .xls file."}), 400

    job_id = uuid.uuid4().hex[:10]
    job_upload_dir = os.path.join(config.UPLOAD_FOLDER, job_id)
    job_output_dir = os.path.join(config.OUTPUT_FOLDER, job_id)
    os.makedirs(job_upload_dir, exist_ok=True)
    os.makedirs(job_output_dir, exist_ok=True)

    excel_path = os.path.join(job_upload_dir, "data.xlsx")
    excel_file.save(excel_path)

    # Use uploaded template if provided; otherwise use DEMONEWPDF.pdf master template
    if template_file and template_file.filename != "":
        if not _allowed_file(template_file.filename, config.ALLOWED_PDF_EXTENSIONS):
            return jsonify({"error": "Template must be a .pdf file."}), 400
        template_path = os.path.join(job_upload_dir, "template.pdf")
        template_file.save(template_path)
    else:
        template_path = DEFAULT_MASTER_TEMPLATE

    template_display_name = template_file.filename if (template_file and template_file.filename != "") else os.path.basename(DEFAULT_MASTER_TEMPLATE)

    # 1. Detect template structure & fields dynamically
    try:
        template_structure = template_detector.detect_template_structure(template_path)
        template_structure.template_name = template_display_name
    except Exception as exc:
        return jsonify({"error": f"Could not analyze template structure: {exc}"}), 400

    # 2. Check mapping & produce warnings
    try:
        mapping_report = mapping_engine.analyze_mapping(excel_path, template_structure)
    except Exception as exc:
        return jsonify({"error": f"Could not analyze column mappings: {exc}"}), 400

    if not mapping_report.is_valid:
        return jsonify({"error": "Invalid Excel data", "details": mapping_report.errors}), 400

    try:
        consumers = excel_reader.read_consumers(excel_path)
    except Exception as exc:
        return jsonify({"error": f"Could not read Excel file: {exc}"}), 400

    if not consumers:
        return jsonify({"error": "No usable rows found in the Excel file."}), 400

    consumption_history = excel_reader.build_consumption_history(consumers)

    month_counts = {}
    for consumer in consumers:
        month_tag = extract_billing_month_tag(consumer)
        if month_tag:
            month_counts[month_tag] = month_counts.get(month_tag, 0) + 1

    generated_files = []
    errors = []
    previous_total = None
    previous_due_date = None
    used_filenames = set()

    for index, consumer in enumerate(consumers, start=1):
        try:
            if previous_total is not None and consumer.get("previous_payment") is None:
                consumer["previous_payment"] = previous_total
                consumer["previous_payment_date"] = previous_due_date

            bill = billing_engine.compute_bill(consumer)

            previous_total = bill.total_amount_due
            previous_due_date = consumer.get("due_date")

            output_filename = build_bill_filename(
                consumer,
                index,
                total_consumers=len(consumers),
                month_counts=month_counts,
                used_filenames=used_filenames,
            )
            output_path = os.path.join(job_output_dir, output_filename)

            pdf_generator.generate_bill_pdf(
                template_path, consumer, bill, output_path,
                consumption_history=consumption_history,
                template_structure=template_structure,
            )
            generated_files.append(output_filename)
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            errors.append(f"Row {index} ERROR:\n{tb}")

    if not generated_files:
        return jsonify({"error": "No PDFs could be generated.", "details": errors}), 500

    zip_path = os.path.join(config.OUTPUT_FOLDER, f"{job_id}.zip")
    zip_directory(job_output_dir, zip_path)

    response = send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name="Generated_Bills.zip",
    )
    response.headers["X-Generated-Count"] = str(len(generated_files))
    response.headers["X-Template-Name"] = template_structure.template_name
    if mapping_report.warnings:
        response.headers["X-Mapping-Warnings"] = str(len(mapping_report.warnings))
    if errors:
        response.headers["X-Generation-Errors"] = str(len(errors))
    response.headers["Access-Control-Expose-Headers"] = "X-Generated-Count, X-Template-Name, X-Mapping-Warnings, X-Generation-Errors"
    return response


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": f"File too large. Max size is {config.MAX_CONTENT_LENGTH_MB} MB."}), 413


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
