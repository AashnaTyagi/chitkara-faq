(() => {
  "use strict";

  const API_BASE = (document.querySelector('meta[name="api-base"]')?.content || "").replace(/\/$/, "");
  const STORE_KEY = "chitkara-uniassist-ai-v1";

  const els = {
    scroller: document.getElementById("scroller"),
    welcome: document.getElementById("welcome"),
    log: document.getElementById("log"),
    form: document.getElementById("composer"),
    input: document.getElementById("input"),
    send: document.getElementById("send"),
    newChat: document.getElementById("newChat"),
  };

  let state = { conversationId: null, messages: [] };
  let busy = false;

  // ---------- storage (per browser tab)
  function load() {
    try {
      const saved = JSON.parse(sessionStorage.getItem(STORE_KEY) || "null");
      if (saved && Array.isArray(saved.messages)) state = saved;
    } catch { /* ignore */ }
  }
  function save() {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify(state)); } catch { /* ignore */ }
  }

  // ---------- markdown
  function escapeHtml(s) {
    return s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }
  function renderMarkdown(text) {
    let html;
    if (window.marked && window.DOMPurify) {
      html = DOMPurify.sanitize(marked.parse(text, { gfm: true, breaks: true }));
    } else {
      html = "<p>" + escapeHtml(text).replace(/\n/g, "<br>") + "</p>";
    }
    const box = document.createElement("div");
    box.className = "bubble";
    box.innerHTML = html;

    box.querySelectorAll("table").forEach(t => {
      const wrap = document.createElement("div");
      wrap.className = "table-wrap";
      t.replaceWith(wrap);
      wrap.appendChild(t);
    });
    box.querySelectorAll("a").forEach(a => { a.target = "_blank"; a.rel = "noopener noreferrer"; });
    box.querySelectorAll("p").forEach(p => {
      if (/^\s*sources?\s*:/i.test(p.textContent)) p.classList.add("source");
    });
    return box;
  }

  // ---------- rendering
  function messageNode(m, index) {
    const li = document.createElement("li");
    li.className = `msg ${m.role}`;

    if (m.role === "user") {
      const who = document.createElement("span");
      who.className = "who";
      who.textContent = "You";
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = m.text;
      li.append(who, bubble);
    } else if (m.role === "bot") {
      const who = document.createElement("span");
      who.className = "who";
      who.textContent = "UniAssist-Ai";
      li.append(who, renderMarkdown(m.text));

      if (m.trace && m.trace.length) {
        const details = document.createElement("details");
        details.className = "trace";
        const summary = document.createElement("summary");
        summary.textContent = "How this was answered";
        details.appendChild(summary);
        m.trace.forEach(call => {
          const p = document.createElement("p");
          p.textContent = `Searched university records for: "${call.question}"`;
          details.appendChild(p);
        });
        li.appendChild(details);
      }
    } else if (m.role === "error") {
      const bubble = document.createElement("div");
      bubble.className = "bubble";
      bubble.textContent = m.text;
      if (m.retry && index === state.messages.length - 1) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "retry";
        btn.textContent = "Try again";
        btn.addEventListener("click", () => {
          state.messages.pop();                 // remove the error
          const last = state.messages.pop();    // remove the failed user message
          save();
          if (last && last.role === "user") ask(last.text);
        });
        bubble.appendChild(btn);
      }
      li.appendChild(bubble);
    }
    return li;
  }

  function typingNode() {
    const li = document.createElement("li");
    li.className = "msg bot typing";
    li.id = "typing";
    const who = document.createElement("span");
    who.className = "who";
    who.textContent = "UniAssist-Ai";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerHTML = '<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span><span>Checking university records</span>';
    li.append(who, bubble);
    return li;
  }

  function render() {
    const started = state.messages.length > 0;
    els.welcome.hidden = started;
    els.newChat.hidden = !started;
    els.log.replaceChildren(...state.messages.map(messageNode));
    if (busy) els.log.appendChild(typingNode());
    requestAnimationFrame(() => { els.scroller.scrollTop = started || busy ? els.scroller.scrollHeight : 0; });
  }

  function setBusy(value) {
    busy = value;
    els.send.disabled = value;
    els.input.disabled = value;
    render();
    if (!value) els.input.focus();
  }

  // ---------- API
  async function ask(text) {
    const question = text.trim();
    if (!question || busy) return;

    state.messages.push({ role: "user", text: question });
    save();
    setBusy(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question, conversation_id: state.conversationId }),
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        const detail = typeof data.detail === "string" ? data.detail : "UniAssist-Ai couldn't get an answer right now.";
        state.messages.push({ role: "error", text: detail, retry: res.status !== 422 });
      } else {
        state.conversationId = data.conversation_id;
        state.messages.push({ role: "bot", text: data.answer, trace: data.kb_calls || [] });
      }
    } catch {
      state.messages.push({ role: "error", text: "Couldn't reach UniAssist-Ai. Check your internet connection.", retry: true });
    }

    save();
    setBusy(false);
  }

  // ---------- input handling
  function autoGrow() {
    els.input.style.height = "auto";
    els.input.style.height = Math.min(els.input.scrollHeight, 160) + "px";
  }

  els.form.addEventListener("submit", e => {
    e.preventDefault();
    const text = els.input.value;
    els.input.value = "";
    autoGrow();
    ask(text);
  });

  els.input.addEventListener("input", autoGrow);
  els.input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      els.form.requestSubmit();
    }
  });

  document.querySelectorAll(".ask").forEach(btn => {
    btn.addEventListener("click", () => ask(btn.textContent));
  });

  els.newChat.addEventListener("click", () => {
    state = { conversationId: null, messages: [] };
    save();
    render();
    els.input.focus();
  });

  load();
  render();
})();
