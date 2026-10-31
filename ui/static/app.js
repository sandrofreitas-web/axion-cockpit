/**
 * Axion Cockpit — Frontend Application Controller
 * Gerencia a frota de projetos, visualização de documentação em tempo real,
 * renderização client-side de diagramas Mermaid.js e quadro Kanban de notas.
 */

// Inicializa o Mermaid.js com tema escuro adaptado
if (window.mermaid) {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    securityLevel: 'loose',
    themeVariables: {
      darkMode: true,
      background: '#0d1117',
      primaryColor: '#1f6feb',
      primaryTextColor: '#c9d1d9',
      primaryBorderColor: '#388bfd',
      lineColor: '#58a6ff',
      secondaryColor: '#161b22',
      tertiaryColor: '#21262d'
    }
  });
}

const state = {
  projects: [],
  selectedProjectId: null,
  selectedProjectData: null,
  docsData: null,
  notesData: [],
  activeTab: 'tab-techspec',
  viewMode: {
    workflows: 'diagram',
    database: 'diagram'
  }
};

// =============================================================================
// DOM Elements
// =============================================================================
const elements = {
  projectList: document.getElementById('project-list-container'),
  projectSearch: document.getElementById('project-search-input'),
  viewEmpty: document.getElementById('view-empty'),
  viewProject: document.getElementById('view-project'),
  breadcrumb: document.getElementById('active-project-breadcrumb'),
  
  // Banner
  projTitle: document.getElementById('proj-title'),
  projVersion: document.getElementById('proj-version'),
  projGitBranch: document.getElementById('proj-git-branch'),
  projGitDirty: document.getElementById('proj-git-dirty'),
  projPath: document.getElementById('proj-path'),
  projTags: document.getElementById('proj-tags'),
  
  // Tab Buttons
  tabButtons: document.querySelectorAll('.tab-btn'),
  tabPanes: document.querySelectorAll('.tab-pane'),
  countWorkflows: document.getElementById('count-workflows'),
  countDatabase: document.getElementById('count-database'),
  countNotes: document.getElementById('count-notes'),
  
  // Tab 1: Techspec
  techspecMarkdown: document.getElementById('techspec-markdown'),
  envIndicatorsList: document.getElementById('env-indicators-list'),
  docsFoundList: document.getElementById('docs-found-list'),
  gitTelemetryInfo: document.getElementById('git-telemetry-info'),
  
  // Tab 2: Workflows
  workflowsContainer: document.getElementById('workflows-diagram-container'),
  btnWfViewDiagram: document.getElementById('btn-wf-view-diagram'),
  btnWfViewRaw: document.getElementById('btn-wf-view-raw'),
  
  // Tab 3: Database
  databaseContainer: document.getElementById('database-diagram-container'),
  btnDbViewDiagram: document.getElementById('btn-db-view-diagram'),
  btnDbViewRaw: document.getElementById('btn-db-view-raw'),
  
  // Tab 4: Notes Kanban
  cardsIdea: document.getElementById('cards-idea'),
  cardsPlanned: document.getElementById('cards-planned'),
  cardsInReview: document.getElementById('cards-in_review'),
  cardsIncorporated: document.getElementById('cards-incorporated'),
  countColIdea: document.getElementById('count-col-idea'),
  countColPlanned: document.getElementById('count-col-planned'),
  countColInReview: document.getElementById('count-col-in_review'),
  countColIncorporated: document.getElementById('count-col-incorporated'),
  
  // Modals & Forms
  modalAddProject: document.getElementById('modal-add-project'),
  formAddProject: document.getElementById('form-add-project'),
  btnOpenAddProject: document.getElementById('btn-open-add-project'),
  btnEmptyAddProject: document.getElementById('btn-empty-add-project'),
  
  modalNote: document.getElementById('modal-note'),
  formNote: document.getElementById('form-note'),
  btnOpenAddNote: document.getElementById('btn-open-add-note'),
  btnDeleteNote: document.getElementById('btn-delete-note'),
  modalNoteTitle: document.getElementById('modal-note-title'),
  
  modalVersion: document.getElementById('modal-version'),
  formVersion: document.getElementById('form-version'),
  btnOpenVersionModal: document.getElementById('btn-open-version-modal'),
  versionNotesList: document.getElementById('version-notes-list'),
  versionInputNew: document.getElementById('version-input-new'),
  
  btnRefreshProject: document.getElementById('btn-refresh-project'),
  btnDeleteProject: document.getElementById('btn-delete-project')
};

// =============================================================================
// API Service Calls
// =============================================================================
const api = {
  async getProjects() {
    const res = await fetch('/api/projects');
    if (!res.ok) throw new Error('Falha ao listar projetos');
    return res.json();
  },

  async addProject(payload) {
    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Falha ao registrar projeto');
    return data;
  },

  async deleteProject(id) {
    const res = await fetch(`/api/projects/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Falha ao desvincular projeto');
    return res.json();
  },

  async getProjectDocs(id) {
    const res = await fetch(`/api/projects/${id}/docs`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Falha ao ler documentação');
    return data;
  },

  async getNotes(id) {
    const res = await fetch(`/api/projects/${id}/notes`);
    if (!res.ok) throw new Error('Falha ao ler notas');
    return res.json();
  },

  async saveNote(projectId, noteData, isEdit = false, noteId = null) {
    const url = isEdit ? `/api/projects/${projectId}/notes/${noteId}` : `/api/projects/${projectId}/notes`;
    const method = isEdit ? 'PUT' : 'POST';
    const res = await fetch(url, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(noteData)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Falha ao salvar nota');
    return data;
  },

  async deleteNote(projectId, noteId) {
    const res = await fetch(`/api/projects/${projectId}/notes/${noteId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Falha ao excluir nota');
    return res.json();
  },

  async updateVersion(projectId, version) {
    const res = await fetch(`/api/projects/${projectId}/version`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Falha ao atualizar versão');
    return data;
  }
};

// =============================================================================
// Rendering & UI Handlers
// =============================================================================

function renderProjectsSidebar() {
  const searchTerm = (elements.projectSearch.value || '').toLowerCase();
  const filtered = state.projects.filter(p => 
    p.name.toLowerCase().includes(searchTerm) || 
    p.path.toLowerCase().includes(searchTerm) ||
    (p.tags && p.tags.some(t => t.toLowerCase().includes(searchTerm)))
  );

  if (filtered.length === 0) {
    elements.projectList.innerHTML = `
      <div class="empty-list-notice">
        ${searchTerm ? 'Nenhum projeto encontrado no filtro.' : 'Nenhum projeto registrado.'}
      </div>
    `;
    return;
  }

  elements.projectList.innerHTML = filtered.map(p => {
    const isSelected = p.id === state.selectedProjectId;
    const isDirty = p.git && p.git.is_dirty;
    const branch = (p.git && p.git.branch) ? p.git.branch : 'no-git';
    const accessible = p.accessible !== false;

    return `
      <div class="project-item ${isSelected ? 'active' : ''} ${!accessible ? 'inaccessible' : ''}" data-id="${p.id}">
        <div class="proj-item-header">
          <strong class="proj-item-name">${escapeHtml(p.name)}</strong>
          <span class="proj-item-version">${escapeHtml(p.current_version || 'v1.0.0')}</span>
        </div>
        <div class="proj-item-path" title="${escapeHtml(p.path)}">${escapeHtml(p.path)}</div>
        <div class="proj-item-meta">
          <span class="meta-tag git-tag"><span class="git-icon">🌿</span> ${escapeHtml(branch)}</span>
          ${isDirty ? `<span class="meta-tag dirty-tag">● ${p.git.uncommitted_count} pendente(s)</span>` : ''}
          ${!accessible ? `<span class="meta-tag error-tag">Inacessível</span>` : ''}
        </div>
      </div>
    `;
  }).join('');

  // Bind click
  elements.projectList.querySelectorAll('.project-item').forEach(el => {
    el.addEventListener('click', () => {
      const id = el.getAttribute('data-id');
      selectProject(id);
    });
  });
}

async function selectProject(projectId) {
  state.selectedProjectId = projectId;
  state.selectedProjectData = state.projects.find(p => p.id === projectId);
  renderProjectsSidebar();

  if (!state.selectedProjectData) {
    elements.viewEmpty.style.display = 'block';
    elements.viewProject.style.display = 'none';
    elements.breadcrumb.textContent = 'Nenhum projeto selecionado';
    return;
  }

  elements.viewEmpty.style.display = 'none';
  elements.viewProject.style.display = 'block';
  elements.breadcrumb.textContent = state.selectedProjectData.name;

  // Banner
  elements.projTitle.textContent = state.selectedProjectData.name;
  elements.projVersion.textContent = state.selectedProjectData.current_version || 'v1.0.0';
  elements.projPath.textContent = state.selectedProjectData.path;

  const git = state.selectedProjectData.git || {};
  elements.projGitBranch.innerHTML = `<span class="git-icon">🌿</span> ${escapeHtml(git.branch || 'no-git')}`;
  if (git.is_dirty) {
    elements.projGitDirty.style.display = 'inline-flex';
    elements.projGitDirty.textContent = `● ${git.uncommitted_count} arquivos alterados`;
  } else {
    elements.projGitDirty.style.display = 'none';
  }

  // Tags
  const tags = state.selectedProjectData.tags || [];
  elements.projTags.innerHTML = tags.map(t => `<span class="tag-pill">${escapeHtml(t)}</span>`).join('');

  // Carrega Dados do Projeto (Docs & Notas em paralelo)
  await Promise.all([
    loadDocs(projectId),
    loadNotes(projectId)
  ]);
}

async function loadDocs(projectId) {
  elements.techspecMarkdown.innerHTML = `<p class="muted-text">Carregando documentação viva do disco...</p>`;
  elements.workflowsContainer.innerHTML = `<p class="muted-text">Lendo diagramas...</p>`;
  elements.databaseContainer.innerHTML = `<p class="muted-text">Lendo esquemas relacionais...</p>`;

  try {
    const docs = await api.getProjectDocs(projectId);
    state.docsData = docs;

    // Badges de Contagem
    elements.countWorkflows.textContent = docs.workflows.length;
    elements.countDatabase.textContent = docs.database.length;

    // Tab 1: Render Techspec Markdown
    if (docs.primary_doc) {
      if (window.marked) {
        elements.techspecMarkdown.innerHTML = marked.parse(docs.primary_doc);
      } else {
        elements.techspecMarkdown.innerHTML = `<pre>${escapeHtml(docs.primary_doc)}</pre>`;
      }
    } else {
      elements.techspecMarkdown.innerHTML = `
        <div class="empty-docs-box">
          <h3>Nenhuma documentação formal detectada</h3>
          <p>O OS procurou por <code>ARCHITECTURE.md</code>, <code>TECHSPEC.md</code> ou <code>README.md</code> neste diretório.</p>
          <p>Você pode criar um arquivo <code>ARCHITECTURE.md</code> no projeto usando nosso template padrão.</p>
        </div>
      `;
    }

    // Sidebar de Metadados da Tab 1
    renderEnvIndicators(docs.env_indicators);
    renderDocsFound(docs.files_found);
    renderGitTelemetry(docs.git);

    // Tab 2: Render Workflows
    renderMermaidSection(elements.workflowsContainer, docs.workflows, state.viewMode.workflows, 'wf');

    // Tab 3: Render Database ERD
    renderMermaidSection(elements.databaseContainer, docs.database, state.viewMode.database, 'db');

  } catch (err) {
    elements.techspecMarkdown.innerHTML = `<div class="error-box">Erro ao ler documentação: ${escapeHtml(err.message)}</div>`;
  }
}

function renderEnvIndicators(env) {
  if (!env) {
    elements.envIndicatorsList.innerHTML = '<li>Nenhum manifesto detectado</li>';
    return;
  }
  const items = [
    { label: 'Python (pyproject.toml)', active: env.has_pyproject },
    { label: 'Node.js (package.json)', active: env.has_package_json },
    { label: 'Docker (Dockerfile)', active: env.has_dockerfile },
    { label: 'Docker Compose', active: env.has_compose },
    { label: 'Prisma ORM (schema.prisma)', active: env.has_prisma },
  ];
  elements.envIndicatorsList.innerHTML = items.map(it => `
    <li class="${it.active ? 'active' : 'inactive'}">
      <span class="bullet">${it.active ? '✓' : '—'}</span>
      <span>${it.label}</span>
    </li>
  `).join('');
}

function renderDocsFound(files) {
  if (!files || files.length === 0) {
    elements.docsFoundList.innerHTML = '<li>Nenhum arquivo encontrado</li>';
    return;
  }
  elements.docsFoundList.innerHTML = files.map(f => `
    <li>
      <span class="doc-name">📄 ${escapeHtml(f.relative_path)}</span>
      <span class="doc-size">${formatBytes(f.size_bytes)}</span>
    </li>
  `).join('');
}

function renderGitTelemetry(git) {
  if (!git || !git.is_repo) {
    elements.gitTelemetryInfo.innerHTML = '<p class="muted-text">Diretório não é um repositório Git.</p>';
    return;
  }
  elements.gitTelemetryInfo.innerHTML = `
    <div class="telemetry-item">
      <span>Branch Atual:</span>
      <strong>${escapeHtml(git.branch || 'unknown')}</strong>
    </div>
    <div class="telemetry-item">
      <span>Arquivos Alterados:</span>
      <strong class="${git.is_dirty ? 'text-warning' : 'text-success'}">${git.uncommitted_count}</strong>
    </div>
    ${git.last_commit ? `
      <div class="telemetry-item">
        <span>Último Commit:</span>
        <small class="mono-text">${escapeHtml(git.last_commit)}</small>
      </div>
    ` : ''}
  `;
}

async function renderMermaidSection(container, blocks, viewMode, prefix) {
  if (!blocks || blocks.length === 0) {
    container.innerHTML = `<div class="empty-diagram-notice">Nenhum bloco de diagrama encontrado na documentação deste projeto.</div>`;
    return;
  }

  let html = '';
  blocks.forEach((b, index) => {
    const blockId = `${prefix}-diagram-${index}`;
    html += `
      <div class="diagram-card">
        <div class="diagram-card-header">
          <span class="source-file">Origem: <code>${escapeHtml(b.source_file || 'docs')}</code></span>
          <span class="diagram-type-pill">${escapeHtml(b.type)}</span>
        </div>
        <div class="diagram-render-area" id="${blockId}-area">
          ${viewMode === 'raw' ? `
            <pre class="raw-code-box"><code>${escapeHtml(b.code)}</code></pre>
          ` : `
            <div class="mermaid-target" id="${blockId}">
              <div class="diagram-loading">Renderizando diagrama...</div>
            </div>
          `}
        </div>
      </div>
    `;
  });
  container.innerHTML = html;

  if (viewMode === 'diagram' && window.mermaid) {
    blocks.forEach(async (b, index) => {
      const blockId = `${prefix}-diagram-${index}`;
      const target = document.getElementById(blockId);
      if (!target) return;
      try {
        const renderId = `svg-${blockId}-${Date.now()}`;
        const { svg } = await mermaid.render(renderId, b.code);
        target.innerHTML = svg;
      } catch (err) {
        target.innerHTML = `
          <div class="mermaid-error-box">
            <h4>⚠️ Erro na sintaxe do diagrama Mermaid</h4>
            <p>${escapeHtml(err.message || 'Sintaxe inválida')}</p>
            <pre class="raw-code-box"><code>${escapeHtml(b.code)}</code></pre>
          </div>
        `;
      }
    });
  }
}

async function loadNotes(projectId) {
  try {
    const notes = await api.getNotes(projectId);
    state.notesData = notes;
    elements.countNotes.textContent = notes.length;
    renderNotesKanban(notes);
  } catch (err) {
    console.error('Erro ao ler notas:', err);
  }
}

function renderNotesKanban(notes) {
  const cols = {
    idea: [],
    planned: [],
    in_review: [],
    incorporated: []
  };

  notes.forEach(n => {
    const st = (n.status || 'idea').toLowerCase();
    if (cols[st]) cols[st].push(n);
    else cols.idea.push(n);
  });

  // Atualiza contadores
  elements.countColIdea.textContent = cols.idea.length;
  elements.countColPlanned.textContent = cols.planned.length;
  elements.countColInReview.textContent = cols.in_review.length;
  elements.countColIncorporated.textContent = cols.incorporated.length;

  const renderCard = (n) => `
    <div class="note-card" data-note-id="${n.id}">
      <div class="note-card-title">${escapeHtml(n.title)}</div>
      ${n.version_target ? `<div class="note-card-version">Alvo: ${escapeHtml(n.version_target)}</div>` : ''}
      <div class="note-card-excerpt">${escapeHtml(n.content ? n.content.substring(0, 100) : '')}</div>
      <div class="note-card-footer">
        <span class="note-date">${n.created_at ? n.created_at.substring(0, 10) : ''}</span>
        <button class="btn-card-edit" title="Editar">✏️</button>
      </div>
    </div>
  `;

  elements.cardsIdea.innerHTML = cols.idea.map(renderCard).join('') || '<div class="kanban-empty">Sem notas</div>';
  elements.cardsPlanned.innerHTML = cols.planned.map(renderCard).join('') || '<div class="kanban-empty">Sem notas</div>';
  elements.cardsInReview.innerHTML = cols.in_review.map(renderCard).join('') || '<div class="kanban-empty">Sem notas</div>';
  elements.cardsIncorporated.innerHTML = cols.incorporated.map(renderCard).join('') || '<div class="kanban-empty">Sem notas</div>';

  // Bind edit clicks
  document.querySelectorAll('.note-card').forEach(card => {
    card.addEventListener('click', () => {
      const noteId = card.getAttribute('data-note-id');
      const note = state.notesData.find(n => n.id === noteId);
      if (note) openNoteModal(note);
    });
  });
}

function openNoteModal(note = null) {
  const isEdit = !!note;
  elements.modalNoteTitle.textContent = isEdit ? 'Editar Nota de Melhoria' : 'Nova Nota de Melhoria';
  document.getElementById('note-input-id').value = isEdit ? note.id : '';
  document.getElementById('note-input-title').value = isEdit ? note.title : '';
  document.getElementById('note-input-status').value = isEdit ? note.status : 'idea';
  document.getElementById('note-input-version-target').value = isEdit ? (note.version_target || '') : (state.selectedProjectData.current_version || '');
  document.getElementById('note-input-target-files').value = isEdit && note.target_files ? note.target_files.join(', ') : '';
  document.getElementById('note-input-content').value = isEdit ? (note.content || '') : '';
  elements.btnDeleteNote.style.display = isEdit ? 'inline-flex' : 'none';
  elements.modalNote.style.display = 'flex';
}

function closeAllModals() {
  document.querySelectorAll('.modal-overlay').forEach(m => m.style.display = 'none');
}

// =============================================================================
// Event Listeners Setup
// =============================================================================

function setupEvents() {
  // Tabs Navigation
  elements.tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      state.activeTab = targetTab;
      elements.tabButtons.forEach(b => b.classList.remove('active'));
      elements.tabPanes.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(targetTab).classList.add('active');
    });
  });

  // Search filter
  elements.projectSearch.addEventListener('input', () => {
    renderProjectsSidebar();
  });

  // View toggles para Workflows
  elements.btnWfViewDiagram.addEventListener('click', () => {
    state.viewMode.workflows = 'diagram';
    elements.btnWfViewDiagram.classList.add('active');
    elements.btnWfViewRaw.classList.remove('active');
    if (state.docsData) renderMermaidSection(elements.workflowsContainer, state.docsData.workflows, 'diagram', 'wf');
  });
  elements.btnWfViewRaw.addEventListener('click', () => {
    state.viewMode.workflows = 'raw';
    elements.btnWfViewRaw.classList.add('active');
    elements.btnWfViewDiagram.classList.remove('active');
    if (state.docsData) renderMermaidSection(elements.workflowsContainer, state.docsData.workflows, 'raw', 'wf');
  });

  // View toggles para Database
  elements.btnDbViewDiagram.addEventListener('click', () => {
    state.viewMode.database = 'diagram';
    elements.btnDbViewDiagram.classList.add('active');
    elements.btnDbViewRaw.classList.remove('active');
    if (state.docsData) renderMermaidSection(elements.databaseContainer, state.docsData.database, 'diagram', 'db');
  });
  elements.btnDbViewRaw.addEventListener('click', () => {
    state.viewMode.database = 'raw';
    elements.btnDbViewRaw.classList.add('active');
    elements.btnDbViewDiagram.classList.remove('active');
    if (state.docsData) renderMermaidSection(elements.databaseContainer, state.docsData.database, 'raw', 'db');
  });

  // Modals Open
  const openAddProjectModal = () => { elements.modalAddProject.style.display = 'flex'; };
  elements.btnOpenAddProject.addEventListener('click', openAddProjectModal);
  elements.btnEmptyAddProject.addEventListener('click', openAddProjectModal);
  elements.btnOpenAddNote.addEventListener('click', () => openNoteModal(null));

  elements.btnOpenVersionModal.addEventListener('click', () => {
    if (!state.selectedProjectData) return;
    elements.versionInputNew.value = state.selectedProjectData.current_version || 'v1.1.0';
    const incorporated = state.notesData.filter(n => n.status === 'incorporated');
    if (incorporated.length > 0) {
      elements.versionNotesList.innerHTML = incorporated.map(n => `<li>✓ ${escapeHtml(n.title)}</li>`).join('');
    } else {
      elements.versionNotesList.innerHTML = '<li class="muted-text">Nenhuma nota marcada como incorporada ainda.</li>';
    }
    elements.modalVersion.style.display = 'flex';
  });

  // Modals Close
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.getAttribute('data-close-modal');
      const m = document.getElementById(modalId);
      if (m) m.style.display = 'none';
    });
  });

  // Submit Add Project
  elements.formAddProject.addEventListener('submit', async (e) => {
    e.preventDefault();
    const rawPath = document.getElementById('proj-input-path').value.trim();
    const name = document.getElementById('proj-input-name').value.trim();
    const version = document.getElementById('proj-input-version').value.trim();
    const tagsRaw = document.getElementById('proj-input-tags').value.trim();
    const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];

    try {
      const created = await api.addProject({ path: rawPath, name, version, tags });
      closeAllModals();
      elements.formAddProject.reset();
      await init();
      selectProject(created.id);
    } catch (err) {
      alert('Erro: ' + err.message);
    }
  });

  // Submit Note Form
  elements.formNote.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!state.selectedProjectId) return;
    const noteId = document.getElementById('note-input-id').value;
    const title = document.getElementById('note-input-title').value.trim();
    const status = document.getElementById('note-input-status').value;
    const version_target = document.getElementById('note-input-version-target').value.trim();
    const targetFilesRaw = document.getElementById('note-input-target-files').value.trim();
    const target_files = targetFilesRaw ? targetFilesRaw.split(',').map(f => f.trim()).filter(Boolean) : [];
    const content = document.getElementById('note-input-content').value;

    const isEdit = !!noteId;
    try {
      await api.saveNote(state.selectedProjectId, {
        title,
        status,
        version_target,
        target_files,
        content
      }, isEdit, noteId);
      closeAllModals();
      await loadNotes(state.selectedProjectId);
    } catch (err) {
      alert('Erro ao salvar nota: ' + err.message);
    }
  });

  // Delete Note Button
  elements.btnDeleteNote.addEventListener('click', async () => {
    const noteId = document.getElementById('note-input-id').value;
    if (!noteId || !state.selectedProjectId) return;
    if (!confirm('Deseja realmente excluir esta anotação?')) return;
    try {
      await api.deleteNote(state.selectedProjectId, noteId);
      closeAllModals();
      await loadNotes(state.selectedProjectId);
    } catch (err) {
      alert('Erro ao excluir nota: ' + err.message);
    }
  });

  // Submit Version Bump Form
  elements.formVersion.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (!state.selectedProjectId) return;
    const newVersion = elements.versionInputNew.value.trim();
    if (!newVersion) return;
    try {
      await api.updateVersion(state.selectedProjectId, newVersion);
      closeAllModals();
      await init();
      selectProject(state.selectedProjectId);
    } catch (err) {
      alert('Erro ao atualizar versão: ' + err.message);
    }
  });

  // Refresh Docs Button
  elements.btnRefreshProject.addEventListener('click', () => {
    if (state.selectedProjectId) {
      loadDocs(state.selectedProjectId);
      loadNotes(state.selectedProjectId);
    }
  });

  // Delete Project Button
  elements.btnDeleteProject.addEventListener('click', async () => {
    if (!state.selectedProjectId || !state.selectedProjectData) return;
    const confirmMsg = `Deseja desvincular o projeto "${state.selectedProjectData.name}" do OS?\n(A pasta em disco NÃO será excluída).`;
    if (!confirm(confirmMsg)) return;
    try {
      await api.deleteProject(state.selectedProjectId);
      state.selectedProjectId = null;
      await init();
      if (state.projects.length > 0) {
        selectProject(state.projects[0].id);
      } else {
        elements.viewEmpty.style.display = 'block';
        elements.viewProject.style.display = 'none';
        elements.breadcrumb.textContent = 'Nenhum projeto selecionado';
      }
    } catch (err) {
      alert('Erro ao remover projeto: ' + err.message);
    }
  });
}

// =============================================================================
// Helpers
// =============================================================================
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// =============================================================================
// Bootstrap
// =============================================================================
async function init() {
  try {
    state.projects = await api.getProjects();
    renderProjectsSidebar();
    if (state.projects.length > 0 && !state.selectedProjectId) {
      selectProject(state.projects[0].id);
    } else if (state.selectedProjectId) {
      selectProject(state.selectedProjectId);
    }
  } catch (err) {
    console.error('Falha ao inicializar Axion Cockpit:', err);
    elements.projectList.innerHTML = `<div class="error-box">Erro ao conectar com a API: ${escapeHtml(err.message)}</div>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupEvents();
  init();
});
