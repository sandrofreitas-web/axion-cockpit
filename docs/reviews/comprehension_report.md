# Comprehension Test: docs/designs/local_project_os.md

## Paraphrase of Feature Specification (Lines 1–219)

### What this proposes
The feature specification proposes transforming the `skills-library` repository into a local, non-intrusive operations and architecture cockpit ("Local Project OS") for monitoring multiple local software repositories from their absolute filesystem paths. It scans project documentation to extract and cache architecture summaries, workflows, and database entity-relationship models rendered client-side using Mermaid.js. It also establishes an isolated, Markdown-based ledger for tracking technical notes and improvement ideas outside project repositories, backed by a pre-version reconciliation audit step that compares pending notes against local filesystem and Git changes before bumping a project's registered version in a flat-file database (`data/projects.json`).

### How the existing system works, per this document
Currently, developers navigate between disparate local directories to inspect architecture, workflows, and schemas, which creates fragmented visibility, stale centralized documentation, and premature commits for unhomologated ideas. Additionally, this repository currently functions as a central skill catalog with multi-LLM synchronization tooling (`sync_skills.py`, `catalog.json`), a model that has become obsolete with decentralized agent environments.

---

## Paraphrase of Detailed Implementation Plan (Lines 220–294)

### What this proposes
The implementation plan details a six-phase migration that starts by expurging all legacy skill files, templates, validation workflows, and global skill folders. It sets up flat-file directories (`data/projects.json`, `data/notes/`, `data/cache/`) with documentation templates, and creates three Python backend modules: `scanner.py` (passive disk scan), `reconciler.py` (note vs. Git/filesystem change comparison), and `llm_bridge.py` (text parsing into Mermaid and JSON summaries). Finally, it updates `ui/app.py` with REST endpoints, converts `ui/index.html` into a multi-tab dashboard with interactive Mermaid views and a Kanban notes board, and rewrites repository governance files (`README.md` and `.gitignore`).

### How the existing system works, per this document
The existing repository contains a legacy Python server (`ui/app.py`) and frontend (`ui/index.html`) coupled to skill synchronization logic, internal path restrictions (`is_internal_project`), and an older fleet registry (`ui/fleet.json`). It also houses obsolete global skill folders (`global/*`), skill authoring templates (`templates/SKILL_TEMPLATE.md`), and automated CI catalog validation workflows (`.github/workflows/validate.yml`) that are slated for removal.

---

## Comprehension Findings & Clarity Audit

### Finding 1: Undefined Core External Actor / Tool ("Orca")
* **Severity**: Major
* **Affected Scope**: Section 1 (Line 18), Section 3.2 (Line 47), Section 4.3 (Line 138), Section 5.4 (Line 215), Section 6.6 (Line 292).
* **Discrepancy Description & Rationale**:
The document repeatedly assumes reader familiarity with "Orca" as the external orchestration and execution actor ("...a orquestração via Orca", "...comando operacional permanecem externos (via CLI/Orca)", "Operador/Orca implementa a melhoria no projeto", "Fluxo de trabalho com o Orca"). There is neither an inline definition nor a reference/link explaining what Orca is (e.g., whether it is an internal orchestrator CLI, a multi-agent framework, or a third-party process). A fresh reader without institutional knowledge cannot identify how the operator interacts with Orca.

### Finding 2: Mental Leap & Ambiguity between Non-Goal NG1 and LLM Bridge Execution
* **Severity**: Major
* **Affected Scope**: Section 3.2 (Line 47: NG1), Section 4.1 (Lines 73, 93, 102), Section 4.2 (Lines 114–119), Section 6.3 (Lines 254–256).
* **Discrepancy Description & Rationale**:
Non-Goal NG1 states: *"O OS não executa comandos nem controla runtimes de LLM/agentes; a execução e o comando operacional permanecem externos (via CLI/Orca)"*. However, Section 4.2 and Section 6.3 assign `app/engine/llm_bridge.py` the role of executing an *"extração assistida por LLM"* to produce `_summary.json` containing Mermaid diagrams and tech specs. The document does not explain how `llm_bridge.py` accomplishes LLM inference without violating NG1. It is unclear whether it calls an external LLM API directly (e.g., OpenAI/Gemini/Anthropic SDKs), delegates to a local CLI, or relies on an external caller/agent to write the cache file.

### Finding 3: Vague Heuristic Association for Reconciler Checks
* **Severity**: Nit
* **Affected Scope**: Section 4.3 (Lines 141–145), Section 4.4 (Line 167), Section 6.3 (Lines 252–253).
* **Discrepancy Description & Rationale**:
The document describes that `reconciler.py` compares pending notes with disk changes and outputs a *"Relatório de Reconciliação (Diff e Verificações)"*. However, it leaves vague how the engine associates a specific note with modified files or Git diffs (e.g., whether notes require frontmatter target paths, or whether it simply presents uncommitted Git changes for human visual confirmation).

### Finding 4: Inconsistent Note Lifecycle Status Vocabulary
* **Severity**: Nit
* **Affected Scope**: Section 3.1 (Line 41), Section 4.3 (Lines 136, 142, 148), Section 6.5 (Line 280).
* **Discrepancy Description & Rationale**:
The permitted lifecycle states for notes vary across sections:
- Line 41: `Ideia`, `Planejado`, `Incorporado`
- Line 136: `Aberta`
- Line 142: `Planejada`, `Em Revisão`
- Line 280: `Ideia` -> `Planejado` -> `Em Revisão` -> `Incorporado`
A canonical enumeration should be established across the design to ensure consistent schema validation between frontend and backend.
