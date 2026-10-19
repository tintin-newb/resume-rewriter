// assets/js/app.js

// Global State
const state = {
  currentTab: 'generate',
  selectedFile: null,
  activeTaskId: null,
  eventSource: null,
  jdMode: 'url',
  
  // History state
  history: {
    items: [],
    offset: 0,
    limit: 15,
    hasMore: true,
    isLoading: false,
    search: '',
    searchTimeout: null,
    observer: null
  },

  // Detail Modal state
  activeDetail: null,
  activeDocMode: 'rewritten', // 'rewritten' | 'source' | 'diff'
  docCache: {
    source: null,
    rewritten: null
  }
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
  initDropzone();
  initHistoryObserver();
  loadSystemHealth();
  loadConfig();
  loadHistory(true);
});

// --- Tab Switching (Fully Independent) ---
function switchTab(tabName) {
  if (state.currentTab === tabName) return;

  state.currentTab = tabName;

  // Update nav buttons
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`nav-tab-${tabName}`).classList.add('active');

  // Update tab visibility
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
  document.getElementById(`tab-${tabName}`).classList.add('active');

  // If opening history and list is empty, fetch fresh
  if (tabName === 'history' && state.history.items.length === 0) {
    loadHistory(true);
  }
}

// --- Drag & Drop File Upload ---
function initDropzone() {
  const dropzone = document.getElementById('dropzone');
  if (!dropzone) return;

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files && files.length > 0) {
      setSelectedFile(files[0]);
    }
  });
}

function handleFileSelect(e) {
  if (e.target.files && e.target.files.length > 0) {
    setSelectedFile(e.target.files[0]);
  }
}

function setSelectedFile(file) {
  state.selectedFile = file;
  document.getElementById('file-name-display').textContent = `${file.name} (${formatBytes(file.size)})`;
  document.getElementById('file-pill').classList.add('visible');
  document.getElementById('dropzone').style.display = 'none';
}

function clearSelectedFile(e) {
  if (e) e.stopPropagation();
  state.selectedFile = null;
  document.getElementById('file-input-resume').value = '';
  document.getElementById('file-pill').classList.remove('visible');
  document.getElementById('dropzone').style.display = 'block';
}

function formatBytes(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// --- JD Mode Toggle & Accordion ---
function setJDMode(mode) {
  state.jdMode = mode;
  document.getElementById('btn-mode-url').classList.toggle('active', mode === 'url');
  document.getElementById('btn-mode-text').classList.toggle('active', mode === 'text');
  document.getElementById('jd-url-container').style.display = mode === 'url' ? 'block' : 'none';
  document.getElementById('jd-text-container').style.display = mode === 'text' ? 'block' : 'none';
}

function toggleAccordion(id) {
  const el = document.getElementById(id);
  const arrow = document.getElementById('accordion-arrow');
  const isOpen = el.classList.toggle('open');
  arrow.textContent = isOpen ? '▲' : '▼';
}

// --- Agent Guidance Tabs & Indicators ---
function setAuxAgentMode(agent) {
  const modes = ['recruiter', 'rewriter', 'referral', 'general'];
  modes.forEach(m => {
    const btn = document.getElementById(`btn-aux-${m}`);
    const panel = document.getElementById(`aux-panel-${m}`);
    if (btn) btn.classList.toggle('active', m === agent);
    if (panel) panel.style.display = (m === agent) ? 'block' : 'none';
  });
}
window.setAuxAgentMode = setAuxAgentMode;

function updateAuxIndicators() {
  const modes = ['recruiter', 'rewriter', 'referral', 'general'];
  modes.forEach(m => {
    const input = document.getElementById(`input-aux-${m}`);
    const dot = document.getElementById(`dot-aux-${m}`);
    if (input && dot) {
      dot.style.display = input.value.trim().length > 0 ? 'inline-block' : 'none';
    }
  });
}
window.updateAuxIndicators = updateAuxIndicators;

// --- Pipeline Execution & Live Stepper ---
async function handleGenerateSubmit(e) {
  e.preventDefault();

  if (!state.selectedFile) {
    showToast('Please select or drop a base resume file.', 'error');
    return;
  }

  const company = document.getElementById('input-company').value.trim();
  const jobId = document.getElementById('input-job-id').value.trim();
  const role = document.getElementById('input-role').value.trim();
  const url = document.getElementById('input-jd-url').value.trim();
  const jdText = document.getElementById('input-jd-text').value.trim();

  const recruiterInst = document.getElementById('input-aux-recruiter')?.value.trim() || '';
  const rewriterInst = document.getElementById('input-aux-rewriter')?.value.trim() || '';
  const referralInst = document.getElementById('input-aux-referral')?.value.trim() || '';
  const generalInst = (document.getElementById('input-aux-general')?.value || document.getElementById('input-auxiliary-instructions')?.value || '').trim();

  const maxLoops = document.getElementById('input-max-loops').value;
  const force = document.getElementById('check-force').checked;
  const skipBootstrap = document.getElementById('check-skip-bootstrap').checked;

  if (state.jdMode === 'url' && !url) {
    showToast('Please provide a valid Job URL.', 'error');
    return;
  }
  if (state.jdMode === 'text' && !jdText) {
    showToast('Please paste the job description text.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('resume', state.selectedFile);
  formData.append('company', company);
  formData.append('job_id', jobId);
  formData.append('role', role);
  if (state.jdMode === 'url') formData.append('url', url);
  if (state.jdMode === 'text') formData.append('jd_text', jdText);
  if (recruiterInst) formData.append('recruiter_instructions', recruiterInst);
  if (rewriterInst) formData.append('rewriter_instructions', rewriterInst);
  if (referralInst) formData.append('referral_instructions', referralInst);
  if (generalInst) formData.append('auxiliary_instructions', generalInst);
  if (maxLoops) formData.append('max_loops', maxLoops);
  formData.append('force', force);
  formData.append('skip_bootstrap', skipBootstrap);

  const submitBtn = document.getElementById('btn-submit-generate');
  submitBtn.disabled = true;
  submitBtn.innerHTML = `
    <span class="status-dot warning" style="animation: pulse 1s infinite;"></span>
    <span>Orchestrating Agents...</span>
  `;

  // Reset Stepper
  document.getElementById('pipeline-empty-state').style.display = 'none';
  const stepper = document.getElementById('stepper-list');
  stepper.style.display = 'flex';
  stepper.innerHTML = '';
  updatePipelineStatusBadge('Running...', 'running');

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to initiate optimization pipeline.');
    }

    const data = await res.json();
    state.activeTaskId = data.task_id;
    startSSEStream(data.task_id);

  } catch (err) {
    showToast(err.message, 'error');
    updatePipelineStatusBadge('Failed', 'failed');
    submitBtn.disabled = false;
    submitBtn.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
      <span>Execute Optimization Pipeline</span>
    `;
  }
}

function startSSEStream(taskId) {
  if (state.eventSource) {
    state.eventSource.close();
  }

  const es = new EventSource(`/api/generate/stream/${taskId}`);
  state.eventSource = es;

  es.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      handlePipelineEvent(parsed);
    } catch (e) {
      console.error('Failed to parse SSE event', e);
    }
  };

  es.onerror = (err) => {
    console.warn('SSE stream closed or interrupted', err);
    es.close();
  };
}

function handlePipelineEvent(event) {
  const { type, data } = event;

  if (type === 'step') {
    renderStepCard(data);
  } else if (type === 'cached') {
    updatePipelineStatusBadge('Cached Record', 'completed');
    showToast('A cached evaluation already exists for this job requisition.', 'info');
    finishGenerationRun();
  } else if (type === 'complete') {
    updatePipelineStatusBadge('Completed', 'completed');
    showToast('Resume optimization completed successfully!', 'success');
    finishGenerationRun();
    // Refresh history feed in background so it's ready when user switches
    loadHistory(true);
  } else if (type === 'error') {
    updatePipelineStatusBadge('Failed', 'failed');
    showToast(`Error: ${data.error || 'Pipeline encountered a failure.'}`, 'error');
    renderErrorCard(data.error);
    finishGenerationRun();
  }
}

function finishGenerationRun() {
  const submitBtn = document.getElementById('btn-submit-generate');
  submitBtn.disabled = false;
  submitBtn.innerHTML = `
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
    <span>Execute Optimization Pipeline</span>
  `;
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
}

function updatePipelineStatusBadge(text, className) {
  const badge = document.getElementById('pipeline-status-badge');
  badge.textContent = text;
  badge.className = `pipeline-status-badge ${className}`;
}

function renderStepCard(data) {
  const stepper = document.getElementById('stepper-list');
  const stepId = `step-${data.step}-${data.data && data.data.round ? data.data.round : 'main'}`;

  let card = document.getElementById(stepId);
  if (!card) {
    card = document.createElement('div');
    card.id = stepId;
    card.className = `step-card ${data.status === 'in_progress' ? 'active' : 'completed'}`;
    stepper.appendChild(card);
  } else {
    card.className = `step-card ${data.status === 'in_progress' ? 'active' : 'completed'}`;
  }

  let bodyContent = '';

  if (data.step === 'bootstrap') {
    bodyContent = `<div>${data.message || 'System connectivity verified.'}</div>`;
  } else if (data.step === 'dedup') {
    bodyContent = `<div>${data.message || ''}</div>`;
  } else if (data.step === 'ingestion') {
    bodyContent = `<div>${data.message || ''}</div>`;
  } else if (data.step === 'recruiter') {
    const d = data.data || {};
    const tier = d.match_tier || 'Pending';
    const isPass = ['High Match', 'Perfect Match'].includes(tier);
    const tierClass = isPass ? 'high' : 'average';

    const strengthsHtml = (d.strengths || []).map(s => `<li style="color: var(--accent-emerald);">✓ ${escapeHtml(s)}</li>`).join('');
    const gapsHtml = (d.gaps || []).map(g => `<li style="color: var(--accent-rose);">✗ ${escapeHtml(g)}</li>`).join('');
    const suggHtml = (d.suggestions || []).map(s => `<li>→ ${escapeHtml(s)}</li>`).join('');

    bodyContent = `
      <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 8px;">
        <span class="badge-tier ${tierClass}">${tier}</span>
        <span style="font-size: 0.75rem; color: var(--text-muted);">${d.is_qualified ? 'Meets Minimum Qualifications' : 'Under Minimum Qualifications'}</span>
      </div>
      <div class="verdict-box">${escapeHtml(d.recruiter_verdict || '')}</div>
      ${strengthsHtml ? `<ul style="list-style: none; margin-top: 8px; font-size: 0.8rem;">${strengthsHtml}</ul>` : ''}
      ${gapsHtml ? `<ul style="list-style: none; margin-top: 6px; font-size: 0.8rem;">${gapsHtml}</ul>` : ''}
      ${suggHtml ? `<ul style="list-style: none; margin-top: 6px; font-size: 0.8rem; color: var(--accent-amber);">${suggHtml}</ul>` : ''}
    `;
  } else if (data.step === 'rewriter') {
    const d = data.data || {};
    const mods = (d.modifications_made || []).map(m => `<li>• ${escapeHtml(m)}</li>`).join('');
    bodyContent = `
      <div style="font-size: 0.8rem; color: var(--text-muted);">Accomplishments re-anchored with categorized action verbs:</div>
      <ul style="list-style: none; margin-top: 6px; font-size: 0.8rem; color: var(--accent-sky);">${mods}</ul>
    `;
  } else if (data.step === 'referral') {
    const d = data.data || {};
    bodyContent = `
      <div class="verdict-box" style="border-left-color: var(--accent-emerald); font-family: var(--font-mono); font-size: 0.8rem;">
        ${escapeHtml(d.referral_message || 'Referral message drafted.')}
      </div>
    `;
  } else if (data.step === 'save_artifacts') {
    const d = data.data || {};
    bodyContent = `
      <div style="font-size: 0.8rem; color: var(--accent-emerald);">
        ✓ Optimized resume saved to: <code style="font-family: var(--font-mono);">${escapeHtml(d.saved_file_path || '')}</code>
      </div>
    `;
  } else {
    bodyContent = `<div>${data.message || ''}</div>`;
  }

  card.innerHTML = `
    <div class="step-header">
      <div class="step-meta">
        <div class="step-icon-circle">${data.status === 'in_progress' ? '⟳' : '✓'}</div>
        <div class="step-title">${data.title || data.step}</div>
      </div>
      <div style="font-size: 0.75rem; color: var(--text-subtle);">${new Date().toLocaleTimeString()}</div>
    </div>
    <div class="step-body">${bodyContent}</div>
  `;

  // Auto-scroll stepper to bottom
  card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function renderErrorCard(errText) {
  const stepper = document.getElementById('stepper-list');
  const card = document.createElement('div');
  card.className = 'step-card';
  card.style.borderColor = 'var(--accent-rose)';
  card.innerHTML = `
    <div class="step-header">
      <div class="step-meta">
        <div class="step-icon-circle" style="color: var(--accent-rose); border-color: var(--accent-rose);">✕</div>
        <div class="step-title" style="color: var(--accent-rose);">Pipeline Failed</div>
      </div>
    </div>
    <div class="step-body" style="color: var(--accent-rose);">${escapeHtml(errText || 'An unexpected error occurred.')}</div>
  `;
  stepper.appendChild(card);
}

// --- History Feed & Lazy Loading ---
function initHistoryObserver() {
  const sentinel = document.getElementById('history-sentinel');
  if (!sentinel) return;

  state.history.observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting && state.history.hasMore && !state.history.isLoading) {
      loadHistory(false);
    }
  }, { rootMargin: '200px' });

  state.history.observer.observe(sentinel);
}

function debounceHistorySearch() {
  clearTimeout(state.history.searchTimeout);
  state.history.searchTimeout = setTimeout(() => {
    state.history.search = document.getElementById('input-history-search').value.trim();
    loadHistory(true);
  }, 300);
}

function reloadHistory() {
  loadHistory(true);
}

async function loadHistory(reset = false) {
  if (state.history.isLoading) return;

  if (reset) {
    state.history.offset = 0;
    state.history.hasMore = true;
    state.history.items = [];
    document.getElementById('history-grid').innerHTML = '';
  }

  if (!state.history.hasMore) return;

  state.history.isLoading = true;
  document.getElementById('history-loading-spinner').style.display = 'inline';

  const params = new URLSearchParams({
    offset: state.history.offset,
    limit: state.history.limit
  });
  if (state.history.search) {
    params.append('search', state.history.search);
  }

  try {
    const res = await fetch(`/api/history?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch history.');

    const data = await res.json();
    state.history.hasMore = data.has_more;
    state.history.offset += data.items.length;
    state.history.items.push(...data.items);

    renderHistoryItems(data.items, reset);

  } catch (err) {
    showToast(`History load error: ${err.message}`, 'error');
  } finally {
    state.history.isLoading = false;
    document.getElementById('history-loading-spinner').style.display = 'none';
  }
}

function renderHistoryItems(items, reset) {
  const grid = document.getElementById('history-grid');

  if (reset && items.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; color: var(--text-subtle); padding: 60px 20px;">
        <div style="font-size: 2.5rem; margin-bottom: 8px; opacity: 0.6;">📂</div>
        <p style="font-weight: 600; color: var(--text-muted);">No Application Runs Found</p>
        <p style="font-size: 0.825rem; margin-top: 4px;">Run a generation in the Generate tab to see your historical evaluations here.</p>
      </div>
    `;
    return;
  }

  items.forEach(item => {
    const card = document.createElement('div');
    card.className = 'history-card';
    card.onclick = () => openDetailModal(item.id);

    const tier = item.match_tier || 'Pending';
    const isPass = ['High Match', 'Perfect Match'].includes(tier);
    const tierClass = isPass ? 'high' : 'average';
    const updatedTime = item.updated_at ? new Date(item.updated_at).toLocaleDateString() : '';
    const hasReferral = Boolean(item.referral_message && item.referral_message.trim());

    card.innerHTML = `
      <div>
        <div class="history-header">
          <div>
            <div class="history-company">${escapeHtml(item.company)}</div>
            <div class="history-role">${escapeHtml(item.role)}</div>
            <span class="history-job-id">${escapeHtml(item.job_id)}</span>
          </div>
          <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
            <span class="badge-tier ${tierClass}">${tier}</span>
            ${hasReferral ? `<span class="badge-tier referral" style="cursor: pointer;" title="Click to view referral note" onclick="event.stopPropagation(); openDetailModal(${item.id}, 'referral')">✉ Referral</span>` : ''}
          </div>
        </div>

        <div class="history-summary">
          ${item.recruiter_verdict ? escapeHtml(item.recruiter_verdict) : '<em>No recruiter audit summary available.</em>'}
        </div>

        ${hasReferral ? `
          <div class="history-referral-box" style="cursor: pointer;" title="Click to view full referral message" onclick="event.stopPropagation(); openDetailModal(${item.id}, 'referral')">
            <div class="history-referral-box-header">
              <span>✉ Referral Outreach Note</span>
              <span style="font-size: 0.7rem; font-weight: 500; opacity: 0.85;">View Note →</span>
            </div>
            <div class="history-referral-text">${escapeHtml(item.referral_message)}</div>
          </div>
        ` : ''}
      </div>

      <div class="history-footer">
        <span>Updated: ${updatedTime}</span>
        <div class="history-actions" onclick="event.stopPropagation()">
          ${hasReferral ? `
            <button class="btn-secondary" style="padding: 4px 10px; font-size: 0.75rem; border-color: rgba(16, 185, 129, 0.4); color: var(--accent-emerald);" onclick="event.stopPropagation(); openDetailModal(${item.id}, 'referral')">
              ✉ Referral
            </button>
          ` : ''}
          <button class="btn-secondary" style="padding: 4px 10px; font-size: 0.75rem;" onclick="openDetailModal(${item.id})">
            Inspect Details
          </button>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });
}

// --- Run Details Modal & Document Viewer ---
async function openDetailModal(appId, initialMode = 'rewritten') {
  const modalBackdrop = document.getElementById('modal-detail-backdrop');
  modalBackdrop.classList.add('open');

  document.getElementById('modal-title').textContent = 'Loading...';
  document.getElementById('modal-meta').textContent = '';
  document.getElementById('modal-recruiter-verdict').textContent = 'Loading verdict...';
  document.getElementById('doc-viewer-single').innerHTML = '<p style="color: var(--text-subtle);">Fetching resume documents...</p>';

  state.activeDetail = null;
  state.docCache.source = null;
  state.docCache.rewritten = null;

  try {
    const res = await fetch(`/api/history/${appId}`);
    if (!res.ok) throw new Error('Failed to fetch details.');

    const record = await res.json();
    state.activeDetail = record;

    document.getElementById('modal-title').textContent = `${record.role} at ${record.company}`;
    document.getElementById('modal-meta').textContent = `Job ID: ${record.job_id} | Updated: ${new Date(record.updated_at).toLocaleString()}`;
    
    const tier = record.match_tier || 'Pending';
    const isPass = ['High Match', 'Perfect Match'].includes(tier);
    const tierBadge = document.getElementById('modal-match-tier');
    tierBadge.textContent = tier;
    tierBadge.className = `badge-tier ${isPass ? 'high' : 'average'}`;

    document.getElementById('modal-recruiter-verdict').textContent = record.recruiter_verdict || 'No verdict recorded for this run.';

    const referralWrap = document.getElementById('modal-referral-wrap');
    const btnReferralTab = document.getElementById('btn-doc-referral');
    const hasReferral = Boolean(record.referral_message && record.referral_message.trim());
    if (hasReferral) {
      document.getElementById('modal-referral-message').textContent = record.referral_message;
      if (btnReferralTab) btnReferralTab.style.display = 'inline-block';
    } else {
      if (referralWrap) referralWrap.style.display = 'none';
      if (btnReferralTab) btnReferralTab.style.display = 'none';
    }

    // Default to requested mode (fallback to rewritten if referral requested but not available)
    const targetMode = (initialMode === 'referral' && hasReferral) ? 'referral' : 'rewritten';
    await switchDocMode(targetMode);

  } catch (err) {
    showToast(`Error opening modal: ${err.message}`, 'error');
  }
}

function closeDetailModal(e) {
  if (e && e.target !== e.currentTarget && !e.target.classList.contains('modal-backdrop')) return;
  document.getElementById('modal-detail-backdrop').classList.remove('open');
}

async function switchDocMode(mode) {
  state.activeDocMode = mode;
  document.getElementById('btn-doc-rewritten').classList.toggle('active', mode === 'rewritten');
  document.getElementById('btn-doc-source').classList.toggle('active', mode === 'source');
  document.getElementById('btn-doc-diff').classList.toggle('active', mode === 'diff');
  const btnReferral = document.getElementById('btn-doc-referral');
  if (btnReferral) btnReferral.classList.toggle('active', mode === 'referral');

  const btnCopyDoc = document.getElementById('btn-copy-doc');
  if (btnCopyDoc) {
    btnCopyDoc.textContent = mode === 'referral' ? 'Copy Referral Message' : 'Copy Markdown';
  }

  const singleViewer = document.getElementById('doc-viewer-single');
  const diffViewer = document.getElementById('doc-viewer-diff');
  const referralWrap = document.getElementById('modal-referral-wrap');

  if (!state.activeDetail) return;
  const appId = state.activeDetail.id;

  if (mode === 'referral') {
    if (referralWrap) referralWrap.style.display = 'none';
    singleViewer.style.display = 'block';
    diffViewer.style.display = 'none';

    const referralMsg = state.activeDetail.referral_message;
    if (!referralMsg) {
      singleViewer.innerHTML = `<p style="color: var(--accent-amber);">No cold referral message recorded for this application.</p>`;
      return;
    }

    singleViewer.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.04); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: var(--radius-md); padding: 18px; margin-bottom: 12px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; border-bottom: 1px solid rgba(16, 185, 129, 0.2); padding-bottom: 10px;">
          <div>
            <div style="font-weight: 700; color: var(--accent-emerald); font-size: 0.95rem; display: flex; align-items: center; gap: 6px;">
              <span>✉</span> Tailored Referral Outreach Note
            </div>
            <div style="font-size: 0.775rem; color: var(--text-muted); margin-top: 2px;">
              Company: <strong style="color: var(--text-main);">${escapeHtml(state.activeDetail.company || 'Company')}</strong> | Role: <strong style="color: var(--text-main);">${escapeHtml(state.activeDetail.role || 'Role')}</strong>
            </div>
          </div>
          <button class="btn-primary" style="width: auto; padding: 6px 14px; font-size: 0.78rem; margin-top: 0; background: var(--accent-emerald);" onclick="copyReferralMessage()">
            Copy Message
          </button>
        </div>
        <div style="background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 14px; font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.6; color: var(--text-main); white-space: pre-wrap; user-select: all;">${escapeHtml(referralMsg)}</div>
        <p style="font-size: 0.75rem; color: var(--text-subtle); margin-top: 10px; margin-bottom: 0;">
          💡 <em>Pro-tip: Send this directly to an engineering peer or recruiter at ${escapeHtml(state.activeDetail.company || 'the target company')}.</em>
        </p>
      </div>
    `;
    return;
  }

  if (mode === 'diff') {
    if (referralWrap && state.activeDetail.referral_message) referralWrap.style.display = 'block';
    singleViewer.style.display = 'none';
    diffViewer.style.display = 'grid';
    await renderDiffView(appId);
    return;
  }

  if (referralWrap && state.activeDetail.referral_message) referralWrap.style.display = 'block';
  singleViewer.style.display = 'block';
  diffViewer.style.display = 'none';

  const docType = mode === 'source' ? 'source' : 'rewritten';

  if (state.docCache[docType]) {
    renderDocumentContent(state.docCache[docType], singleViewer);
    return;
  }

  singleViewer.innerHTML = `<p style="color: var(--text-subtle);">Fetching ${docType} document...</p>`;

  try {
    const res = await fetch(`/api/document/${docType}/${appId}`);
    if (!res.ok) {
      singleViewer.innerHTML = `<p style="color: var(--accent-amber);">No ${docType} file found or accessible on disk.</p>`;
      return;
    }

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/pdf')) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      singleViewer.innerHTML = `<iframe src="${url}" style="width: 100%; height: 500px; border: none; border-radius: 6px;"></iframe>`;
      state.docCache[docType] = { type: 'pdf', url: url };
    } else {
      const json = await res.json();
      state.docCache[docType] = { type: 'text', content: json.content };
      renderDocumentContent(state.docCache[docType], singleViewer);
    }

  } catch (err) {
    singleViewer.innerHTML = `<p style="color: var(--accent-rose);">Failed to load document: ${escapeHtml(err.message)}</p>`;
  }
}

function renderDocumentContent(docObj, container) {
  if (docObj.type === 'pdf') {
    container.innerHTML = `<iframe src="${docObj.url}" style="width: 100%; height: 500px; border: none; border-radius: 6px;"></iframe>`;
  } else {
    // Render Markdown cleanly via marked.js
    if (window.marked) {
      container.innerHTML = window.marked.parse(docObj.content || '');
    } else {
      container.innerHTML = `<pre style="white-space: pre-wrap; font-family: var(--font-mono);">${escapeHtml(docObj.content || '')}</pre>`;
    }
  }
}

async function renderDiffView(appId) {
  const origBox = document.getElementById('diff-original-content');
  const rewritBox = document.getElementById('diff-rewritten-content');

  origBox.innerHTML = 'Loading original...';
  rewritBox.innerHTML = 'Loading rewritten...';

  // Fetch source
  if (!state.docCache.source) {
    try {
      const res = await fetch(`/api/document/source/${appId}`);
      if (res.ok) {
        const json = await res.json();
        state.docCache.source = { type: 'text', content: json.content };
      }
    } catch (e) {}
  }

  // Fetch rewritten
  if (!state.docCache.rewritten) {
    try {
      const res = await fetch(`/api/document/rewritten/${appId}`);
      if (res.ok) {
        const json = await res.json();
        state.docCache.rewritten = { type: 'text', content: json.content };
      }
    } catch (e) {}
  }

  if (state.docCache.source && state.docCache.source.content) {
    origBox.innerHTML = window.marked ? window.marked.parse(state.docCache.source.content) : escapeHtml(state.docCache.source.content);
  } else {
    origBox.innerHTML = '<span style="color: var(--text-subtle);">Original source file not found or is binary PDF.</span>';
  }

  if (state.docCache.rewritten && state.docCache.rewritten.content) {
    rewritBox.innerHTML = window.marked ? window.marked.parse(state.docCache.rewritten.content) : escapeHtml(state.docCache.rewritten.content);
  } else {
    rewritBox.innerHTML = '<span style="color: var(--text-subtle);">Rewritten resume content not found.</span>';
  }
}

function copyToClipboard(text, successMsg = 'Copied to clipboard!') {
  if (!text || !text.trim()) {
    showToast('Nothing to copy.', 'info');
    return;
  }
  const clean = text.trim();
  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(clean)
      .then(() => showToast(successMsg, 'success'))
      .catch(() => fallbackCopy(clean, successMsg));
  } else {
    fallbackCopy(clean, successMsg);
  }
}

function fallbackCopy(text, successMsg) {
  try {
    const el = document.createElement('textarea');
    el.value = text;
    el.setAttribute('readonly', '');
    el.style.position = 'absolute';
    el.style.left = '-9999px';
    document.body.appendChild(el);
    el.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(el);
    if (ok) {
      showToast(successMsg, 'success');
    } else {
      showToast('Unable to copy text.', 'error');
    }
  } catch (err) {
    showToast('Copy failed.', 'error');
  }
}

function copyActiveDocument() {
  if (state.activeDocMode === 'referral') {
    copyReferralMessage();
    return;
  }
  const docType = state.activeDocMode === 'source' ? 'source' : 'rewritten';
  const cached = state.docCache[docType];
  if (cached && cached.content) {
    copyToClipboard(cached.content, 'Markdown copied to clipboard!');
  } else {
    showToast('No markdown text to copy.', 'info');
  }
}

function copyReferralMessage() {
  const msg = (state.activeDetail && state.activeDetail.referral_message) ||
              document.getElementById('modal-referral-message').textContent;
  copyToClipboard(msg, 'Referral message copied to clipboard!');
}

// --- Settings & Configuration Drawer ---
function openSettingsDrawer() {
  document.getElementById('drawer-settings-backdrop').classList.add('open');
  document.getElementById('drawer-settings').classList.add('open');
  loadConfig();
}

function closeSettingsDrawer(e) {
  if (e && e.target !== e.currentTarget && !e.target.classList.contains('drawer-backdrop')) return;
  document.getElementById('drawer-settings-backdrop').classList.remove('open');
  document.getElementById('drawer-settings').classList.remove('open');
}

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;

    const data = await res.json();
    const s = data.settings || {};

    document.getElementById('settings-file-badge').textContent = data.env_file_path || '~/.resume-rewriter/config.env';
    document.getElementById('cfg-ollama-url').value = s.OLLAMA_BASE_URL || '';
    document.getElementById('cfg-ollama-model').value = s.OLLAMA_MODEL || '';
    document.getElementById('cfg-pg-host').value = s.POSTGRES_HOST || '';
    document.getElementById('cfg-pg-port').value = s.POSTGRES_PORT || 5432;
    document.getElementById('cfg-pg-db').value = s.POSTGRES_DB || '';
    document.getElementById('cfg-pg-user').value = s.POSTGRES_USER || '';
    document.getElementById('cfg-pg-pass').value = s.POSTGRES_PASSWORD || '';
    document.getElementById('cfg-max-loops').value = s.MAX_LOOPS || 3;
    document.getElementById('cfg-rewriter-temp').value = s.REWRITER_TEMP !== undefined ? s.REWRITER_TEMP : 0.2;
    document.getElementById('cfg-recruiter-temp').value = s.RECRUITER_TEMP !== undefined ? s.RECRUITER_TEMP : 0.0;

  } catch (err) {
    console.warn('Failed to load system config', err);
  }
}

async function saveSystemConfig() {
  const payload = {
    OLLAMA_BASE_URL: document.getElementById('cfg-ollama-url').value.trim(),
    OLLAMA_MODEL: document.getElementById('cfg-ollama-model').value.trim(),
    POSTGRES_HOST: document.getElementById('cfg-pg-host').value.trim(),
    POSTGRES_PORT: parseInt(document.getElementById('cfg-pg-port').value) || 5432,
    POSTGRES_DB: document.getElementById('cfg-pg-db').value.trim(),
    POSTGRES_USER: document.getElementById('cfg-pg-user').value.trim(),
    POSTGRES_PASSWORD: document.getElementById('cfg-pg-pass').value,
    MAX_LOOPS: parseInt(document.getElementById('cfg-max-loops').value) || 3,
    REWRITER_TEMP: parseFloat(document.getElementById('cfg-rewriter-temp').value) || 0.2,
    RECRUITER_TEMP: parseFloat(document.getElementById('cfg-recruiter-temp').value) || 0.0,
  };

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error('Failed to save settings.');

    const data = await res.json();
    showToast(`Saved to ${data.env_file_path}`, 'success');
    closeSettingsDrawer();
    loadSystemHealth();

  } catch (err) {
    showToast(`Error saving config: ${err.message}`, 'error');
  }
}

async function testSystemConnections() {
  showToast('Testing PostgreSQL and Ollama connections...', 'info');

  const payload = {
    OLLAMA_BASE_URL: document.getElementById('cfg-ollama-url').value.trim(),
    OLLAMA_MODEL: document.getElementById('cfg-ollama-model').value.trim(),
    POSTGRES_HOST: document.getElementById('cfg-pg-host').value.trim(),
    POSTGRES_PORT: parseInt(document.getElementById('cfg-pg-port').value) || 5432,
    POSTGRES_DB: document.getElementById('cfg-pg-db').value.trim(),
    POSTGRES_USER: document.getElementById('cfg-pg-user').value.trim(),
    POSTGRES_PASSWORD: document.getElementById('cfg-pg-pass').value
  };

  try {
    const res = await fetch('/api/config/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    const pg = data.postgres;
    const ol = data.ollama;

    if (data.all_healthy) {
      showToast('All systems healthy! Postgres & Ollama connected.', 'success');
    } else {
      let msg = '';
      if (!pg.ok) msg += `Postgres: ${pg.message} `;
      if (!ol.ok) msg += `Ollama: ${ol.message}`;
      showToast(`Warning: ${msg}`, 'error');
    }

    updateHealthBadge(data.all_healthy, data.all_healthy ? 'System Ready' : 'Service Issue');

  } catch (err) {
    showToast(`Connectivity test failed: ${err.message}`, 'error');
  }
}

async function loadSystemHealth() {
  try {
    const res = await fetch('/api/config/test', { method: 'POST' });
    const data = await res.json();
    updateHealthBadge(data.all_healthy, data.all_healthy ? 'System Ready' : 'Service Issue');
  } catch (err) {
    updateHealthBadge(false, 'Offline');
  }
}

function updateHealthBadge(isHealthy, text) {
  const dot = document.getElementById('health-dot');
  const txt = document.getElementById('health-text');
  dot.className = `status-dot ${isHealthy ? '' : 'danger'}`;
  txt.textContent = text;
}

// --- Utilities ---
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const icon = type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ';
  toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
