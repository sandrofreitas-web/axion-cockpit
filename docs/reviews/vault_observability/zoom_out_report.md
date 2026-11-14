# Initial Zoom Out Report — `vault_observability_and_entity_cockpit.md`

* **Reviewer:** `egm-zoom-out` (Stage 5)
* **Target:** [docs/designs/vault_observability_and_entity_cockpit.md](file:///C:/Docker/nexus-cockpit/docs/designs/vault_observability_and_entity_cockpit.md)

Contexto e objetivo estão suficientemente definidos; os problemas identificados concentram-se em otimização prematura, duplicação com componentes existentes em `ui/`, acoplamento de políticas do cockpit ao `main_vault` e scaffolding YAGNI.

---

### 1. [Major] Otimização prematura e YAGNI no índice `sqlite3` (`/tmp/nexus_vault_index.db`)
* **Escopo afetado:** `Overview` (L13), `Goals — G3` (L30), `Technical Plan §3` (L128–141), `Alternative C` (L183–187), `Detailed Implementation Plan §5` (L249–252).
* **Racional de simplicidade:**
  * O documento admite em `Alternative C` (L185) que o vault atual tem apenas ~40–50 notas e que leitura direta atende o volume sem gargalo. Introduzir `sqlite3` com 4 tabelas (`scan_runs`, `vault_nodes`, `project_repo_links`, `scan_errors`), `WAL`, `busy_timeout`, migração por `PRAGMA user_version` e invalidação em dois níveis (`size_bytes`/`mtime_ns` + `content_sha256` + `schema_hash`) é otimização prematura.
  * Os argumentos usados para descartar o cache em memória já existente em `ui/infra_scanner.py` (`_CACHE`, L30–33) não justificam o banco:
    1. Um snapshot em memória protegido por `threading.Lock` já desacopla chamadas `git` e I/O do Google Drive das requisições `GET` e permite manter o snapshot anterior quando `vault_status == "unavailable"`.
    2. A tabela `scan_runs` armazena histórico de varreduras, mas **nenhum endpoint da API (`§5`, L158–162), CUJ ou tela da UI consulta histórico de execuções** (e `/tmp` no container é perdido em recriações de qualquer modo).
    3. Manter apenas snapshot em memória elimina um módulo inteiro (`ui/vault_index.py`) e evita ter de emendar `NG4` em `docs/designs/local_project_os.md` (L51) e `Zero Persistent Database` em `docs/designs/infra_and_subsystems_catalog.md` (L32).

---

### 2. [Major] Pipeline duplicado entre `ui/infra_scanner.py` e os novos módulos `vault_*`
* **Escopo afetado:** `Technical Plan §1, §4, §5` (L89–106, L143–158), `Detailed Implementation Plan §4, §6, §8` (L244–268).
* **Racional de simplicidade:**
  * `ui/infra_scanner.py` já executa varredura de `02_Recursos_e_Infra/*.md`, extrai portas de `docker-compose.yml` (`extract_compose_ports_from_content`, L147–212; leitura em `scan_infrastructure_directory`, L418–440), detecta colisões (`detect_port_collisions`, L215–268) e resolve caminhos (`resolve_vault_path`, L271–323).
  * O plano atual apenas remove `parse_yaml_frontmatter` e ajusta `resolve_vault_path` em `infra_scanner.py` (item 8, L267), criando em paralelo um **segundo pipeline** (`vault_validator.py` + `vault_index.py` + `vault_reconciler.py`) que lê os mesmos arquivos de `02_Recursos_e_Infra`, lê `data/projects.json` e reimplementa a extração de portas de `docker-compose.yml` para calcular `port_mismatch` (L152, L257).
  * Além disso, `ui/app.py` (`POST /api/infra/config`, L464–481) e `ui/infra_scanner.py` (L292–298) persistem `vault_path` em `data/config.json`, mecanismo ignorado pelo novo fluxo do `/main_vault`, criando risco de `/api/infra` e `/api/vault/overview` operarem sobre diretórios distintos.
  * **Recomendação:** Unificar a leitura de `02_Recursos_e_Infra` e reutilizar `infra_scanner.extract_compose_ports_from_content` (fazendo `GET /api/infra` consumir o mesmo snapshot/scanner do vault, sem dois caches e dois leitores paralelos).

---

### 3. [Major] Acoplamento de política de privacidade e UI do cockpit ao manifesto `vault_schemas.json` no `main_vault`
* **Escopo afetado:** `Technical Plan §2` (L110–120), `Detailed Implementation Plan §1–2, §4` (L229–237, L244–247).
* **Racional de simplicidade:**
  * Reaproveitar regras estruturais de validação (`entities`, `required_fields`, `allowed_enums`, `ignored_filenames`) entre `Test-VaultSchemas.ps1` e Python evita duplicação de contrato. Porém, colocar `allow_body_preview` (L118) e `age_policy` (L117) dentro de `main_vault/scripts/harness/vault_schemas.json` mistura responsabilidades do harness CLI com regras de apresentação e segurança do servidor web.
  * A proibição de expor o corpo bruto de `05_Areas` é um requisito de segurança do backend (`ui/app.py`); ela não deve depender de um campo configurável em um JSON armazenado no Google Drive.
  * Do mesmo modo, vincular `GET /api/vault/entities` e o estado `schema_error` exclusivamente à leitura de `vault_schemas.json` no `/main_vault` acopla a navegação da UI à disponibilidade do mount do Drive.

---

### 4. [Major] Scaffolding especulativo para `age_policy` e `age_exempt` sem uso no desenho (YAGNI)
* **Escopo afetado:** `Goals — G5` (L32), `CUJ 2` (L53–55), `Technical Plan §2–3` (L117, L139), `Detailed Implementation Plan §1, §4` (L232, L247).
* **Racional de simplicidade:**
  * O plano define `age_policy` (`enabled: true` com "limiares" para `01_Projetos` e `exempt: true` para `04_Arquitetura_ADRs` e `05_Areas`) e persiste `doc_date` e `age_exempt` no schema do índice.
  * Entretanto, nenhuma das 4 regras da matriz de divergência (`§4`, L149–154), nenhum endpoint e nenhum CUJ define alerta de idade ou limiar de dias para `01_Projetos`. Modelar configuração, campo de banco e lógica de validação para isentar ADRs e Áreas de um alerta de obsolescência por idade que não existe no escopo é YAGNI.

---

### 5. [Nit] Fragmentação de módulos Python e queda de altitude no Plano Técnico
* **Escopo afetado:** `Technical Plan §1, §3, §4` (L90–93, L131–141, L146), `Detailed Implementation Plan §3–7` (L239–263).
* **Racional de simplicidade:**
  * Extrair `ui/vault_parser.py` elimina de fato a duplicação entre `infra_scanner.py:parse_yaml_frontmatter` e `app.py:parse_markdown_note`. Já dividir o restante em 3 novos módulos (`vault_validator.py`, `vault_index.py`, `vault_reconciler.py`) além de `infra_scanner.py` para ~40–50 notas fragmenta um fluxo simples; validação e reconciliação podem coexistir em um único módulo de varredura do vault.
  * No `Technical Plan` (que deve manter visão arquitetural), há detalhes de implementação de código que pertencem apenas à execução: número de linha específico (`linha 82` em `ui/scanner.py`, L262), diretivas literais (`PRAGMA busy_timeout=5000`, `PRAGMA journal_mode=WAL`, L132), `tempfile.gettempdir()` (L131) e formato exato de comando Git (`git log -1 --format=%cI`, L262).
