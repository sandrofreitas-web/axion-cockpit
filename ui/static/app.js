/**
 * Axion Cockpit — Frontend Application Controller
 * Gerencia a frota de projetos, visualização de documentação em tempo real,
 * renderização client-side de diagramas Mermaid.js e quadro Kanban de notas.
 */

// Inicializa o Mermaid.js com tema escuro adaptado e renderização em tamanho real
if (window.mermaid) {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    securityLevel: 'loose',
    flowchart: {
      useMaxWidth: false,
      htmlLabels: true,
      curve: 'basis'
    },
    sequence: {
      useMaxWidth: false,
      showSequenceNumbers: true,
      actorFontSize: 14,
      messageFontSize: 13
    },
    er: {
      useMaxWidth: false,
      fontSize: 13
    },
    themeVariables: {
      darkMode: true,
      background: '#0d1117',
      primaryColor: '#161b22',
      primaryTextColor: '#f0f6fc',
      primaryBorderColor: '#388bfd',
      lineColor: '#58a6ff',
      secondaryColor: '#21262d',
      tertiaryColor: '#161b22',
      mainBkg: '#161b22',
      nodeBorder: '#388bfd',
      nodeTextColor: '#f0f6fc',
      clusterBkg: '#0d1117',
      clusterBorder: '#30363d',
      titleColor: '#58a6ff',
      edgeLabelBackground: '#161b22',
      actorBorder: '#388bfd',
      actorBkg: '#161b22',
      actorTextColor: '#f0f6fc',
      actorLineColor: '#58a6ff',
      signalColor: '#58a6ff',
      signalTextColor: '#f0f6fc',
      labelBoxBkgColor: '#161b22',
      labelBoxBorderColor: '#388bfd',
      labelTextColor: '#f0f6fc',
      loopTextColor: '#f0f6fc',
      noteBorderColor: '#d29922',
      noteBkgColor: '#272015',
      noteTextColor: '#f0f6fc',
      fontSize: '14px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
    }
  });
}

// Controlador de Pan & Zoom para Viewports Mermaid
class DiagramPanZoom {
  constructor(viewportEl, canvasEl, onScaleChange) {
    this.viewport = viewportEl;
    this.canvas = canvasEl;
    this.onScaleChange = onScaleChange;
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.isDragging = false;
    this.startX = 0;
    this.startY = 0;
    this.setupEvents();
  }

  updateTransform(smooth = false) {
    this.canvas.style.transition = smooth ? 'transform 0.15s ease-out' : 'none';
    this.canvas.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
    if (this.onScaleChange) {
      this.onScaleChange(this.scale);
    }
  }

  zoomIn(step = 0.25) {
    this.scale = Math.min(3.5, Math.round((this.scale + step) * 100) / 100);
    this.updateTransform(true);
  }

  zoomOut(step = 0.25) {
    this.scale = Math.max(0.3, Math.round((this.scale - step) * 100) / 100);
    this.updateTransform(true);
  }

  reset() {
    this.scale = 1.0;
    this.panX = 0;
    this.panY = 0;
    this.updateTransform(true);
  }

  fitToViewport() {
    const svg = this.canvas.querySelector('svg');
    if (!svg) return;
    const vpRect = this.viewport.getBoundingClientRect();
    const svgBBox = svg.getBBox ? svg.getBBox() : null;
    const w = (svgBBox && svgBBox.width > 0) ? svgBBox.width : (svg.clientWidth || 800);
    const h = (svgBBox && svgBBox.height > 0) ? svgBBox.height : (svg.clientHeight || 500);

    if (w > 0 && h > 0 && vpRect.width > 0 && vpRect.height > 0) {
      const availW = vpRect.width - 64;
      const availH = vpRect.height - 64;
      const ratio = Math.min(availW / w, availH / h, 1.25);
      this.scale = Math.max(0.4, Math.min(1.5, Math.round(ratio * 100) / 100));
      this.panX = 0;
      this.panY = 0;
      this.updateTransform(true);
    }
  }

  setupEvents() {
    this.viewport.addEventListener('mousedown', (e) => {
      if (e.button !== 0) return;
      this.isDragging = true;
      this.viewport.classList.add('is-dragging');
      this.startX = e.clientX - this.panX;
      this.startY = e.clientY - this.panY;
    });

    window.addEventListener('mousemove', (e) => {
      if (!this.isDragging) return;
      this.panX = e.clientX - this.startX;
      this.panY = e.clientY - this.startY;
      this.updateTransform(false);
    });

    window.addEventListener('mouseup', () => {
      if (this.isDragging) {
        this.isDragging = false;
        this.viewport.classList.remove('is-dragging');
      }
    });

    // Zoom com a roda do mouse
    this.viewport.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY < 0 ? 0.15 : -0.15;
      const newScale = Math.max(0.3, Math.min(3.5, this.scale + delta));
      this.scale = Math.round(newScale * 100) / 100;
      this.updateTransform(false);
    }, { passive: false });

    // Duplo clique para ajustar
    this.viewport.addEventListener('dblclick', () => {
      this.fitToViewport();
    });
  }
}

// Registro global de controladores de PanZoom
const activePanZooms = new Map();
let fullscreenPanZoom = null;

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

  async discoverProjects() {
    try {
      const res = await fetch('/api/projects/discover');
      if (!res.ok) return [];
      return await res.json();
    } catch {
      return [];
    }
  },

  async browsePath(subpath = '') {
    try {
      const q = subpath ? `?path=${encodeURIComponent(subpath)}` : '';
      const res = await fetch(`/api/system/browse${q}`);
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
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

  async ingestProject(payload) {
    const res = await fetch('/api/projects/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Falha ao ingerir projeto');
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

  // Limpa instâncias antigas de pan-zoom deste prefixo
  for (const [k, v] of activePanZooms.entries()) {
    if (k.startsWith(prefix)) {
      activePanZooms.delete(k);
    }
  }

  let html = '';
  blocks.forEach((b, index) => {
    const blockId = `${prefix}-diagram-${index}`;
    html += `
      <div class="diagram-card" id="${blockId}-card">
        <div class="diagram-card-header">
          <div class="diagram-header-info">
            <span class="source-file">Origem: <code>${escapeHtml(b.source_file || 'docs')}</code></span>
            <span class="diagram-type-pill">${escapeHtml(b.type)}</span>
          </div>
          ${viewMode === 'diagram' ? `
            <div class="diagram-toolbar-controls">
              <button type="button" class="diagram-tool-btn" data-action="zoom-out" data-target="${blockId}" title="Diminuir Zoom">🔍−</button>
              <span class="zoom-level-badge" id="${blockId}-zoom-badge">100%</span>
              <button type="button" class="diagram-tool-btn" data-action="zoom-in" data-target="${blockId}" title="Aumentar Zoom">🔍+</button>
              <button type="button" class="diagram-tool-btn" data-action="fit" data-target="${blockId}" title="Ajustar à tela">Ajustar</button>
              <button type="button" class="diagram-tool-btn" data-action="fullscreen" data-target="${blockId}" title="Visualizar em Tela Cheia">⛶ Tela Cheia</button>
              <button type="button" class="diagram-tool-btn" data-action="copy" data-target="${blockId}" title="Copiar código Mermaid">📋 Copiar</button>
            </div>
          ` : ''}
        </div>
        <div class="diagram-render-area" id="${blockId}-area">
          ${viewMode === 'raw' ? `
            <pre class="raw-code-box"><code>${escapeHtml(b.code)}</code></pre>
          ` : `
            <div class="diagram-canvas" id="${blockId}-canvas">
              <div class="diagram-loading">Renderizando diagrama...</div>
            </div>
            <div class="diagram-viewport-hint">Arraste para mover • Scroll para zoom • Duplo clique para ajustar</div>
          `}
        </div>
      </div>
    `;
  });
  container.innerHTML = html;

  if (viewMode === 'diagram' && window.mermaid) {
    blocks.forEach(async (b, index) => {
      const blockId = `${prefix}-diagram-${index}`;
      const areaEl = document.getElementById(`${blockId}-area`);
      const canvasEl = document.getElementById(`${blockId}-canvas`);
      const badgeEl = document.getElementById(`${blockId}-zoom-badge`);
      if (!canvasEl || !areaEl) return;

      try {
        const renderId = `svg-${blockId}-${Date.now()}`;
        const { svg } = await mermaid.render(renderId, b.code);
        canvasEl.innerHTML = svg;

        // Configura Pan & Zoom com escala automática
        const panZoom = new DiagramPanZoom(areaEl, canvasEl, (scale) => {
          if (badgeEl) badgeEl.textContent = `${Math.round(scale * 100)}%`;
        });
        activePanZooms.set(blockId, { panZoom, block: b, svg });
        setTimeout(() => panZoom.fitToViewport(), 40);

      } catch (err) {
        canvasEl.innerHTML = `
          <div class="mermaid-error-box">
            <h4>⚠️ Erro na sintaxe do diagrama Mermaid</h4>
            <p>${escapeHtml(err.message || 'Sintaxe inválida')}</p>
            <pre class="raw-code-box"><code>${escapeHtml(b.code)}</code></pre>
          </div>
        `;
      }
    });

    // Event Delegation para a toolbar dos cards
    container.querySelectorAll('.diagram-tool-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const action = btn.getAttribute('data-action');
        const targetId = btn.getAttribute('data-target');
        const entry = activePanZooms.get(targetId);
        if (!entry) return;

        if (action === 'zoom-in') entry.panZoom.zoomIn();
        else if (action === 'zoom-out') entry.panZoom.zoomOut();
        else if (action === 'fit') entry.panZoom.fitToViewport();
        else if (action === 'fullscreen') openFullscreenDiagram(entry.block, entry.svg);
        else if (action === 'copy') {
          navigator.clipboard.writeText(entry.block.code).then(() => {
            const original = btn.innerHTML;
            btn.innerHTML = '✓ Copiado!';
            setTimeout(() => { btn.innerHTML = original; }, 1500);
          });
        }
      });
    });
  }
}

function openFullscreenDiagram(block, svgHtml) {
  const modal = document.getElementById('modal-diagram-fullscreen');
  const canvas = document.getElementById('fs-diagram-canvas');
  const viewport = document.getElementById('fs-diagram-viewport');
  const badge = document.getElementById('fs-zoom-badge');
  const typeEl = document.getElementById('fs-diagram-type');
  const sourceEl = document.getElementById('fs-diagram-source');
  const copyBtn = document.getElementById('btn-fs-copy-code');
  if (!modal || !canvas || !viewport) return;

  typeEl.textContent = block.type || 'diagram';
  sourceEl.innerHTML = `Origem: <code>${escapeHtml(block.source_file || 'docs')}</code>`;
  canvas.innerHTML = svgHtml;
  modal.style.display = 'flex';

  fullscreenPanZoom = new DiagramPanZoom(viewport, canvas, (scale) => {
    if (badge) badge.textContent = `${Math.round(scale * 100)}%`;
  });

  setTimeout(() => {
    fullscreenPanZoom.fitToViewport();
  }, 50);

  // Bind botões do modal de tela cheia
  const btnZoomIn = document.getElementById('btn-fs-zoom-in');
  const btnZoomOut = document.getElementById('btn-fs-zoom-out');
  const btnReset = document.getElementById('btn-fs-zoom-reset');

  btnZoomIn.onclick = () => fullscreenPanZoom && fullscreenPanZoom.zoomIn();
  btnZoomOut.onclick = () => fullscreenPanZoom && fullscreenPanZoom.zoomOut();
  btnReset.onclick = () => fullscreenPanZoom && fullscreenPanZoom.fitToViewport();
  if (copyBtn) {
    copyBtn.onclick = () => {
      navigator.clipboard.writeText(block.code).then(() => {
        copyBtn.textContent = '✓ Copiado!';
        setTimeout(() => { copyBtn.textContent = '📋 Copiar'; }, 1500);
      });
    };
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

  // Navegador de Pastas do Disco
  let currentBrowsePath = '';
  let currentBrowseData = null;

  async function loadFolderBrowser(subpath = '') {
    const container = document.getElementById('browser-list-container');
    const breadcrumb = document.getElementById('browser-current-display');
    const btnUp = document.getElementById('browser-btn-up');
    if (!container) return;

    container.innerHTML = '<div class="browser-loading">Carregando pastas...</div>';
    const data = await api.browsePath(subpath);
    if (!data) {
      container.innerHTML = '<div class="browser-empty">Não foi possível ler as pastas.</div>';
      return;
    }

    currentBrowsePath = data.current_rel || '';
    currentBrowseData = data;

    if (breadcrumb) {
      breadcrumb.textContent = data.current_display || 'C:\\Docker';
    }
    if (btnUp) {
      btnUp.disabled = data.is_root;
    }

    if (!data.folders || data.folders.length === 0) {
      container.innerHTML = '<div class="browser-empty">Nenhuma subpasta encontrada neste nível.</div>';
      return;
    }

    container.innerHTML = data.folders.map(f => `
      <div class="browser-folder-item" data-folder-path="${escapeHtml(f.rel_path)}" data-folder-name="${escapeHtml(f.name)}" data-host-path="${escapeHtml(f.host_path)}">
        <div class="folder-name">
          <span>📁</span>
          <span>${escapeHtml(f.name)}</span>
          ${f.has_subfolders ? '<small style="font-size:10px; color:var(--text-muted);">(subpastas)</small>' : ''}
        </div>
        <div class="folder-actions">
          <button type="button" class="btn-folder-select" data-select-path="${escapeHtml(f.rel_path)}" data-select-name="${escapeHtml(f.name)}" title="Selecionar esta pasta">
            ✓ Selecionar
          </button>
        </div>
      </div>
    `).join('');

    container.querySelectorAll('.browser-folder-item').forEach(el => {
      el.addEventListener('click', (e) => {
        if (e.target.closest('.btn-folder-select')) return;
        const nextPath = el.getAttribute('data-folder-path');
        loadFolderBrowser(nextPath);
      });

      const selectBtn = el.querySelector('.btn-folder-select');
      if (selectBtn) {
        selectBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const folderRel = selectBtn.getAttribute('data-select-path');
          const folderName = selectBtn.getAttribute('data-select-name');
          applySelectedFolder(folderRel, folderName);
        });
      }
    });
  }

  function applySelectedFolder(folderPath, folderName) {
    const pathInput = document.getElementById('proj-input-path');
    const nameInput = document.getElementById('proj-input-name');
    if (pathInput) pathInput.value = folderPath;
    if (nameInput && !nameInput.value) {
      nameInput.value = folderName.split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    }
    const drawer = document.getElementById('folder-browser-drawer');
    if (drawer) drawer.style.display = 'none';
  }

  // Eventos do Navegador de Pastas
  const btnBrowse = document.getElementById('btn-browse-folders');
  const browserDrawer = document.getElementById('folder-browser-drawer');
  const btnBrowserUp = document.getElementById('browser-btn-up');
  const btnBrowserSelectCurrent = document.getElementById('browser-btn-select-current');

  if (btnBrowse && browserDrawer) {
    btnBrowse.addEventListener('click', () => {
      const isVisible = browserDrawer.style.display !== 'none';
      if (isVisible) {
        browserDrawer.style.display = 'none';
      } else {
        browserDrawer.style.display = 'block';
        loadFolderBrowser(currentBrowsePath);
      }
    });
  }

  if (btnBrowserUp) {
    btnBrowserUp.addEventListener('click', () => {
      if (currentBrowseData && currentBrowseData.parent_rel !== undefined) {
        loadFolderBrowser(currentBrowseData.parent_rel);
      }
    });
  }

  if (btnBrowserSelectCurrent) {
    btnBrowserSelectCurrent.addEventListener('click', () => {
      if (currentBrowseData) {
        const folderName = currentBrowsePath ? currentBrowsePath.split('/').pop() : 'Docker';
        applySelectedFolder(currentBrowsePath || '.', folderName);
      }
    });
  }

  // Estado de Ingestão de Pasta do Windows
  let currentIngestedDocs = {};
  let currentIngestedManifests = {};
  let selectedFolderBaseName = '';

  const nativeFolderPicker = document.getElementById('native-folder-picker');
  const btnTriggerPicker = document.getElementById('btn-trigger-picker');
  const pickerZone = document.getElementById('ingest-picker-zone');
  const selectedCard = document.getElementById('ingest-selected-card');
  const btnChangeFolder = document.getElementById('btn-change-folder');
  const folderNameEl = document.getElementById('ingest-folder-name');
  const docsCountEl = document.getElementById('ingest-docs-count');
  const docsChipsEl = document.getElementById('ingest-docs-chips');
  const submitIngestBtn = document.getElementById('btn-submit-ingest');
  const nameInput = document.getElementById('proj-input-name');
  const pathInput = document.getElementById('proj-input-path');

  function resetIngestModal() {
    currentIngestedDocs = {};
    currentIngestedManifests = {};
    selectedFolderBaseName = '';
    if (pickerZone) pickerZone.style.display = 'block';
    if (selectedCard) selectedCard.style.display = 'none';
    if (submitIngestBtn) submitIngestBtn.disabled = true;
    if (nativeFolderPicker) nativeFolderPicker.value = '';
    if (elements.formAddProject) elements.formAddProject.reset();
  }

  if (btnTriggerPicker && nativeFolderPicker) {
    btnTriggerPicker.addEventListener('click', () => {
      nativeFolderPicker.click();
    });
  }
  if (pickerZone && nativeFolderPicker) {
    pickerZone.addEventListener('click', (e) => {
      if (e.target !== btnTriggerPicker) {
        nativeFolderPicker.click();
      }
    });
  }
  if (btnChangeFolder && nativeFolderPicker) {
    btnChangeFolder.addEventListener('click', () => {
      nativeFolderPicker.click();
    });
  }

  if (nativeFolderPicker) {
    nativeFolderPicker.addEventListener('change', async (e) => {
      const files = Array.from(e.target.files || []);
      if (files.length === 0) return;

      const firstRel = files[0].webkitRelativePath || '';
      selectedFolderBaseName = firstRel.split('/')[0] || 'projeto';

      currentIngestedDocs = {};
      currentIngestedManifests = {};

      const relevantNames = new Set([
        'readme.md', 'architecture.md', 'techspec.md', 'workflows.md',
        'database.md', 'schema.md', 'dockerfile', 'docker-compose.yml',
        'docker-compose.yaml', 'package.json', 'pyproject.toml',
        'requirements.txt', 'schema.prisma'
      ]);

      const detectedDocChips = [];

      for (const file of files) {
        const parts = file.webkitRelativePath.split('/');
        parts.shift(); // remove nome da pasta raiz
        const relPath = parts.join('/');
        const lowerName = file.name.toLowerCase();
        const isMd = lowerName.endsWith('.md');
        const isManifest = relevantNames.has(lowerName);

        if (isMd || isManifest) {
          if (lowerName === 'dockerfile') currentIngestedManifests.has_dockerfile = true;
          if (lowerName.startsWith('docker-compose')) currentIngestedManifests.has_compose = true;
          if (lowerName === 'package.json') currentIngestedManifests.has_package_json = true;
          if (lowerName === 'pyproject.toml') currentIngestedManifests.has_pyproject = true;
          if (lowerName === 'schema.prisma') currentIngestedManifests.has_prisma = true;

          if (file.size <= 2 * 1024 * 1024) {
            try {
              const text = await file.text();
              currentIngestedDocs[relPath] = text;
              detectedDocChips.push(relPath);
            } catch (err) {
              console.warn('Erro ao ler', file.name, err);
            }
          }
        }
      }

      pickerZone.style.display = 'none';
      selectedCard.style.display = 'block';
      folderNameEl.textContent = selectedFolderBaseName;
      docsCountEl.textContent = `${detectedDocChips.length} documento(s) e manifesto(s) encontrados`;

      if (detectedDocChips.length > 0) {
        docsChipsEl.innerHTML = detectedDocChips.slice(0, 10).map(c => `
          <span class="ingest-doc-chip">📄 ${escapeHtml(c)}</span>
        `).join('') + (detectedDocChips.length > 10 ? `<span class="ingest-doc-chip">+${detectedDocChips.length - 10} mais</span>` : '');
      } else {
        docsChipsEl.innerHTML = '<span class="muted-text" style="font-size:11px;">Nenhum arquivo README.md ou ARCHITECTURE.md detectado nesta pasta.</span>';
      }

      if (nameInput) {
        nameInput.value = selectedFolderBaseName.split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
      }
      if (pathInput) {
        pathInput.value = selectedFolderBaseName;
      }
      if (submitIngestBtn) {
        submitIngestBtn.disabled = false;
      }
    });
  }

  // Modals Open
  const openAddProjectModal = async () => {
    resetIngestModal();
    elements.modalAddProject.style.display = 'flex';
    const chipsContainer = document.getElementById('discovered-projects-chips');
    if (chipsContainer) {
      const discovered = await api.discoverProjects();
      if (discovered && discovered.length > 0) {
        chipsContainer.innerHTML = discovered.map(d => `
          <button type="button" class="btn btn-secondary btn-sm" style="padding: 2px 8px; font-size: 11px; border-radius: 12px; cursor: pointer;" title="Clique para usar ${escapeHtml(d.name)}" data-proj-name="${escapeHtml(d.name)}" data-proj-path="${escapeHtml(d.path)}">
            📁 ${escapeHtml(d.name)}
          </button>
        `).join('');
        chipsContainer.querySelectorAll('button').forEach(btn => {
          btn.addEventListener('click', () => {
            const pathVal = btn.getAttribute('data-proj-path');
            const nameVal = btn.getAttribute('data-proj-name');
            if (pathInput) pathInput.value = pathVal;
            if (nameInput) {
              nameInput.value = nameVal.split(/[-_]/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            }
            if (submitIngestBtn) submitIngestBtn.disabled = false;
          });
        });
      }
    }
  };

  // Habilita botão se digitar no input de caminho manual
  if (pathInput && submitIngestBtn) {
    pathInput.addEventListener('input', () => {
      if (pathInput.value.trim().length > 0) {
        submitIngestBtn.disabled = false;
      }
    });
  }

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
      if (modalId === 'modal-add-project') resetIngestModal();
    });
  });

  // Submit Ingest / Add Project
  elements.formAddProject.addEventListener('submit', async (e) => {
    e.preventDefault();
    const rawInput = (pathInput ? pathInput.value : '').trim();
    const rawPath = rawInput.replace(/^["']+|["']+$/g, '').trim();
    const name = (nameInput ? nameInput.value : '').trim();
    const version = document.getElementById('proj-input-version').value.trim();
    const tagsRaw = document.getElementById('proj-input-tags').value.trim();
    const tags = tagsRaw ? tagsRaw.split(',').map(t => t.trim()).filter(Boolean) : [];

    try {
      let created;
      if (selectedFolderBaseName || Object.keys(currentIngestedDocs).length > 0) {
        // Modelo de Ingestão Nativo
        created = await api.ingestProject({
          name: name || selectedFolderBaseName,
          folder_name: selectedFolderBaseName,
          path: rawPath || selectedFolderBaseName,
          version,
          tags,
          docs: currentIngestedDocs,
          manifests: currentIngestedManifests
        });
      } else {
        if (!rawPath) {
          alert('Por favor, selecione uma pasta no Windows ou informe o caminho.');
          return;
        }
        created = await api.addProject({ path: rawPath, name, version, tags });
      }

      closeAllModals();
      resetIngestModal();
      await init();
      selectProject(created.id);
    } catch (err) {
      alert('Erro ao ingerir projeto: ' + err.message);
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
