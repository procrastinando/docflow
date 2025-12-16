import os
import threading
import uuid
import time
import shutil
import zipfile
import json
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from unstructured.partition.pdf import partition_pdf

app = Flask(__name__)

# CONFIGURATION
# We use absolute paths to ensure they work regardless of where the script runs
BASE_DIR = '/app/data' 
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, 'processed')
HISTORY_FILE = os.path.join(BASE_DIR, 'history.json')
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'doc'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

# --- CRITICAL FIX: Ensure directories exist at runtime ---
# This fixes the issue where mounting a Docker volume hides the folders created during build
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Global Job Store
jobs = {}

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(entry):
    history = load_history()
    history.insert(0, entry) # Prepend
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- CORE PROCESSING LOGIC ---
def process_file_thread(job_id, filepath, original_filename, options):
    try:
        jobs[job_id]['status'] = 'Initializing...'
        jobs[job_id]['progress'] = 10
        
        # Create a temp dir for this job
        job_dir = os.path.join(app.config['PROCESSED_FOLDER'], job_id)
        os.makedirs(job_dir, exist_ok=True)
        
        # Temp dir for raw extracted images
        extraction_dir = os.path.join(job_dir, "raw_extracted")
        os.makedirs(extraction_dir, exist_ok=True)

        # 1. Parsing Strategy
        strategy = options.get('strategy', 'hi_res')
        model = options.get('model', 'yolox')
        infer_tables = options.get('infer_tables', True)
        extract_images = options.get('extract_images', True)
        
        jobs[job_id]['status'] = f'Partitioning PDF ({strategy})... this may take time'
        
        # 2. RUN UNSTRUCTURED
        # Note: We wrap this in a try/except for the specific partition call
        try:
            elements = partition_pdf(
                filename=filepath,
                strategy=strategy,
                model_name=model if strategy == 'hi_res' else None,
                infer_table_structure=infer_tables,
                extract_images_in_pdf=extract_images,
                extract_image_block_types=["Image", "Table"] if extract_images else [],
                extract_image_block_output_dir=extraction_dir,
            )
        except Exception as e:
            raise RuntimeError(f"Unstructured Partition Failed: {str(e)}")

        jobs[job_id]['progress'] = 60
        jobs[job_id]['status'] = 'Formatting Output...'

        # 3. Format Output
        base_name = os.path.splitext(original_filename)[0]
        # Sanitize base_name for file systems
        base_name = secure_filename(base_name)
        
        md_content = f"# {base_name}\n\n"
        
        for el in elements:
            el_type = el.category
            el_text = str(el)
            
            if el_type == "Title":
                md_content += f"## {el_text}\n\n"
            elif el_type == "Table":
                md_content += f"\n**[Table Data]**\n{el.metadata.text_as_html if hasattr(el.metadata, 'text_as_html') and el.metadata.text_as_html else el_text}\n\n"
            elif el_type == "Image":
                md_content += f"\n![Figure]({base_name}_images_placeholder.jpg)\n*Image Text: {el_text}*\n\n"
            else:
                md_content += f"{el_text}\n\n"

        # 4. Write Markdown
        md_path = os.path.join(job_dir, f"{base_name}.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        jobs[job_id]['progress'] = 80
        jobs[job_id]['status'] = 'Flattening & Compressing...'

        # 5. Flatten & Rename Assets
        if os.path.exists(extraction_dir):
            for asset in os.listdir(extraction_dir):
                old_path = os.path.join(extraction_dir, asset)
                
                # Determine type
                prefix = "asset"
                if "figure" in asset.lower() or "image" in asset.lower():
                    prefix = "images"
                elif "table" in asset.lower():
                    prefix = "tables"
                
                # New Name: papername_images_figure-1.jpg
                new_name = f"{base_name}_{prefix}_{asset}"
                new_path = os.path.join(job_dir, new_name)
                
                shutil.move(old_path, new_path)

        # Remove temp raw folder
        if os.path.exists(extraction_dir):
            shutil.rmtree(extraction_dir)

        # 6. Create ZIP
        zip_filename = f"{base_name}_processed.zip"
        zip_path = os.path.join(app.config['PROCESSED_FOLDER'], zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(md_path, arcname=f"{base_name}.md")
            for root, dirs, files in os.walk(job_dir):
                for file in files:
                    if file != f"{base_name}.md":
                         zipf.write(os.path.join(root, file), arcname=file)

        # Cleanup Job Dir
        shutil.rmtree(job_dir)
        
        jobs[job_id]['progress'] = 100
        jobs[job_id]['status'] = 'Complete'
        jobs[job_id]['result_file'] = zip_filename

        save_history({
            'id': job_id,
            'filename': original_filename,
            'date': time.strftime("%Y-%m-%d %H:%M"),
            'zip_name': zip_filename
        })

    except Exception as e:
        print(f"JOB FAILED: {e}")
        jobs[job_id]['status'] = f"Error: {str(e)}"
        jobs[job_id]['progress'] = 0

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    # Ensure folders exist (Double check for safety)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        job_id = str(uuid.uuid4())
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{job_id}_{filename}")
        
        print(f"Saving file to: {filepath}") # Debug log
        file.save(filepath)
        
        options = {
            'strategy': request.form.get('strategy'),
            'model': request.form.get('model'),
            'infer_tables': request.form.get('infer_tables') == 'true',
            'extract_images': request.form.get('extract_images') == 'true'
        }

        jobs[job_id] = {'status': 'Queued', 'progress': 0}
        thread = threading.Thread(target=process_file_thread, args=(job_id, filepath, filename, options))
        thread.start()
        
        return jsonify({'job_id': job_id})
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/status/<job_id>')
def status(job_id):
    return jsonify(jobs.get(job_id, {'status': 'Unknown'}))

@app.route('/download/<filename>')
def download(filename):
    return send_file(os.path.join(app.config['PROCESSED_FOLDER'], filename), as_attachment=True)

@app.route('/history')
def get_history():
    return jsonify(load_history())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)