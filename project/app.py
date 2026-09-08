"""
app.py
======
Flask web application. Serves a single upload page where the user provides
a template PDF and an Excel file of consumer data, then generates one bill
PDF per row (via billing_engine + pdf_mapper + pdf_generator) and returns
all of them as a single ZIP download.
"""

import os
import uuid

from flask import Flask, render_template, request, send_file, jsonify

import config
import excel_reader
import billing_engine
import pdf_generator
from utils.file_utils import safe_customer_id, zip_directory, clear_directory

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH_MB * 1024 * 1024

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.OUTPUT_FOLDER, exist_ok=True)


def _allowed_file(filename: str, allowed_extensions: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate", methods=["POST"])
def generate():
    template_file = request.files.get("template_pdf")
    excel_file = request.files.get("excel_file")

    if not template_file or template_file.filename == "":
        return jsonify({"error": "Please upload a template PDF."}), 400
    if not excel_file or excel_file.filename == "":
        return jsonify({"error": "Please upload an Excel file."}), 400

    if not _allowed_file(template_file.filename, config.ALLOWED_PDF_EXTENSIONS):
        return jsonify({"error": "Template must be a .pdf file."}), 400
    if not _allowed_file(excel_file.filename, config.ALLOWED_EXCEL_EXTENSIONS):
        return jsonify({"error": "Consumer data must be a .xlsx or .xls file."}), 400

    job_id = uuid.uuid4().hex[:10]
    job_upload_dir = os.path.join(config.UPLOAD_FOLDER, job_id)
    job_output_dir = os.path.join(config.OUTPUT_FOLDER, job_id)
    os.makedirs(job_upload_dir, exist_ok=True)
    os.makedirs(job_output_dir, exist_ok=True)

    template_path = os.path.join(job_upload_dir, "template.pdf")
    excel_path = os.path.join(job_upload_dir, "data.xlsx")
    template_file.save(template_path)
    excel_file.save(excel_path)

    try:
        consumers = excel_reader.read_consumers(excel_path)
    except Exception as exc:
        return jsonify({"error": f"Could not read Excel file: {exc}"}), 400

    if not consumers:
        return jsonify({"error": "No usable rows found in the Excel file."}), 400
        
    consumption_history = excel_reader.build_consumption_history(consumers)

    generated_files = []
    errors = []
    previous_total = None
    previous_due_date = None
    for index, consumer in enumerate(consumers, start=1):
        try:
            if previous_total is not None:
                consumer["previous_payment"] = previous_total
                consumer["previous_payment_date"] = previous_due_date

            bill = billing_engine.compute_bill(consumer)

            previous_total = bill.total_amount_due
            previous_due_date = consumer.get("due_date")
            # Prefer Customer_ID; fall back to the consumer's name when the
            # sheet doesn't have an ID column (e.g. a contact-list-style
            # sheet with only Name/Address/Email), so the file is still
            # saved under something recognizable instead of just "row_N".
            filename_source = consumer.get("customer_id") or consumer.get("consumer_name")
            customer_id = safe_customer_id(filename_source, index)
            billing_month_tag = str(consumer.get("billing_month") or "").strip().replace(" ", "_").replace("/", "-")
            output_filename = f"{billing_month_tag}.pdf" if billing_month_tag else f"Invoice_{customer_id}_{index}.pdf"  
            output_path = os.path.join(job_output_dir, output_filename)
            pdf_generator.generate_bill_pdf(template_path, consumer, bill, output_path, consumption_history=consumption_history)
            generated_files.append(output_filename)
        except Exception as exc:
            errors.append(f"Row {index} ({consumer.get('consumer_name', 'unknown')}): {exc}")

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
    if errors:
        response.headers["X-Generation-Errors"] = str(len(errors))
    return response


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": f"File too large. Max size is {config.MAX_CONTENT_LENGTH_MB} MB."}), 413


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
