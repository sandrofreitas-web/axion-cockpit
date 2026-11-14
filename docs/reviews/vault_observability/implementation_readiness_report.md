# Implementation Readiness Report — `vault_observability_and_entity_cockpit.md`

* **Stage:** 9 (Implementation Readiness Test — `egm-implementation-readiness`, `egm-codebase-details`, `egm-style`)
* **Target:** [docs/designs/vault_observability_and_entity_cockpit.md](file:///C:/Docker/nexus-cockpit/docs/designs/vault_observability_and_entity_cockpit.md) (`DetailedRange`: 225..309)

**Veredito:** **Reprovado para implementação imediata (Not Ready)** — Violações da *Zero-Decision Rule*, incompatibilidades de contrato com `tests/` e código atual, e lacunas de schema DDL/REST API.

---

## Parte 1 — Implementation Readiness (`egm-implementation-readiness`)

### Blockers

1. **Contrato do manifesto `vault_schemas.json` subespecificado (L229–238, L110–120)**
   * Faltam listas fechadas de `required_fields`, `optional_fields` e `allowed_enums` para os 4 domínios (ex.: `04_Arquitetura_ADRs` tem valores reais `"Aprovado / Implementado"` e `"Substituído"`; `02_Recursos_e_Infra` tem `"Ativo / Produção"` e diferença de ignorados entre `Test-VaultSchemas.ps1` [`README.md`] e `ui/infra_scanner.py:349` [`readme.md`, `home_lab_specifications.md`, `oracle.md`]).
   * Faltam valores exatos de `non_frontmatter_policy` (e se `warning_non_contract` entra em `scan_errors`/`errors_count`), extensões ignoradas vs `-Filter "*.md"`, política de `caminho_drive` em Linux/Docker e limiares numéricos de `age_policy` para `01_Projetos`.

2. **Schema DDL do `sqlite3` incompleto e contradição na FK de `project_repo_links` (L249–252, L137–141)**
   * Faltam tipos SQL, PKs, `NOT NULL`, `DEFAULT`, `ON DELETE` e valor inicial de `PRAGMA user_version`.
   * `project_repo_links.vault_rel_path (FK -> vault_nodes.rel_path)` torna impossível persistir `unlinked_cockpit_project` (projetos em `data/projects.json` sem ficha no vault).
   * Falta definir quando ocorre a primeira indexação no boot de `ui/app.py` (síncrono, thread de startup, ou lazy) e como isso interage com o `HEALTHCHECK`.

3. **Regras objetivas da Matriz de Divergência e Reconciliação N:1 subespecificadas (L254–257, L145–154)**
   * `archived_active_repo`: falta limiar em dias de "commit recente" e regra objetiva para "repositório dedicado vs módulo incorporado" em vínculo N:1.
   * `port_mismatch`: falta definir fórmula de conjunto (especialmente com `portas: []` e vínculo N:1 com subconjuntos de portas) e se compara `host_port` ou `container_port`.
   * `not_mounted_in_runtime` vs `missing_on_disk`: falta critério para detectar se `/drive_projects` está vazio por Drive desmontado no host.
   * Matching `data/projects.json` ↔ `01_Projetos`: falta algoritmo exato para caminhos relativos (`igreja-crist-evan`, `projects/Project_Siaebr`) e registros `ingested: true` (`finaceiro-pessoal`).

4. **Contratos de Request/Response da REST API ausentes (L269–272, L158–162)**
   * Faltam payloads JSON exatos, parâmetros e códigos HTTP (`200`, `400`, `503`) para `GET /api/status`, `GET /api/vault/entities`, `GET /api/vault/overview?entity=<nome>` e `POST /api/vault/reindex` (incluindo tratamento de `entidade: "Todas"` em notas como `ADR-008` ao filtrar por entidade específica).

### Majors

5. **Assinaturas de `vault_parser.py` e compatibilidade com testes existentes (L239–247, L264–272)** — Falta assinatura/retorno de `parse_frontmatter` / `parse_vault_file`, estratégia de adaptação para `tests/test_infra_scanner.py` e `tests/test_server.py` (que esperam defaults legados), e escopo não descrito de `tests/test_infra_scanner.py (Modify)`.
6. **Especificação incompleta da UI para a aba `🧠 Vault & Entidades` (L274–277)** — Falta layout/exibição para `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas` (exigidos no CUJ 1), origem dinâmica das opções do seletor de entidade e polling/atualização do selo `last_indexed_at`.
7. **Precedência e colisão semântica nas variáveis `AXION_VAULT_*` (L264–267, L279–282, L213)** — `AXION_VAULT_HOST_DIR` aponta para subpasta `02_Recursos_e_Infra` enquanto `NEXUS_VAULT_HOST_DIR` aponta para a raiz `main_vault`; falta explicitar `environment:` no Compose (`NEXUS_VAULT_ROOT`, `DRIVE_PROJECTS_DIR`).
8. **Remoção de CORS em `do_OPTIONS` e assinatura de `create_server(...)` (L269–272)** — `ui/app.py:208-213` também envia `Access-Control-Allow-Origin: *` em `do_OPTIONS`; falta assinatura de `create_server(...)` e fallback `last_commit_iso: ""` em `ui/app.py:271` e `ui/scanner.py:275,283`.
9. **Efeito colateral em `data/projects.json` e `resolve_project_path` com `/drive_projects:ro` (L284–287)** — Confirmar comportamento para `finaceiro-pessoal` (`ingested: true`) e eventual migração de `data/notes/axion-cockpit/` → `nexus-cockpit/`.
10. **Escopo de testes de `tests/test_infra_scanner.py`, `single-flight`, `schema_error` e alvos exatos de path traversal (L294–305).**

### Nits

11. **Encoding UTF-8 no PowerShell 5.1 (`Get-Content -Encoding UTF8 | ConvertFrom-Json`) para acentos em `Test-VaultSchemas.ps1` (L302).**
12. **Labels e comentários residuais `Axion Cockpit` em `Dockerfile` (L2, L10, L43) e `ui/static/app.js` (L2, L1577).**

---

## Parte 2 — Codebase Details (`egm-codebase-details`)

### Blockers
1. **Quebra da Regra Zero-Decision no contrato de `vault_schemas.json`** (campos/enums exatos por domínio, reconciliação de ignorados entre `infra_scanner.py:349` e `Test-VaultSchemas.ps1:71`, limiar em dias de `age_policy`, política de `caminho_drive`).
2. **Incompatibilidade de assinatura e quebra de testes na substituição do parser YAML:** `tests/test_infra_scanner.py:22-61` chama `parse_yaml_frontmatter` esperando `dict` plano (`{}` se não fechado); `tests/test_server.py:124-144` e `ui/app.py:329,575` chamam `parse_markdown_note` esperando defaults de nota local; e `ui/app.py:164` (`write_markdown_note`) grava `title` sem escape de `\"`/`\\` (quebrando roundtrip se `vault_parser.py` desescapar).

### Majors
3. **Ausência de Fases Incrementais e Checkpoints** no `Detailed Implementation Plan` (exigido por `implementation-readiness-standard.md` — lista plana de 14 arquivos apesar de `concepts_brief.md` prever Fase 0).
4. **Contratos de API `/api/vault/*` e `/api/status` subespecificados + omissão de `do_OPTIONS` (`ui/app.py:208-213`) + `INGESTED_BASE_DIR` (`ui/app.py:35,40`) e `ui/infra_scanner.py:291,473` na injeção de caminhos para testes.**
5. **Lacunas no `sqlite3`:** `vault_nodes` não tem `metadata_json` nem coluna de idade computada para responder `/api/vault/overview` sem reler o disco; FK impede `unlinked_cockpit_project`; falta definir startup e remoção de arquivos deletados do disco.
6. **Regras de divergência e reuso omitido (`ui/infra_scanner.py:147-268`):** `SIAEBR_Project.md` (`[8501, 8000, 5432, 6379]`) vs `SIAEBR_MatPlan.md` (`[8501, 8000]`) no mesmo repo `Project_Siaebr` exige regra explícita de conjunto/união para `port_mismatch`; `extract_compose_ports_from_content` e `detect_port_collisions` não são reutilizadas explicitamente no Item 6.
7. **Divergência de variáveis de ambiente (`NEXUS_VAULT_HOST_DIR`, `NEXUS_VAULT_ROOT`, `AXION_VAULT_PATH`, `DRIVE_PROJECTS_DIR`) e cascata de resolução da raiz do vault.**
8. **Paridade de regex de wikilinks absolutos:** `Test-VaultSchemas.ps1:116-117` remove blocos cercados e código inline antes de aplicar a regex; `vault_validator.py` omite essa sanitização prévia.
9. **Migração omitida de `data/notes/axion-cockpit/` (e `data/ingested/axion-cockpit/`) e arquivos residuais (`.github/workflows/ci.yml:1`, `docs/reviews/README.md`).**

### Nits
10. Fallback de `git` em `ui/app.py:271` e `ui/scanner.py:269-276` incluindo `last_commit_iso: ""`.
11. `ui/index.html:40,44,510` (placeholder `/vault`), `ui/static/app.js:1326-1349` (`switchDomain` binário), labels em `Dockerfile` e necessidade de manter `HOST=0.0.0.0` dentro do container para `127.0.0.1:4100:4100`.

---

## Parte 3 — Estilo & Prontidão (`egm-style`)

### Majors
1. **Escopo omitido para `tests/test_infra_scanner.py (Modify)`** agrupado no Item 14 (L294–297).
2. **Inconsistência de caminhos relativos e ausência de links clicáveis** dentro de `Proposed Changes` (mistura `../../ui/...`, `data/projects.json`, `scanner.resolve...`, `\` vs `/`).
3. **Método de verificação impreciso para restrição de bind (`Test-NetConnection / ss` na L303):** usar `docker port` e `Get-NetTCPConnection -LocalPort 4100 | Select-Object LocalAddress,LocalPort`.
4. **Critérios verificáveis ausentes ou ambíguos no `Verification Plan` (L301–305):** substituir formulação retórica por `exit code 0`, `0` falhas/erros/skipped, comando explícito em container limpo, critério objetivo de paridade Python vs PowerShell, endpoints/códigos exatos de traversal e override de `NEXUS_VAULT_ROOT` para testar `unavailable`.
5. **Termos ambíguos e âncora frágil (L237, L257, L262, L267, L272):** `"atualmente descoberta"`, `"durante reindexação (ou alteração)"`, referência frágil `(linha 82)`, precedência de fallback legado e justificativa vaga `"que facilite testes isolados"`.

### Nits
* Redundância lexical (`"paridade exata"`, `"allowlist estrita"`), `SIAEBR_Project` sem `.md`, `NG4` sem qualificar documento de origem, ordem de precedência do path do `.db`, `"3ª aba"` / `"ledger local"`, agrupamento de 8 arquivos no Item 13 e rodapé `*Drafted with EGM*`.
