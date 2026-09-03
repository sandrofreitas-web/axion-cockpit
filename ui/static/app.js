// Skills OS Frontend JavaScript Controller
let catalogState = {};
let fleetState = [];
let activePreviewTarget = 'cursor';
let currentPreviews = {};

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initHub();
  initFleet();
  initStudio();
  initConsole();
  refreshAll();
});

// Navigation
function initNavigation() {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
      document.querySelectorAll('.view-panel').forEach((p) => p.classList.remove('active'));

      item.classList.add('active');
      const targetTab = item.getAttribute('data-tab');
      const targetPanel = document.getElementById(`view-${targetTab}`);
      if (targetPanel) targetPanel.classList.add('active');
    });
  });
}

// Refresh Data
async function refreshAll() {
  try {
    const [catRes, fleetRes] = await Promise.all([
      fetch('/api/catalog'),
      fetch('/api/fleet'),
    ]);

    catalogState = await catRes.json();
    fleetState = await fleetRes.json();

    const hubCount = Object.keys(catalogState).length;
    const fleetCount = fleetState.length;
    const hubBadge = document.getElementById('nav-count-hub');
    const fleetBadge = document.getElementById('nav-count-fleet');
    if (hubBadge) hubBadge.innerText = hubCount;
    if (fleetBadge) fleetBadge.innerText = fleetCount;

    renderHub();
    renderFleet();
    renderMetrics();
  } catch (err) {
    console.error('Erro ao buscar dados:', err);
  }
}

// HUB VIEW
let selectedSkillName = null;

function initHub() {
  const searchInput = document.getElementById('hub-search');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => {
      renderHub(e.target.value.toLowerCase());
    });
  }

  const validateBtn = document.getElementById('btn-validate-ci');
  if (validateBtn) {
    validateBtn.addEventListener('click', async () => {
      showConsole('⚡ Executando validação de CI e linter de skills...');
      try {
        const res = await fetch('/api/validate', { method: 'POST' });
        const data = await res.json();
        appendConsole(data.output);
      } catch (e) {
        appendConsole('Erro ao executar validação: ' + e);
      }
    });
  }

  const newSkillBtn = document.getElementById('btn-new-skill-hub');
  if (newSkillBtn) {
    newSkillBtn.addEventListener('click', () => {
      createNewSkillInStudio();
    });
  }

  const closeInspectorBtn = document.getElementById('btn-close-inspector');
  if (closeInspectorBtn) {
    closeInspectorBtn.addEventListener('click', () => {
      closeSkillInspector();
    });
  }

  const inspectorEditBtn = document.getElementById('btn-inspector-edit');
  if (inspectorEditBtn) {
    inspectorEditBtn.addEventListener('click', () => {
      if (selectedSkillName) {
        loadSkillIntoStudio(selectedSkillName);
      }
    });
  }

  // Fecha modal de fallback se existir
  const closeModalBtn = document.getElementById('btn-close-modal');
  if (closeModalBtn) {
    closeModalBtn.addEventListener('click', () => {
      const modal = document.getElementById('skill-modal');
      if (modal) modal.classList.remove('open');
    });
  }
}

function renderHub(query = '') {
  const container = document.getElementById('hub-cards-container');
  if (!container) return;
  container.innerHTML = '';

  Object.entries(catalogState).forEach(([name, skill]) => {
    const desc = skill.description || '';
    const tags = skill.tags || [];
    const status = skill.status || 'stable';
    const version = skill.version || '1.0.0';
    const compat = skill.compatible_with || ['claude', 'gemini', 'cursor', 'windsurf', 'copilot'];

    // Filtro de busca
    if (query) {
      const matchName = name.toLowerCase().includes(query);
      const matchDesc = desc.toLowerCase().includes(query);
      const matchTag = tags.some((t) => t.toLowerCase().includes(query));
      if (!matchName && !matchDesc && !matchTag) return;
    }

    const card = document.createElement('div');
    card.className = `skill-card ${selectedSkillName === name ? 'active-inspect' : ''}`;
    card.id = `skill-card-${name}`;
    card.innerHTML = `
      <div>
        <div class="skill-header">
          <div class="skill-title-group">
            <h3>${name}</h3>
          </div>
          <div style="display: flex; gap: 6px; align-items: center;">
            <span class="badge-version">v${version}</span>
            <span class="badge-status ${status}">${status}</span>
          </div>
        </div>
        <p class="skill-desc">${desc}</p>
        <div class="skill-tags">
          ${tags.map((t) => `<span class="tag-pill">#${t}</span>`).join('')}
        </div>
      </div>
      <div class="skill-footer">
        <div class="compat-icons">
          <span class="ide-badge ${compat.includes('antigravity') ? 'active' : ''}">Agents</span>
          <span class="ide-badge ${compat.includes('claude') ? 'active' : ''}">Claude</span>
          <span class="ide-badge ${compat.includes('cursor') ? 'active' : ''}">Cursor</span>
          <span class="ide-badge ${compat.includes('gemini') ? 'active' : ''}">Gemini</span>
          <span class="ide-badge ${compat.includes('copilot') ? 'active' : ''}">Copilot</span>
        </div>
        <button class="btn-inspect" onclick="openSkillInspector('${name}')">Inspecionar ↗</button>
      </div>
    `;
    container.appendChild(card);
  });
}

window.openSkillInspector = function (name) {
  const skill = catalogState[name];
  if (!skill) return;

  selectedSkillName = name;

  // Atualiza destaque nos cards
  document.querySelectorAll('.skill-card').forEach((c) => c.classList.remove('active-inspect'));
  const activeCard = document.getElementById(`skill-card-${name}`);
  if (activeCard) activeCard.classList.add('active-inspect');

  // Atualiza painel Split Inspector
  const inspectorPane = document.getElementById('hub-inspector-pane');
  const titleEl = document.getElementById('inspector-skill-title');
  const bodyEl = document.getElementById('inspector-skill-body');
  const editBtn = document.getElementById('btn-inspector-edit');

  if (titleEl) titleEl.innerText = `${name} (v${skill.version || '1.0.0'})`;
  if (editBtn) editBtn.style.display = 'inline-flex';

  if (bodyEl) {
    const rawSource = skill.raw || skill.body || 'Conteúdo canônico não carregado.';
    const usedByProjects = skill.used_by && skill.used_by.length > 0 ? skill.used_by.join(', ') : 'Nenhum projeto consumindo diretamente';

    bodyEl.innerHTML = `
      <div style="margin-bottom: 14px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
        <span class="badge-status ${skill.status || 'stable'}">${skill.status || 'stable'}</span>
        <span class="badge-version">v${skill.version || '1.0.0'}</span>
        <span class="tag-pill" style="font-size: 10px;">${skill.path || 'global/' + name + '/SKILL.md'}</span>
      </div>

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px;">Descrição & Propósito</h4>
        <p style="font-size: 13px; line-height: 1.55; color: var(--text-main);">${skill.description || 'Sem descrição cadastrada'}</p>
      </div>

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px;">Uso na Frota</h4>
        <p style="font-family: var(--font-mono); font-size: 11px; color: var(--accent-cyan);">${usedByProjects}</p>
      </div>

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 6px;">Tags Indexadas</h4>
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          ${(skill.tags || []).map((t) => `<span class="tag-pill">#${t}</span>`).join('')}
        </div>
      </div>

      <div style="margin-bottom: 14px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
          <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase;">Fonte Canônica (SKILL.md)</h4>
          <button class="btn-inspect-mini" onclick="navigator.clipboard.writeText(\`${escapeHtml(rawSource).replace(/`/g, '\\`')}\`); alert('Código copiado!')">Copiar</button>
        </div>
        <pre style="background: var(--bg-editor); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 12px; font-family: var(--font-mono); font-size: 11.5px; font-weight: 400; line-height: 1.6; color: #CBD5E1; max-height: 280px; overflow-y: auto; white-space: pre-wrap;">${escapeHtml(rawSource)}</pre>
      </div>

      <div style="padding-top: 10px; border-top: 1px solid var(--border-subtle); display: flex; gap: 8px;">
        <button class="btn-project-sync" style="flex: 1; justify-content: center;" onclick="loadSkillIntoStudio('${name}')">
          ✏️ Abrir no Studio para Editar
        </button>
      </div>
    `;
  }

  if (inspectorPane) inspectorPane.classList.add('open');
};

window.closeSkillInspector = function () {
  selectedSkillName = null;
  const inspectorPane = document.getElementById('hub-inspector-pane');
  if (inspectorPane) inspectorPane.classList.remove('open');
  document.querySelectorAll('.skill-card').forEach((c) => c.classList.remove('active-inspect'));
};

window.openSkillModal = window.openSkillInspector;

let allFleetCollapsed = true;
let fleetCollapsedState = {};
let selectedProjectIdx = null;

// FLEET VIEW
function initFleet() {
  const syncAllBtn = document.getElementById('btn-sync-all');
  if (syncAllBtn) {
    syncAllBtn.addEventListener('click', async () => {
      showConsole('🚀 Iniciando sincronização de toda a frota de projetos...');
      try {
        const res = await fetch('/api/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
        const data = await res.json();
        Object.entries(data.outputs || {}).forEach(([proj, out]) => {
          appendConsole(`\n[PROJETO: ${proj}]\n${out}`);
        });
        refreshAll();
      } catch (e) {
        appendConsole('Erro ao sincronizar frota: ' + e);
      }
    });
  }

  const toggleAllBtn = document.getElementById('btn-toggle-all-fleet');
  if (toggleAllBtn) {
    toggleAllBtn.addEventListener('click', () => {
      allFleetCollapsed = !allFleetCollapsed;
      fleetState.forEach((p, idx) => {
        fleetCollapsedState[idx] = allFleetCollapsed;
      });
      renderFleet();
    });
  }

  const fleetSearchInput = document.getElementById('fleet-search');
  if (fleetSearchInput) {
    fleetSearchInput.addEventListener('input', (e) => {
      renderFleet(e.target.value.toLowerCase());
    });
  }

  // Modal de adicionar projeto
  const addProjectModalBtn = document.getElementById('btn-add-project-modal');
  const projectModal = document.getElementById('project-modal');
  const closeProjectModalBtn = document.getElementById('btn-close-project-modal');
  const cancelProjectModalBtn = document.getElementById('btn-cancel-project-modal');
  const saveProjectModalBtn = document.getElementById('btn-save-project-modal');

  if (addProjectModalBtn && projectModal) {
    addProjectModalBtn.addEventListener('click', () => {
      document.getElementById('input-project-name').value = '';
      document.getElementById('input-project-path').value = '';
      document.getElementById('input-project-desc').value = '';
      projectModal.classList.add('open');
    });
  }

  const closeProjectModal = () => {
    if (projectModal) projectModal.classList.remove('open');
  };

  if (closeProjectModalBtn) closeProjectModalBtn.addEventListener('click', closeProjectModal);
  if (cancelProjectModalBtn) cancelProjectModalBtn.addEventListener('click', closeProjectModal);

  if (saveProjectModalBtn) {
    saveProjectModalBtn.addEventListener('click', async () => {
      const name = document.getElementById('input-project-name').value.trim();
      const path = document.getElementById('input-project-path').value.trim();
      const desc = document.getElementById('input-project-desc').value.trim();

      if (!path) {
        alert('Por favor informe o caminho do projeto no disco.');
        return;
      }

      showConsole(`📁 Adicionando projeto à frota: ${name || path}...`);
      try {
        const res = await fetch('/api/fleet/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, path, description: desc }),
        });
        const data = await res.json();
        if (!res.ok || data.error) {
          alert(`Erro ao adicionar projeto: ${data.error}`);
          appendConsole(`❌ Erro: ${data.error}`);
          return;
        }

        appendConsole(`✓ Projeto '${name || path}' conectado com sucesso à frota.`);
        closeProjectModal();
        await refreshAll();
      } catch (err) {
        appendConsole(`❌ Erro de conexão: ${err}`);
      }
    });
  }

  // Split Inspector Actions
  const closeFleetInspectorBtn = document.getElementById('btn-close-fleet-inspector');
  if (closeFleetInspectorBtn) {
    closeFleetInspectorBtn.addEventListener('click', () => {
      closeFleetInspector();
    });
  }

  const inspectorSyncBtn = document.getElementById('btn-inspector-project-sync');
  if (inspectorSyncBtn) {
    inspectorSyncBtn.addEventListener('click', () => {
      if (selectedProjectIdx !== null && fleetState[selectedProjectIdx]) {
        syncProject(fleetState[selectedProjectIdx].path);
      }
    });
  }
}

function renderFleet(query = '') {
  const container = document.getElementById('fleet-cards-container');
  if (!container) return;
  container.innerHTML = '';

  fleetState.forEach((project, pIdx) => {
    const name = project.name || '';
    const path = project.path || '';
    const desc = project.description || '';

    // Filtro de busca
    if (query) {
      const matchName = name.toLowerCase().includes(query);
      const matchPath = path.toLowerCase().includes(query);
      const matchDesc = desc.toLowerCase().includes(query);
      const matchSkill = Object.keys(project.locked_skills || {}).some((s) => s.toLowerCase().includes(query));
      const matchLocal = (project.local_skills || []).some((l) => l.name.toLowerCase().includes(query));
      if (!matchName && !matchPath && !matchDesc && !matchSkill && !matchLocal) return;
    }

    const isCollapsed = fleetCollapsedState[pIdx] ?? allFleetCollapsed;
    const card = document.createElement('div');
    card.className = `fleet-card ${isCollapsed ? 'collapsed' : ''} ${selectedProjectIdx === pIdx ? 'active-inspect' : ''}`;
    card.id = `fleet-card-${pIdx}`;

    const globalSkillNames = Object.keys(catalogState);
    const lockedSkills = project.locked_skills || {};
    const localSkills = project.local_skills || [];

    card.innerHTML = `
      <div class="fleet-header">
        <div style="display: flex; align-items: center; gap: 12px; min-width: 0;">
          <button class="btn-collapse-toggle" title="Compactar/Expandir" onclick="toggleProjectCollapse(${pIdx})">
            ${isCollapsed ? '▶' : '▼'}
          </button>
          <div class="fleet-title-group" style="min-width: 0;">
            <h3>
              <span>🏢</span> ${name}
              ${project.has_lock ? '<span class="badge-status stable">Lockfile Ativo</span>' : '<span class="badge-status draft">Sem Lockfile</span>'}
              <span class="badge-version" style="margin-left: 6px;">${Object.keys(lockedSkills).length} globais • ${localSkills.length} locais</span>
            </h3>
            <div class="project-path">${path}</div>
          </div>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-shrink: 0;">
          <button class="btn-inspect" onclick="openProjectInspector(${pIdx})">Inspecionar ↗</button>
          <button class="btn-project-sync" onclick="syncProject('${project.path.replace(/\\/g, '\\\\')}')">
            ⚡ 1-Click Sync
          </button>
        </div>
      </div>

      <div class="fleet-skills-section">
        <!-- Global Skills Checkboxes -->
        <div class="fleet-skills-block">
          <h5>📦 Skills Globais Ativas (${Object.keys(lockedSkills).length}/${globalSkillNames.length})</h5>
          <div class="skill-toggle-list">
            ${globalSkillNames.map((gName) => {
              const isChecked = Boolean(lockedSkills[gName]);
              return `
                <div class="skill-toggle-item">
                  <label>
                    <input type="checkbox" ${isChecked ? 'checked' : ''} 
                      onchange="toggleProjectSkill('${project.path.replace(/\\/g, '\\\\')}', '${gName}', this.checked)">
                    <span style="font-weight: 500;">${gName}</span>
                  </label>
                  <span class="badge-version">v${(lockedSkills[gName] && lockedSkills[gName].version) || catalogState[gName].version || '1.0'}</span>
                </div>
              `;
            }).join('')}
          </div>
        </div>

        <!-- Local Skills List -->
        <div class="fleet-skills-block">
          <h5>🧩 Skills Locais Exclusivas (${localSkills.length})</h5>
          <div class="skill-toggle-list">
            ${localSkills.length === 0 ? '<div style="color: var(--text-dim); font-size: 12px; padding: 10px;">Nenhuma skill local criada ainda.</div>' : ''}
            ${localSkills.map((loc, lIdx) => `
              <div class="skill-toggle-item" style="border-left: 3px solid var(--accent-emerald); display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                <div style="flex: 1; min-width: 0; overflow: hidden;">
                  <div style="font-weight: 600; color: #34D399; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${loc.name}</div>
                  <div style="font-size: 11px; color: var(--text-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${(loc.frontmatter && loc.frontmatter.description) || 'Skill local do projeto'}</div>
                </div>
                <button class="btn-inspect-mini" style="flex-shrink: 0;" onclick="openLocalSkillInspector(${pIdx}, ${lIdx})">Inspecionar ↗</button>
              </div>
            `).join('')}
          </div>
        </div>
      </div>

      <!-- IDE Generated Folders Status -->
      <div class="fleet-ide-status" style="display: flex; align-items: center; justify-content: space-between; font-size: 12px; color: var(--text-dim); padding-top: 8px;">
        <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
          <span style="font-family: var(--font-mono); font-size: 10px; text-transform: uppercase;">Compiladores:</span>
          <span class="ide-badge ${project.generated_status.antigravity ? 'active' : ''}">.agents ${project.generated_status.antigravity ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.cursor ? 'active' : ''}">.cursor ${project.generated_status.cursor ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.claude ? 'active' : ''}">.claude ${project.generated_status.claude ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.gemini ? 'active' : ''}">.gemini ${project.generated_status.gemini ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.copilot ? 'active' : ''}">.github ${project.generated_status.copilot ? '✓' : '✗'}</span>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

window.toggleProjectCollapse = function (pIdx) {
  fleetCollapsedState[pIdx] = !(fleetCollapsedState[pIdx] ?? allFleetCollapsed);
  renderFleet();
};

window.openProjectInspector = function (pIdx) {
  const project = fleetState[pIdx];
  if (!project) return;

  selectedProjectIdx = pIdx;

  // Atualiza destaque no card ativo
  document.querySelectorAll('.fleet-card').forEach((c) => c.classList.remove('active-inspect'));
  const card = document.getElementById(`fleet-card-${pIdx}`);
  if (card) card.classList.add('active-inspect');

  const inspectorPane = document.getElementById('fleet-inspector-pane');
  const titleEl = document.getElementById('inspector-project-title');
  const bodyEl = document.getElementById('inspector-project-body');
  const syncBtn = document.getElementById('btn-inspector-project-sync');

  if (titleEl) titleEl.innerText = `${project.name}`;
  if (syncBtn) syncBtn.style.display = 'inline-flex';

  const lockedSkills = project.locked_skills || {};
  const localSkills = project.local_skills || [];

  if (bodyEl) {
    bodyEl.innerHTML = `
      <div style="margin-bottom: 14px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
        ${project.has_lock ? '<span class="badge-status stable">Lockfile Presente</span>' : '<span class="badge-status draft">Sem Lockfile</span>'}
        <span class="badge-version">${Object.keys(lockedSkills).length} Globais</span>
        <span class="badge-version">${localSkills.length} Locais</span>
      </div>

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px;">Caminho Absoluto</h4>
        <code style="font-family: var(--font-mono); font-size: 11.5px; color: var(--accent-cyan); word-break: break-all;">${project.path}</code>
      </div>

      ${project.description ? `
      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px;">Descrição</h4>
        <p style="font-size: 13px; color: var(--text-main); line-height: 1.5;">${project.description}</p>
      </div>` : ''}

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 6px;">Status dos Formatos Gerados</h4>
        <div style="display: flex; gap: 6px; flex-wrap: wrap;">
          <span class="ide-badge ${project.generated_status.antigravity ? 'active' : ''}">Antigravity (.agents/) ${project.generated_status.antigravity ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.cursor ? 'active' : ''}">Cursor (.mdc) ${project.generated_status.cursor ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.claude ? 'active' : ''}">Claude (.claude/) ${project.generated_status.claude ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.gemini ? 'active' : ''}">Gemini (GEMINI.md) ${project.generated_status.gemini ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.windsurf ? 'active' : ''}">Windsurf (.windsurf/) ${project.generated_status.windsurf ? '✓' : '✗'}</span>
          <span class="ide-badge ${project.generated_status.copilot ? 'active' : ''}">Copilot (instructions) ${project.generated_status.copilot ? '✓' : '✗'}</span>
        </div>
      </div>

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 6px;">Skills Globais Consumidas</h4>
        <div style="display: flex; flex-direction: column; gap: 6px;">
          ${Object.keys(lockedSkills).length === 0 ? '<span style="color: var(--text-dim); font-size: 12px;">Nenhuma skill global ativada no lockfile.</span>' : ''}
          ${Object.entries(lockedSkills).map(([sName, sMeta]) => `
            <div style="background: var(--bg-editor); border: 1px solid var(--border-subtle); padding: 6px 10px; border-radius: 4px; display: flex; justify-content: space-between; align-items: center; font-size: 12px;">
              <span style="font-family: var(--font-mono); color: #FFFFFF;">${sName}</span>
              <span class="badge-version">v${sMeta.version || '1.0'}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <div style="padding-top: 12px; border-top: 1px solid var(--border-subtle); display: flex; gap: 8px;">
        <button class="btn-project-sync" style="flex: 1; justify-content: center;" onclick="syncProject('${project.path.replace(/\\/g, '\\\\')}')">
          ⚡ Sincronizar Projeto Agora
        </button>
        <button class="btn-inspect" style="color: var(--accent-rose); border-color: rgba(239, 68, 68, 0.4);" onclick="removeProjectFromFleet('${project.path.replace(/\\/g, '\\\\')}')">
          🗑️ Remover
        </button>
      </div>
    `;
  }

  if (inspectorPane) inspectorPane.classList.add('open');
};

window.openLocalSkillInspector = function (pIdx, lIdx) {
  const project = fleetState[pIdx];
  if (!project) return;
  const loc = project.local_skills[lIdx];
  if (!loc) return;

  selectedProjectIdx = pIdx;

  const inspectorPane = document.getElementById('fleet-inspector-pane');
  const titleEl = document.getElementById('inspector-project-title');
  const bodyEl = document.getElementById('inspector-project-body');
  const syncBtn = document.getElementById('btn-inspector-project-sync');

  if (titleEl) titleEl.innerText = `🧩 ${loc.name} [Local]`;
  if (syncBtn) syncBtn.style.display = 'none';

  const fm = loc.frontmatter || {};
  const globs = fm.globs ? (Array.isArray(fm.globs) ? fm.globs.join(', ') : fm.globs) : 'Nenhum glob';
  const tags = fm.tags || [];
  const rawSource = loc.raw || loc.body || 'Sem conteúdo carregado.';

  if (bodyEl) {
    bodyEl.innerHTML = `
      <div style="margin-bottom: 14px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;">
        <span class="badge-status draft">Skill Local Exclusiva</span>
        <span class="tag-pill" style="color: var(--accent-emerald);">🏢 ${project.name}</span>
      </div>

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px;">Descrição</h4>
        <p style="font-size: 13px; line-height: 1.5; color: var(--text-main);">${fm.description || 'Sem descrição'}</p>
      </div>

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px;">Caminho Local no Projeto</h4>
        <code style="font-family: var(--font-mono); font-size: 11.5px; color: var(--accent-cyan); word-break: break-all;">${loc.path || ''}</code>
      </div>

      <div style="margin-bottom: 14px;">
        <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px;">Gatilhos por Arquivo (Globs)</h4>
        <code style="font-family: var(--font-mono); font-size: 11.5px; color: #A5B4FC;">${globs}</code>
      </div>

      <div style="margin-bottom: 14px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
          <h4 style="font-family: var(--font-mono); font-size: 10px; font-weight: 700; color: var(--text-dim); text-transform: uppercase;">Fonte Local (SKILL.md)</h4>
          <button class="btn-inspect-mini" onclick="navigator.clipboard.writeText(\`${escapeHtml(rawSource).replace(/`/g, '\\`')}\`); alert('Código copiado!')">Copiar</button>
        </div>
        <pre style="background: var(--bg-editor); border: 1px solid var(--border-subtle); border-radius: 6px; padding: 12px; font-family: var(--font-mono); font-size: 11.5px; font-weight: 400; line-height: 1.6; color: #CBD5E1; max-height: 240px; overflow-y: auto; white-space: pre-wrap;">${escapeHtml(rawSource)}</pre>
      </div>

      <div style="padding-top: 10px; border-top: 1px solid var(--border-subtle); display: flex; gap: 8px;">
        <button class="btn-project-sync" style="flex: 1; justify-content: center;" onclick="promoteSkill('${project.path.replace(/\\/g, '\\\\')}', '${loc.name}')">
          🚀 Promover para Global (1-Click)
        </button>
        <button class="btn-inspect" onclick="loadLocalSkillIntoStudio('${escapeHtml(rawSource).replace(/'/g, "\\'")}')">
          ✏️ Studio
        </button>
      </div>
    `;
  }

  if (inspectorPane) inspectorPane.classList.add('open');
};

window.promoteSkill = async function (projectPath, skillName) {
  if (!confirm(`Deseja promover a skill local '${skillName}' para o catálogo global compartilhado?\n\nEla será movida para 'skills-library/global/${skillName}/', registrada no catalog.json e sincronizada automaticamente.`)) {
    return;
  }

  showConsole(`🚀 Iniciando promoção da skill local [${skillName}]...`);
  try {
    const res = await fetch('/api/skill/promote', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, skill_name: skillName }),
    });

    const data = await res.json();
    if (!res.ok || data.error) {
      appendConsole(`❌ Erro na promoção: ${data.error || 'Falha na requisição'}`);
      alert(`Erro ao promover skill: ${data.error}`);
      return;
    }

    appendConsole(`✓ ${data.message}`);
    if (data.sync_output) {
      appendConsole(`\n${data.sync_output}`);
    }

    catalogState = data.catalog || catalogState;
    await refreshAll();

    // Fecha o inspector da frota e abre a nova skill no Hub
    closeFleetInspector();
    openSkillInspector(skillName);
    alert(`🎉 Skill '${skillName}' promovida para o catálogo global com sucesso!`);
  } catch (err) {
    appendConsole(`❌ Erro de conexão ao promover skill: ${err}`);
  }
};

window.closeFleetInspector = function () {
  selectedProjectIdx = null;
  const inspectorPane = document.getElementById('fleet-inspector-pane');
  if (inspectorPane) inspectorPane.classList.remove('open');
  document.querySelectorAll('.fleet-card').forEach((c) => c.classList.remove('active-inspect'));
};

window.removeProjectFromFleet = async function (projectPath) {
  if (!confirm(`Deseja realmente remover o projeto da frota gerenciada?\n\n${projectPath}`)) {
    return;
  }

  showConsole(`Removendo projeto da frota: ${projectPath}...`);
  try {
    const res = await fetch('/api/fleet/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path: projectPath }),
    });
    const data = await res.json();
    appendConsole(`✓ Projeto removido com sucesso.`);
    closeFleetInspector();
    await refreshAll();
  } catch (err) {
    appendConsole(`❌ Erro ao remover projeto: ${err}`);
  }
};

window.loadLocalSkillIntoStudio = function (rawText) {
  // Troca para aba studio
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
  document.querySelectorAll('.view-panel').forEach((p) => p.classList.remove('active'));

  const studioNav = document.querySelector('.nav-item[data-tab="studio"]');
  const studioPanel = document.getElementById('view-studio');
  if (studioNav) studioNav.classList.add('active');
  if (studioPanel) studioPanel.classList.add('active');

  const editor = document.getElementById('studio-editor');
  if (editor) {
    editor.value = rawText;
    editor.focus();
  }
  updateLivePreview();
  showConsole(`✨ Skill local carregada no Studio. Edite e clique em "Salvar / Publicar Skill" para torná-la global!`);
};

window.openLocalSkillModal = window.openLocalSkillInspector;

window.syncProject = async function (projectPath) {
  showConsole(`Sincronizando projeto: ${projectPath}...`);
  try {
    const res = await fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath }),
    });
    const data = await res.json();
    appendConsole(data.output || 'Concluído.');
    refreshAll();
  } catch (e) {
    appendConsole('Erro: ' + e);
  }
};

window.toggleProjectSkill = async function (projectPath, skillName, enable) {
  showConsole(`${enable ? 'Adicionando' : 'Removendo'} skill '${skillName}' em ${projectPath}...`);
  try {
    const res = await fetch('/api/lock/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_path: projectPath, skill_name: skillName, enable }),
    });
    const data = await res.json();
    appendConsole(data.sync_output || 'Atualizado.');
    refreshAll();
  } catch (e) {
    appendConsole('Erro: ' + e);
  }
};

// STUDIO VIEW
function initStudio() {
  const defaultSkillTemplate = `---
name: minha-nova-skill
description: >
  Explique com palavras-chave claras o que a skill faz e quando a LLM
  deve aciona-la automaticamente (ex: gatilhos, tipos de arquivos, comandos).
tags: [dev, backend, api]
globs: ["src/**/*.py", "api/**/*.ts"]
always_apply: false
compatible_with: [claude, gemini, cursor, windsurf, copilot]
status: draft
version: "1.0.0"
---

# Nome da Skill

Resumo direto em 1 frase do proposito da skill.

## Quando usar
- "frase ou comando tipico do usuario"
- Contexto ou cenario especifico onde esta regra se aplica

## Como fazer
1. Passo a passo objetivo ou diretriz tecnica.
2. Exemplos de codigo ou saida esperada:
\`\`\`python
# Exemplo concreto
def exemplo():
    pass
\`\`\`

## O que NUNCA fazer
- Proibicoes criticas e antipatterns.
`;

  const editor = document.getElementById('studio-editor');
  editor.value = defaultSkillTemplate;

  let debounceTimeout = null;
  editor.addEventListener('input', () => {
    clearTimeout(debounceTimeout);
    debounceTimeout = setTimeout(updateLivePreview, 250);
  });

  document.querySelectorAll('.preview-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.preview-tab').forEach((t) => t.classList.remove('active'));
      tab.classList.add('active');
      activePreviewTarget = tab.getAttribute('data-target');
      renderActivePreview();
    });
  });

  const templateBtn = document.getElementById('btn-studio-template');
  if (templateBtn) {
    templateBtn.addEventListener('click', () => {
      editor.value = defaultSkillTemplate;
      updateLivePreview();
      showConsole('📄 Template canônico de SKILL.md carregado no editor.');
    });
  }

  const saveBtn = document.getElementById('btn-studio-save');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      await saveCurrentSkillFromStudio();
    });
  }

  updateLivePreview();
}

async function saveCurrentSkillFromStudio() {
  const editor = document.getElementById('studio-editor');
  const rawText = editor.value.trim();

  if (!rawText) {
    alert('O editor está vazio. Escreva ou carregue um template de skill antes de salvar.');
    return;
  }

  showConsole('💾 Salvando skill e sincronizando catálogo...');
  try {
    const res = await fetch('/api/skill/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw: rawText }),
    });

    const data = await res.json();
    if (!res.ok || data.error) {
      appendConsole(`❌ Erro ao salvar: ${data.error || 'Falha na requisição'}`);
      alert(`Erro ao salvar skill: ${data.error}`);
      return;
    }

    appendConsole(`✓ ${data.message}`);
    appendConsole(`✓ Catálogo atualizado com ${Object.keys(data.catalog || {}).length} skills.`);

    // Atualiza estado global
    catalogState = data.catalog || catalogState;
    await refreshAll();

    // Se estiver inspecionando esta skill, atualiza o split inspector
    if (data.skill_name) {
      openSkillInspector(data.skill_name);
    }
  } catch (err) {
    appendConsole(`❌ Erro de conexão ao salvar skill: ${err}`);
  }
}

window.createNewSkillInStudio = function () {
  // Troca para aba studio
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
  document.querySelectorAll('.view-panel').forEach((p) => p.classList.remove('active'));

  const studioNav = document.querySelector('.nav-item[data-tab="studio"]');
  const studioPanel = document.getElementById('view-studio');
  if (studioNav) studioNav.classList.add('active');
  if (studioPanel) studioPanel.classList.add('active');

  const editor = document.getElementById('studio-editor');
  if (editor) {
    editor.value = defaultSkillTemplate;
    editor.focus();
  }
  updateLivePreview();
  showConsole('✨ Modo de Criação: Defina o nome e instruções no SKILL.md e clique em "Salvar / Publicar Skill".');
};

window.loadSkillIntoStudio = function (name) {
  const skill = catalogState[name];
  if (!skill) return;

  // Troca para aba studio
  document.querySelectorAll('.nav-item').forEach((n) => n.classList.remove('active'));
  document.querySelectorAll('.view-panel').forEach((p) => p.classList.remove('active'));

  const studioNav = document.querySelector('.nav-item[data-tab="studio"]');
  const studioPanel = document.getElementById('view-studio');
  if (studioNav) studioNav.classList.add('active');
  if (studioPanel) studioPanel.classList.add('active');

  const editor = document.getElementById('studio-editor');
  if (editor) {
    editor.value = skill.raw || skill.body || defaultSkillTemplate;
    editor.focus();
  }
  updateLivePreview();
  showConsole(`✏️ Editando skill: [${name}] no Skill Studio.`);
};

async function updateLivePreview() {
  const rawText = document.getElementById('studio-editor').value;
  try {
    const res = await fetch('/api/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ raw: rawText }),
    });
    const data = await res.json();
    if (data.previews) {
      currentPreviews = data.previews;
      renderActivePreview();
    }
  } catch (e) {
    console.error('Erro de preview:', e);
  }
}

function renderActivePreview() {
  const codeEl = document.getElementById('studio-preview-code');
  if (!currentPreviews[activePreviewTarget]) {
    codeEl.innerText = '// Digite seu SKILL.md no editor ao lado para ver o preview compilado...';
    return;
  }

  const p = currentPreviews[activePreviewTarget];
  if (typeof p === 'object' && p.file) {
    codeEl.innerText = `// [Import no GEMINI.md]:\n${p.import}\n\n// [Arquivo .gemini/skills/<nome>.md]:\n${p.file}`;
  } else {
    codeEl.innerText = p;
  }
}

// METRICS VIEW
function renderMetrics() {
  const container = document.getElementById('metrics-insights-container');
  if (!container) return;

  // 1. Coleta todas as skills locais nos projetos da frota
  const allLocalSkills = [];
  fleetState.forEach((project) => {
    (project.local_skills || []).forEach((loc) => {
      allLocalSkills.push({
        project_name: project.name,
        project_path: project.path,
        skill_name: loc.name,
        description: (loc.frontmatter && loc.frontmatter.description) || 'Skill local exclusiva do projeto',
        path: loc.path || '',
      });
    });
  });

  let promotionCardsHtml = '';
  if (allLocalSkills.length > 0) {
    promotionCardsHtml = `
      <div style="margin-bottom: 24px;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
          <h3 style="font-size: 16px; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 8px;">
            <span>🚀</span> Oportunidades de Promoção Detectadas na Frota (${allLocalSkills.length})
          </h3>
          <span class="badge-version">Regra de Ouro: Skill útil em ≥ 2 projetos deve ser Global</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px;">
          ${allLocalSkills.map((item) => `
            <div class="stat-card" style="border-left: 4px solid var(--accent-cyan); display: flex; flex-direction: column; justify-content: space-between; gap: 12px;">
              <div>
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                  <h4 style="font-size: 15px; font-weight: 700; color: #38BDF8;">🧩 ${item.skill_name}</h4>
                  <span class="badge-status draft">Local</span>
                </div>
                <div style="font-size: 11px; color: var(--text-dim); margin-bottom: 6px;">Projeto: <strong>${item.project_name}</strong></div>
                <p style="font-size: 12.5px; color: var(--text-muted); line-height: 1.45;">${item.description}</p>
              </div>
              <div style="display: flex; gap: 8px; border-top: 1px solid var(--border-subtle); padding-top: 10px;">
                <button class="btn-project-sync" style="flex: 1; justify-content: center;" onclick="promoteSkill('${item.project_path.replace(/\\/g, '\\\\')}', '${item.skill_name}')">
                  🚀 Promover para Global Agora
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;
  } else {
    promotionCardsHtml = `
      <div class="stat-card" style="margin-bottom: 24px; border-left: 4px solid var(--accent-emerald);">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px; color: #34D399;">✓ Nenhuma Skill Local Pendente</h4>
          <p style="font-size: 12.5px; color: var(--text-muted); line-height: 1.4;">
            Todas as skills dos projetos estão catalogadas e padronizadas no repositório global!
          </p>
        </div>
      </div>
    `;
  }

  container.innerHTML = `
    ${promotionCardsHtml}
    <h3 style="font-size: 16px; font-weight: 700; color: var(--text-main); margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
      <span>📊</span> Telemetria & Padrões de Governança
    </h3>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px;">
      <div class="stat-card" style="border-left: 4px solid var(--accent-emerald);">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px;">🎯 Padrão de Dependências Python</h4>
          <p style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">
            A skill <code>managing-python-dependencies</code> (uv) e <code>fastapi-clean-architecture</code> estão ativas para consumo universal.
          </p>
        </div>
      </div>
      <div class="stat-card" style="border-left: 4px solid var(--accent-purple);">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px;">⚡ Compilador Multi-LLM Ativo</h4>
          <p style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">
            Transpilação simultânea para 6 ferramentas: Antigravity, Claude, Cursor (.mdc), Gemini, Windsurf e Copilot.
          </p>
        </div>
      </div>
      <div class="stat-card" style="border-left: 4px solid var(--accent-amber);">
        <div>
          <h4 style="font-size: 15px; margin-bottom: 4px;">🛡️ CI & Integridade Garantida</h4>
          <p style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">
            Linter automático de sintaxe YAML, lockfiles e catálogo versionado no GitHub.
          </p>
        </div>
      </div>
    </div>
  `;
}

// CONSOLE DRAWER
function initConsole() {
  const closeBtn = document.getElementById('btn-close-console');
  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      document.getElementById('output-console').classList.remove('open');
    });
  }

  const toggleBtn = document.getElementById('btn-toggle-console');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const consoleEl = document.getElementById('output-console');
      consoleEl.classList.toggle('open');
    });
  }
}

function showConsole(initialText = '') {
  const consoleEl = document.getElementById('output-console');
  const textEl = document.getElementById('console-output-text');
  textEl.innerText = initialText;
  consoleEl.classList.add('open');
}

function appendConsole(text) {
  const textEl = document.getElementById('console-output-text');
  textEl.innerText += '\n' + text;
  textEl.scrollTop = textEl.scrollHeight;
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
