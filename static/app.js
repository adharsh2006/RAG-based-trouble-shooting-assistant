document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const sidebar = document.getElementById('sidebar');
  const mainContent = document.querySelector('.main-content');
  const collapseSidebarBtn = document.getElementById('collapse-sidebar-btn');
  const expandSidebarBtn = document.getElementById('expand-sidebar-btn');
  const sidebarBackdrop = document.getElementById('sidebar-backdrop');
  const newChatBtn = document.getElementById('new-chat-btn');
  const historyList = document.getElementById('history-list');
  const clearCurrentChatBtn = document.getElementById('clear-current-chat-btn');

  const emptyState = document.getElementById('empty-state');
  const activeChat = document.getElementById('active-chat');
  const messagesContainer = document.getElementById('messages-container');
  const bottomBarContainer = document.getElementById('bottom-bar-container');

  const centerInput = document.getElementById('center-prompt-input');
  const centerSendBtn = document.getElementById('center-send-btn');
  const bottomInput = document.getElementById('bottom-prompt-input');
  const bottomSendBtn = document.getElementById('bottom-send-btn');

  // Application State
  let currentSessionId = null;
  let isGenerating = false;

  // Initialize Marked markdown parser
  marked.setOptions({
    highlight: function(code, lang) {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value;
      }
      return hljs.highlightAuto(code).value;
    },
    breaks: true
  });

  // --- Sidebar Drawer Control ---
  function toggleSidebar(show) {
    if (window.innerWidth <= 768) {
      if (show) {
        sidebar.classList.add('open');
        sidebarBackdrop.classList.add('show');
      } else {
        sidebar.classList.remove('open');
        sidebarBackdrop.classList.remove('show');
      }
    } else {
      if (show) {
        sidebar.classList.remove('collapsed');
        mainContent.classList.remove('expanded-view');
        expandSidebarBtn.classList.add('hidden');
      } else {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('expanded-view');
        expandSidebarBtn.classList.remove('hidden');
      }
    }
  }

  collapseSidebarBtn.addEventListener('click', () => toggleSidebar(false));
  expandSidebarBtn.addEventListener('click', () => toggleSidebar(true));
  sidebarBackdrop.addEventListener('click', () => toggleSidebar(false));

  // --- Textarea Auto-Resize ---
  function setupAutoResize(textarea) {
    textarea.addEventListener('input', () => {
      textarea.style.height = 'auto';
      textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px';
    });
  }
  setupAutoResize(centerInput);
  setupAutoResize(bottomInput);

  // --- Fetch & Render History Sessions ---
  async function loadHistory() {
    try {
      const res = await fetch('/api/history');
      const sessions = await res.json();
      historyList.innerHTML = '';

      if (sessions.length === 0) {
        historyList.innerHTML = '<div style="padding: 12px; font-size: 0.8rem; color: var(--text-dim);">No chats yet.</div>';
        return;
      }

      sessions.forEach(session => {
        const item = document.createElement('div');
        item.className = `history-item ${session.id === currentSessionId ? 'active' : ''}`;
        item.dataset.id = session.id;

        item.innerHTML = `
          <span class="history-title" title="${escapeHtml(session.title)}">${escapeHtml(session.title)}</span>
          <div class="history-actions">
            <button class="item-action-btn delete-btn" title="Delete chat">🗑️</button>
          </div>
        `;

        item.addEventListener('click', (e) => {
          if (e.target.classList.contains('delete-btn')) {
            e.stopPropagation();
            deleteSession(session.id);
            return;
          }
          selectSession(session.id);
        });

        historyList.appendChild(item);
      });
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  }

  // --- Select & Load Session ---
  async function selectSession(sessionId) {
    if (isGenerating) return;
    currentSessionId = sessionId;

    try {
      const res = await fetch(`/api/history/${sessionId}`);
      if (!res.ok) {
        showEmptyState();
        return;
      }
      const session = await res.json();

      // Highlight active session in sidebar
      document.querySelectorAll('.history-item').forEach(el => {
        el.classList.toggle('active', el.dataset.id === sessionId);
      });

      if (!session.messages || session.messages.length === 0) {
        showEmptyState();
      } else {
        showActiveChatState();
        renderMessages(session.messages);
      }
    } catch (err) {
      console.error('Failed to select session:', err);
    }
  }

  // --- Delete Session ---
  async function deleteSession(sessionId) {
    if (isGenerating) return;
    try {
      await fetch(`/api/history/${sessionId}`, { method: 'DELETE' });
      if (currentSessionId === sessionId) {
        currentSessionId = null;
        showEmptyState();
      }
      loadHistory();
    } catch (err) {
      console.error('Failed to delete session:', err);
    }
  }

  // --- State Switchers ---
  function showEmptyState() {
    emptyState.classList.remove('hidden');
    activeChat.classList.add('hidden');
    bottomBarContainer.classList.add('hidden');
    messagesContainer.innerHTML = '';
    centerInput.value = '';
    centerInput.style.height = 'auto';
  }

  function showActiveChatState() {
    emptyState.classList.add('hidden');
    activeChat.classList.remove('hidden');
    bottomBarContainer.classList.remove('hidden');
  }

  // --- Render Past Messages ---
  function renderMessages(messages) {
    messagesContainer.innerHTML = '';
    messages.forEach(msg => {
      if (msg.role === 'user') {
        addUserBubble(msg.content);
      } else {
        addAssistantBubble(msg.content, msg.metadata);
      }
    });
    scrollToBottom();
  }

  function addUserBubble(text) {
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrapper';
    wrap.innerHTML = `<div class="msg-user">🧑 ${escapeHtml(text)}</div>`;
    messagesContainer.appendChild(wrap);
    scrollToBottom();
  }

  function addAssistantBubble(content = '', metadata = null) {
    const wrap = document.createElement('div');
    wrap.className = 'msg-wrapper';

    let metaHtml = '';
    if (metadata) {
      if (metadata.rewritten_query) {
        metaHtml += `<div class="rewrite-badge">🔄 Searched for: ${escapeHtml(metadata.rewritten_query)}</div>`;
      }
    }

    let sourcesHtml = '';
    if (metadata && metadata.sources && metadata.sources.length > 0) {
      sourcesHtml += '<div class="sources-container">';
      metadata.sources.forEach(src => {
        let badgeClass = 'badge-pdf';
        let label = `📄 ${src}`;
        if (src.includes('incidents')) {
          badgeClass = 'badge-incident';
          label = '📊 Incidents DB';
        } else if (src.startsWith('http')) {
          badgeClass = 'badge-web';
          label = `🌐 ${src.split('/')[2] || src}`;
        }
        sourcesHtml += `<span class="source-badge ${badgeClass}">${escapeHtml(label)}</span>`;
      });
      sourcesHtml += '</div>';
    }

    let chunksHtml = '';
    if (metadata && metadata.chunks && metadata.chunks.length > 0) {
      chunksHtml += `<button class="chunks-toggle" onclick="this.nextElementSibling.classList.toggle('hidden')">🔍 View ${metadata.chunks.length} retrieved chunks ▼</button>`;
      chunksHtml += '<div class="chunks-detail hidden">';
      metadata.chunks.forEach((c, idx) => {
        chunksHtml += `
          <div class="chunk-card">
            <div class="chunk-header">Chunk ${idx + 1} · ${(c.source_type || '').toUpperCase()}</div>
            <div>${escapeHtml(c.content)}...</div>
          </div>
        `;
      });
      chunksHtml += '</div>';
    }

    const parsedMarkdown = marked.parse(content || '');

    wrap.innerHTML = `
      <div class="msg-assistant">
        ${metaHtml}
        <div class="markdown-body">${parsedMarkdown}</div>
        ${sourcesHtml}
        ${chunksHtml}
      </div>
    `;

    messagesContainer.appendChild(wrap);
    addCopyCodeButtons(wrap);
    scrollToBottom();
    return wrap;
  }

  function addCopyCodeButtons(container) {
    container.querySelectorAll('pre').forEach(pre => {
      if (pre.querySelector('.copy-code-btn')) return;
      const btn = document.createElement('button');
      btn.className = 'copy-code-btn';
      btn.innerText = 'Copy';
      btn.addEventListener('click', () => {
        const code = pre.querySelector('code')?.innerText || pre.innerText;
        navigator.clipboard.writeText(code);
        btn.innerText = 'Copied!';
        setTimeout(() => btn.innerText = 'Copy', 2000);
      });
      pre.style.position = 'relative';
      pre.appendChild(btn);
    });
  }

  function scrollToBottom() {
    const viewport = document.querySelector('.chat-viewport');
    viewport.scrollTop = viewport.scrollHeight;
  }

  function escapeHtml(str) {
    return (str || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // --- Send Message Handler (SSE Streaming) ---
  async function sendMessage(questionText) {
    const question = questionText.trim();
    if (!question || isGenerating) return;

    isGenerating = true;
    showActiveChatState();
    addUserBubble(question);

    // Prepare assistant streaming box
    const streamWrap = document.createElement('div');
    streamWrap.className = 'msg-wrapper';
    streamWrap.innerHTML = `
      <div class="msg-assistant">
        <div class="meta-slot"></div>
        <div class="markdown-body"><span class="typing-cursor">▌</span></div>
        <div class="sources-slot"></div>
      </div>
    `;
    messagesContainer.appendChild(streamWrap);
    scrollToBottom();

    const markdownSlot = streamWrap.querySelector('.markdown-body');
    const metaSlot = streamWrap.querySelector('.meta-slot');
    const sourcesSlot = streamWrap.querySelector('.sources-slot');

    let fullAnswer = '';
    let currentMeta = null;

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: currentSessionId, question: question })
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete chunk in buffer

        for (const block of lines) {
          if (!block.trim()) continue;

          let eventType = 'message';
          let eventData = '';

          block.split('\n').forEach(line => {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim();
            } else if (line.startsWith('data:')) {
              eventData = line.slice(5).trim();
            }
          });

          if (!eventData) continue;
          const data = JSON.parse(eventData);

          if (eventType === 'metadata') {
            currentMeta = data;
            if (data.rewritten_query) {
              metaSlot.innerHTML = `<div class="rewrite-badge">🔄 Searched for: ${escapeHtml(data.rewritten_query)}</div>`;
            }
            if (data.sources && data.sources.length > 0) {
              let srcHtml = '<div class="sources-container">';
              data.sources.forEach(src => {
                let badgeClass = 'badge-pdf';
                let label = `📄 ${src}`;
                if (src.includes('incidents')) { badgeClass = 'badge-incident'; label = '📊 Incidents DB'; }
                else if (src.startsWith('http')) { badgeClass = 'badge-web'; label = `🌐 ${src.split('/')[2] || src}`; }
                srcHtml += `<span class="source-badge ${badgeClass}">${escapeHtml(label)}</span>`;
              });
              srcHtml += '</div>';
              sourcesSlot.innerHTML = srcHtml;
            }
          } else if (eventType === 'token') {
            fullAnswer += data.text;
            markdownSlot.innerHTML = marked.parse(fullAnswer) + ' <span class="typing-cursor">▌</span>';
            scrollToBottom();
          } else if (eventType === 'done') {
            currentSessionId = data.session_id;
            markdownSlot.innerHTML = marked.parse(fullAnswer);
            addCopyCodeButtons(streamWrap);
            hljs.highlightAll();
            loadHistory();
          }
        }
      }
    } catch (err) {
      console.error('Error during chat stream:', err);
      markdownSlot.innerHTML += '<p style="color: #f38ba8;">⚠️ Error connecting to server.</p>';
    } finally {
      isGenerating = false;
      bottomInput.value = '';
      bottomInput.style.height = 'auto';
      centerInput.value = '';
      centerInput.style.height = 'auto';
      scrollToBottom();
    }
  }

  // --- Event Listeners ---
  newChatBtn.addEventListener('click', async () => {
    if (isGenerating) return;
    try {
      const res = await fetch('/api/history/new', { method: 'POST' });
      const session = await res.json();
      currentSessionId = session.id;
      await loadHistory();
      showEmptyState();
    } catch (err) {
      console.error('Failed to create new chat:', err);
    }
  });

  clearCurrentChatBtn.addEventListener('click', () => {
    if (currentSessionId) {
      deleteSession(currentSessionId);
    } else {
      showEmptyState();
    }
  });

  centerSendBtn.addEventListener('click', () => sendMessage(centerInput.value));
  bottomSendBtn.addEventListener('click', () => sendMessage(bottomInput.value));

  centerInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(centerInput.value);
    }
  });

  bottomInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(bottomInput.value);
    }
  });

  // Suggestion card clicks
  document.querySelectorAll('.suggestion-card').forEach(card => {
    card.addEventListener('click', () => {
      const prompt = card.dataset.prompt;
      if (prompt) sendMessage(prompt);
    });
  });

  // Initial Load
  loadHistory();
});
