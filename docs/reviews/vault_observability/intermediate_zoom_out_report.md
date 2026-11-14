# Intermediate Zoom Out Report — `vault_observability_and_entity_cockpit.md`

* **Stage:** 8 (Intermediate Zoom Out — `egm-zoom-out`)
* **Target:** [docs/designs/vault_observability_and_entity_cockpit.md](file:///C:/Docker/nexus-cockpit/docs/designs/vault_observability_and_entity_cockpit.md)
* **Base avaliada:** [zoom_out_report.md](./zoom_out_report.md), [comprehension_report.md](./comprehension_report.md) e [critic_report.md](./critic_report.md)

## Veredito Geral

O documento **requer simplificação estrutural antes da implementação**. Ao cruzar os estágios 5, 6 e 7, observa-se que o desenho original já introduzia infraestrutura excessiva para um vault de ~40–50 notas (`sqlite3` com 4 tabelas + 4 novos módulos paralelos ao `ui/infra_scanner.py`), e **várias das mitigações propostas no `critic_report.md` agravam esse inchaço** ao tentar remediar sintomas da escolha de banco relacional e da duplicação de pipelines. Simplificar a arquitetura raiz elimina simultaneamente os Blockers do Stage 7 e a maior parte do código especulativo.

---

## Achados

### 1. [Blocker] `sqlite3` (`/tmp/nexus_vault_index.db`) é a causa-raiz da complexidade do desenho e das mitigações pesadas do Stage 7
* **Escopo afetado:** `Overview` (L13), `Goals — G3` (L30), `Technical Plan §3` (L128–141), `Alternative C` (L183–187), `Detailed Implementation Plan §5, §13` (L249–252, L292); `critic_report.md` (Blocker #2.1, #2.4; Major #3.1, #3.2, #5.1).
* **Racional de simplicidade:**
  * O volume declarado é ~40–50 notas (`Alternative C`, L185), nenhuma rota da API (`§5`, L158–162) ou CUJ consulta histórico de `scan_runs`, e `/tmp` é perdido ao recriar o container (inviabilizando o CUJ 4 entre reinícios, como apontado no Stage 7 Major #3.3).
  * Quase toda a complexidade adicional proposta pelo Stage 7 existe apenas para contornar efeitos colaterais do `sqlite3`:
    1. A FK `project_repo_links.vault_rel_path -> vault_nodes.rel_path` impediu persistir `unlinked_cockpit_project`, levando o Stage 7 a propor uma **5ª tabela (`cockpit_project_audit`)** (Blocker #2.1).
    2. A FK `scan_errors.run_id -> scan_runs.id` fez um run `unavailable` ocultar os erros do último snapshot válido, levando à proposta de ponteiro para o último `scan_runs.id` `available` (Blocker #2.4).
    3. Concorrência `WAL` em `ThreadingTCPServer` levou o Stage 7 a exigir init-once de `WAL`/`user_version` sob lock, conexões read-only para leitores, transações `BEGIN IMMEDIATE ... COMMIT` e política específica de timeout no `single-flight` (Major #3.1, #3.2).
    4. Invalidação por `content_sha256` dos `.md` não detecta mudanças em `data/projects.json`, `docker-compose.yml` ou `.git`, levando o Stage 7 a propor dois estágios de cache desacoplados (Major #5.1).
  * **Simplificação estrutural recomendada:** Substituir `sqlite3` e `ui/vault_index.py` por um **snapshot imutável em memória** (dicionário Python trocado atomicamente por referência sob `threading.Lock`, preservando o último snapshot válido quando o vault ficar `unavailable`). Isso resolve os Blockers do Stage 7 sem banco nem DDL:
    * `unlinked_cockpit_project` vira uma lista simples no snapshot (zero FK, zero `cockpit_project_audit`).
    * Em `vault_status = "unavailable"`, mantém-se a referência do último snapshot completo (incluindo `scan_errors` e `last_indexed_at`) sem controle de `run_id`.
    * Leitores HTTP acessam a referência imutável sem locks nem conexões SQLite.
    * Evita emendar `NG4` em `docs/designs/local_project_os.md` (L51) e `Zero Persistent Database` em `docs/designs/infra_and_subsystems_catalog.md` (L32).
    * Para cumprir o `start_period: 5s` do `HEALTHCHECK` (`docker-compose.yml:24-29`, Stage 7 Major #5.2), o snapshot pode iniciar vazio/sob demanda sem bloquear o bind do servidor, mantendo `GET /api/status` livre de subprocessos `git` e de I/O no Drive.

---

### 2. [Blocker] Pipeline duplicado com `ui/infra_scanner.py` e brecha da allowlist em rotas legadas
* **Escopo afetado:** `Technical Plan §1, §4, §5` (L89–106, L143–158), `Detailed Implementation Plan §4–8` (L244–268); `ui/infra_scanner.py` (`_CACHE` L30–33, `resolve_vault_path` L271–323, `scan_infrastructure_directory` L326–454, `extract_compose_ports_from_content` L433, `detect_port_collisions` L442); `ui/app.py` (L259–283, L422–481); `ui/scanner.py` (L236–319); `critic_report.md` (Blocker #1.2, Major #2.3, #5.3, #6.2).
* **Racional de simplicidade:**
  * O plano mantém `ui/infra_scanner.py` vivo em paralelo (com seu próprio `_CACHE`, sua própria leitura de `02_Recursos_e_Infra`, `data/projects.json`, `data/config.json` e parser de portas do `docker-compose.yml`) enquanto cria um segundo pipeline (`vault_validator.py` + `vault_index.py` + `vault_reconciler.py`), além de manter `GET /api/projects` executando 3 chamadas `subprocess.run(["git", ...])` síncronas por projeto (`ui/app.py:268`, `ui/scanner.py:287-314`).
  * Essa separação artificial causou diretamente o Blocker #1.2 do Stage 7: `POST /api/infra/config` (`ui/app.py:464-481`) e `POST /api/projects` (`ui/app.py:422-431`) continuam permitindo apontar caminhos dentro de `/main_vault` (como `05_Areas` ou `chaves_ssh`), burlando a allowlist do novo scanner. Também gerou a incompatibilidade do fallback `AXION_VAULT_HOST_DIR` (`docker-compose.yml:23`, que aponta para `.../02_Recursos_e_Infra` e não para a raiz `main_vault`).
  * **Simplificação estrutural recomendada:**
    1. Consolidar a leitura do vault e a reconciliação de projetos/portas em **um único fluxo** (mantendo `ui/vault_parser.py` como parser YAML stdlib único + um módulo unificado de varredura/reconciliação reutilizando `extract_compose_ports_from_content` e `detect_port_collisions`), fazendo `GET /api/infra` consumir a fatia de infraestrutura do mesmo snapshot (e evitando subprocessos `git` síncronos duplicados quando o snapshot já os coletou).
    2. Centralizar o bloqueio de `/main_vault` (e de symlinks que escapem da raiz permitida pós-`resolve()`) em `is_valid_project_path` (`ui/scanner.py:236-263`) e restringir `POST /api/infra/config` à allowlist (ou descontinuar a mutação arbitrária de `vault_path` quando `/main_vault` estiver ativo).
    3. Tratar o fallback legado `AXION_VAULT_HOST_DIR` de forma explícita (resolvendo o diretório pai quando terminar em `02_Recursos_e_Infra` ou isolando `/vault:ro` apenas para retrocompatibilidade de `GET /api/infra`).

---

### 3. [Major] Política de segurança em JSON externo e recomendação YAGNI de paginação no Stage 7
* **Escopo afetado:** `Technical Plan §2` (L110–120), `Detailed Implementation Plan §1, §4` (L229–237, L244–247); `zoom_out_report.md` (#3); `critic_report.md` (Blocker #1.1, #1.3, Major #4, #6.1, #6.3).
* **Racional de simplicidade:**
  * **Segurança de `05_Areas` e diretórios sensíveis:** Colocar `allow_body_preview: false` e a lista de exclusão de pastas sensíveis apenas em `main_vault/scripts/harness/vault_schemas.json` inverte responsabilidades — invariantes de privacidade da API pertencem ao código Python, não a um JSON editável no Google Drive. Para corrigir o Blocker #1.1 do Stage 7 com máxima simplicidade, basta remover `allow_body_preview` do JSON e aplicar no backend uma **projeção fechada hardcoded para `05_Areas`** (expondo apenas domínio, entidade, status contratual e códigos de erro sanitizados em `scan_errors`, sem corpo, valores de frontmatter ou paths/títulos sensíveis), além de manter o bloqueio de `.`-prefixed, `chaves_ssh` e `.env` em código Python.
  * **Paginação (over-engineering no Stage 7):** O `critic_report.md` (Major #4) recomenda adicionar *"teto de volumetria / paginação"* na nova seção `Risks & Mitigations`. Para ~40–50 notas, implementar paginação na API e na SPA é **YAGNI e otimização prematura**. Basta impor um limite simples de tamanho por arquivo `.md` antes da leitura em memória (`stat().st_size`, resolvendo a ausência real vista no comentário de `ui/scanner.py:395`).
  * **CSRF local (Stage 7 Blocker #1.3):** Manter `HOST=0.0.0.0` dentro do container (com bind `127.0.0.1:4100` no `docker-compose.yml`) e adicionar verificação simples de `Origin`/`Sec-Fetch-Site` + `Content-Type: application/json` nas rotas mutáveis (`POST/PUT/DELETE`) resolve o risco de CSRF sem infraestrutura extra; porém, evitar checagem rígida de `Host` hardcoded para não quebrar acesso via `localhost` vs `127.0.0.1`.

---

### 4. [Major] Scaffolding especulativo de `age_policy` / `age_exempt` sem consumidor no sistema
* **Escopo afetado:** `Goals — G5` (L32), `CUJ 2` (L53–55), `Technical Plan §2–3` (L117, L139), `Detailed Implementation Plan §1, §4` (L232, L247); `zoom_out_report.md` (#4); `comprehension_report.md` (#2).
* **Racional de simplicidade:**
  * O documento modela `age_policy` (com "limiares" não especificados para `01_Projetos` e omissão de `02_Recursos_e_Infra`) além de `doc_date` e `age_exempt`. Contudo, nenhuma das 4 regras da matriz de divergência (`§4`, L149–154), nenhum endpoint e nenhum card da UI avalia ou exibe alerta de obsolescência por idade.
  * Remover `age_policy` e `age_exempt` do backend do cockpit elimina configuração e campos mortos; se o script PowerShell `Test-VaultSchemas.ps1` já possuir regra própria de idade no `main_vault`, isso deve ser apenas documentado no escopo do harness sem replicar scaffolding ocioso no Python.

---

### 5. [Major] Lacunas de especificação e contradições nominais que bloqueiam implementação segura (Stages 6 e 7)
* **Escopo afetado:** `Overview` / `Goals` / `Non-Goals` / `Alternatives Considered` (L13, L33, L37–41, L180, L185, L187), `Technical Plan §1–2, §4` (L77, L80–106, L112–120, L139–140, L148–154), `Additional Resources` (L217).
* **Racional de simplicidade e completude:** Sem adicionar novos componentes, o documento precisa fechar as lacunas objetivas apontadas nos estágios 6 e 7 antes da codificação:
  1. **Contratos completos em `vault_schemas.json`:** Especificar `required_fields`, `optional_fields` e `allowed_enums` também para `01_Projetos` (incluindo o campo `portas` usado em `port_mismatch`), `02_Recursos_e_Infra` e `05_Areas`, além da `non_frontmatter_policy` para `02_Recursos_e_Infra` e lista de extensões binárias ignoradas. Remover `"Todas"` de `entities` no manifesto (mantendo-a apenas como filtro de query/UI).
  2. **Critérios objetivos na Matriz de Divergência:** Definir o critério temporal binário de "commit recente" em `archived_active_repo` (ex.: `N` dias ou `last_commit_iso > doc_date`), a regra para repositórios N:1 quando há fichas mistas (`Arquivado` + ativa), e se `port_mismatch` compara portas de host, container ou ambas.
  3. **Seção obrigatória e correções de consistência:** Adicionar `## Risks & Mitigations` (exigida pelo `feature-spec-standard.md`, cobrindo limite de tamanho por arquivo `.md` e fluxo de `vault_status = "schema_error"`), corrigir a colisão `G6` (L33 vs L180), harmonizar `NG3`/`NG4` com `NG-A..NG-E` definindo `NG4` e `Zero Drift` inline, alinhar `links_status: 'ok'` vs `link_state: 'accessible'`, esclarecer `"3 Domínios"` na SPA vs 4 domínios do vault, corrigir `### Additional Resources` para H2 (`##`), e corrigir o diagrama Mermaid (seta invertida em `PS`, `VR` desconectado, `SPA` dentro de `Container`, `data/` ausente, `/projects:ro` ausente no texto da L77, caminho `ui/static/app.js`).

---

### 6. [Nit] Queda de altitude no Plano Técnico e pequenos desvios textuais
* **Escopo afetado:** `Technical Plan §3, §5`, `Detailed Implementation Plan §3–7` (L131–132, L158, L213, L219, L262).
* **Racional de simplicidade:** Remover detalhes literais de implementação de código do texto arquitetural (`linha 82`, `PRAGMA busy_timeout=5000`, `git log -1 --format=%cI`, `tempfile.gettempdir()`) — vários dos quais desaparecem ao retirar o `sqlite3` —, corrigir a confusão entre `AXION_VAULT_HOST_DIR` e `AXION_VAULT_PATH` na L213, adicionar link/resumo breve da `ADR-008`, evitar o termo *"ledger local"* para `data/projects.json`/`data/config.json` e corrigir *"versão do `vault_schemas.json` (`schema_hash`)"*.
