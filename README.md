# DocFlow

**Local, Privacy-First Document Processing for RAG Pipelines.**

DocFlow is a self-hosted web application that transforms complex unstructured documents (PDFs, Scientific Papers) into clean, structured Markdown, Images, and Tables. It is designed specifically to prepare data for RAG (Retrieval-Augmented Generation) systems like **AnythingLLM**, **Dify**, or **LangChain**.

Powered by [Unstructured.io](https://unstructured.io/), Flask, and Docker. Optimized for CPU inference.

## Features

*   **RAG-Ready Output:** Converts PDFs into a single `.md` (Markdown) file with embedded table text.
*   **Asset Extraction:** Automatically extracts and renames Figures (Images) and Tables (CSV) into a flat file structure.
*   **Privacy First:** Runs 100% offline on your hardware. No data is sent to third-party APIs.
*   **CPU Optimized:** Configured to run efficiently on multi-core CPUs (supports `YOLOX` and `Detectron2` ONNX models).
*   **Modern UI:** Dark-themed web interface with drag-and-drop, progress tracking, and job history.
*   **Persistent History:** Keeps track of processed files even after container restarts.

## Getting Started

### Prerequisites
*   Docker & Docker Compose

### Method 1: Docker Compose (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/procrastinando/docflow.git
    cd docflow
    ```

2.  **Start the container:**
    ```bash
    docker compose up -d --build
    ```

3.  **Access the UI:**
    Open your browser and go to `http://localhost:5000` (or your server IP).

### Method 2: Manual Docker Build

If you prefer running without Compose:

```bash
# 1. Build the image
docker build -t docflow .

# 2. Run the container
# We mount ./data to persist uploads and history
docker run -d \
  -p 5000:5000 \
  --name docflow \
  --cpus=10 \
  --memory=16g \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/models:/app/models \
  docflow
```

---

## Usage Guide

### 1. Processing Strategies
*   **Hi-Res (Recommended):** Uses Computer Vision models (YOLOX/Detectron2) to "see" the document. Necessary for multi-column scientific papers, tables, and images. *Slower, but accurate.*
*   **Fast:** Standard text extraction. Very fast, but ignores tables/images and may scramble columns.

### 2. Output Format
DocFlow produces a `.zip` file designed for immediate ingestion into Vector Databases.

**Example Input:** `Quantum_Physics_Paper.pdf`

**Example Output (Inside ZIP):**
```text
/
├── Quantum_Physics_Paper.md                  # Main content (Text + Table representation)
├── Quantum_Physics_Paper_images_figure-1.jpg # Extracted diagram
├── Quantum_Physics_Paper_images_figure-2.jpg # Extracted chart
└── Quantum_Physics_Paper_tables_table-1.csv  # Extracted table data
```

The Markdown file automatically references the figures so LLMs know where images belong in the context.

---

## Configuration

### Docker Compose Configuration
If you need to adjust resource limits, edit the `docker-compose.yml`:

```yaml
services:
  docflow:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data      # Persistence for history/uploads
      - ./models:/app/models  # Cache for AI models
    deploy:
      resources:
        limits:
          cpus: '20'          # Adjust based on your server
          memory: 30G
    restart: unless-stopped
```

### Deploying Behind a Proxy (Cloudflare Tunnel / Nginx)
DocFlow uses relative paths for all API calls. It works out-of-the-box behind **Cloudflare Zero Trust Tunnels** or Nginx reverse proxies without additional configuration.

*Note: If processing large scanned PDFs (>100MB), ensure your proxy's "Client Body Size" limit is increased.*

---

## Tech Stack

*   **Backend:** Python 3.10, Flask, Threading.
*   **Core Engine:** [Unstructured](https://github.com/unstructured-io/unstructured) (Open Source).
*   **Frontend:** HTML5, CSS3, Vanilla JS.
*   **Inference:** ONNX / PyTorch (CPU Mode).
