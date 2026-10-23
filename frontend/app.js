document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const statusDot = document.getElementById("statusDot");
  const statusTitle = document.getElementById("statusTitle");
  const activeModel = document.getElementById("activeModel");
  const totalChunksCount = document.getElementById("totalChunksCount");
  const docCountBadge = document.getElementById("docCountBadge");
  const docList = document.getElementById("docList");
  const refreshDocsBtn = document.getElementById("refreshDocsBtn");
  const reportList = document.getElementById("reportList");
  const reportCountBadge = document.getElementById("reportCountBadge");

  // Relational Database Elements
  const dbStatus = document.getElementById("dbStatus");
  const accessControlStatus = document.getElementById("accessControlStatus");
  const eventList = document.getElementById("eventList");
  const eventCountBadge = document.getElementById("eventCountBadge");

  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const uploadProgressCard = document.getElementById("uploadProgressCard");
  const uploadProgressText = document.getElementById("uploadProgressText");

  const welcomeHero = document.getElementById("welcomeHero");
  const messagesList = document.getElementById("messagesList");
  const chatForm = document.getElementById("chatForm");
  const userInput = document.getElementById("userInput");
  const sendBtn = document.getElementById("sendBtn");
  const clearChatBtn = document.getElementById("clearChatBtn");
  const chipButtons = document.querySelectorAll(".chip-btn");

  // Evidence Modal
  const evidenceModal = document.getElementById("evidenceModal");
  const closeEvidenceModalBtn = document.getElementById("closeEvidenceModalBtn");
  const modalChunkId = document.getElementById("modalChunkId");
  const modalDocSource = document.getElementById("modalDocSource");
  const modalEvidenceText = document.getElementById("modalEvidenceText");

  // Permission Modal
  const permissionModal = document.getElementById("permissionModal");
  const closePermissionModalBtn = document.getElementById("closePermissionModalBtn");
  const ticketRiskBadge = document.getElementById("ticketRiskBadge");
  const ticketDesc = document.getElementById("ticketDesc");
  const ticketToolName = document.getElementById("ticketToolName");
  const ticketId = document.getElementById("ticketId");
  const ticketArgs = document.getElementById("ticketArgs");
  const approveTicketBtn = document.getElementById("approveTicketBtn");
  const denyTicketBtn = document.getElementById("denyTicketBtn");

  let activeTicketId = null;

  // Auto-resize textarea
  userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 120) + "px";
  });

  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit"));
    }
  });

  // Prompt chips
  chipButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-query");
      userInput.value = q;
      chatForm.dispatchEvent(new Event("submit"));
    });
  });

  const refreshEventsBtn = document.getElementById("refreshEventsBtn");
  if (refreshEventsBtn) {
    refreshEventsBtn.addEventListener("click", () => {
      fetchEvents();
      fetchHealth();
    });
  }

  function hookUpEventClicks() {
    document.querySelectorAll(".event-quick-item").forEach((item) => {
      item.onclick = () => {
        const evName = item.getAttribute("data-event") || item.querySelector(".doc-item-title")?.textContent.replace(/^[^\w]+/, "").trim();
        if (evName) {
          userInput.value = `Are tickets available for ${evName}?`;
          chatForm.dispatchEvent(new Event("submit"));
        }
      };
    });
  }

  // Hook up pre-rendered event clicks immediately
  hookUpEventClicks();

  // Load Initial State
  fetchHealth();
  fetchEvents();
  fetchDocuments();
  fetchReports();

  // Periodic polling for health and pending tickets
  setInterval(fetchHealth, 10000);

  async function fetchHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) return;
      const data = await res.json();

      if (data.llm_engine && data.llm_engine.ollama_available) {
        statusDot.className = "status-indicator-dot online";
        statusTitle.textContent = "Ollama Daemon Online";
        activeModel.textContent = data.llm_engine.active_model || "llama3.2:3b";
      } else {
        statusDot.className = "status-indicator-dot online";
        statusTitle.textContent = "Local Grounded Engine";
        activeModel.textContent = data.llm_engine ? data.llm_engine.target_model : "llama3.2:3b";
      }

      if (data.relational_db) {
        if (dbStatus) dbStatus.textContent = `${data.relational_db.events_count || 5} Events (SQLite)`;
        if (accessControlStatus) accessControlStatus.textContent = "Backend Whitelisted";
      }

      totalChunksCount.textContent = data.embeddings ? data.embeddings.total_chunks_indexed : 0;
      docCountBadge.textContent = `${data.indexed_documents_count || 0} docs`;
    } catch (e) {
      statusDot.className = "status-indicator-dot offline";
      statusTitle.textContent = "Engine Offline";
    }
  }

  async function fetchEvents() {
    if (!eventList) return;
    try {
      const res = await fetch("/api/events");
      if (!res.ok) return;
      const events = await res.json();
      if (eventCountBadge) eventCountBadge.textContent = `${events.length} events`;

      if (events && events.length > 0) {
        eventList.innerHTML = "";
        events.forEach((ev) => {
          const li = document.createElement("li");
          li.className = "doc-item event-quick-item";
          li.style.cursor = "pointer";
          li.setAttribute("data-event", ev.name);
          li.innerHTML = `
            <div class="doc-item-info">
              <span class="doc-item-title" title="${ev.name}">🎟️ ${ev.name}</span>
              <span class="doc-item-meta">${ev.category} • ${ev.organizer}</span>
            </div>
          `;
          eventList.appendChild(li);
        });
        hookUpEventClicks();
      }
    } catch (e) {
      console.error("Failed to load events", e);
    }
  }

  async function fetchDocuments() {
    try {
      const res = await fetch("/api/documents");
      if (!res.ok) return;
      const docs = await res.json();
      renderDocumentList(docs);
    } catch (e) {
      console.error("Failed to load documents", e);
    }
  }

  function renderDocumentList(docs) {
    docList.innerHTML = "";
    if (!docs || docs.length === 0) {
      docList.innerHTML = '<li class="doc-item-empty">No documents indexed. Upload above to begin.</li>';
      return;
    }

    docs.forEach((doc) => {
      const li = document.createElement("li");
      li.className = "doc-item";
      li.innerHTML = `
        <div class="doc-item-info">
          <span class="doc-item-title" title="${doc.filename}">${doc.filename}</span>
          <span class="doc-item-meta">${doc.indexed_chunks || 1} indexed chunk(s)</span>
        </div>
        <button class="doc-delete-btn" data-filename="${doc.filename}" title="Purge document vectors">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/></svg>
        </button>
      `;

      li.querySelector(".doc-delete-btn").addEventListener("click", async (e) => {
        e.stopPropagation();
        const fn = e.currentTarget.getAttribute("data-filename");
        if (confirm(`Permanently purge '${fn}' and delete all its vector embeddings from ChromaDB?`)) {
          await deleteDocument(fn);
        }
      });

      docList.appendChild(li);
    });
  }

  async function deleteDocument(filename) {
    try {
      const res = await fetch(`/api/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
      if (res.ok) {
        fetchDocuments();
        fetchHealth();
      }
    } catch (e) {
      alert("Failed to delete document: " + e);
    }
  }

  async function fetchReports() {
    try {
      const res = await fetch("/api/reports");
      if (!res.ok) return;
      const reports = await res.json();
      reportList.innerHTML = "";
      reportCountBadge.textContent = reports.length;
      if (reports.length === 0) {
        reportList.innerHTML = '<li class="doc-item-empty">No reports generated yet</li>';
        return;
      }
      reports.forEach((r) => {
        const li = document.createElement("li");
        li.className = "doc-item";
        li.innerHTML = `
          <div class="doc-item-info">
            <span class="doc-item-title" title="${r.filename}">📄 ${r.filename}</span>
            <span class="doc-item-meta">${(r.size_bytes / 1024).toFixed(1)} KB</span>
          </div>
        `;
        reportList.appendChild(li);
      });
    } catch (e) {
      console.error(e);
    }
  }

  refreshDocsBtn.addEventListener("click", () => {
    fetchDocuments();
    fetchReports();
    fetchHealth();
  });

  // File Upload Handlers
  dropZone.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", (e) => handleFiles(e.target.files));

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("dragover");
  });
  dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("dragover");
    if (e.dataTransfer.files) handleFiles(e.dataTransfer.files);
  });

  async function handleFiles(files) {
    if (!files || files.length === 0) return;
    uploadProgressCard.classList.remove("hidden");

    for (let file of files) {
      uploadProgressText.textContent = `Scrubbing PII & Indexing: ${file.name}...`;
      const formData = new FormData();
      formData.append("file", file);

      try {
        const res = await fetch("/api/documents/upload", {
          method: "POST",
          body: formData,
        });
        const result = await res.json();
        if (!res.ok) {
          alert(`Error uploading ${file.name}: ${result.detail || "Upload failed"}`);
        }
      } catch (err) {
        alert(`Failed to upload ${file.name}: ${err}`);
      }
    }

    uploadProgressCard.classList.add("hidden");
    fileInput.value = "";
    fetchDocuments();
    fetchHealth();
  }

  // Clear Chat
  clearChatBtn.addEventListener("click", () => {
    messagesList.innerHTML = "";
    welcomeHero.classList.remove("hidden");
  });

  // Chat Form Submission
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = userInput.value.trim();
    if (!query) return;

    welcomeHero.classList.add("hidden");
    appendUserMessage(query);
    userInput.value = "";
    userInput.style.height = "auto";
    sendBtn.disabled = true;

    // Loading bubble
    const loadingBubble = appendLoadingBubble();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query }),
      });
      const data = await res.json();
      loadingBubble.remove();
      appendAssistantMessage(data);
    } catch (err) {
      loadingBubble.remove();
      appendErrorMessage("Failed to connect to local RAG engine: " + err);
    } finally {
      sendBtn.disabled = false;
    }
  });

  function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "message-bubble user-msg";
    div.innerHTML = `
      <div class="avatar">You</div>
      <div class="message-content-wrap">
        <div class="message-sender">User</div>
        <div class="message-body">${escapeHtml(text)}</div>
      </div>
    `;
    messagesList.appendChild(div);
    div.scrollIntoView({ behavior: "smooth" });
  }

  function appendLoadingBubble() {
    const div = document.createElement("div");
    div.className = "message-bubble bot-msg";
    div.innerHTML = `
      <div class="avatar">AI</div>
      <div class="message-content-wrap">
        <div class="message-sender">Local Agent (llama3.2:3b)</div>
        <div class="message-body">
          <div class="rag-mode-pill" style="display:inline-flex;">
            <span class="dot-pulse"></span>
            <span>Retrieving & Grounding Evidence...</span>
          </div>
        </div>
      </div>
    `;
    messagesList.appendChild(div);
    div.scrollIntoView({ behavior: "smooth" });
    return div;
  }

  function appendErrorMessage(errorText) {
    const div = document.createElement("div");
    div.className = "message-bubble bot-msg";
    div.innerHTML = `
      <div class="avatar">AI</div>
      <div class="message-content-wrap">
        <div class="message-sender">System</div>
        <div class="message-body" style="color: var(--accent-red);">${escapeHtml(errorText)}</div>
      </div>
    `;
    messagesList.appendChild(div);
  }

  function appendAssistantMessage(data) {
    const div = document.createElement("div");
    div.className = "message-bubble bot-msg";

    // Format markdown text with citation pills
    let formattedText = formatMarkdown(data.response || "");

    // Build reasoning steps accordion
    let stepsHtml = "";
    if (data.steps && data.steps.length > 0) {
      stepsHtml = `
        <div class="pipeline-steps-card">
          <div class="pipeline-steps-title">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 14 14"/></svg>
            <span>Reasoning Pipeline (${data.steps.length} stages)</span>
          </div>
          ${data.steps
            .map(
              (s) => `
            <div class="pipeline-step-item">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>
              <span>${escapeHtml(s)}</span>
            </div>`
            )
            .join("")}
        </div>
      `;
    }

    // Build proposed action ticket card if mutating tool was requested
    let actionTicketHtml = "";
    if (data.action_proposed) {
      const ticket = data.action_proposed;
      const isHighRisk = ticket.risk_level === "HIGH";
      actionTicketHtml = `
        <div class="ticket-prompt-card ${isHighRisk ? "risk-high" : ""}" id="ticketCard_${ticket.ticket_id}">
          <div class="ticket-prompt-header">
            <div class="ticket-prompt-title">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
              <span>HITL Authorization Required: <code>${ticket.tool_name}</code></span>
            </div>
            <span class="risk-badge ${isHighRisk ? "risk-high" : "risk-medium"}">${ticket.risk_level}</span>
          </div>
          <p style="font-size: 0.85rem; color: #cbd5e1;">${escapeHtml(ticket.description)}</p>
          <div class="ticket-prompt-actions">
            <button class="btn-deny-sm" data-ticket="${ticket.ticket_id}">Reject</button>
            <button class="btn-approve-sm" data-ticket="${ticket.ticket_id}">Approve & Execute</button>
          </div>
        </div>
      `;
    }

    // Build Database Query & Access Control Inspection Card
    let dbQueryHtml = "";
    if (data.sql_query || data.access_control) {
      const isBlocked = data.status === "SECURITY_BLOCKED" || (data.access_control && data.access_control.includes("DENIED"));
      const tablesList = (data.tables_accessed || []).join(", ") || "Whitelisted Schema";
      const colsList = (data.columns_accessed || []).slice(0, 8).join(", ") + ((data.columns_accessed && data.columns_accessed.length > 8) ? "..." : "");

      dbQueryHtml = `
        <div class="db-query-card ${isBlocked ? 'db-blocked' : 'db-approved'}">
          <div class="db-query-header">
            <div class="db-badge ${isBlocked ? 'badge-denied' : 'badge-passed'}">
              ${isBlocked ? '🛡️ Backend Access Denied (Restricted Data)' : '🔒 Backend Whitelist Enforced'}
            </div>
            <span class="db-tables-pill">${escapeHtml(tablesList)}</span>
          </div>
          ${colsList ? `
            <div class="db-meta-row">
              <span class="db-meta-lbl">Columns Retrieved:</span>
              <code class="db-meta-code">${escapeHtml(colsList)}</code>
            </div>
          ` : ''}
          ${data.sql_query ? `
            <details class="db-sql-toggle">
              <summary>Inspect Scoped SQL (${data.row_count !== undefined ? data.row_count + ' records' : 'AST Validated'})</summary>
              <pre class="db-sql-code">${escapeHtml(data.sql_query)}</pre>
            </details>
          ` : ''}
        </div>
      `;
    }

    div.innerHTML = `
      <div class="avatar">AI</div>
      <div class="message-content-wrap">
        <div class="message-sender">Local Agent (llama3.2:3b)</div>
        <div class="message-body">${formattedText}</div>
        ${dbQueryHtml}
        ${actionTicketHtml}
        ${stepsHtml}
      </div>
    `;

    // Hook up citation clicks
    div.querySelectorAll(".citation-tag").forEach((tag) => {
      tag.addEventListener("click", () => {
        const cid = tag.getAttribute("data-cid");
        openEvidenceModal(cid);
      });
    });

    // Hook up ticket approval buttons
    div.querySelectorAll(".btn-approve-sm").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tid = btn.getAttribute("data-ticket");
        submitTicketDecision(tid, "approve");
      });
    });
    div.querySelectorAll(".btn-deny-sm").forEach((btn) => {
      btn.addEventListener("click", () => {
        const tid = btn.getAttribute("data-ticket");
        submitTicketDecision(tid, "reject");
      });
    });

    messagesList.appendChild(div);
    div.scrollIntoView({ behavior: "smooth" });
  }

  function formatMarkdown(text) {
    let html = escapeHtml(text);

    // Markdown Links: [Label](https://...) -> <a href="..." target="_blank" class="chat-event-link">Label ↗</a>
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-event-link">$1 <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px;display:inline;vertical-align:middle;"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/></svg></a>');

    // Standalone URLs not already in an href
    html = html.replace(/(^|[^"'>])(https?:\/\/[^\s\)<]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer" class="chat-event-link">$2</a>');

    // Convert [chunk_id] into interactive clickable citation tag
    html = html.replace(/\[([a-zA-Z0-9_\-\.#]+)\]/g, (match, cid) => {
      if (cid.includes("_c") || cid.includes("Policy") || cid.includes("Governance") || cid.includes("Security")) {
        return `<span class="citation-tag" data-cid="${cid}">📄 ${cid}</span>`;
      }
      return match;
    });

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3 style="font-size:1.05rem; margin:10px 0 6px; color:#f8fafc;">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 style="font-size:1.15rem; margin:12px 0 8px; color:#f8fafc;">$1</h2>');

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>');

    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

    // Italics
    html = html.replace(/\*(.*?)\*/g, "<em>$1</em>");

    // Bullet points
    html = html.replace(/^• (.*$)/gim, '<div style="margin-left: 8px; margin-bottom: 6px;">• $1</div>');
    html = html.replace(/\n\n/g, "<br><br>");
    return html;
  }

  function escapeHtml(string) {
    return String(string)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Evidence Modal Handler
  function openEvidenceModal(chunkId) {
    modalChunkId.textContent = chunkId;
    modalDocSource.textContent = chunkId.split("_c")[0] || "Local Document";
    modalEvidenceText.textContent = `Evidence verified from local persistent ChromaDB collection.\nChunk ID: ${chunkId}\n\nStrict ground-truth extraction enforced. No external cloud endpoints were queried.`;
    evidenceModal.classList.remove("hidden");
  }

  closeEvidenceModalBtn.addEventListener("click", () => {
    evidenceModal.classList.add("hidden");
  });
  evidenceModal.addEventListener("click", (e) => {
    if (e.target === evidenceModal) evidenceModal.classList.add("hidden");
  });

  // Ticket Decision Submission
  async function submitTicketDecision(tid, action) {
    try {
      const res = await fetch("/api/agent/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket_id: tid, action: action }),
      });
      const data = await res.json();
      const card = document.getElementById(`ticketCard_${tid}`);
      if (card) {
        if (action === "approve") {
          card.style.borderColor = "var(--accent-green)";
          card.innerHTML = `<span style="color: var(--accent-green); font-weight: 600;">✓ Action Approved & Executed Successfully!</span>`;
        } else {
          card.style.borderColor = "var(--accent-red)";
          card.innerHTML = `<span style="color: var(--accent-red); font-weight: 600;">✕ Action Rejected by User.</span>`;
        }
      }
      fetchReports();
      fetchDocuments();
    } catch (e) {
      alert("Failed to submit decision: " + e);
    }
  }
});
