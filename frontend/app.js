const API = "/api";
let currentChatId = null;
let pollTimer = null;

// ---------------- Navigation ----------------
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => switchView(btn.dataset.view));
});

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${view}`));
  if (view === "dashboard") loadDashboard();
  if (view === "documents") loadDocuments();
  if (view === "chat") loadChats();
}

function toast(message, kind = "ok") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function timeAgo(iso) {
  const d = new Date(iso + (iso.endsWith("Z") ? "" : "Z"));
  const diffMin = Math.round((Date.now() - d.getTime()) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffH = Math.round(diffMin / 60);
  if (diffH < 24) return `${diffH}h ago`;
  return d.toLocaleDateString();
}

// ---------------- Backend health ----------------
async function checkHealth() {
  const dot = document.getElementById("conn-dot");
  const label = document.getElementById("conn-label");
  try {
    const res = await fetch(`${API}/health`);
    if (!res.ok) throw new Error();
    dot.className = "conn-dot ok";
    label.textContent = "Backend connected";
  } catch {
    dot.className = "conn-dot err";
    label.textContent = "Backend unreachable";
  }
}

// ---------------- Dashboard ----------------
async function loadDashboard() {
  try {
    const stats = await (await fetch(`${API}/dashboard/stats`)).json();
    const grid = document.getElementById("stat-grid");
    grid.innerHTML = "";
    const cards = [
      ["Total documents", stats.total_documents],
      ["Processed", stats.processed],
      ["Processing", stats.processing],
      ["Failed", stats.failed],
      ["Indexed chunks", stats.total_chunks],
      ["Questions asked", stats.total_questions],
    ];
    cards.forEach(([label, value]) => {
      const card = document.createElement("div");
      card.className = "stat-card";
      card.innerHTML = `<div class="stat-value">${value}</div><div class="stat-label">${label}</div>`;
      grid.appendChild(card);
    });

    const docs = await (await fetch(`${API}/documents`)).json();
    const recent = document.getElementById("recent-docs");
    recent.innerHTML = "";
    if (docs.length === 0) {
      recent.innerHTML = `<p class="muted">No documents uploaded yet.</p>`;
    }
    docs.slice(0, 6).forEach((d) => {
      const row = document.createElement("div");
      row.className = "recent-item";
      row.innerHTML = `<span>${d.filename}</span><span class="pill ${d.status}">${d.status}</span>`;
      recent.appendChild(row);
    });
  } catch (e) {
    toast("Could not load dashboard stats — is the backend running?", "err");
  }
}

// ---------------- Documents ----------------
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");

dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  uploadFiles(e.dataTransfer.files);
});
fileInput.addEventListener("change", () => uploadFiles(fileInput.files));

async function uploadFiles(fileList) {
  for (const file of fileList) {
    const form = new FormData();
    form.append("file", file);
    try {
      const res = await fetch(`${API}/documents`, { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }
      toast(`Uploading "${file.name}"…`, "ok");
    } catch (e) {
      toast(`Failed to upload "${file.name}": ${e.message}`, "err");
    }
  }
  loadDocuments();
  startPolling();
}

async function loadDocuments() {
  try {
    const docs = await (await fetch(`${API}/documents`)).json();
    const body = document.getElementById("doc-table-body");
    body.innerHTML = "";
    if (docs.length === 0) {
      body.innerHTML = `<tr><td colspan="6" class="muted">No documents yet — upload one above.</td></tr>`;
      return;
    }
    docs.forEach((d) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${d.filename}${d.error_message ? `<div class="error-note">${d.error_message}</div>` : ""}</td>
        <td>${d.file_type.replace(".", "").toUpperCase()}</td>
        <td><span class="pill ${d.status}">${d.status}</span></td>
        <td>${d.num_chunks}</td>
        <td>${timeAgo(d.uploaded_at)}</td>
        <td class="doc-actions">
          <button data-action="reprocess" data-id="${d.id}">Reprocess</button>
          <button data-action="delete" data-id="${d.id}" class="danger">Delete</button>
        </td>`;
      body.appendChild(tr);
    });

    body.querySelectorAll("button[data-action='delete']").forEach((btn) =>
      btn.addEventListener("click", () => deleteDocument(btn.dataset.id))
    );
    body.querySelectorAll("button[data-action='reprocess']").forEach((btn) =>
      btn.addEventListener("click", () => reprocessDocument(btn.dataset.id))
    );

    const stillProcessing = docs.some((d) => d.status === "processing");
    if (stillProcessing) startPolling(); else stopPolling();
  } catch (e) {
    toast("Could not load documents — is the backend running?", "err");
  }
}

function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    loadDocuments();
    if (document.getElementById("view-dashboard").classList.contains("active")) loadDashboard();
  }, 3000);
}
function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}

async function deleteDocument(id) {
  if (!confirm("Delete this document and all its indexed chunks?")) return;
  await fetch(`${API}/documents/${id}`, { method: "DELETE" });
  toast("Document deleted", "ok");
  loadDocuments();
}

async function reprocessDocument(id) {
  await fetch(`${API}/documents/${id}/reprocess`, { method: "POST" });
  toast("Reprocessing started", "ok");
  loadDocuments();
  startPolling();
}

// ---------------- Chat ----------------
document.getElementById("new-chat-btn").addEventListener("click", createNewChat);

async function loadChats() {
  const chats = await (await fetch(`${API}/chats`)).json();
  const list = document.getElementById("chat-list");
  list.innerHTML = "";
  chats.forEach((c) => {
    const item = document.createElement("div");
    item.className = "chat-list-item" + (c.id === currentChatId ? " active" : "");
    item.textContent = c.title;
    item.addEventListener("click", () => openChat(c.id));
    list.appendChild(item);
  });
  if (!currentChatId && chats.length > 0) openChat(chats[0].id);
  if (chats.length === 0) createNewChat();
}

async function createNewChat() {
  const res = await fetch(`${API}/chats`, { method: "POST" });
  const chat = await res.json();
  currentChatId = chat.id;
  await loadChats();
  renderMessages([]);
}

async function openChat(chatId) {
  currentChatId = chatId;
  document.querySelectorAll(".chat-list-item").forEach((el, i) => {});
  await loadChats();
  const messages = await (await fetch(`${API}/chats/${chatId}/messages`)).json();
  renderMessages(messages);
}

function renderMessages(messages) {
  const container = document.getElementById("chat-messages");
  container.innerHTML = "";
  if (messages.length === 0) {
    container.innerHTML = `<div class="chat-empty">
      <p>Ask a question about your uploaded documents.</p>
      <p class="muted">Answers are grounded only in what you've uploaded — if it's not in there, you'll be told so.</p>
    </div>`;
    return;
  }
  messages.forEach((m) => container.appendChild(renderMessage(m)));
  container.scrollTop = container.scrollHeight;
}

function renderMessage(m) {
  const div = document.createElement("div");
  const notFound = m.role === "assistant" && /couldn.?t find information/i.test(m.content);
  div.className = `msg ${m.role}` + (notFound ? " not-found" : "");
  const textEl = document.createElement("div");
  textEl.textContent = m.content;
  div.appendChild(textEl);

  if (m.sources && m.sources.length > 0) {
    const src = document.createElement("div");
    src.className = "msg-sources";
    src.innerHTML = "Sources: " + m.sources.map(s =>
      `<span class="source-tag">📄 ${s.doc_name}${s.page ? ` — p.${s.page}` : ""}</span>`
    ).join("");
    div.appendChild(src);
  }
  return div;
}

document.getElementById("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = document.getElementById("chat-input");
  const question = input.value.trim();
  if (!question) return;
  if (!currentChatId) await createNewChat();

  input.value = "";
  const container = document.getElementById("chat-messages");
  if (container.querySelector(".chat-empty")) container.innerHTML = "";
  container.appendChild(renderMessage({ role: "user", content: question }));
  const loadingEl = document.createElement("div");
  loadingEl.className = "msg loading";
  loadingEl.textContent = "Searching your documents…";
  container.appendChild(loadingEl);
  container.scrollTop = container.scrollHeight;

  const sendBtn = document.getElementById("chat-send-btn");
  sendBtn.disabled = true;

  try {
    const res = await fetch(`${API}/chats/${currentChatId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const data = await res.json();
    loadingEl.remove();
    if (!res.ok) {
      container.appendChild(renderMessage({ role: "assistant", content: data.detail || "Something went wrong." }));
    } else {
      container.appendChild(renderMessage({ role: "assistant", content: data.answer, sources: data.sources }));
    }
    container.scrollTop = container.scrollHeight;
    loadChats();
  } catch (e) {
    loadingEl.remove();
    container.appendChild(renderMessage({ role: "assistant", content: "Could not reach the backend. Is it running?" }));
  } finally {
    sendBtn.disabled = false;
  }
});

// ---------------- Init ----------------
checkHealth();
loadDashboard();
setInterval(checkHealth, 10000);
