/**
 * Personal AI Chatbot — Frontend Logic
 * Strictly uses local FastAPI endpoints: /api/upload, /api/profile, /api/chat
 */

document.addEventListener('DOMContentLoaded', () => {
  // -------------------------------------------------------------------------
  // DOM Elements
  // -------------------------------------------------------------------------
  const profileStatusBadge = document.getElementById('profileStatusBadge');
  const profileStatusText = document.getElementById('profileStatusText');
  const viewToggleBtn = document.getElementById('viewToggleBtn');
  const knowledgePanel = document.getElementById('knowledgePanel');
  const chatPanel = document.getElementById('chatPanel');

  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const urlInput = document.getElementById('urlInput');
  const urlImportBtn = document.getElementById('urlImportBtn');
  const refreshProfileBtn = document.getElementById('refreshProfileBtn');

  const statWords = document.getElementById('statWords');
  const statChars = document.getElementById('statChars');
  const statSections = document.getElementById('statSections');

  const formattedPreview = document.getElementById('formattedPreview');
  const rawPreview = document.getElementById('rawPreview');
  const copyMdBtn = document.getElementById('copyMdBtn');
  const toggleRawMdBtn = document.getElementById('toggleRawMdBtn');

  const chatMessages = document.getElementById('chatMessages');
  const chatForm = document.getElementById('chatForm');
  const messageInput = document.getElementById('messageInput');
  const sendBtn = document.getElementById('sendBtn');
  const clearChatBtn = document.getElementById('clearChatBtn');
  const quickPrompts = document.getElementById('quickPrompts');
  const toastContainer = document.getElementById('toastContainer');

  // -------------------------------------------------------------------------
  // State
  // -------------------------------------------------------------------------
  let activeMarkdown = '';
  let showRawMarkdown = false;
  let chatHistory = [];
  let isSending = false;

  // -------------------------------------------------------------------------
  // Toast Notification System
  // -------------------------------------------------------------------------
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span>${escapeHtml(message)}</span>
    `;
    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(100%)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 4500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Simple Markdown to HTML formatter for the preview
  function renderMarkdownToHtml(md) {
    if (!md || !md.trim()) {
      return '<p class="empty-state-text">No profile loaded. Upload a document or enter a URL above.</p>';
    }

    let html = escapeHtml(md);

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold & Italics
    html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');

    // Horizontal Rule
    html = html.replace(/^---$/gim, '<hr />');

    // Bullet lists
    html = html.replace(/^\- (.*$)/gim, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>');
    html = html.replace(/<\/ul>\s*<ul>/gim, '');

    // Line breaks / paragraphs
    html = html.replace(/\n\n+/g, '</p><p>');
    html = `<p>${html}</p>`;
    html = html.replace(/<p>\s*<\/p>/g, '');
    html = html.replace(/<p>\s*(<h[1-3]>)/g, '$1');
    html = html.replace(/(<\/h[1-3]>)\s*<\/p>/g, '$1');
    html = html.replace(/<p>\s*(<hr \/>)/g, '$1');
    html = html.replace(/(<hr \/>)\s*<\/p>/g, '$1');
    html = html.replace(/<p>\s*(<ul>)/g, '$1');
    html = html.replace(/(<\/ul>)\s*<\/p>/g, '$1');

    return html;
  }

  // -------------------------------------------------------------------------
  // Profile Fetch & UI Update
  // -------------------------------------------------------------------------
  async function loadProfile() {
    try {
      profileStatusText.textContent = 'Loading profile...';
      const res = await fetch('/api/profile');
      if (!res.ok) throw new Error('Failed to fetch profile details');

      const data = await res.json();
      if (data.exists && data.markdown) {
        activeMarkdown = data.markdown;
        updateProfileUI(data);
      } else {
        setEmptyProfileState();
      }
    } catch (err) {
      console.error(err);
      setEmptyProfileState();
      showToast('Could not reach backend API or profile not loaded.', 'error');
    }
  }

  function updateProfileUI(data) {
    profileStatusBadge.className = 'status-badge status-ready';
    profileStatusText.textContent = 'Profile Loaded';

    statWords.textContent = (data.stats && data.stats.words) ? data.stats.words.toLocaleString() : '0';
    statChars.textContent = (data.stats && data.stats.characters) ? data.stats.characters.toLocaleString() : '0';
    statSections.textContent = (data.stats && data.stats.sections) ? data.stats.sections.length : '0';

    rawPreview.textContent = data.markdown;
    formattedPreview.innerHTML = renderMarkdownToHtml(data.markdown);
  }

  function setEmptyProfileState() {
    activeMarkdown = '';
    profileStatusBadge.className = 'status-badge status-empty';
    profileStatusText.textContent = 'No Profile Loaded';

    statWords.textContent = '0';
    statChars.textContent = '0';
    statSections.textContent = '0';

    rawPreview.textContent = '';
    formattedPreview.innerHTML = '<p class="empty-state-text">No profile loaded. Upload a document (PDF, DOCX, TXT, HTML) or enter a URL above.</p>';
  }

  // -------------------------------------------------------------------------
  // Upload & Import Handlers
  // -------------------------------------------------------------------------
  // Dropzone click & drag events
  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('dragover');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileUpload(e.target.files[0]);
    }
  });

  async function handleFileUpload(file) {
    if (!file) return;

    // Validate size (< 10MB)
    if (file.size > 10 * 1024 * 1024) {
      showToast('File is too large! Maximum supported size is 10MB.', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const originalText = profileStatusText.textContent;
    profileStatusText.textContent = `Extracting ${file.name}...`;
    showToast(`Extracting and converting ${file.name}...`, 'info');

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Failed to process document');
      }

      activeMarkdown = result.markdown;
      updateProfileUI(result);
      showToast(result.message || 'Profile updated successfully!', 'success');
      fileInput.value = '';
    } catch (err) {
      console.error(err);
      profileStatusText.textContent = originalText;
      showToast(err.message, 'error');
    }
  }

  // URL Import
  urlImportBtn.addEventListener('click', handleUrlImport);
  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleUrlImport();
    }
  });

  async function handleUrlImport() {
    const url = urlInput.value.trim();
    if (!url) {
      showToast('Please enter a URL first.', 'error');
      return;
    }

    const formData = new FormData();
    formData.append('url', url);

    urlImportBtn.disabled = true;
    urlImportBtn.textContent = 'Importing...';

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });

      const result = await res.json();
      if (!res.ok) {
        throw new Error(result.detail || 'Could not import from URL');
      }

      activeMarkdown = result.markdown;
      updateProfileUI(result);
      showToast(result.message || 'URL content converted and saved!', 'success');
      urlInput.value = '';
    } catch (err) {
      console.error(err);
      showToast(err.message, 'error');
    } finally {
      urlImportBtn.disabled = false;
      urlImportBtn.textContent = 'Import';
    }
  }

  // Refresh profile button
  refreshProfileBtn.addEventListener('click', () => {
    loadProfile();
    showToast('Profile refreshed from disk.', 'info');
  });

  // Toggle raw vs formatted
  toggleRawMdBtn.addEventListener('click', () => {
    showRawMarkdown = !showRawMarkdown;
    if (showRawMarkdown) {
      formattedPreview.classList.add('hidden');
      rawPreview.classList.remove('hidden');
      toggleRawMdBtn.textContent = 'Formatted View';
    } else {
      rawPreview.classList.add('hidden');
      formattedPreview.classList.remove('hidden');
      toggleRawMdBtn.textContent = 'Raw / Formatted';
    }
  });

  // Copy markdown to clipboard
  copyMdBtn.addEventListener('click', async () => {
    if (!activeMarkdown) {
      showToast('No markdown content to copy.', 'info');
      return;
    }
    try {
      await navigator.clipboard.writeText(activeMarkdown);
      showToast('Markdown copied to clipboard!', 'success');
    } catch (err) {
      showToast('Failed to copy to clipboard.', 'error');
    }
  });

  // -------------------------------------------------------------------------
  // Chat Messaging System
  // -------------------------------------------------------------------------
  // Auto-resize message input
  messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
  });

  // Enter to send
  messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleChatSubmit();
    }
  });

  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    handleChatSubmit();
  });

  async function handleChatSubmit() {
    const text = messageInput.value.trim();
    if (!text || isSending) return;

    // Reset input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Append user message to UI
    appendUserMessage(text);

    // Show typing indicator
    const typingIndicator = showTypingIndicator();

    isSending = true;
    sendBtn.disabled = true;

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: chatHistory
        })
      });

      const data = await res.json();
      removeTypingIndicator(typingIndicator);

      if (!res.ok) {
        throw new Error(data.detail || 'Chat request failed');
      }

      // Append assistant message with source section tag
      appendAssistantMessage(data.reply, data.source_section);

      // Add to session history
      chatHistory.push({ role: 'user', content: text });
      chatHistory.push({ role: 'assistant', content: data.reply });

    } catch (err) {
      console.error(err);
      removeTypingIndicator(typingIndicator);
      appendAssistantMessage(
        `Sorry, I encountered an issue processing your request: ${err.message}`,
        'Error'
      );
    } finally {
      isSending = false;
      sendBtn.disabled = false;
      messageInput.focus();
    }
  }

  function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row message-user';
    row.innerHTML = `
      <div class="msg-avatar">You</div>
      <div class="msg-content-wrapper">
        <div class="msg-bubble">
          <p>${escapeHtml(text)}</p>
        </div>
      </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
  }

  function appendAssistantMessage(text, sourceSection = 'Profile') {
    const row = document.createElement('div');
    row.className = 'message-row message-assistant';
    
    const isNone = !sourceSection || sourceSection.toLowerCase() === 'none';
    const tagClass = isNone ? 'msg-source-tag source-none' : 'msg-source-tag';
    const tagLabel = isNone ? 'No profile source' : `Source: ${escapeHtml(sourceSection)}`;

    row.innerHTML = `
      <div class="msg-avatar">AI</div>
      <div class="msg-content-wrapper">
        <div class="msg-bubble">
          <p>${escapeHtml(text)}</p>
        </div>
        <div class="${tagClass}">
          <span class="source-icon">📌</span>
          <span>${tagLabel}</span>
        </div>
      </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
  }

  function showTypingIndicator() {
    const row = document.createElement('div');
    row.className = 'message-row message-assistant';
    row.id = 'typingIndicatorRow';
    row.innerHTML = `
      <div class="msg-avatar">AI</div>
      <div class="msg-content-wrapper">
        <div class="msg-bubble typing-bubble">
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
          <span class="typing-dot"></span>
        </div>
      </div>
    `;
    chatMessages.appendChild(row);
    scrollToBottom();
    return row;
  }

  function removeTypingIndicator(el) {
    if (el && el.parentNode) {
      el.remove();
    }
  }

  function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Clear chat button
  clearChatBtn.addEventListener('click', () => {
    chatHistory = [];
    chatMessages.innerHTML = `
      <div class="message-row message-assistant">
        <div class="msg-avatar">AI</div>
        <div class="msg-content-wrapper">
          <div class="msg-bubble">
            <p>Chat cleared! Ask me anything about my experience, education, skills, or background.</p>
          </div>
          <div class="msg-source-tag">
            <span class="source-icon">📌</span>
            <span>Source: Profile Overview</span>
          </div>
        </div>
      </div>
    `;
    showToast('Conversation history reset.', 'info');
  });

  // Quick Prompt Chips
  quickPrompts.addEventListener('click', (e) => {
    if (e.target.classList.contains('prompt-chip')) {
      const promptText = e.target.textContent;
      messageInput.value = promptText;
      handleChatSubmit();
    }
  });

  // Mobile View Toggle
  viewToggleBtn.addEventListener('click', () => {
    const isShowingKnowledge = knowledgePanel.classList.contains('active-view');
    if (isShowingKnowledge) {
      knowledgePanel.classList.remove('active-view');
      chatPanel.classList.remove('inactive-view');
      viewToggleBtn.textContent = 'View Profile';
    } else {
      knowledgePanel.classList.add('active-view');
      chatPanel.classList.add('inactive-view');
      viewToggleBtn.textContent = 'View Chat';
    }
  });

  // Initial Load
  loadProfile();
});
