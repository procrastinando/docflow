document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const processBtn = document.getElementById('process-btn');
    const uploadSection = document.getElementById('upload-section');
    const processingSection = document.getElementById('processing-section');
    const successSection = document.getElementById('success-section');
    const progressBar = document.getElementById('progress-bar');
    const statusText = document.getElementById('status-text');
    
    let selectedFile = null;

    // Load History on Start
    loadHistory();

    // --- DRAG AND DROP HANDLERS ---
    // These work entirely in the browser. Cloudflare does not interfere here.
    
    // Trigger file input when clicking the box
    dropZone.addEventListener('click', () => fileInput.click());
    
    // Handle file selection via Click
    fileInput.addEventListener('change', (e) => handleFile(e.target.files[0]));
    
    // Visual feedback when dragging over
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault(); // Essential to allow dropping
        e.stopPropagation();
        dropZone.style.borderColor = '#8b5cf6';
        dropZone.style.background = 'rgba(139, 92, 246, 0.05)';
    });
    
    // Remove feedback when leaving
    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.style.borderColor = '#334155';
        dropZone.style.background = 'transparent';
    });
    
    // Handle the actual Drop
    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();
        dropZone.style.borderColor = '#334155';
        dropZone.style.background = 'transparent';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFile(files[0]);
        }
    });

    function handleFile(file) {
        if (!file) return;
        selectedFile = file;
        
        // Show filename in UI
        const display = document.getElementById('filename-display');
        display.textContent = file.name;
        document.getElementById('file-info').classList.remove('hidden');
        
        // Enable button
        processBtn.disabled = false;
        processBtn.textContent = "Start Processing 🚀";
    }

    // --- UPLOAD LOGIC ---
    processBtn.addEventListener('click', async () => {
        if (!selectedFile) return;

        // UI Transition
        uploadSection.classList.add('hidden');
        processingSection.classList.remove('hidden');

        // Form Data
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('strategy', document.getElementById('strategy').value);
        formData.append('model', document.getElementById('model').value);
        formData.append('infer_tables', document.getElementById('infer_tables').checked);
        formData.append('extract_images', document.getElementById('extract_images').checked);

        try {
            // NOTE: We use a relative path '/upload'. 
            // This ensures it works through Cloudflare Tunnel automatically.
            const res = await fetch('/upload', { method: 'POST', body: formData });
            
            if (!res.ok) {
                const errData = await res.json();
                throw new Error(errData.error || 'Upload failed');
            }

            const data = await res.json();
            
            // Start Polling
            pollStatus(data.job_id);

        } catch (err) {
            alert("Error: " + err.message);
            location.reload(); // Reset on error
        }
    });

    function pollStatus(jobId) {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/status/${jobId}`);
                const data = await res.json();

                statusText.textContent = data.status;
                progressBar.style.width = data.progress + '%';

                if (data.status === 'Complete') {
                    clearInterval(interval);
                    showSuccess(data.result_file);
                    loadHistory(); 
                }
                if (String(data.status).startsWith('Error')) {
                    clearInterval(interval);
                    alert(data.status);
                    location.reload();
                }
            } catch (e) {
                console.error("Polling error", e);
            }
        }, 1000);
    }

    function showSuccess(filename) {
        processingSection.classList.add('hidden');
        successSection.classList.remove('hidden');
        document.getElementById('result-filename').textContent = filename;
        document.getElementById('download-link').href = `/download/${filename}`;
    }

    document.getElementById('reset-btn').addEventListener('click', () => location.reload());

    async function loadHistory() {
        try {
            const res = await fetch('/history');
            const history = await res.json();
            const list = document.getElementById('history-list');
            list.innerHTML = '';
            
            history.forEach(item => {
                const li = document.createElement('li');
                li.className = 'history-item';
                // Note the class 'history-filename' to match CSS
                li.innerHTML = `
                    <div>
                        <div class="history-filename">${item.filename}</div>
                        <div style="font-size:0.8em; color:#94a3b8">${item.date}</div>
                    </div>
                    <a href="/download/${item.zip_name}">⬇ JSON/MD</a>
                `;
                list.appendChild(li);
            });
        } catch (e) {
            console.error("Could not load history");
        }
    }
});