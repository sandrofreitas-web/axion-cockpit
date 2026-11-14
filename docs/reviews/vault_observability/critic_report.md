# Critic Review Report — `vault_observability_and_entity_cockpit.md`

* **Stage:** 7 (Critic Review — `egm-design`, `egm-structural`, `egm-style`)
* **Target:** [docs/designs/vault_observability_and_entity_cockpit.md](file:///C:/Docker/nexus-cockpit/docs/designs/vault_observability_and_entity_cockpit.md) (`FeatureRange`: 1..224)

---

## Parte 1 — Revisão Crítica de Design (`egm-design`)

**Veredito:** **Reprovado para implementação no estado atual** — **2 Blockers** e **4 Majors** (+ **1 Nit**).

### 1. [Blocker] Superfície de Vazamento em `05_Areas`, Bypass da Allowlist em Endpoints Legados e CSRF
* **Affected Scope:** L22–L33, L77, L118–L161, L211; `ui/app.py` (L422–L481); `ui/scanner.py` (L38–L108, L236–L263); `docker-compose.yml` (L11–L15).
* **Finding & Recommendation:**
  1. **Exposição residual em `05_Areas` via metadados e `scan_errors`:** O design restringe apenas `allow_body_preview: false` (omissão do corpo Markdown), mas sem allowlist estrita de campos em `vault_nodes` e na resposta de `/api/vault/overview`, valores sensíveis em frontmatter, títulos, `rel_path` ou trechos literais em `scan_errors.detail` ainda podem vazar via API. Definir projeção fechada de campos exportáveis para `domain == "areas"` e sanitizar `scan_errors.detail` para emitir apenas códigos/nomes de campos faltantes.
  2. **Bypass da allowlist `/main_vault:ro` via rotas legadas e symlinks:** `POST /api/infra/config` (`ui/app.py:464-481`) aceita qualquer `vault_path` existente sem validar allowlist; `POST /api/projects` (`ui/app.py:422-431`) usa `is_valid_project_path` (`ui/scanner.py:236-263`), permitindo registrar `/main_vault/...` como projeto e expor arquivos via `GET /api/projects/{id}/docs`; symlinks dentro de pastas permitidas também não são bloqueados sem checagem pós-`resolve()`. Exigir `resolved.is_relative_to(allowed_domain_root)`, restringir `POST /api/infra/config` e bloquear `/main_vault` em `POST /api/projects`.
  3. **Bind `127.0.0.1` vs `HOST=0.0.0.0` no container e risco de CSRF:** Manter `HOST=0.0.0.0` dentro do container (necessário para `127.0.0.1:${PORT:-4100}:4100` no host funcionar). Remover `Access-Control-Allow-Origin: *` protege leitura cross-origin (SOP), mas não bloqueia CSRF em `POST`/`PUT`/`DELETE` (`POST /api/vault/reindex`, `POST /api/infra/config`, `POST/DELETE /api/projects`); validar cabeçalhos `Host`, `Origin`/`Sec-Fetch-Site` e `Content-Type: application/json`.

### 2. [Blocker] Incoerências no Schema Relacional (`project_repo_links`) e Regras de Divergência Mal Especificadas
* **Affected Scope:** L137–L154.
* **Finding & Recommendation:**
  1. **`unlinked_cockpit_project` impossível de persistir em `project_repo_links`:** `project_repo_links` declara `vault_rel_path (FK)` referenciando `vault_nodes(rel_path)` com `PRAGMA foreign_keys=ON`, mas `unlinked_cockpit_project` não possui ficha em `01_Projetos`. Mover para tabela própria (`cockpit_project_audit`) ou campo dedicado do snapshot.
  2. **`archived_active_repo` não é binário nem determinístico:** Falta limiar objetivo de "commit recente" (`N` dias ou posterior a `doc_date`) e regra objetiva para distinguir repositório dedicado de módulo compartilhado no caso N:1.
  3. **Origem de `port_mismatch` inconsistente:** Hoje apenas `02_Recursos_e_Infra` extrai portas de `servicos_ativos` (`ui/infra_scanner.py:374-382`); falta especificar o campo de portas em `01_Projetos` no `vault_schemas.json` e separar divergência de ficha vs colisão global.
  4. **Inconsistência de `scan_errors` durante `vault_status = "unavailable"`:** `scan_errors` referencia `run_id` de `scan_runs`; quando entra novo `run_id` `unavailable`, consultar erros pelo último `run_id` apaga os erros de contrato do último snapshot válido. Vincular o snapshot ativo ao último `scan_runs.id` com `vault_status = "available"`.

### 3. [Major] Concorrência SQLite WAL, Locks em `ThreadingTCPServer` e Ciclo de Vida Efêmero
* **Affected Scope:** L130–L136, L162, L205; `ui/app.py` (L640).
* **Finding & Recommendation:**
  1. Executar criação de schema, `PRAGMA journal_mode=WAL` e checagem de `user_version` **uma única vez** na inicialização sob lock; conexões leitoras devem abrir em modo read-only ou ajustar apenas `busy_timeout=5000` e `foreign_keys=ON`.
  2. Envolver a escrita da reindexação em transação única `BEGIN IMMEDIATE ... COMMIT` e definir política exata de `single-flight` (`blocking=False` coalescido ou wait com timeout curto) para evitar timeouts HTTP sob I/O lento no `G:\`.
  3. Documentar explicitamente a limitação do `/tmp` efêmero: se o container reiniciar enquanto o Drive estiver offline, não haverá snapshot anterior para preservar no CUJ 4.

### 4. [Major] Violação do `feature-spec-standard.md`: Ausência de Seção Explícita `Risks & Mitigations`
* **Affected Scope:** L1–L224 vs `feature-spec-standard.md`.
* **Finding & Recommendation:** Adicionar seção `## Risks & Mitigations` cobrindo limite de tamanho por arquivo `.md` antes do hash/leitura em memória (`ui/scanner.py:395` hoje só tem comentário de 2MB sem `stat().st_size` check), fluxo completo de `vault_status = "schema_error"`, e teto de volumetria / paginação.

### 5. [Major] Escalabilidade, Cold Start e Falha de Invalidação de Cache em `docker-compose.yml` / `projects.json`
* **Affected Scope:** L136, L152, L158, L212; `ui/app.py` (L259–L275); `docker-compose.yml` (L24–L28).
* **Finding & Recommendation:**
  1. Alterações em `data/projects.json`, `docker-compose.yml` dos projetos ou `.git` local não alteram o SHA-256 dos arquivos `.md`: desacoplar cache de parse/validação dos `.md` da etapa de reconciliação N:1 + Compose + Git.
  2. Definir comportamento de *cold start* para que o servidor HTTP abra a porta antes da primeira indexação e responda `200` em `/api/status` dentro do `start_period: 5s`.
  3. `GET /api/projects` continua disparando 3 subprocessos `git` síncronos por projeto, incluindo repos em `/drive_projects`.

### 6. [Major] Lacunas nos Contratos da API, Filtro `"Todas"` no Manifesto e Fallback Legado Incompatível
* **Affected Scope:** L28, L77, L112–L115, L158–L162, L213; `docker-compose.yml` (L23).
* **Finding & Recommendation:**
  1. Remover `"Todas"` de `entities` no `vault_schemas.json`, mantendo-a apenas como filtro de query/UI.
  2. `AXION_VAULT_HOST_DIR` legado aponta para `.../02_Recursos_e_Infra` e não para a raiz `main_vault` — o fallback precisa detectar esse sufixo e resolver o diretório pai (ou separar `/vault:ro` legado).
  3. Bloqueio de diretórios sensíveis (`.`-prefixed, `chaves_ssh`, `.env`) deve ser hardcoded em Python além do JSON, e os novos endpoints `/api/vault/*` precisam especificar códigos de erro HTTP (`400`, `503`).

### 7. [Nit] Higiene Documental, Casos de Borda do Parser YAML e Timestamps
* **Affected Scope:** L13, L121–L126, L139, L180, L220.
* **Finding & Recommendation:** Esclarecer origem de `NG4`, especificar comportamento do parser stdlib em chaves aninhadas/blocos multilinha (`|`/`>`)/escape `'`, definir formato canônico de `doc_date`/`indexed_at` e validar links relativos.

---

## Parte 2 — Revisão Estrutural (`egm-structural`)

1. **[Major] Ausência de seção explícita `Risks & Mitigations`** (exigida pelo `feature-spec-standard.md`, após `## Non-Functional Requirements`).
2. **[Major] Quebra de hierarquia de títulos em `Additional Resources`** (L217 usa H3 `### Additional Resources` após divisor `---`, devendo ser H2).
3. **[Major] Referências internas incorretas e colisão entre `Goals`, `Non-Goals` e `Alternatives Considered`** (L180 cita `NG3` e `G6` quando o documento usa `NG-C` e `NG-D`, e `G6` aqui significa Hardening/Identidade; L13, L185, L187 citam `NG4` sem qualificar `./local_project_os.md`).
4. **[Major] Inconsistências de contrato e cobertura entre `Technical Plan` e `Goals`/`CUJs`** (`vault_nodes.links_status` usa `'ok'` vs `project_repo_links.link_state` usa `'accessible'`; omissão de `02_Recursos_e_Infra` em `age_policy` e `non_frontmatter_policy`; `"Todas"` dentro de `entities` do schema; omissão de `/projects:ro` no texto de `§1` L77).
5. **[Major] Problemas sintáticos e semânticos no diagrama Mermaid (`§1`, L80–106)** (rótulo `MV -->|/main_vault:ro (Allowlist)| VP` precisa aspas; `PS -->|Lê contrato único| MV` tem seta invertida; `data/` local não aparece no grafo; `VR` desconectado de `VP`/`VS`/`VI`; `SPA` colocado dentro do `subgraph Container`).
6. **[Nit] Divergência de caminho estático (`ui/index.html + app.js` vs `ui/static/app.js`) e simetria de numeração/divisores.**

---

## Parte 3 — Revisão de Estilo (`egm-style`)

* **Major:**
  1. Colisão de identificadores `G6`, `NG3` e `NG4` (L13, L180, L185, L187).
  2. Inclusão de `"Todas"` em `entities` do schema e texto inconsistente no `CUJ 1` ("exibe exclusivamente...").
  3. Critério não quantificado ("commit recente") na regra descrita como binária (`archived_active_repo`, L61, L150).
  4. Inconsistência de caminhos entre diagrama Mermaid e texto (`ui/static/app.js`, prefixo `ui/` omitido em nós do diagrama, papel de `scanner.py` vs `vault_reconciler.py`).
  5. Termo técnico enganoso ("ledger local" para JSON/Markdown de configuração/notas) e expressão vaga ("I/O pesado" em L158).
* **Nit:** Uniformizar `endurecimento` vs `Hardening`, `working tree suja` vs `alterada`; incluir `schema_error` em `G3`; trocar jargões (`ecossistema`, `números vivos de negócio`, `atrito`); reduzir repetições de `estrito/estrita`; remover advérbios subjetivos (`facilmente`, `inevitavelmente`, `qualquer`, `etc.`); corrigir *"versão do `vault_schemas.json` (`schema_hash`)"*; padronizar tradução (`Atualidade Verificável` em vez de `Frescor`) e idioma dos marcadores `Given/When/Then`.
