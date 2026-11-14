# Nexus Cockpit — Observabilidade do Main Vault e Visão Consolidada por Entidade

* **Author:** @salmeida
* **Date:** 2026-11-13

## Overview

Expandir o `nexus-cockpit` (`C:\Docker\nexus-cockpit`) como painel de observabilidade somente leitura sobre as quatro áreas centrais do `main_vault` (`01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs`, `05_Areas`), consolidando a visualização por entidade/cliente (`Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`, `Todas`) com indicadores de integridade de frontmatter/contratos, frescor por tipo de nota e matriz objetiva de divergência entre fichas do vault e repositórios locais / telemetria Git.

O sistema utilizará um índice local `sqlite3` (biblioteca padrão do Python) estritamente como camada derivada e descartável dos arquivos Markdown, preservando o `main_vault` como única fonte da verdade, sem execução de agentes ou `n8n` pela web, sem escrita sobre o vault e sem conexão direta a bancos de dados externos de clientes.

---

## Analysis

A proposta foi submetida à revisão paralela de 6 lentes Goldfish (`egm-zoom-out`, `egm-comprehension`, `egm-design`, `egm-codebase-details`, `egm-implementation-readiness`, `egm-structural`) contra o código atual do `nexus-cockpit` e os arquivos reais do `main_vault`. Os pontos críticos levantados foram resolvidos pelas decisões de escopo abaixo:

### 1. Índice Local `sqlite3` Derivado e Emenda Formal de `NG4` / `Zero Drift`
* Embora o volume atual (~40–50 arquivos Markdown) pudesse ser atendido apenas pelo cache em memória de 30s de `ui/infra_scanner.py`, optou-se por manter `sqlite3` (stdlib Python) como índice local derivado para sustentar consultas consolidadas por entidade, diagnóstico estrutural de varredura (`scan_runs` / `scan_errors`) e snapshots de telemetria Git sem disparar subprocessos síncronos a cada request HTTP.
* **Mitigações obrigatórias:**
  * Emendar formalmente `NG4` e `Zero Drift` em [local_project_os.md](file:///C:/Docker/nexus-cockpit/docs/designs/local_project_os.md) e [infra_and_subsystems_catalog.md](file:///C:/Docker/nexus-cockpit/docs/designs/infra_and_subsystems_catalog.md), restringindo `sqlite3` exclusivamente a índice descartável/reconstruível (ex.: em `/tmp/nexus_vault_index.db` ou fora do contexto `COPY data/` no `Dockerfile`), sem alterar a persistência plana de `data/projects.json`, `data/config.json` e `data/notes/`.
  * Invalidar por `(relative_path, size_bytes, mtime_ns)` + hash SHA-256 do conteúdo (nunca confiar apenas em `st_mtime` do Google Drive), proteger reindexação com `threading.Lock` (single-flight), usar conexões por thread com `busy_timeout` e preservar o índice anterior se o mount do Drive ficar temporariamente indisponível (`vault_status: "unavailable"`).
  * Exibir na UI o timestamp `last_indexed_at` e botão de reindexação manual, removendo selos contraditórios e separando explicitamente na documentação a fronteira **Observabilidade Read-Only do Vault** da camada **Ledger Local do Cockpit** (`data/notes/`, `projects.json`).

### 2. Escopo Completo das 4 Pastas com Isenção por Tipo de Artefato e Segurança
* O cockpit passa a ler `01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas` mantendo políticas distintas por pasta para evitar falsos alarmes:
  * **`01_Projetos`:** Validação de contrato + frescor por atividade + cruzamento Git/Docker.
  * **`02_Recursos_e_Infra`:** Validação de contrato + matriz de portas (`docker-compose.yml` vs fichas).
  * **`04_Arquitetura_ADRs`:** Apenas integridade de contrato (`adr`, `titulo`, `data`, `status`, `entidade`, `contexto`) e alerta caso `status == "Substituído"` sem referência à substituta; **isento de alarme de idade/obsolescência** (ADRs aprovadas são imutáveis).
  * **`05_Areas`:** Apenas integridade de contrato e pontes; **isento de alarme de idade**; sem expor o corpo bruto de notas sensíveis (como dados bancários/CNPJ de `ICENV_Memoria_Institucional.md` ou perfis pessoais) nos endpoints da API — exibindo apenas metadados estruturados, status de conformidade e timestamps; notas auxiliares sem frontmatter e arquivos binários recebem tratamento explícito definido em schema, sem desaparecerem silenciosamente nem quebrarem o índice.
* **Hardening de segurança e mounts:** Montar no Docker **apenas** as 4 subpastas em `:ro` (ou subpaths explícitos sem expor `.agents/`, `scripts/`, `.obsidian/` ou `chaves_ssh/`), alterar `docker-compose.yml` para `127.0.0.1:4100` (em vez de `0.0.0.0:4100`) e remover `Access-Control-Allow-Origin: *` de `ui/app.py`.

### 3. Contrato Único via Manifesto JSON Compartilhado (`vault_schemas.json`)
* Em vez de duplicar regras normativas entre `scripts/harness/Test-VaultSchemas.ps1` (PowerShell) e Python, um manifesto JSON único (`vault_schemas.json`) passa a ser a fonte normativa lida tanto pelo harness PowerShell (`ConvertFrom-Json`) quanto pelo validador Python stdlib do `nexus-cockpit` (`json`).
* O manifesto cobrirá explicitamente as 4 pastas (incluindo `04_Arquitetura_ADRs`, hoje descoberta no `Test-VaultSchemas.ps1`, e as exclusões de `_Template_*.md`, `README.md`, `00_INDICE_AREAS.md`), além de registrar entidades extensíveis conforme `ADR-008`.
* Os dois parsers YAML manuais atuais (`ui/infra_scanner.py:parse_yaml_frontmatter` e `ui/app.py:parse_markdown_note`) serão consolidados em um único parser stdlib estrito: tratando UTF-8 BOM (`\ufeff`), desescapando `\\` em strings entre aspas, tratando `#` e listas inline corretamente, preservando campos ausentes como `None` (sem injetar `status: "Desconhecido"`) e registrando falhas em vez de engolir exceções.

### 4. Vínculo N:1 e Matriz Restrita de Divergência de Status
* **Vínculo `01_Projetos` ↔ `projects.json`:** Matching determinístico por caminho canônico normalizado de `repositorio_local` (com suporte opcional a chave explícita `cockpit_id` / `vault_note_path`), tratando strings não-filesystem (`"Notebook Dell (192.168.15.176)"`, `"Incorporado em ..."`, `""`) como `non_path_reference` e suportando múltiplos módulos para o mesmo repositório (`SIAEBR_Project.md` + `SIAEBR_MatPlan.md` → `Project_Siaebr`).
* **Repositórios e caminhos no Drive:** Suportar mount opcional em `:ro` para `G:\Meu Drive\01 Projetos` (permitindo telemetria Git real para `Financeiro_Pessoal`, `Sistema_de_Obras` e `ICENV_Treasury`) e distinguir caminhos não montados no container (`I:\Meu Drive`, `G:\...` ausente) como `not_mounted_in_runtime`, evitando falsos positivos de link quebrado.
* **Matriz limitada de divergência:** Restringir alertas de divergência apenas a condições objetivas e binárias:
  * `vault.status == "Arquivado"` com commits Git recentes ou working tree alterada;
  * `vault.status in ("Produção", "Em Desenvolvimento")` com `repositorio_local` (quando path válido e sob mount acessível) inexistente ou não-Git;
  * Divergência entre `portas` declaradas na ficha e portas expostas no `docker-compose.yml` do projeto;
  * Projeto registrado em `projects.json` sem ficha correspondente em `01_Projetos` (órfão).
  * Estados como `is_dirty` em projeto `Produção` ou ausência de `repositorio_local` em estudos/infra são exibidos apenas como **indicadores informativos**, nunca como erro de divergência.

### 5. Pré-requisito de Saneamento (`axion-cockpit` → `nexus-cockpit`) e Performance
* Antes de expandir a UI e o scanner: atualizar `ui/scanner.py` (linha 82, que ainda testa `"axion-cockpit"`), `docker-compose.yml`, `ui/index.html`, `ui/app.py`, `data/projects.json` e links em `docs/` para `nexus-cockpit` (mantendo fallback legado para `AXION_VAULT_PATH` / `AXION_VAULT_HOST_DIR` e detecção automática de `/vault` legado vs raiz).
* Mover o `HEALTHCHECK` (`docker-compose.yml` e `Dockerfile`) de `GET /api/projects` para `GET /api/status` para eliminar execuções síncronas de `git` a cada 30s, e refatorar inicialização/testes (`ui/app.py`, `tests/`) para injeção explícita de `vault_root`, `projects_file` e `db_path` sem vazar fixtures para `data/` ou ler o `G:\Meu Drive` real em CI.

---

## Goals vs. Non-Goals

* **In-Scope Goals:**
  * Painel de observabilidade somente leitura consolidado por entidade (`Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`, `Todas`) cobrindo `01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas`.
  * Índice `sqlite3` local derivado e descartável com invalidação por SHA-256, `last_indexed_at` visível e botão de reindexação manual.
  * Validação de contratos compartilhada via manifesto JSON único (`vault_schemas.json`) entre `Test-VaultSchemas.ps1` e o parser YAML unificado do cockpit.
  * Isenção explícita de obsolescência por idade para ADRs e Áreas, e não exposição do corpo bruto de notas sensíveis de `05_Areas` na API.
  * Vínculo determinístico N:1 entre `01_Projetos` e repositórios locais (com mount opcional `:ro` para `G:\Meu Drive\01 Projetos`) e matriz binária limitada de divergência.
  * Saneamento `axion-cockpit` → `nexus-cockpit`, hardening (`127.0.0.1:4100`, remoção de `CORS: *`) e `HEALTHCHECK` em `/api/status`.

* **Out-of-Scope Non-Goals:**
  * Executar agentes de IA, LLMs, prompts ou fluxos `n8n` dentro do `nexus-cockpit`.
  * Editar arquivos do `main_vault` ou código dos repositórios pela interface web.
  * Conectar o cockpit diretamente a bancos de dados externos de clientes (PostgreSQL SIAE BR, Supabase ICENV, etc.) via *data pointers*.
  * Adotar a taxonomia de ~49 arquivos normativos de `_system/` de `starmynd-org/infinite-brain-os` ou implementar busca vetorial (`pgvector`).
  * Heurísticas abertas de "score de obsolescência" por `st_mtime` sobre ADRs/memoriais ou auto-mutação de `status` entre vault e `projects.json`.

---

## Alternatives Weighed

1. **Adotar a estrutura completa de `starmynd-org/infinite-brain-os` dentro do `nexus-cockpit`:**
   * *Motivo da rejeição:* `infinite-brain-os` é uma convenção de arquivos Markdown/YAML + validador Bash (`_system/validate.sh`) sem servidor web nem runtime próprio; o `main_vault` já cumpre esse papel com `AGENTS.md`, `00_Dashboard/` e `Test-VaultSchemas.ps1`. Importar ~49 arquivos de regras duplicaria o vault e aumentaria o atrito operacional no Windows.
2. **Conectar o `nexus-cockpit` diretamente a bancos de clientes via *Data Pointers* + `pgvector`:**
   * *Motivo da rejeição:* Quebraria a restrição de zero dependências externas (`G6`) e zero conexão a bancos de produção (`NG3`), exigiria guardar credenciais sensíveis no container Docker e dependeria de VPN corporativa (`192.18.10.20`), sem resolver o gargalo prioritário de integridade do vault.
3. **Cache apenas em memória (TTL 30s) sem `sqlite3`:**
   * *Motivo da rejeição:* Embora suficiente para o volume atual de ~40–50 notas e aderente ao `NG4` original, não persiste histórico de diagnósticos de varredura (`scan_runs` / `scan_errors`) nem snapshots de telemetria Git desacoplados das requisições HTTP. Optou-se por manter `sqlite3` estritamente como índice derivado descartável com emenda formal de `NG4`.
4. **Restringir a V1 a `01_Projetos` + `02_Recursos_e_Infra` (excluindo `04_Arquitetura_ADRs` e `05_Areas`):**
   * *Motivo da rejeição:* Deixaria os dossiês comerciais/institucionais de clientes (`05_Areas`) e as decisões arquiteturais (`04_Arquitetura_ADRs`) fora da visão consolidada por entidade. Em vez de excluir as pastas, definiu-se isenção de idade para ambas, validação via JSON único e restrição contra exposição do corpo bruto de `05_Areas`.
5. **Reimplementar regras de `Test-VaultSchemas.ps1` diretamente em Python:**
   * *Motivo da rejeição:* Criaria duas fontes de verdade normativas sujeitas a dessincronização quando novos clientes/regras forem adicionados (`ADR-008`). Substituído pelo manifesto JSON único (`vault_schemas.json`).

---

## Key Decisions & Staging for Next Steps

Decisões fechadas para o documento formal de design (`/egm-draft`):

1. **Persistência:** `sqlite3` mantido exclusivamente como índice derivado descartável (com emenda formal de `NG4` / `Zero Drift` em `local_project_os.md` e `infra_and_subsystems_catalog.md`), invalidado por `(size_bytes, mtime_ns, sha256)` e protegido por lock single-flight.
2. **Escopo do Vault e Isenções:** Leitura `:ro` das 4 pastas (`01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs`, `05_Areas`) sem montar a raiz de `main_vault`; isenção de idade para ADRs e Áreas; API retorna apenas metadados/status de conformidade para `05_Areas` (sem corpo bruto).
3. **Contrato Único:** Manifesto `vault_schemas.json` compartilhado entre `Test-VaultSchemas.ps1` e o validador Python stdlib, acompanhado da unificação do parser YAML em `ui/`.
4. **Divergência e Vínculo N:1:** Matching determinístico por `repositorio_local` normalizado com suporte N:1, distinção de `not_mounted_in_runtime` vs `missing_on_disk` vs `non_path_reference`, mount `:ro` opcional para `G:\Meu Drive\01 Projetos`, e matriz de divergência limitada a condições binárias objetivas (`Arquivado` ativo, repo esperado ausente, portas divergentes, órfão em `projects.json`).
5. **Fase 0 Obrigatória:** Saneamento `axion-cockpit` → `nexus-cockpit` (incluindo `ui/scanner.py:82`), bind `127.0.0.1:4100`, remoção de `CORS: *`, `HEALTHCHECK` em `/api/status` e injeção de caminhos para testes isolados em CI.
