# Comprehension Report — `vault_observability_and_entity_cockpit.md`

* **Reviewer:** `egm-comprehension` (Stage 6)
* **Target:** [docs/designs/vault_observability_and_entity_cockpit.md](file:///C:/Docker/nexus-cockpit/docs/designs/vault_observability_and_entity_cockpit.md)

**What this proposes**

O documento propõe expandir o `nexus-cockpit` (painel web em Docker) para atuar como observador somente leitura sobre quatro pastas do `main_vault` (`01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas`), consolidando os dados por entidade (`Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`, `Todas`). Para isso, introduz um manifesto JSON único (`vault_schemas.json`) compartilhado com o script PowerShell `Test-VaultSchemas.ps1`, substitui dois parsers YAML duplicados por um parser Python stdlib estrito (`ui/vault_parser.py`) e adiciona um índice `sqlite3` efêmero e descartável em `/tmp/nexus_vault_index.db` como camada derivada de leitura. Também implementa reconciliação N:1 entre fichas de projeto e repositórios Git (incluindo mounts em `G:\Meu Drive\01 Projetos`), uma matriz restrita de 4 divergências binárias, isenção de idade para ADRs/Áreas e bloqueio de exposição do corpo bruto de `05_Areas` na API. Por fim, conclui a renomeação de `axion-cockpit` para `nexus-cockpit`, restringe o bind Docker para `127.0.0.1:4100`, remove `Access-Control-Allow-Origin: *` e aponta o `HEALTHCHECK` para `GET /api/status`.

**How the existing system works, per this document**

Atualmente, o `nexus-cockpit` (ainda identificado como `axion-cockpit` em vários trechos do código, `data/projects.json`, `docker-compose.yml` e `ui/scanner.py`) é uma aplicação web com backend Python (`ThreadingTCPServer` em `ui/app.py`) e interface SPA em HTML/JS/CSS servida em `0.0.0.0:4100` com `CORS: *`. O container monta apenas `02_Recursos_e_Infra:/vault:ro` e `/projects:ro` (para repositórios em `C:\Docker`), deixando invisíveis as demais pastas do `main_vault` e os repositórios em `G:\Meu Drive\01 Projetos\*`, enquanto o `HEALTHCHECK` consulta `GET /api/projects` a cada 30s disparando comandos `git` síncronos. O sistema possui dois parsers YAML manuais duplicados (`ui/infra_scanner.py` e `ui/app.py`) que silenciam exceções e falham em casos como UTF-8 BOM, escapes `\\` e ausência de frontmatter, além de manter um estado local editável em `data/projects.json`, `data/config.json` e `data/notes/{project_id}/*.md`. Paralelamente, a governança de schemas do vault roda apenas via CLI PowerShell no host (`Test-VaultSchemas.ps1`) com regras hardcoded e sem cobrir `04_Arquitetura_ADRs`.

---

### Achados de Compreensão e Lacunas

1. **Severity**: Major
2. **Affected Scope**: `Overview` (L13), `Goals` (L33), `Non-Goals` (L37–41), `Technical Plan §2` (L112), `Alternatives Considered` (`Alternative B`, L180; `Alternative C`, L185, L187), `Target Files #13` (L292) — termos `G6`, `NG3`, `NG4`, `Zero Drift`, `ADR-008`.
3. **Discrepancy Description & Rationale**:
   - **Colisão do identificador `G6`**: Na L180, a `Alternative B` afirma que conectar bancos externos violaria `NG3 (zero conexão a bancos de produção) e G6 (zero dependências externas de pip)`. Contudo, na seção `Goals` (L33) deste mesmo documento, `G6` significa **"Saneamento de Identidade, Hardening e Saúde"** (enquanto zero dependências `pip` está no `NG-D`, L40). Além disso, os Não-Objetivos deste documento usam letras (`NG-A` a `NG-E`), mas o texto cita `NG3` (L180) e `NG4` (L13, L185, L187, L292) vindos de outros documentos sem explicar a correspondência.
   - **Conceitos normativos não explicados inline (`NG4`, `Zero Drift`, `ADR-008`)**: Embora `./local_project_os.md` e `./infra_and_subsystems_catalog.md` sejam linkados, `NG4` e `Zero Drift` não têm uma definição breve inline explicando o que exigem/proíbem hoje (apenas se infere que `NG4` vetava `sqlite3`). Já a `ADR-008` é citada quatro vezes (L13, L20, L112, L198) tanto pela renomeação para `Nexus` quanto como base para a lista de `entities` permitidas, mas não possui link nem resumo do seu conteúdo.

1. **Severity**: Major
2. **Affected Scope**: `Technical Plan §2` (L113–120), `Technical Plan §4` (L148–153), `Target Files #1` e `#6` (L232, L257, L262) — regras omitidas de `vault_schemas.json` e critérios da Matriz de Divergência.
3. **Discrepancy Description & Rationale**:
   - **Schemas incompletos por domínio**: A L115 detalha `required_fields` e `optional_fields` apenas para `04_Arquitetura_ADRs`, deixando não especificados quais campos obrigatórios/opcionais e enums se aplicam a `01_Projetos`, `02_Recursos_e_Infra` e `05_Areas` (o leitor só descobre alguns campos por menções esparsas no texto, como `repositorio_local`, `portas`, `status`, `cockpit_id`).
   - **Lacunas em `age_policy` e `non_frontmatter_policy`**: A L117 define `age_policy` para `01_Projetos` ("com limiares") e isenção para `04_Arquitetura_ADRs` e `05_Areas`, mas não informa quais são esses limiares numéricos nem qual é a política para `02_Recursos_e_Infra`. Da mesma forma, a L119 exemplifica `non_frontmatter_policy` para três pastas sem esclarecer a regra para `02_Recursos_e_Infra`, nem qual critério define "notas auxiliares" em `05_Areas` ou quais extensões binárias são ignoradas.
   - **Critérios indefinidos em `archived_active_repo` e `port_mismatch`**: A L150 e a L262 mencionam "commit recente" para `archived_active_repo`, mas não definem o limiar temporal (ex.: dias/meses ou comparação contra `doc_date`) nem como o reconciliador distingue "repositório dedicado" de "módulo incorporado" caso exista vínculo N:1 (L148) em que uma ficha está `Arquivado` e outra está ativa. Em `port_mismatch` (L152), não é explicado o formato esperado de `portas` na ficha nem se a comparação com `docker-compose.yml` valida portas de host, container ou ambas.

1. **Severity**: Major
2. **Affected Scope**: `Technical Plan §1` (Mermaid L95), `Technical Plan §2` (L112, L232, L237), `Technical Plan §3` (L139–140), `Technical Plan §5` (L165, L277).
3. **Discrepancy Description & Rationale**:
   - **Sobrecarga de "domínios" na UI vs. vault**: O diagrama Mermaid (L95) menciona `3 Domínios` na SPA e as L165/L277 falam na "3ª aba de domínio `🧠 Vault & Entidades`", porém o documento nunca nomeia quais são as outras 2 abas existentes. Para um leitor novo, "3 Domínios" colide com os 4 `domain` do banco/vault (`projects`, `infra`, `adrs`, `areas`, L139).
   - **`"Todas"` dentro da lista de entidades do schema**: As L112 e L232 colocam `"Todas"` dentro de `entities` no `vault_schemas.json`, e a L237 indica que `Test-VaultSchemas.ps1` substituirá `$allowedEntities` por essa lista. Fica ambíguo se `"Todas"` é um valor aceito no frontmatter de notas do vault ou apenas uma opção de filtro da UI/API.
   - **Inconsistência nominal e semântica entre `vault_nodes.links_status` e `project_repo_links.link_state`**: A L139 usa `'ok'` em `vault_nodes.links_status`, enquanto a L140 usa `'accessible'` em `project_repo_links.link_state` para os mesmos três estados de falha restantes. Além disso, o texto não explica o que `vault_nodes.links_status` mede em nós que não são `01_Projetos` (`infra`, `adrs`, `areas`) — por exemplo, se avalia `[[wikilinks]]` internos ou apenas vínculo de repositório.

1. **Severity**: Nit
2. **Affected Scope**: `Non-Goals` (L39), `Technical Plan §1` (L78), `Alternatives Considered` (`Alternative B`, L177, L180), `Non-Functional Requirements` (L213), `Additional Resources` (L219), `Target Files #8` e `#14` (L267, L297).
3. **Discrepancy Description & Rationale**:
   - **Termos e artefatos locais não definidos**: `*data pointers*` / `Data Pointers` (L39, L177) aparece sem definição; `data/config.json` (L78) e `data/ingested/` (L297) são citados sem explicar o que guardam no sistema atual; e `Postgres local de Finanças/Obras` / VPN `192.18.10.20` (L180) são mencionados sem contexto prévio.
   - **Referência externa sem link nem resumo**: `G:\Meu Drive\main_vault\01_Projetos\Pessoal\Nexus_Estudo_Infinity_OS.md` (L219) está apenas como caminho de texto puro sem explicação do papel desse estudo na compreensão da proposta.
   - **Descrição imprecisa de variáveis de fallback**: A L213 agrupa `AXION_VAULT_HOST_DIR` e `AXION_VAULT_PATH` como fallback "caso `NEXUS_VAULT_HOST_DIR` não seja definida", mas a L267 mostra que `AXION_VAULT_PATH` é fallback de container para `NEXUS_VAULT_ROOT`, enquanto `AXION_VAULT_HOST_DIR` é a variável de host do `docker-compose.yml`.
