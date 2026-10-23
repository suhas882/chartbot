# 🚀 Deployment Guide: Privacy-First Agentic RAG & Event Database Chatbot

This guide explains how to deploy the application across different environments:
1. **Containerized Deployment (Docker Compose - Recommended)**
2. **Standalone Docker Container**
3. **Linux / VPS Server (Ubuntu/Debian with Systemd & Nginx)**
4. **Cloud Platforms (AWS, DigitalOcean, Render, Railway)**

---

## 🛠️ System Overview & Architecture

- **Backend:** FastAPI (Python 3.11) with Uvicorn ASGI server
- **Frontend:** Responsive Vanilla HTML5/CSS/JavaScript with glassmorphic dark theme
- **Relational DB:** SQLite3 (`data/events.db`) with read-only connection URI & engine-level access control
- **Vector DB:** ChromaDB (embedded SQLite `data/chroma_data/chroma.sqlite3`) + BM25Okapi lexical index
- **LLM Engine:** Local Ollama daemon (`llama3.2:3b`) with automatic in-process fallback (`Qwen2.5-0.5B-Instruct`)
- **Security:** Zero-Trust Access Control Whitelisting + Human-In-The-Loop Permission Governor + PII Scrubbing

---

## Option 1: Docker Compose Deployment (Recommended)

This setup launches both the **FastAPI Chatbot** and the **Ollama Engine** in isolated containers connected over a private bridge network.

### Step 1: Clone / Copy the Project to Your Server
```bash
git clone <your-repo-url>
cd chartbot
```

### Step 2: Start the Containers
```bash
docker compose up -d --build
```

### Step 3: Download the LLM Model inside Ollama
Once the containers are running, pull the model into the Ollama container:
```bash
docker exec -it local_ollama_engine ollama pull llama3.2:3b
```

### Step 4: Access the Application
Open your browser and navigate to:
```
http://<your-server-ip>:8000
```

To view logs:
```bash
docker compose logs -f
```

To stop:
```bash
docker compose down
```

---

## Option 2: Standalone Docker Deployment

If you already have Ollama running on your host machine or an external server:

### Step 1: Build the Image
```bash
docker build -t event-rag-chatbot:latest .
```

### Step 2: Run the Container
```bash
docker run -d \
  --name event_chatbot \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -e OLLAMA_HOST=http://host.docker.internal:11434 \
  -e LLM_MODEL=llama3.2:3b \
  event-rag-chatbot:latest
```

---

## Option 3: Native Linux / VPS Deployment (Ubuntu / Debian)

### Step 1: Install Python 3.11 & Virtual Environment
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv python3-pip curl git
```

### Step 2: Setup Project & Virtual Environment
```bash
git clone <your-repo-url> /opt/chartbot
cd /opt/chartbot

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Initialize Database & Ingest Sample Documents
```bash
python init_event_db.py
python ingest_samples.py
```

### Step 4: Configure Systemd Service
Create a systemd unit file `/etc/systemd/system/chartbot.service`:
```ini
[Unit]
Description=Privacy-First Agentic RAG Chatbot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/chartbot
ExecStart=/opt/chartbot/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
Environment="PATH=/opt/chartbot/venv/bin"
Environment="OLLAMA_HOST=http://127.0.0.1:11434"
Environment="LLM_MODEL=llama3.2:3b"

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable chartbot
sudo systemctl start chartbot
sudo systemctl status chartbot
```

### Step 5: Configure Nginx as Reverse Proxy & SSL
Install Nginx:
```bash
sudo apt install -y nginx
```

Create `/etc/nginx/sites-available/chartbot`:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and reload Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/chartbot /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

*(Optional) Add Free Let's Encrypt SSL:*
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

---

## Option 4: Cloud Platforms (Render / Railway / DigitalOcean App Platform)

### Deploying via Git Push:
1. Push your repository to GitHub or GitLab.
2. Link your repository in **Render** or **Railway**.
3. Set the following configuration:
   - **Environment:** `Docker`
   - **Docker Context Directory:** `.`
   - **Port:** `8000`
   - **Persistent Disk:** Mount `/app/data` to persist documents, reports, and database changes.
   - **Environment Variables:**
     - `LOCAL_ONLY_MODE=true`
     - `OLLAMA_HOST=http://127.0.0.1:11434` (If using external Ollama)

---

## ⚙️ Environment Variables Reference

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Address of the local Ollama daemon |
| `LLM_MODEL` | `llama3.2:3b` | Target open-source model name in Ollama |
| `LOCAL_ONLY_MODE` | `true` | When true, zero external cloud endpoints are queried |
| `ENABLE_PII_SCRUBBING` | `true` | Sanitizes emails, phones, SSNs before vector storage |
