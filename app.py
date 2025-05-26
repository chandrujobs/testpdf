import os
import io
import json
import logging
from datetime import datetime
from zipfile import ZipFile
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Import your custom processor
from custom import redact_pdf_bytes, validate_pdf_bytes

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'pdf'}

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Flask app setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_pdf_file(file):
    """Validate uploaded PDF file"""
    if not file or file.filename == '':
        return False, "No file selected"
    
    if not allowed_file(file.filename):
        return False, "Only PDF files are allowed"
    
    # Read file content for validation
    file_content = file.read()
    file.seek(0)  # Reset file pointer
    
    if len(file_content) == 0:
        return False, "File is empty"
    
    if not validate_pdf_bytes(file_content):
        return False, "Invalid PDF file"
    
    return True, "Valid"

def generate_output_filename(original_filename, suffix="_redacted"):
    """Generate output filename with timestamp"""
    name, ext = os.path.splitext(original_filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{name}{suffix}_{timestamp}{ext}"

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(e):
    return jsonify({"error": "File too large. Maximum size is 50MB."}), 413

@app.errorhandler(Exception)
def handle_general_error(e):
    logger.error(f"Unexpected error: {e}")
    return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

# ─── Static Files ─────────────────────────────────────────────────────────

@app.route('/favicon.ico')
def favicon():
    return '', 204  # No content

# ─── Main Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/hc')
def hc():
    return render_template('hc.html')

@app.route('/faqs')
def faqs():
    return render_template('faqs.html')

@app.route('/about')
def about():
    return render_template('about.html')

# ─── Custom PDF Redaction ─────────────────────────────────────────────────

@app.route('/custom', methods=['GET', 'POST'])
def custom():
    if request.method == 'POST':
        try:
            files = request.files.getlist('pdfs')
            if not files or all(f.filename == '' for f in files):
                return jsonify({"error": "No files uploaded"}), 400

            # Validate files
            for file in files:
                is_valid, message = validate_pdf_file(file)
                if not is_valid:
                    return jsonify({"error": f"File '{file.filename}': {message}"}), 400

            terms_map = json.loads(request.form.get('custom_terms', '{}'))
            
            # FIXED: Correct parameter checking for checkboxes
            redact_logos = request.form.get('redact_logos') == 'on'
            redact_numbers = request.form.get('redact_numbers') == 'on'
            
            logger.info(f"Processing with redact_logos={redact_logos}, redact_numbers={redact_numbers}")
            logger.info(f"Form data received: {dict(request.form)}")
            
            return process_custom_files(files, terms_map, redact_logos, redact_numbers)

        except json.JSONDecodeError:
            return jsonify({"error": "Invalid terms format"}), 400
        except Exception as e:
            logger.error(f"Custom processing error: {e}")
            return jsonify({"error": "Processing failed. Please try again."}), 500

    return render_template('custom.html')

def process_custom_files(files, terms_map, redact_logos, redact_numbers=False):
    """Process custom redaction files with proper parameter handling"""
    outputs = []
    
    for file in files:
        try:
            filename = secure_filename(file.filename)
            terms = terms_map.get(filename, [])
            
            file_content = file.read()
            
            logger.info(f"Processing {filename} with {len(terms)} terms, redact_logos={redact_logos}, redact_numbers={redact_numbers}")
            
            # Use enhanced redact_pdf_bytes function with proper boolean values
            redacted_bytes = redact_pdf_bytes(
                pdf_bytes=file_content, 
                terms=terms, 
                redact_logos=redact_logos,
                redact_numbers=redact_numbers
            )
            outputs.append((generate_output_filename(filename), redacted_bytes))
            
        except Exception as e:
            logger.error(f"Error processing {file.filename}: {e}")
            continue
    
    if not outputs:
        return jsonify({"error": "No files were successfully processed"}), 500
    
    # Single file - return directly
    if len(outputs) == 1:
        filename, content = outputs[0]
        return send_file(
            io.BytesIO(content),
            as_attachment=True,
            download_name=filename,
            mimetype='application/pdf'
        )
    
    # Multiple files - create ZIP
    memory_file = io.BytesIO()
    with ZipFile(memory_file, 'w') as zipf:
        for filename, content in outputs:
            zipf.writestr(filename, content)
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        as_attachment=True,
        download_name=f'redacted_custom_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
        mimetype='application/zip'
    )

# ─── AJAX Preview ─────────────────────────────────────────────────────────

@app.route('/preview_redacted', methods=['POST'])
def preview_redacted():
    """AJAX endpoint for previewing redacted PDF with proper parameter handling"""
    try:
        pdf_file = request.files.get('pdf')
        if not pdf_file:
            return jsonify({"error": "No file uploaded"}), 400

        is_valid, message = validate_pdf_file(pdf_file)
        if not is_valid:
            return jsonify({"error": message}), 400

        filename = secure_filename(pdf_file.filename)
        
        # Parse custom terms
        try:
            raw_terms = request.form.get('custom_terms', '[]')
            data = json.loads(raw_terms)
            
            if isinstance(data, dict):
                terms = data.get(filename, [])
            elif isinstance(data, list):
                terms = data
            else:
                terms = []
        except json.JSONDecodeError:
            terms = []

        # FIXED: Correct parameter checking for preview - match the frontend parameter names
        redact_logos = request.form.get('remove_logos') == 'true'
        redact_numbers = request.form.get('redact_numbers') == 'true'
        
        logger.info(f"Preview for {filename} with {len(terms)} terms")
        logger.info(f"Preview with redact_logos={redact_logos}, redact_numbers={redact_numbers}")
        logger.info(f"Preview form data: {dict(request.form)}")
        
        file_content = pdf_file.read()
        
        # Use enhanced redact_pdf_bytes function
        redacted_bytes = redact_pdf_bytes(
            pdf_bytes=file_content, 
            terms=terms, 
            redact_logos=redact_logos,
            redact_numbers=redact_numbers
        )
        
        return send_file(
            io.BytesIO(redacted_bytes),
            mimetype='application/pdf'
        )

    except Exception as e:
        logger.error(f"Preview error: {e}")
        return jsonify({"error": "Preview generation failed"}), 500

# ─── Debug Endpoint ─────────────────────────────────────────────────────────

@app.route('/debug_logos', methods=['POST'])
def debug_logos():
    """Debug endpoint to see what the logo detection is finding"""
    try:
        pdf_file = request.files.get('pdf')
        if not pdf_file:
            return jsonify({"error": "No file uploaded"}), 400

        is_valid, message = validate_pdf_file(pdf_file)
        if not is_valid:
            return jsonify({"error": message}), 400

        file_content = pdf_file.read()
        
        # Import required modules
        import fitz
        from custom import find_logos_simple
        
        doc = fitz.open(stream=file_content, filetype="pdf")
        page = doc[0]  # First page
        
        # Get all text elements in header area for analysis
        text_dict = page.get_text("dict")
        page_rect = page.rect
        header_elements = []
        
        for block in text_dict.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        bbox = fitz.Rect(span["bbox"])
                        
                        # Only elements in top 40% of page
                        if text and bbox.y0 <= page_rect.height * 0.4:
                            header_elements.append({
                                "text": text,
                                "bbox": [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
                                "color": span.get("color", 0),
                                "size": span.get("size", 12),
                                "font": span.get("font", ""),
                                "flags": span.get("flags", 0),
                                "position_percent": {
                                    "y": (bbox.y0 / page_rect.height) * 100,
                                    "x": (bbox.x0 / page_rect.width) * 100
                                }
                            })
        
        # Run logo detection
        logo_boxes = find_logos_simple(page)
        
        doc.close()
        
        return jsonify({
            "header_elements": header_elements,
            "detected_logos": [[box.x0, box.y0, box.x1, box.y1] for box in logo_boxes],
            "page_dimensions": [page_rect.width, page_rect.height]
        })

    except Exception as e:
        logger.error(f"Debug error: {e}")
        return jsonify({"error": str(e)}), 500

# ─── Health Check ─────────────────────────────────────────────────────────

@app.route('/health')
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "upload_folder": app.config['UPLOAD_FOLDER']
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
