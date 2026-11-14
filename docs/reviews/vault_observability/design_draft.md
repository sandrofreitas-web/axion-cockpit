# Nexus Cockpit — Observabilidade do Main Vault e Visão Consolidada por Entidade

*   **Author:** @salmeida
*   **Status:** Draft
*   **Date:** 2026-11-13

--------------------------------------------------------------------------------

## Overview

Este documento define a arquitetura e o plano de implementação para expandir o `nexus-cockpit` (`C:\Docker\nexus-cockpit`) como painel web de observabilidade somente leitura sobre as quatro áreas centrais do `main_vault` (`01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas`), consolidando a leitura por entidade (`Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`, `Todas`).

A extensão mantém os arquivos Markdown do `main_vault` como única fonte da verdade, introduz um índice `sqlite3` local estritamente como camada derivada e descartável (emendando `NG4` e `Zero Drift` em [local_project_os.md](file:///C:/Docker/nexus-cockpit/docs/designs/local_project_os.md) e [infra_and_subsystems_catalog.md](file:///C:/Docker/nexus-cockpit/docs/designs/infra_and_subsystems_catalog.md)), adota um manifesto JSON único (`vault_schemas.json`) compartilhado com o harness PowerShell do vault (`Test-VaultSchemas.ps1`), executa o saneamento de identidade de `axion-cockpit` para `nexus-cockpit` (`ADR-008`) e aplica endurecimento de rede local.

## The Problem

Hoje o ecossistema sofre quatro lacunas operacionais entre o console web (`nexus-cockpit`) e a base de governança (`main_vault`):

1. **Visibilidade parcial do `main_vault` no console:** O `docker-compose.yml` monta apenas `02_Recursos_e_Infra:/vault:ro`, deixando `01_Projetos`, `04_Arquitetura_ADRs` e `05_Areas` invisíveis na UI web. Além disso, não há consolidação cruzada por entidade/cliente conectando fichas de projetos do vault, ADRs, infraestrutura e repositórios Git locais.
2. **Descompasso de identidade e vínculo frágil com repositórios:** Apesar da `ADR-008` ter renomeado o sistema para `Nexus` (`Pessoal`), o código, a UI, `data/projects.json`, `docker-compose.yml` e `ui/scanner.py` ainda carregam referências hardcoded a `axion-cockpit` e `AXION_VAULT_*`. Paralelamente, `01_Projetos/` possui vínculo N:1 com repositórios (`SIAEBR_Project.md` e `SIAEBR_MatPlan.md` → `Project_Siaebr`) e repositórios em `G:\Meu Drive\01 Projetos\*` ficam fora do mount `/projects:ro`, gerando ausência de telemetria Git real.
3. **Validação de contratos fragmentada e parser YAML frágil:** O `Test-VaultSchemas.ps1` roda apenas via CLI PowerShell no host e não cobre `04_Arquitetura_ADRs`, enquanto o cockpit possui dois parsers YAML manuais duplicados (`ui/infra_scanner.py` e `ui/app.py`) que não tratam UTF-8 BOM, escape de `\\`, listas inline ou ausência de frontmatter, e silenciam exceções de leitura.
4. **Riscos operacionais e de exposição local:** O container atual expõe `0.0.0.0:4100` com `Access-Control-Allow-Origin: *` e aponta o `HEALTHCHECK` a cada 30s para `GET /api/projects` (disparando subprocessos `git` síncronos por projeto). Ao incluir `05_Areas` (que contém dados institucionais e bancários sensíveis), a exposição da API sem restrição de loopback e sem filtragem de corpo bruto cria risco direto de vazamento local.

A solução proposta resolve esses pontos mantendo o cockpit como observador somente leitura do vault, com índice `sqlite3` descartável invalidado por conteúdo, contrato único em JSON, política explícita de isenção de idade para ADRs/Áreas e matriz binária objetiva de divergência.

## Goals

*   **G1 — Visão Consolidada por Entidade:** Exibir no cockpit um recorte por entidade (`Todas`, `Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`, extensível via registro declarativo) agregando fichas de `01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e metadados de `05_Areas` com indicadores numéricos de conformidade e vínculos.
*   **G2 — Contrato Único via `vault_schemas.json` e Parser YAML Unificado:** Substituir os dois parsers manuais duplicados por um único parser stdlib estrito (com suporte a UTF-8 BOM, desescape `\\`, tratamento correto de `#` e listas, sem defaults falsos) validando contra um manifesto `vault_schemas.json` compartilhado entre `Test-VaultSchemas.ps1` e o backend Python.
*   **G3 — Índice `sqlite3` Derivado com Frescor Verificável:** Persistir metadados, erros de varredura (`scan_errors`) e snapshots de telemetria Git em `sqlite3` local descartável (invalidado por tamanho, `mtime_ns` e SHA-256), expondo `last_indexed_at`, status do vault (`available` / `unavailable`) e botão de reindexação manual na UI.
*   **G4 — Vínculo Determinístico N:1 e Matriz Restrita de Divergência:** Ligar fichas de `01_Projetos` aos repositórios locais por caminho canônico normalizado de `repositorio_local` (suportando múltiplos módulos por repo e distinguindo `non_path_reference` e `not_mounted_in_runtime`), sinalizando apenas divergências objetivas (`Arquivado` ativo no Git, repo esperado ausente sob mount válido, portas divergentes, registro órfão em `projects.json`).
*   **G5 — Política Diferenciada de Idade e Privacidade de `05_Areas`:** Isentar `04_Arquitetura_ADRs` e `05_Areas` de alertas de obsolescência por idade e impedir que endpoints de observabilidade do vault exponham o corpo bruto de notas de `05_Areas`.
*   **G6 — Saneamento de Identidade, Hardening e Saúde:** Concluir a migração `axion-cockpit` → `nexus-cockpit` (com fallback temporário para variáveis `AXION_VAULT_*`), restringir o bind Docker para `127.0.0.1:4100`, remover `Access-Control-Allow-Origin: *` e redirecionar o `HEALTHCHECK` para `GET /api/status`.

## Non-Goals

*   **NG-A — Execução de Agentes, LLMs ou Automações:** O `nexus-cockpit` não dispara subagentes, comandos CLI, prompts ou fluxos `n8n`.
*   **NG-B — Escrita no `main_vault` ou nos Repositórios Monitorados:** Nenhuma rota web cria, edita ou promove arquivos Markdown dentro do `main_vault` ou altera código-fonte dos projetos.
*   **NG-C — Conexão Direta a Bancos Externos de Clientes:** O cockpit não abre conexões TCP/SQL com bancos de produção ou staging (PostgreSQL SIAE BR, Supabase ICENV, etc.) via *data pointers*, nem armazena credenciais de clientes.
*   **NG-D — Adoção da Taxonomia `_system/` do `infinite-brain-os` ou Busca Vetorial:** Não serão importados os arquivos normativos de `starmynd-org/infinite-brain-os` nem adicionadas dependências externas (`pip install`, `pgvector`, embeddings).
*   **NG-E — Auto-Mutação de Status:** O sistema nunca reescreve `status` no frontmatter do vault nem em `data/projects.json` a partir de heurísticas Git.

## Open Questions

Nenhuma questão arquitetural em aberto. As decisões sobre volumes Docker, localização de `vault_schemas.json` e persistência/modo do `sqlite3` foram resolvidas e incorporadas no Plano Técnico.

## Critical User Journeys (CUJs)

### CUJ 1: Consulta Consolidada por Entidade no Cockpit

*   **Given**: O container do `nexus-cockpit` está em execução em `127.0.0.1:4100` com as 4 pastas do `main_vault` montadas em `:ro` e o índice `sqlite3` populado.
*   **When**: O operador seleciona a entidade `SIAE BR` (ou `Pessoal`, `Axion Skill`, `Igreja ICENV`, `Todas`) no painel de observabilidade do vault.
*   **Then**: A interface exibe exclusivamente os projetos (`01_Projetos`), recursos de infraestrutura (`02_Recursos_e_Infra`), ADRs (`04_Arquitetura_ADRs`) e metadados de áreas (`05_Areas`) vinculados àquela entidade, mostrando contadores de conformidade de contrato, vínculos N:1 (`SIAEBR_Project` e `SIAEBR_MatPlan` ligados ao repo `Project_Siaebr`), `last_indexed_at` e sem exibir conteúdo bruto de notas de `05_Areas`.

### CUJ 2: Auditoria de Integridade de Contratos e Isenção de Idade

*   **Given**: O `main_vault` contém uma ADR aprovada com data de 6 meses atrás em `04_Arquitetura_ADRs/`, uma nota sem frontmatter em `05_Areas/` e um projeto em `01_Projetos/` com campo obrigatório ausente segundo `vault_schemas.json`.
*   **When**: O operador executa uma reindexação manual ou abre a aba de auditoria de contratos no cockpit.
*   **Then**: O painel sinaliza erro de contrato no projeto com campo ausente, registra o status explícito da nota sem frontmatter em `05_Areas/` conforme a regra do manifesto, e exibe a ADR aprovada como conforme (sem nenhum alerta de obsolescência por idade).

### CUJ 3: Detecção Limitada de Divergência Vault ↔ Git / Docker Compose

*   **Given**: O vault possui `Categorizador_Code.md` (`status: "Arquivado"`), `ICENV_Site.md` (`status: "Produção"`) e `HomeLab_Server.md` (`repositorio_local: "Notebook Dell (192.168.15.176)"`).
*   **When**: O indexador cruza os projetos do vault com os repositórios locais montados e os manifestos `docker-compose.yml`.
*   **Then**: `HomeLab_Server.md` recebe estado `non_path_reference` (sem erro de caminho); se `ICENV_Site.md` tiver working tree suja no Git local, recebe apenas badge informativo `is_dirty`; e somente violações objetivas da matriz (como ficha `Arquivado` com commits recentes em repositório dedicado, `Produção` com `repositorio_local` ausente sob mount acessível, ou colisão/divergência de portas declaradas) geram alerta de divergência.

### CUJ 4: Degradação Graciosa com Google Drive ou Mount Indisponível

*   **Given**: O índice `sqlite3` já possui um snapshot válido indexado anteriormente, mas o Google Drive (`G:\`) é desmontado ou um repositório em `G:\Meu Drive\01 Projetos` não está montado no container Linux.
*   **When**: O operador acessa o cockpit ou aciona o refresh do índice.
*   **Then**: O servidor responde `200` no `HEALTHCHECK` (`GET /api/status`), mantém o último snapshot válido sinalizando `vault_status: "unavailable"` (ou marca os repositórios não montados como `not_mounted_in_runtime`), sem apagar os dados anteriores nem reportar 100% do vault como vazio ou quebrado.

--------------------------------------------------------------------------------

## Technical Plan (Architecture)

### 1. Arquitetura Geral e Fronteira de Dados

O `nexus-cockpit` passa a operar com duas fronteiras explícitas e isoladas:

1. **Observabilidade Read-Only do `main_vault`:** Montagem somente leitura do `main_vault` em `/main_vault:ro` (via `NEXUS_VAULT_HOST_DIR`) e dos repositórios do Drive em `/drive_projects:ro` (via `DRIVE_PROJECTS_HOST_DIR`), com **allowlist estrita** no scanner permitindo apenas `01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs`, `05_Areas` e `scripts/harness/vault_schemas.json`. Diretórios como `.agents/`, `.obsidian/`, `chaves_ssh/` e o restante de `scripts/` nunca são indexados nem servidos pela API.
2. **Estado Local do Cockpit (`data/`):** Mantém `data/projects.json`, `data/config.json` e `data/notes/{project_id}/*.md` como ledger local editável exclusivamente para o catálogo do cockpit, separado do vault.

```mermaid
flowchart TD
    subgraph Host["Host Windows / Google Drive"]
        MV["main_vault (01_Projetos, 02_Recursos_e_Infra, 04_Arquitetura_ADRs, 05_Areas, vault_schemas.json)"]
        DP["Drive Repos (G:/Meu Drive/01 Projetos)"]
        LP["Repos Locais (C:/Docker)"]
        PS["Test-VaultSchemas.ps1 (Host CLI)"]
    end

    subgraph Container["nexus-cockpit (127.0.0.1:4100)"]
        VP["vault_parser.py (YAML stdlib estrito)"]
        VS["vault_validator.py (Lê vault_schemas.json)"]
        VI["vault_index.py (/tmp/nexus_vault_index.db, WAL)"]
        VR["vault_reconciler.py (Match N:1 + Matriz Divergência)"]
        API["ui/app.py (REST API sem CORS *)"]
        SPA["ui/index.html + app.js (3 Domínios + Filtro Entidade)"]
    end

    PS -->|Lê contrato único| MV
    MV -->|/main_vault:ro (Allowlist)| VP
    MV -->|/main_vault:ro| VS
    DP -->|/drive_projects:ro| VR
    LP -->|/projects:ro| VR
    VP --> VS --> VI
    VR --> VI
    VI --> API --> SPA
```

### 2. Contrato Único (`vault_schemas.json`) e Parser YAML Unificado

*   **Localização e leitura:** O manifesto canônico reside em `main_vault/scripts/harness/vault_schemas.json` (com suporte a override `NEXUS_SCHEMA_PATH` apenas para testes/CI). Tanto `Test-VaultSchemas.ps1` (`ConvertFrom-Json`) quanto `ui/vault_validator.py` (`json`) consomem exatamente o mesmo arquivo.
*   **Estrutura declarativa do manifesto:**
    *   `entities`: lista extensível de entidades permitidas (`["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV", "Todas"]`), alinhada à `ADR-008`.
    *   `domains`: definição por pasta (`01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs`, `05_Areas`) contendo:
        *   `recursive` (`bool`), `ignored_filenames` (`README.md`, `_Template_Projeto.md`, `00_INDICE_AREAS.md`, etc.), `ignored_dirs` (`chaves_ssh`, `.obsidian`, `.git`);
        *   `required_fields` e `optional_fields` por domínio (cobrindo `04_Arquitetura_ADRs` com `adr`, `titulo`, `data`, `status`, `entidade`, `contexto`);
        *   `allowed_enums` (ex.: `01_Projetos.status`, `04_Arquitetura_ADRs.status`);
        *   `age_policy`: `enabled: true` com limiares apenas para `01_Projetos`, e `enabled: false` (`exempt: true`) para `04_Arquitetura_ADRs` e `05_Areas`;
        *   `allow_body_preview`: `true` para projetos/infra/ADRs, `false` para `05_Areas` (bloqueio estrito de exposição de corpo bruto);
        *   `non_frontmatter_policy`: comportamento explícito por pasta (ex.: `error` em `01_Projetos`/`04_Arquitetura_ADRs`, `warning_non_contract` para notas auxiliares em `05_Areas`, ignorando arquivos binários como `.pdf`/`.jpg`).
    *   `global_rules`: regex de proibição de wikilinks absolutos (`[[C:\...`) e checagem de notas vazias (0 bytes).
*   **Parser YAML unificado (`ui/vault_parser.py`):** Substitui `parse_yaml_frontmatter` (`ui/infra_scanner.py`) e `parse_markdown_note` (`ui/app.py`) por um parser único stdlib que:
    1. Remove UTF-8 BOM (`\ufeff`) antes de detectar delimitadores `---`;
    2. Diferencia `frontmatter_status`: `"ok"`, `"missing"`, `"malformed"`;
    3. Desescapa sequências `\\` e `\"` em strings com aspas duplas;
    4. Trata comentários `#` apenas fora de strings e trata listas inline (`[a, b]`) e listas multiline (`- item`);
    5. Nunca injeta valores padrão artificiais (`status: "Desconhecido"`), preservando campos ausentes como `None` para que o validador detecte violações reais.

### 3. Índice Derivado `sqlite3` (`/tmp/nexus_vault_index.db`)

*   **Ciclo de vida e concorrência:**
    *   Armazenado em `/tmp/nexus_vault_index.db` no container (ou `tempfile.gettempdir()` no host Windows; injetável via `NEXUS_INDEX_DB_PATH` em testes), fora de `./data` para evitar qualquer impacto no `COPY data/` do `Dockerfile` ou locks em binds NTFS ↔ WSL2.
    *   Configuração por conexão de thread: `PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=5000;`, `PRAGMA foreign_keys=ON;`. Versão controlada por `PRAGMA user_version` (se divergir, recria automaticamente as tabelas do zero).
    *   Reindexação protegida por `threading.Lock` (padrão *single-flight*): se dois requests acionarem refresh simultaneamente, o segundo aguarda ou retorna o snapshot corrente sem varredura paralela no `G:\`.
*   **Invalidação e Degradação Graciosa:**
    *   Antes de limpar tabelas, `vault_index.py` verifica se a raiz do vault e o manifesto `vault_schemas.json` estão acessíveis. Se inacessíveis, registra um `scan_run` com `vault_status = "unavailable"` e **preserva o último snapshot válido** em vez de zerar o índice.
    *   Cada arquivo é verificado por `(rel_path, size_bytes, mtime_ns)`. Se `size_bytes` ou `mtime_ns` mudarem (ou em `force_refresh`), recalcula `content_sha256`; só re-parseia e re-valida se o SHA-256 divergir ou a versão do `vault_schemas.json` (`schema_hash`) tiver mudado.
*   **Esquema relacional enxuto:**
    *   `scan_runs`: `id`, `started_at`, `finished_at`, `vault_status` (`available` | `unavailable` | `schema_error`), `schema_hash`, `files_total`, `errors_count`.
    *   `vault_nodes`: `rel_path` (PK), `domain` (`projects` | `infra` | `adrs` | `areas`), `entity`, `title`, `status`, `frontmatter_status`, `validation_errors_json`, `links_status` (`ok` | `not_mounted_in_runtime` | `non_path_reference` | `missing_on_disk`), `ports_json`, `size_bytes`, `mtime_ns`, `content_sha256`, `doc_date`, `age_exempt` (bool), `indexed_at`.
    *   `project_repo_links`: `vault_rel_path` (FK), `cockpit_project_id` (nullable), `raw_repo_ref`, `normalized_repo_path`, `link_state` (`accessible` | `not_mounted_in_runtime` | `non_path_reference` | `missing_on_disk`), `git_branch`, `git_is_dirty`, `git_uncommitted_count`, `git_last_commit_iso`, `git_checked_at`, `divergence_flags_json`.
    *   `scan_errors`: `id`, `run_id`, `rel_path`, `error_type`, `detail`, `occurred_at`.

### 4. Reconciliação N:1 e Matriz Limitada de Divergência

*   **Normalização e vínculo N:1 (`ui/vault_reconciler.py`):**
    *   `ui/scanner.py:resolve_cross_platform_path` passa a mapear `C:\Docker\...` → `/projects/...` (substituindo `"axion-cockpit"` por `"nexus-cockpit"`) e `G:\Meu Drive\01 Projetos\...` → `/drive_projects/...` quando o mount existir.
    *   Strings de `repositorio_local` vazias (`""`), IPs/descrições (`"Notebook Dell (192.168.15.176)"`) ou textos de incorporação (`"Incorporado em ..."`) são classificados como `non_path_reference` sem tentativa de `git`.
    *   O vínculo entre `01_Projetos/*.md` e `data/projects.json` usa matching determinístico por caminho normalizado (ou campo opcional explícito `cockpit_id`), permitindo que múltiplas fichas apontem para o mesmo repositório (`SIAEBR_Project.md` + `SIAEBR_MatPlan.md` → `Project_Siaebr`) sem erro de duplicidade.
*   **Regras estritas de divergência (apenas 4 condições binárias):**
    1. `archived_active_repo`: ficha com `status == "Arquivado"` apontando para repositório dedicado (não compartilhado como módulo incorporado) com commit recente ou working tree alterada.
    2. `expected_repo_missing`: ficha com `status in ("Produção", "Em Desenvolvimento")` e `link_state == "missing_on_disk"` (apenas quando o caminho pertence a um mount ativo; se o drive não estiver montado, marca `not_mounted_in_runtime`).
    3. `port_mismatch`: colisão ou divergência entre `portas` declaradas na ficha e portas extraídas do `docker-compose.yml` do repositório vinculado.
    4. `unlinked_cockpit_project`: projeto ativo em `data/projects.json` sem nenhuma ficha correspondente em `01_Projetos`.
*   `is_dirty` em projetos `Produção` ou `Em Desenvolvimento`, bem como diferença simples entre data de commit e `mtime`, aparecem apenas como metadado informativo.

### 5. Contratos da REST API, UI e Saneamento

*   **Endpoints existentes preservados:** `GET /api/status` (passa a reportar `"app": "Nexus Cockpit"` e estado resumido do índice sem I/O pesado, tornando-se o alvo do `HEALTHCHECK` a cada 30s), `GET /api/projects` (adiciona `git.last_commit_iso`), `GET /api/infra` (mantém retrocompatibilidade detectando `/main_vault/02_Recursos_e_Infra` ou `/vault` legado).
*   **Novos endpoints read-only do vault:**
    *   `GET /api/vault/entities`: lista entidades configuradas em `vault_schemas.json` com contadores agregados (projetos, infra, ADRs, áreas, erros de contrato, divergências).
    *   `GET /api/vault/overview?entity=<nome>`: retorna snapshot completo filtrado por entidade (`vault_nodes`, `project_repo_links`, `scan_errors`, `last_indexed_at`, `vault_status`). Para `domain == "areas"`, garante omissão estrita de conteúdo/corpo das notas.
    *   `POST /api/vault/reindex`: aciona reindexação síncrona protegida por `threading.Lock` (única mutação permitida, restrita ao índice derivado em `/tmp`).
*   **Hardening e UI (`ui/app.py`, `ui/index.html`, `ui/static/app.js`):**
    *   Bind padrão no `docker-compose.yml` alterado para `127.0.0.1:${PORT:-4100}:4100` e remoção do cabeçalho `Access-Control-Allow-Origin: *` de `ui/app.py`.
    *   Topbar atualizada para `NEXUS.COCKPIT`, adição da 3ª aba de domínio `🧠 Vault & Entidades` com seletor de entidade (`Todas`, `Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`), selo dinâmico `Índice: <last_indexed_at>` + botão `↻ Reindexar`, cards de saúde de contratos e tabela de divergências/vínculos N:1.

### 6. Requisitos Não-Funcionais Críticos

*   **Segurança e Privacidade:** O servidor escuta apenas em `127.0.0.1` no host, sem `CORS: *`; o scanner opera sobre allowlist fechada de 4 pastas e nunca retorna o conteúdo Markdown de `05_Areas` na API; `chaves_ssh/`, `.agents/` e `.env` permanecem inacessíveis aos endpoints.
*   **Desempenho e Latência:** Coleta de `git` em lote executa apenas durante a reindexação (e somente para repositórios que mudaram ou sob refresh explícito), mantendo `GET /api/status`, `GET /api/vault/overview` e `GET /api/vault/entities` respondendo direto do `/tmp/nexus_vault_index.db` sem subprocessos no caminho de leitura da UI.
*   **Migração e Rollback:** Variáveis legadas `AXION_VAULT_HOST_DIR` e `AXION_VAULT_PATH` continuam aceitas como fallback com aviso de deprecação caso `NEXUS_VAULT_HOST_DIR` não seja definida; o rollback consiste em reverter a imagem/branch sem qualquer migração destrutiva em `data/` ou no `main_vault`.

--------------------------------------------------------------------------------

## Alternatives Considered

### Alternative A: Adotar a estrutura completa de `starmynd-org/infinite-brain-os` dentro do `nexus-cockpit`

*   **Pros**: Fornece uma taxonomia pronta de namespaces, promoções (`intake/` -> `memory/` -> `canon/`) e ~49 arquivos de contrato normativo em `_system/`.
*   **Cons**: Duplica o papel do `main_vault` (que já possui `01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs`, `05_Areas`, `AGENTS.md`, `00_Dashboard/` e `Test-VaultSchemas.ps1`), depende de validador em Bash/awk incompatível nativamente com PowerShell no Windows e exige alto atrito de manutenção manual para um operador solo.
*   **Reason for Rejection**: O `infinite-brain-os` é uma convenção de repositório Markdown sem servidor web nem runtime próprio; replicar sua árvore de regras no `nexus-cockpit` criaria uma segunda fonte da verdade sem resolver a observabilidade local.

### Alternative B: Conectar o `nexus-cockpit` diretamente a bancos externos de clientes via Data Pointers e `pgvector`

*   **Pros**: Permitiria consultar números vivos de negócio (PostgreSQL SIAE BR, Supabase ICENV, Postgres local de Finanças/Obras) e executar busca semântica híbrida diretamente pela interface do cockpit.
*   **Cons**: Violaria os não-objetivos `NG3` (zero conexão a bancos de produção) e `G6` (zero dependências externas de `pip`), exigiria armazenar segredos de clientes dentro do container Docker, quebraria em redes sem VPN corporativa (`192.18.10.20`) e desviaria o console para um cliente SQL/BI.
*   **Reason for Rejection**: Aumenta a superfície de risco de credenciais e dependências externas para fora do escopo prioritário de integridade e governança do vault.

### Alternative C: Cache apenas em memória (TTL 30s) sem `sqlite3`

*   **Pros**: Mantém `NG4` intacto sem alteração documental, atende facilmente o volume atual de ~40–50 notas com leitura direta em SSD e elimina código de schema e controle de locks `sqlite3`.
*   **Cons**: Não persiste histórico de execuções de varredura (`scan_runs` e `scan_errors`) nem snapshots de telemetria Git desacoplados dos requests HTTP, mantendo pressão de leitura/Git sob carregamentos repetidos da interface.
*   **Reason for Rejection**: Escolheu-se manter `sqlite3` (da biblioteca padrão do Python) exclusivamente como índice descartável em `/tmp/nexus_vault_index.db` com emenda formal de `NG4`, garantindo isolamento de leitura HTTP em relação a subprocessos `git` e I/O do Google Drive.

### Alternative D: Restringir a V1 a `01_Projetos` + `02_Recursos_e_Infra` (excluindo `04_Arquitetura_ADRs` e `05_Areas`)

*   **Pros**: Evita lidar com pastas heterogêneas (ADRs imutáveis, notas sem frontmatter, arquivos binários e dados institucionais/bancários sensíveis em `05_Areas`) que já possuem painéis no Obsidian (`00_Dashboard/`).
*   **Cons**: Deixa a visão consolidada por entidade incompleta, ocultando ADRs e a situação contratual dos dossiês comerciais/institucionais (`05_Areas`) no console único.
*   **Reason for Rejection**: Manteve-se a leitura das 4 pastas mediante isenção explícita de idade para ADRs e Áreas, validação via manifesto único e bloqueio de exposição do corpo bruto de `05_Areas` na API.

### Alternative E: Reimplementar regras de validação em Python duplicando `Test-VaultSchemas.ps1` (ou acoplar o manifesto ao repo `nexus-cockpit`)

*   **Pros**: Evitaria alterar `Test-VaultSchemas.ps1` no `main_vault` ou depender do mount `/main_vault:ro` para ler as definições de schema.
*   **Cons**: Regras duplicadas divergem inevitavelmente quando novas entidades (`ADR-008`) ou campos obrigatórios são adicionados; inversamente, versionar o JSON apenas no `nexus-cockpit` acoplaria os scripts do `main_vault` ao caminho físico de outro repositório.
*   **Reason for Rejection**: Adotou-se o manifesto `vault_schemas.json` canônico em `main_vault/scripts/harness/`, consumido como fonte única por PowerShell e Python.

### Alternative F: Mounts separados por subpasta ou índice `sqlite3` persistido em `data/cache/`

*   **Pros**: Mounts individuais isolariam ainda mais o filesystem do container, e persistir o `.db` em `./data/cache/` sobreviveria a `docker compose up --force-recreate`.
*   **Cons**: Múltiplas entradas de volume no `docker-compose.yml` aumentam atrito de manutenção se o vault ganhar novos diretórios, e usar `WAL` em bind-mount Windows NTFS → WSL2 introduz risco de lock/corrupção e risco de inclusão acidental no `COPY data/` do `Dockerfile`.
*   **Reason for Rejection**: Adotou-se mount único `/main_vault:ro` com allowlist estrita no scanner e índice `sqlite3` efêmero em `/tmp/nexus_vault_index.db` (`WAL` nativo em filesystem Linux).

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Target Files to Create/Modify

#### 1. `G:\Meu Drive\main_vault\scripts\harness\vault_schemas.json` (Create)

*   **Type / Scope**: Schema Manifesto JSON (Fonte única de contrato entre harness do vault e `nexus-cockpit`)
*   **Proposed Changes**: Definir o contrato declarativo contendo `schema_version`, `entities` (`["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV", "Todas"]`), `global_rules` (checagem de arquivo vazio 0 bytes e regex de wikilinks absolutos proibidos) e `domains` para `01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas` — especificando `recursive`, `ignored_filenames`, `ignored_dirs` (`chaves_ssh`, `.obsidian`, `.git`), `required_fields`, `optional_fields`, `allowed_enums`, `age_policy` (`exempt: true` para ADRs e Áreas), `allow_body_preview` (`false` para `05_Areas`) e `non_frontmatter_policy`.

#### 2. `G:\Meu Drive\main_vault\scripts\harness\Test-VaultSchemas.ps1` (Modify)

*   **Type / Scope**: Script PowerShell do Harness (`main_vault`)
*   **Proposed Changes**: Substituir listas e regras hardcoded (`$allowedStatus`, `$allowedEntities`, blocos `if/else` por pasta) pela leitura de `vault_schemas.json` via `ConvertFrom-Json`, adicionando a validação de `04_Arquitetura_ADRs` (atualmente descoberta) e garantindo paridade exata de regras com o backend Python.

#### 3. `ui/vault_parser.py` (Create)

*   **Type / Scope**: Módulo Python Stdlib (Parser YAML Estrito Unificado)
*   **Proposed Changes**: Implementar `parse_frontmatter(content: str)` e `parse_vault_file(path: Path)` para substituir os parsers duplicados. Tratar remoção de UTF-8 BOM (`\ufeff`), delimitação estrita de bloco `---`, desescape de `\\` e `\"` em strings com aspas duplas, isolamento de comentários `#` fora de aspas, listas inline (`[a, b]`) e multiline (`- item`), retorno explícito de `frontmatter_status` (`"ok"` | `"missing"` | `"malformed"`), preservação de campos ausentes como `None` (sem defaults artificiais) e propagação de erros estruturados em vez de `except Exception: pass`.

#### 4. `ui/vault_validator.py` (Create)

*   **Type / Scope**: Módulo Python Stdlib (Validador de Contratos por Domínio)
*   **Proposed Changes**: Carregar `vault_schemas.json` a partir de `vault_root/scripts/harness/vault_schemas.json` (ou `NEXUS_SCHEMA_PATH` / parâmetro injetável em testes), calcular `schema_hash` (SHA-256), aplicar a allowlist estrita de 4 pastas, ignorar extensões binárias/arquivos listados, validar campos obrigatórios, enums, wikilinks absolutos e 0 bytes, e marcar `age_exempt` para `04_Arquitetura_ADRs` e `05_Areas`.

#### 5. `ui/vault_index.py` (Create)

*   **Type / Scope**: Módulo Python Stdlib (`sqlite3` — Índice Derivado Descartável)
*   **Proposed Changes**: Gerenciar `/tmp/nexus_vault_index.db` (ou `tempfile.gettempdir()` no Windows / `db_path` injetável) usando conexões por thread com `PRAGMA journal_mode=WAL`, `PRAGMA busy_timeout=5000`, `PRAGMA foreign_keys=ON` e controle de schema via `PRAGMA user_version`. Criar tabelas `scan_runs`, `vault_nodes`, `project_repo_links` e `scan_errors`. Implementar `reindex_vault(force: bool = False)` protegido por `threading.Lock` (single-flight), checando `(rel_path, size_bytes, mtime_ns)` e `content_sha256` + `schema_hash`, preservando o snapshot anterior com `vault_status = "unavailable"` se o mount ou manifesto estiver inacessível, e fornecendo consultas read-only filtradas por entidade (garantindo ausência de corpo bruto para `05_Areas`).

#### 6. `ui/vault_reconciler.py` (Create)

*   **Type / Scope**: Módulo Python Stdlib (Reconciliação N:1 e Matriz de Divergência)
*   **Proposed Changes**: Cruzar fichas de `01_Projetos` com `data/projects.json`, repositórios locais e portas de `docker-compose.yml`. Normalizar `repositorio_local` via `scanner.resolve_cross_platform_path` (e campo opcional `cockpit_id`), classificar `link_state` (`accessible`, `not_mounted_in_runtime`, `non_path_reference`, `missing_on_disk`), suportar múltiplos módulos apontando para o mesmo repositório (ex.: `SIAEBR_Project` e `SIAEBR_MatPlan` → `Project_Siaebr`), coletar snapshots Git apenas durante reindexação (ou alteração) e calcular as 4 flags binárias de divergência (`archived_active_repo`, `expected_repo_missing`, `port_mismatch`, `unlinked_cockpit_project`), mantendo `is_dirty` apenas como flag informativa.

#### 7. `ui/scanner.py` (Modify)

*   **Type / Scope**: Módulo Python Stdlib (Resolução de Caminhos e Telemetria Git)
*   **Proposed Changes**: Atualizar `resolve_cross_platform_path` substituindo `"axion-cockpit"` por `"nexus-cockpit"` na resolução de `/app` (linha 82) e adicionando mapeamento opcional para `DRIVE_PROJECTS_DIR` (`/drive_projects`, traduzindo `G:\Meu Drive\01 Projetos\...`). Estender `get_git_telemetry` para retornar também `last_commit_iso` via `git log -1 --format=%cI` (usado para avaliar atividade recente em `archived_active_repo` sem depender de texto relativo `%cr`).

#### 8. `ui/infra_scanner.py` (Modify)

*   **Type / Scope**: Módulo Python Stdlib (Scanner de Infraestrutura Global)
*   **Proposed Changes**: Remover `parse_yaml_frontmatter` duplicado e reutilizar `vault_parser.parse_frontmatter`; atualizar `resolve_vault_path` para aceitar `NEXUS_VAULT_ROOT` / `/main_vault` (resolvendo automaticamente a subpasta `02_Recursos_e_Infra` para manter o comportamento de `/api/infra`), mantendo fallback legado explícito para `AXION_VAULT_PATH` e `/vault`.

#### 9. `ui/app.py` (Modify)

*   **Type / Scope**: Servidor HTTP/REST (`ThreadingTCPServer`)
*   **Proposed Changes**: Remover `parse_markdown_note` duplicado (usando `ui/vault_parser.py`); remover cabeçalho `Access-Control-Allow-Origin: *` das respostas JSON; atualizar `"app": "Nexus Cockpit"` e incluir resumo do índice em `GET /api/status`; adicionar rotas `GET /api/vault/entities`, `GET /api/vault/overview` (com filtro `?entity=` e bloqueio explícito de corpo de `05_Areas`) e `POST /api/vault/reindex`; refatorar a inicialização em tempo de importação (`data/projects.json`, `NOTES_BASE_DIR`) para uma função `create_server(...)` / configuração injetável que facilite testes isolados.

#### 10. `ui/index.html`, `ui/static/app.js`, `ui/static/styles.css` (Modify)

*   **Type / Scope**: Interface Web SPA (HTML5 / Vanilla JS / CSS)
*   **Proposed Changes**: Renomear títulos e marca de `AXION.COCKPIT` para `NEXUS.COCKPIT`; substituir o selo estático `ZERO-DRIFT (ON-DEMAND)` por indicador dinâmico `Índice: <last_indexed_at>` (`available` / `unavailable`) com botão `↻ Reindexar`; adicionar 3ª aba de domínio `🧠 Vault & Entidades` com filtro de entidade (`Todas`, `Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`), cards de resumo (contratos válidos/erros, divergências binárias, erros de varredura), tabela de vínculos N:1 (`01_Projetos` ↔ Git/Compose) e separação visual entre painel de observabilidade read-only do vault e ledger local de notas do cockpit.

#### 11. `docker-compose.yml` e `Dockerfile` (Modify)

*   **Type / Scope**: Infraestrutura de Container e Compose
*   **Proposed Changes**: Renomear serviço, `name`, `image` e `container_name` de `axion-cockpit` para `nexus-cockpit`; alterar port binding para `127.0.0.1:${PORT:-4100}:4100`; atualizar volume do vault para `${NEXUS_VAULT_HOST_DIR:-G:/Meu Drive/main_vault}:/main_vault:ro` e adicionar `${DRIVE_PROJECTS_HOST_DIR:-G:/Meu Drive/01 Projetos}:/drive_projects:ro`; alterar `HEALTHCHECK` em ambos os arquivos de `http://127.0.0.1:4100/api/projects` para `http://127.0.0.1:4100/api/status`.

#### 12. `data/projects.json` (Modify)

*   **Type / Scope**: Registro Local da Frota de Projetos
*   **Proposed Changes**: Atualizar a entrada `axion-cockpit` para `id: "nexus-cockpit"`, `name: "Nexus Cockpit"`, `path: "C:\\Docker\\nexus-cockpit"` e `resolved_path: "/projects/nexus-cockpit"`.

#### 13. Documentação Canônica (`README.md`, `docs/README.md`, `docs/ARCHITECTURE.md`, `docs/API.md`, `docs/DOCKER.md`, `docs/DEVELOPMENT.md`, `docs/designs/local_project_os.md`, `docs/designs/infra_and_subsystems_catalog.md`) (Modify)

*   **Type / Scope**: Documentação Arquitetural e Contratos de Design
*   **Proposed Changes**: Emendar formalmente `NG4` e `Zero Drift` em `local_project_os.md` e `infra_and_subsystems_catalog.md` permitindo `sqlite3` efêmero em `/tmp` como índice derivado descartável e separando explicitamente escrita local (`data/`) de observação read-only do `main_vault`; atualizar definição de `/vault` para `/main_vault` com allowlist; documentar os endpoints `/api/vault/*` e `vault_schemas.json`; corrigir todas as referências e links `file:///C:/Docker/axion-cockpit/...` para `nexus-cockpit` / links relativos `./` e `../`.

#### 14. `tests/test_vault_pipeline.py` (Create), `tests/test_server.py` e `tests/test_infra_scanner.py` (Modify)

*   **Type / Scope**: Suíte de Testes Unitários e de Integração (`unittest`)
*   **Proposed Changes**: Criar suíte isolada em `tempfile.TemporaryDirectory()` com fixtures sintéticas do vault (4 pastas, `vault_schemas.json`, mini-repositórios `git init`, casos N:1, `Arquivado` ativo, UTF-8 BOM, escape `\\`, notas sem frontmatter em `05_Areas`) sem depender de `G:\Meu Drive`. Testar parser unificado, validação pelo manifesto, `vault_index.py` (invalidação por SHA-256, `WAL`, preservação de snapshot quando vault ficar `unavailable`), `vault_reconciler.py` (4 flags de divergência + `non_path_reference` + `not_mounted_in_runtime`), e endpoints REST (`GET /api/vault/entities`, `GET /api/vault/overview` sem corpo de `05_Areas`, ausência de `Access-Control-Allow-Origin: *`). Refatorar `tests/test_server.py` para usar diretório temporário em vez de escrever em `data/ingested/`.

### Verification Plan

*   **Unit & Integration Tests (Python Stdlib):** Executar `python -m unittest discover -s tests -v` dentro de `C:\Docker\nexus-cockpit` (e dentro do container Docker em build limpo sem `G:\` montado), exigindo 100% de aprovação sem pular casos nem acessar o `main_vault` real do host.
*   **PowerShell Schema Harness:** Executar `powershell -ExecutionPolicy Bypass -File "G:\Meu Drive\main_vault\scripts\harness\Test-VaultSchemas.ps1"` verificando leitura bem-sucedida de `vault_schemas.json` e paridade de diagnóstico sobre `01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas`.
*   **Container & Healthcheck:** Subir `docker compose up -d --build`, confirmar `docker inspect` com status `healthy` via `GET /api/status` (sem execuções síncronas de `git` no healthcheck) e validar via `Test-NetConnection` / `ss` que o bind está restrito a `127.0.0.1:4100`.
*   **Security & Privacy Spot-Checks:** Confirmar ausência do cabeçalho `Access-Control-Allow-Origin: *` nas respostas HTTP, confirmar que tentativas de path traversal ou acesso a `.agents/`/`chaves_ssh/` retornam erro/vazio, e inspecionar payload JSON de `GET /api/vault/overview` validando que nenhum conteúdo textual de `05_Areas` é retornado.
*   **Graceful Degradation Check:** Testar reindexação apontando para diretório inexistente após uma carga válida e validar que o snapshot anterior permanece consultável com `vault_status: "unavailable"`.

--------------------------------------------------------------------------------

*Drafted with EGM*
