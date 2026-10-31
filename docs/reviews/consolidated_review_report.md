# Consolidated Review Report: Local Project OS

* **Target Document:** [docs/designs/local_project_os.md](file:///C:/Docker/axion-cockpit/docs/designs/local_project_os.md)
* **Execution Mode:** Consolidated Full Flow (Stages 5, 6, 7, 8, 9)
* **Date:** 2026-10-30
* **Synthesizer Lenses Audited:** `egm-zoom-out` (Initial & Intermediate), `egm-comprehension`, `egm-design`, `egm-structural`, `egm-style`, `egm-implementation-readiness`, `egm-codebase-details`

---

## 1. Executive Summary & Verdict

O documento técnico [local_project_os.md](file:///C:/Docker/axion-cockpit/docs/designs/local_project_os.md) propõe uma visão sólida e valiosa: transformar o repositório em um console local de observabilidade e gestão operacional de múltiplos projetos em disco.

No entanto, a auditoria multi-lente revelou uma **divergência fundamental de identidade arquitetural**:
O documento oscila entre ser um **observador passivo leve e sem dependências** (como pretendido na concepção) e um **sistema complexo com cliente de inferência LLM no backend, cache redundante causador de drift e um motor especulativo de reconciliação de código**.

Ao aplicar o padrão *Zoom Out / YAGNI* e conciliar as análises de implementação e compreensão, o relatório identifica **4 Bloqueadores Centrais** e **6 Itens Maiores** que devem ser corrigidos antes do início da implementação. A correção recomendada reduz o escopo e o código em ~60%, eliminando riscos de drift e dependências pesadas.

---

## 2. Severity Breakdown

| Severidade | Quantidade | Status |
|---|---|---|
| 🔴 **Blocker** | 4 | Exigem resolução imediata no design antes do código |
| 🟡 **Major** | 6 | Riscos de arquitetura, contratos e escopo de implementação |
| 🟢 **Nit** | 3 | Padronização textual, definições de termos e distribuição |
| **Total de Descobertas** | **13** | **Consolidadas e Mapeadas** |

---

## 3. Consolidated Actionable Findings

### 🔴 Blockers

#### B1. Contradição Crítica entre LLM Bridge no Backend e Não-Objetivo NG1
* **Lentes:** `egm-zoom-out` (Etapas 5 e 8), `egm-comprehension` (F2), `egm-critic` (F2), `egm-implementation-readiness` (F3)
* **Problema:** A seção 3.2 estipula explicitamente: `NG1 - O OS não executa comandos nem controla runtimes de LLM/agentes; a execução e o comando operacional permanecem externos (via CLI/Orca)`. Em contradição direta, as seções 4.1, 4.2 e 6.3 criam o módulo `app/engine/llm_bridge.py` no backend em Python para realizar extrações ativas via LLM. Isso introduz dependências pesadas de SDKs (OpenAI/Gemini/Anthropic), chaves de API, timeouts de rede e complexidade de parsing de esquemas em um visualizador local.
* **Resolução Obrigatória:** Eliminar `app/engine/llm_bridge.py` e o endpoint `/api/projects/{id}/sync` do backend. O backend é estritamente um leitor passivo do sistema de arquivos. A elaboração de documentações assistida por LLM é realizada pelo desenvolvedor ou pelo Orca no terminal; o OS apenas lê e renderiza os arquivos Markdown/Mermaid existentes.

#### B2. Cache Persistente (`_summary.json`) Reintroduz o Problema de Drift de Documentação
* **Lentes:** `egm-zoom-out` (Etapas 5 e 8)
* **Problema:** O documento define no Problema #2 o `Risco de Stale Documentation e Duplicação`, mas cria `data/cache/{project_id}_summary.json`. Em discos locais (SSD/NVMe), ler arquivos Markdown sob demanda leva <1ms. Persistir resumos em cache gera drift imediato: ao alterar o código ou a documentação do projeto, o cache do OS fica desatualizado até que ocorra um resync manual.
* **Resolução Obrigatória:** Excluir `data/cache/` do design. A API deve ler os arquivos do projeto sob demanda e o navegador (Mermaid.js) renderiza os diagramas client-side dinamicamente, garantindo fidelidade em tempo real sem duplicação de estado.

#### B3. Omissão dos Arquivos Centrais de Frontend no Plano (`ui/static/app.js` e `ui/static/styles.css`)
* **Lentes:** `egm-codebase-details` (F1)
* **Problema:** A Fase 5 do plano lista apenas `ui/index.html` sob "Arquivos a Modificar". No repositório real, `ui/index.html` é apenas um container HTML (439 linhas); toda a lógica de estado, chamadas REST, renderização de diagramas, controle de abas e modais reside em `ui/static/app.js` (1.278 linhas) e `ui/static/styles.css` (1.250 linhas).
* **Resolução Obrigatória:** Adicionar explicitamente `ui/static/app.js` e `ui/static/styles.css` em "Arquivos a Modificar" na Fase 5, detalhando a remoção dos módulos obsoletos de skills (`initHub`, `initStudio`, `/api/catalog`) e a adição dos controladores do Project OS (`initProjects`, `initMermaidView`, `initNotes`).

#### B4. Contradição de Framework de Servidor (FastAPI vs. `http.server` sem dependências)
* **Lentes:** `egm-zoom-out` (Etapas 5 e 8), `egm-implementation-readiness` (F2)
* **Problema:** O plano cita backend `FastAPI + Uvicorn + Pydantic`, mas o servidor existente (`ui/app.py`) roda com a biblioteca padrão do Python (`http.server` e `socketserver`) com zero dependências externas (`pip install` desnecessário). Migrar para FastAPI adiciona dependências pesadas e atrito de ambiente sem ganho funcional para ~6 rotas simples, além de conflitar com a instrução de execução `python ui/app.py`.
* **Resolução Obrigatória:** Manter a arquitetura baseada na biblioteca padrão do Python (`http.server`), preservando a inicialização instantânea com zero dependências e sem necessidade de virtualenvs.

---

### 🟡 Majors

#### M1. Motor Especulativo de Reconciliação vs. Telemetria Git Já Existente
* **Lentes:** `egm-zoom-out` (Etapas 5 e 8), `egm-comprehension` (F3), `egm-implementation-readiness` (F4)
* **Problema:** O design introduz `app/engine/reconciler.py` propondo validar programaticamente se notas em texto livre foram aplicadas ao código. Essa validação automática é especulativa. Por outro lado, `ui/app.py` já possui a função `get_git_telemetry(project_path)` em ~25 linhas, lendo branch atual, status de arquivos e commits.
* **Resolução:** Remover `app/engine/reconciler.py`. Utilizar a telemetria Git nativa já existente em `ui/app.py` para exibir commits recentes e status de modificações na interface, deixando a verificação a cargo do operador.

#### M2. Ledger de Notas Desconectado dos Repositórios dos Projetos
* **Lentes:** `egm-zoom-out` (Etapas 5 e 8), `egm-critic` (F3 e F4)
* **Problema:** Manter pastas e arquivos Markdown de notas em `skills-library/data/notes/{project_id}/*.md` isola as ideias da história do projeto. Outros desenvolvedores que clonarem o projeto monitorado não terão acesso às notas.
* **Resolução:** Suportar a leitura de notas locais dos projetos (ex.: `<projeto>/docs/notes/` ou `TODO.md`), ou simplificar a persistência de notas do OS em um campo leve no próprio `data/projects.json`.

#### M3. Vulnerabilidade de Path Traversal e Falta de Validação de Caminhos
* **Lentes:** `egm-critic` (F1), `egm-zoom-out` (Etapa 8)
* **Problema:** `POST /api/projects` aceita qualquer caminho em disco sem validação ou sanitização.
* **Resolução:** Adicionar validação com `os.path.realpath`, verificação de `path.is_dir()`, bloqueio de pastas de sistema e amarração estrita do servidor a `127.0.0.1`.

#### M4. Contratos REST Incompletos e Anti-Patterns de Métodos
* **Lentes:** `egm-critic` (F5), `egm-implementation-readiness` (F5)
* **Problema:** `POST /api/projects/{id}/notes` combina criação e edição sem verbo `PUT`/`PATCH`. Códigos de status HTTP e esquemas de erro não foram definidos.
* **Resolução:** Separar criação (`POST`) de mutação (`PUT /api/projects/{id}/notes/{note_id}`), documentar schemas de entrada/saída e códigos HTTP padrão.

#### M5. Inconsistência no Ciclo de Vida e Vocabulário de Status das Notas
* **Lentes:** `egm-comprehension` (F4), `egm-critic` (F3), `egm-implementation-readiness` (F9)
* **Problema:** Diferentes seções usam enumerações distintas: `Ideia`, `Aberta`, `Planejada`, `Em Revisão`, `Incorporada`.
* **Resolução:** Padronizar um enum canônico único em todo o documento: `idea`, `planned`, `in_review`, `incorporated`.

#### M6. Ausência Total de Testes Automatizados e CI
* **Lentes:** `egm-implementation-readiness` (F7)
* **Problema:** A Fase 1 deleta `.github/workflows/validate.yml`, deixando o repositório sem nenhum pipeline de validação ou testes.
* **Resolução:** Incluir testes básicos de unidade (`tests/test_scanner.py`, `tests/test_api.py`) e criar `.github/workflows/ci.yml` na Fase 6.

---

### 🟢 Nits

#### N1. Termo Externo Não Definido ("Orca")
* **Lentes:** `egm-comprehension` (F1), `egm-zoom-out` (Etapa 8)
* **Resolução:** Adicionar nota explicativa definindo o Orca como o CLI orquestrador de agentes externo utilizado pelo desenvolvedor no terminal, sem chamadas diretas ou acoplamento com o Project OS.

#### N2. Assimetria Bilíngue de Cabeçalhos
* **Lentes:** `egm-critic` (F7)
* **Resolução:** Traduzir os cabeçalhos de Nível 2 para Português (`## 1. O Problema`, `## 2. Visão Geral`, `## 3. Objetivos`, etc.), harmonizando o documento.

#### N3. Estratégia de Distribuição do Mermaid.js e Degradação Visual
* **Lentes:** `egm-critic` (F6), `egm-implementation-readiness` (F10)
* **Resolução:** Especificar o carregamento do Mermaid.js (via vendor local ou CDN com fallback) e adicionar tratamento de erro visual com opção de visualizar o Markdown bruto quando a sintaxe for inválida.

---

## 4. Traceability Matrix

| ID | Descoberta Consolidada | Origem (Lentes / Relatórios) | Impacto no Design |
|---|---|---|---|
| **B1** | Contradição LLM Bridge vs. NG1 | Zoom-Out #1/#8, Comprehension #2, Critic #2, Readiness #3 | Remover `llm_bridge.py` do backend |
| **B2** | Drift por cache `_summary.json` | Zoom-Out #2/#8 | Eliminar `data/cache/`; leitura on-demand |
| **B3** | Omissão de `app.js` e `styles.css` | Codebase Details #1 | Incluir arquivos JS/CSS na Fase 5 |
| **B4** | Contradição FastAPI vs. `http.server` | Zoom-Out #3/#8, Readiness #2 | Manter `http.server` sem dependências |
| **M1** | Reconciler vs. Git Telemetry nativa | Zoom-Out #4/#8, Comprehension #3, Readiness #4 | Substituir por `get_git_telemetry()` |
| **M2** | Isolamento de notas vs. docs locais | Zoom-Out #5/#8, Critic #3/#4 | Suportar notas no projeto ou JSON simples |
| **M3** | Path Traversal em caminhos locais | Critic #1, Zoom-Out #8 | Validação `os.path.realpath` e `127.0.0.1` |
| **M4** | Contratos de API e verbos HTTP | Critic #5, Readiness #5 | Separar POST/PUT e schemas explícitos |
| **M5** | Enum de status de notas divergente | Comprehension #4, Critic #3, Readiness #9 | Unificar enum canônico de status |
| **M6** | Omissão de testes e CI | Readiness #7 | Adicionar testes e `.github/workflows/ci.yml` |
| **N1** | Definição de Orca ausente | Comprehension #1, Zoom-Out #6 | Adicionar definição de ator externo |
| **N2** | Títulos bilíngues | Critic #7 | Padronizar títulos em Português |
| **N3** | Distribuição de Mermaid.js | Critic #6, Readiness #10 | Tratar fallback e fonte do script |
