# Relatório Consolidado de Revisão (EGM Review)

- **Documento avaliado:** [vault_observability_and_entity_cockpit.md](file:///C:/Docker/nexus-cockpit/docs/designs/vault_observability_and_entity_cockpit.md) (`FeatureRange`: linhas 1–224; `DetailedRange`: linhas 225–309)
- **Estágios executados:** Estágios 5 a 9 (Preset 1 — fluxo completo ininterrupto)
- **Relatórios de origem:**
  - Estágio 5 (`egm-zoom-out`): [zoom_out_report.md](file:///C:/Docker/nexus-cockpit/zoom_out_report.md)
  - Estágio 6 (`egm-comprehension`): [comprehension_report.md](file:///C:/Docker/nexus-cockpit/comprehension_report.md)
  - Estágio 7 (`egm-design`, `egm-structural`, `egm-style`): [critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)
  - Estágio 8 (`egm-zoom-out` intermediário): [intermediate_zoom_out_report.md](file:///C:/Docker/nexus-cockpit/intermediate_zoom_out_report.md)
  - Estágio 9 (`egm-implementation-readiness`, `egm-codebase-details`, `egm-style`): [implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)
- **Veredito geral:** **Reprovado para implementação no estado atual.** A especificação precisa simplificar a arquitetura de indexação/scan (evitando complexidade acidental e pipelines duplicados), fechar lacunas de segurança e contratos (*Zero-Decision Rule*) para `vault_schemas.json`, matriz de divergência, API REST e parser YAML antes de iniciar o código.

---

## Resumo Executivo

As revisões independentes convergiram em dois eixos principais:

1. **Complexidade acidental em `sqlite3` e pipeline duplicado:** O Estágio 8 (`Intermediate Zoom Out`) apontou que o uso de `sqlite3` (`/tmp/nexus_vault_index.db`) para ~40–50 notas é a causa raiz de múltiplos bloqueios dos Estágios 7 e 9 (DDL incompleto, FK em `project_repo_links` que impede persistir `unlinked_cockpit_project`, concorrência WAL no `ThreadingTCPServer`, acoplamento de `scan_errors` a `run_id` e emenda a `NG4`). Substituir `sqlite3` por um snapshot imutável em memória trocado atomicamente sob `threading.Lock` e consolidar o novo scanner no fluxo de `ui/infra_scanner.py` elimina diretamente boa parte desses bloqueios.
2. **Contratos subespecificados e superfície de segurança:** O plano atual viola a *Zero-Decision Rule* em `vault_schemas.json` (regras omitidas para `01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas`), na matriz de divergência (`archived_active_repo`, `port_mismatch`, N:1), nos payloads/HTTP codes das rotas REST, na compatibilidade do novo parser YAML com `tests/test_infra_scanner.py` e `write_markdown_note`, além de deixar brechas de allowlist em rotas legadas (`POST /api/infra/config`, `POST /api/projects`) e proteção contra CSRF / `CORS: *`.

---

## Itens de Ação Priorizados

### 🔴 Blockers (Impedem implementação segura ou determinística)

#### B1 — Definir arquitetura de índice: adotar snapshot em memória ou corrigir DDL e concorrência do `sqlite3`
- **Origens:** `ZO-M1`, `IZO-B1`, `DES-B2` (FK/scan_errors), `DES-M1`, `IR-B2`
- **Diagnóstico:** Manter `/tmp/nexus_vault_index.db` obriga alterar `NG4` (*Zero Persistent Database*), exige init-once de `WAL`/`user_version` sob lock, transações `BEGIN IMMEDIATE`, política `single-flight`, perde o índice após restart do container e traz um DDL incompleto onde a FK `project_repo_links.vault_rel_path` impede registrar `unlinked_cockpit_project` e `scan_errors` ligada a `run_id` some quando entra `run_id = 'unavailable'`. O ciclo de inicialização no boot também não está especificado.
- **Ação requerida:**
  1. **Opção recomendada (Stage 8):** Remover `sqlite3` e `ui/vault_index.py`, adotando um snapshot imutável em memória atualizado atomicamente sob `threading.Lock`, restaurando `NG4` sem emendas.
  2. **Caso `sqlite3` seja mantido por decisão do owner:** Especificar o DDL completo, remover a FK que bloqueia `unlinked_cockpit_project`, desacoplar `scan_errors` de `run_id` `unavailable`, detalhar init-once de `WAL`/`user_version`, transações `BEGIN IMMEDIATE`, política `single-flight` e o ciclo exato de inicialização no boot.

#### B2 — Unificar pipeline de scan com `ui/infra_scanner.py` e fechar brechas de allowlist, `05_Areas` e CSRF
- **Origens:** `ZO-M2`, `IZO-B2`, `IZO-M1`, `DES-B1`, `IR-M2`, `CD-M3`
- **Diagnóstico:** Os módulos `vault_*` duplicam cache (`_CACHE`), `extract_compose_ports_from_content`, `detect_port_collisions` e `data/config.json` já presentes em `ui/infra_scanner.py`. Rotas mutáveis legadas (`POST /api/infra/config`, `POST /api/projects`) permitem bypass da allowlist do mount `/main_vault:ro`; falta validação pós-`resolve()` contra symlinks; regras de segurança (`05_Areas`, `allow_body_preview`, diretórios sensíveis) não devem residir em JSON do Google Drive; e há risco de CSRF em rotas mutáveis (`HOST=0.0.0.0` interno + `127.0.0.1:4100` no host) somado a `CORS: *` residual em `do_OPTIONS` (`ui/app.py:208-213`).
- **Ação requerida:**
  1. Consolidar o pipeline de scan reutilizando `extract_compose_ports_from_content` e `detect_port_collisions` de `ui/infra_scanner.py`.
  2. Centralizar a validação de caminhos (incluindo checagem pós-`resolve()` contra symlinks e bloqueio de `chaves_ssh`, prefixos `.` e `.env`) em `is_valid_project_path` aplicada também a `POST /api/infra/config` e `POST /api/projects`.
  3. Fixar em Python (não em `vault_schemas.json`) a projeção fechada de campos de `05_Areas` e a sanitização de `scan_errors.detail`.
  4. Remover `CORS: *` inclusive de `do_OPTIONS` (`ui/app.py:208-213`) e validar `Origin`/`Sec-Fetch-Site` + `Content-Type` em rotas mutáveis sem impor cabeçalho `Host` rígido.

#### B3 — Fechar contrato `vault_schemas.json` e alinhar paridade com `Test-VaultSchemas.ps1`
- **Origens:** `ZO-M3`, `IZO-M3`, `IR-B1`, `CD-B1`, `CMP-M2`
- **Diagnóstico:** Faltam definições fechadas de campos e enums para os 4 domínios (`01_Projetos`, `02_Recursos_e_Infra` incluindo `"Ativo / Produção"`, `04_Arquitetura_ADRs` incluindo `"Aprovado / Implementado"` e `"Substituído"`, e `05_Areas`). Há divergência de `ignored_filenames` entre `ui/infra_scanner.py:349` e `Test-VaultSchemas.ps1:71`, omissão de regra para extensões não-`.md` vs `-Filter "*.md"`, semântica incompleta de `non_frontmatter_policy`, indefinição do tratamento de `caminho_drive` dentro do container Linux e presença indevida da opção de UI `"Todas"` dentro de `entities` em `vault_schemas.json`.
- **Ação requerida:**
  1. Especificar campos obrigatórios/opcionais e enums exatos para todos os 4 domínios em `vault_schemas.json`.
  2. Reconciliar `ignored_filenames`, tratamento de extensões não-`.md`, `non_frontmatter_policy` e mapeamento de `caminho_drive` no container Linux.
  3. Retirar controles de UI (`"Todas"` em `entities`) e política de privacidade (`allow_body_preview`) de `vault_schemas.json`.

#### B4 — Especificar critérios determinísticos da Matriz de Divergência e reconciliação N:1
- **Origens:** `DES-B2` (divergência), `CMP-M2`, `IZO-M3`, `IR-B3`, `CD-M4`
- **Diagnóstico:** `archived_active_repo` depende de termo subjetivo (*"commit recente"*) sem limiar em dias nem regra de agregação N:1; `port_mismatch` não especifica o campo esperado em `01_Projetos` nem resolve notas múltiplas para um mesmo projeto (como `SIAEBR_Project.md` `[8501, 8000, 5432, 6379]` vs `SIAEBR_MatPlan.md` `[8501, 8000]` e `portas: []`); não há critério para detectar `/drive_projects` montado vazio nem regra explícita de matching contra caminhos relativos e registros com `ingested: true` em `data/projects.json` (incluindo impacto em `finaceiro-pessoal`).
- **Ação requerida:**
  1. Definir limiar numérico em dias para `archived_active_repo` e sua regra N:1.
  2. Definir campo fonte e algoritmo determinístico N:1 para `port_mismatch`.
  3. Definir como detectar `/drive_projects` vazio e como reconciliar `vault_rel_path` com caminhos relativos e `ingested: true` em `data/projects.json`.

#### B5 — Definir contratos REST completos (payloads JSON e códigos HTTP)
- **Origens:** `DES-M4`, `IR-B4`, `CD-M2`
- **Diagnóstico:** `GET /api/status`, `GET /api/vault/entities`, `GET /api/vault/overview` e `POST /api/vault/reindex` não apresentam o formato JSON completo de sucesso e erro nem seus códigos HTTP; falta também definir o comportamento do filtro `entidade: "Todas"` (citado em `ADR-008`) na camada REST.
- **Ação requerida:** Documentar schemas JSON de entrada/saída, payloads de erro e status codes HTTP de todos os endpoints novos e alterados, explicitando o tratamento de `entidade=Todas`.

#### B6 — Corrigir contrato do parser YAML, compatibilidade com `write_markdown_note` e suíte de testes
- **Origens:** `CD-B2`, `IR-M1`, `DES-N1`
- **Diagnóstico:** A troca do parser YAML quebra contratos existentes: `tests/test_infra_scanner.py:22-61` espera retorno `dict` plano (`{}` em frontmatter não fechado); `tests/test_server.py:124-144` e `ui/app.py:329,575` chamam `parse_markdown_note` esperando defaults locais; e `ui/app.py:164` (`write_markdown_note`) não escapa `\"`/`\\`, quebrando roundtrip caso o novo parser desescape strings. Além disso, `tests/test_infra_scanner.py (Modify)` foi omitido do plano de alterações.
- **Ação requerida:** Definir assinatura exata, comportamento em casos de borda (frontmatter não fechado, chaves aninhadas/duplicadas, blocos `|`/`>`, aspas simples `''`), simetria de escape/unescape com `write_markdown_note`, preservação dos callers em `ui/app.py` e inclusão de `tests/test_infra_scanner.py (Modify)` no plano.

---

### 🟡 Majors (Riscos arquiteturais, lacunas funcionais ou violações de padrão)

#### M1 — Remover scaffolding especulativo de `age_policy` / `age_exempt`
- **Origens:** `ZO-M4`, `CMP-M2`, `IZO-M2`, `IR-B1`
- **Diagnóstico:** `age_policy` e `age_exempt` são citados sem limiares numéricos e não possuem consumidor no backend ou na interface.
- **Ação requerida:** Remover `age_policy` e `age_exempt` da especificação e de `vault_schemas.json` (ou detalhar limiares e consumidor caso permaneçam no escopo).

#### M2 — Adicionar `## Risks & Mitigations` e especificar invalidação, teto de volumetria e cold start
- **Origens:** `DES-M2`, `DES-M3`, `IZO-M1`, `STR-M1`
- **Diagnóstico:** O documento não possui a seção `## Risks & Mitigations` exigida por `feature-spec-standard.md`; não há teto de bytes por `.md` nem fluxo de tratamento para `schema_error`; a invalidação baseada apenas no SHA-256 dos `.md` ignora mudanças em `data/projects.json`, `docker-compose.yml` e `.git`; `GET /api/projects` mantém chamadas síncronas a `git` por projeto; e o tempo de cold start não está alinhado ao `start_period: 5s` do healthcheck.
- **Ação requerida:** Incluir `## Risks & Mitigations` cobrindo limite de bytes por `.md`, `schema_error`, invalidação composta de cache (`projects.json`, `docker-compose.yml`, `.git`), remoção de `git` síncrono em `GET /api/projects` e meta de boot compatível com `start_period: 5s`.

#### M3 — Corrigir colisões de IDs, inconsistências terminológicas e definições inline
- **Origens:** `CMP-M1`, `CMP-M3`, `STR-M3`, `STR-M4`, `STY-M1..M4`, `IZO-M3`, `IZO-N1`
- **Diagnóstico:** Há colisão do ID `G6` (L33 vs L180) e mistura entre `NG3`/`NG4` herdados e `NG-A..NG-E`; termos como `NG4`, `Zero Drift`, `ADR-008` e `CUJ 1` carecem de definição/link inline; há divergência entre `vault_nodes.links_status: 'ok'` e `project_repo_links.link_state: 'accessible'`, indefinição de `links_status` para notas que não são projetos e sobrecarga de "3 Domínios" na SPA contra 4 valores de `domain` no vault.
- **Ação requerida:** Renumerar `G6` e unificar os `NG`s; definir/linkar `NG4`, `Zero Drift`, `ADR-008`, `CUJ 1` e o termo "domínio" na UI vs vault; padronizar o enum de status de vínculo e seu valor para não-projetos.

#### M4 — Corrigir estrutura de cabeçalhos, escopo da seção 1 e diagrama Mermaid
- **Origens:** `STR-M2`, `STR-M5`, `STY-M5`, `IZO-M3`
- **Diagnóstico:** `### Additional Resources` está como H3 em vez de H2; a seção 1 omite `02_Recursos_e_Infra` e `/projects:ro`; referências a `ui/static/app.js` divergem entre texto e diagrama; e o Mermaid apresenta aspas faltantes no rótulo `MV -->|...| VP`, seta invertida em `PS`, ausência de `data/`, nó `VR` desconectado e `SPA` posicionado dentro de `Container`.
- **Ação requerida:** Promover `### Additional Resources` para H2, incluir `02_Recursos_e_Infra` e `/projects:ro` na seção 1, uniformizar caminhos de arquivos e corrigir sintaxe e topologia do diagrama Mermaid.

#### M5 — Definir precedência de variáveis de ambiente, corrigir `AXION_VAULT_HOST_DIR` e completar injeção em `ui/`
- **Origens:** `DES-M4`, `CMP-N1`, `IZO-B2`, `IZO-N1`, `CD-M3`
- **Diagnóstico:** O fallback `AXION_VAULT_HOST_DIR` aponta para a subpasta `02_Recursos_e_Infra`, incompatível com o mount raiz `/main_vault`; não há ordem de precedência formal entre `NEXUS_VAULT_HOST_DIR`, `NEXUS_VAULT_ROOT`, `AXION_VAULT_HOST_DIR`, `AXION_VAULT_PATH` e `DRIVE_PROJECTS_DIR`; e falta especificar a injeção de `INGESTED_BASE_DIR` em `ui/app.py` e de caminhos equivalentes em `ui/infra_scanner.py:291,473`.
- **Ação requerida:** Documentar precedência, defaults e mapeamento raiz `/main_vault:ro` de todas as variáveis de ambiente e especificar os pontos exatos de injeção em `ui/app.py` e `ui/infra_scanner.py`.

#### M6 — Especificar comportamento da SPA para Infra, ADRs, Áreas e `switchDomain`
- **Origens:** `CD-M5`, `STY9-M1..M5`
- **Diagnóstico:** A UI detalha Projetos e consolidação por entidade, mas não especifica renderização, filtros e estados para `02_Recursos_e_Infra`, `04_Arquitetura_ADRs` e `05_Areas`, nem a atualização de `switchDomain` em `ui/static/app.js:1326-1349`.
- **Ação requerida:** Definir os componentes, filtros e contratos visuais de cada domínio na SPA e as alterações necessárias em `switchDomain`.

#### M7 — Adicionar `Phasing & Checkpoints` e corrigir `Verification Plan`
- **Origens:** `CD-M1`, `IR-M6`, `CD-M7`
- **Diagnóstico:** O plano detalhado omite `Phasing & Checkpoints` (exigido por `implementation-readiness-standard.md`, embora `concepts_brief.md` mencionasse Fase 0), usa comandos imprecisos no `Verification Plan` (`Test-NetConnection / ss` em vez de `docker port` + `Get-NetTCPConnection`) e traz critérios de aceitação genéricos.
- **Ação requerida:** Estruturar a execução em fases incrementais com checkpoints objetivos e substituir os comandos de verificação por `docker port` + `Get-NetTCPConnection` e asserções verificáveis.

#### M8 — Cobrir arquivos legados/CI omitidos e paridade da regex de wikilinks
- **Origens:** `CD-M6`, `IR-M5`
- **Diagnóstico:** O plano não trata impactos ou migração em `data/notes/axion-cockpit/`, `.github/workflows/ci.yml:1` e `docs/reviews/README.md`, nem define que a extração de wikilinks em Python deve ignorar blocos de código como faz `Test-VaultSchemas.ps1:116-117`.
- **Ação requerida:** Definir o tratamento de `data/notes/axion-cockpit/`, `.github/workflows/ci.yml` e `docs/reviews/README.md`, e exigir regex de wikilinks com exclusão de blocos de código.

#### M9 — Reduzir fragmentação de módulos, elevar altitude e limpar estilo do texto
- **Origens:** `ZO-N1`, `IZO-N1`, `STY-M1..M5`, `STY9-M1..M5`
- **Diagnóstico:** A especificação divide lógica coesa em 3–4 módulos novos enquanto desce a detalhes de implementação no plano técnico (números de linha, PRAGMAs literais, flags de comando `git`), mistura inglês/português em `Given/When/Then` e usa jargões ou termos subjetivos (*"ledger local"*, *"I/O pesado"*, *"ecossistema"*, *"atrito"*, *"Frescor"*, *"estrito"*, *"facilmente"*, *"inevitavelmente"*).
- **Ação requerida:** Consolidar novos helpers em menor número de módulos (ex.: `ui/vault_parser.py` + extensão de `ui/infra_scanner.py`), remover microdetalhes prematuros de implementação da seção de arquitetura e reescrever trechos opinativos em linguagem objetiva e uniforme.

---

### 🟢 Nits (Clareza, higiene de código e detalhes menores)

#### N1 — Definir termos contextuais, corrigir links e formato de datas
- **Origens:** `CMP-N1`, `DES-N1`, `IZO-N1`
- **Ação requerida:** Contextualizar brevemente `data pointers`, `data/config.json`, `data/ingested/`, Postgres Finanças/Obras e VPN `192.18.10.20`; verificar/corrigir os links para `Nexus_Estudo_Infinity_OS.md` e `concepts_brief.md`; explicitar formato ISO de `doc_date` e `indexed_at`.

#### N2 — Garantir `-Encoding UTF8` no PowerShell 5.1 e `last_commit_iso: ""` em fallbacks
- **Origens:** Estágio 9 Nits (`implementation_readiness_report.md`)
- **Ação requerida:** Usar `Get-Content -Encoding UTF8` no validador PowerShell e garantir `last_commit_iso: ""` nos retornos de fallback em `ui/app.py:271` e `ui/scanner.py:275,283`.

#### N3 — Remover labels legados e placeholder `/vault`
- **Origens:** Estágio 9 Nits (`implementation_readiness_report.md`)
- **Ação requerida:** Limpar labels residuais em `Dockerfile` e `ui/static/app.js` e atualizar o placeholder `/vault` em `ui/index.html:510`.

#### N4 — Padronizar divisores, links relativos no plano e rodapé
- **Origens:** `STR-N1..N2`, `STY-N1..N13`, Estágio 9 Nits (`implementation_readiness_report.md`)
- **Ação requerida:** Corrigir simetria dos divisores horizontais, adicionar links/caminhos relativos nos itens 3–14 do plano de implementação e remover o rodapé `*Drafted with EGM*`.

---

## Matriz de Rastreabilidade

| Estágio / Relatório | Achado de Origem | Item Consolidado |
| :--- | :--- | :--- |
| Estágio 5 ([zoom_out_report.md](file:///C:/Docker/nexus-cockpit/zoom_out_report.md)) | `ZO-M1` (`sqlite3` YAGNI / `NG4`) | **B1** |
| Estágio 5 ([zoom_out_report.md](file:///C:/Docker/nexus-cockpit/zoom_out_report.md)) | `ZO-M2` (Pipeline duplicado com `ui/infra_scanner.py`) | **B2** |
| Estágio 5 ([zoom_out_report.md](file:///C:/Docker/nexus-cockpit/zoom_out_report.md)) | `ZO-M3` (Acoplamento privacidade/UI em `vault_schemas.json`) | **B3** |
| Estágio 5 ([zoom_out_report.md](file:///C:/Docker/nexus-cockpit/zoom_out_report.md)) | `ZO-M4` (`age_policy` / `age_exempt` sem consumidor) | **M1** |
| Estágio 5 ([zoom_out_report.md](file:///C:/Docker/nexus-cockpit/zoom_out_report.md)) | `ZO-N1` (Fragmentação de módulos e queda de altitude) | **M9** |
| Estágio 6 ([comprehension_report.md](file:///C:/Docker/nexus-cockpit/comprehension_report.md)) | `CMP-M1` (`G6`, `NG3`/`NG4` vs `NG-A..E`, definições inline) | **M3** |
| Estágio 6 ([comprehension_report.md](file:///C:/Docker/nexus-cockpit/comprehension_report.md)) | `CMP-M2` (Regras dos 4 domínios, `age_policy`, divergências) | **B3**, **B4**, **M1** |
| Estágio 6 ([comprehension_report.md](file:///C:/Docker/nexus-cockpit/comprehension_report.md)) | `CMP-M3` (`3 Domínios` vs 4, `"Todas"`, `links_status` vs `link_state`) | **B3**, **M3** |
| Estágio 6 ([comprehension_report.md](file:///C:/Docker/nexus-cockpit/comprehension_report.md)) | `CMP-N1` (Termos sem glossário, link ausente, `AXION_VAULT_HOST_DIR`) | **M5**, **N1** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `DES-B1` (`05_Areas`, bypass em rotas legadas, symlinks, CSRF) | **B2** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `DES-B2` (FK `project_repo_links`, `scan_errors`/`run_id`, divergências) | **B1**, **B4** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `DES-M1` (Concorrência SQLite WAL, `BEGIN IMMEDIATE`, `single-flight`) | **B1** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `DES-M2` (Ausência de `## Risks & Mitigations`, limite bytes, `schema_error`) | **M2** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `DES-M3` (Invalidação SHA-256 parcial, cold start, `git` síncrono) | **M2** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `DES-M4` (`"Todas"`, `AXION_VAULT_HOST_DIR`, HTTP codes REST) | **B3**, **B5**, **M5** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `DES-N1` (Bordas YAML, formato datas, link `concepts_brief.md`) | **B6**, **N1** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `STR-M1..M5` (`Risks & Mitigations`, H2, IDs, `§1`, Mermaid) | **M2**, **M3**, **M4** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `STR-N1..N2` (Caminhos de arquivo e simetria de divisores) | **M4**, **N4** |
| Estágio 7 ([critic_report.md](file:///C:/Docker/nexus-cockpit/critic_report.md)) | `STY-M1..M5`, `STY-N1..N13` (IDs, `"Todas"`, jargões, estilo, `Given/When/Then`) | **M3**, **M4**, **M9**, **N4** |
| Estágio 8 ([intermediate_zoom_out_report.md](file:///C:/Docker/nexus-cockpit/intermediate_zoom_out_report.md)) | `IZO-B1` (Substituir `sqlite3` por snapshot em memória sob `threading.Lock`) | **B1** |
| Estágio 8 ([intermediate_zoom_out_report.md](file:///C:/Docker/nexus-cockpit/intermediate_zoom_out_report.md)) | `IZO-B2` (Unificar `infra_scanner`, fechar rotas legadas, `AXION_VAULT_HOST_DIR`) | **B2**, **M5** |
| Estágio 8 ([intermediate_zoom_out_report.md](file:///C:/Docker/nexus-cockpit/intermediate_zoom_out_report.md)) | `IZO-M1` (Segurança em Python, cap de bytes, CSRF sem `Host` rígido) | **B2**, **M2** |
| Estágio 8 ([intermediate_zoom_out_report.md](file:///C:/Docker/nexus-cockpit/intermediate_zoom_out_report.md)) | `IZO-M2` (Remover scaffolding `age_policy` / `age_exempt`) | **M1** |
| Estágio 8 ([intermediate_zoom_out_report.md](file:///C:/Docker/nexus-cockpit/intermediate_zoom_out_report.md)) | `IZO-M3` (Fechar `vault_schemas.json`, divergência, estrutura, Mermaid) | **B3**, **B4**, **M3**, **M4** |
| Estágio 8 ([intermediate_zoom_out_report.md](file:///C:/Docker/nexus-cockpit/intermediate_zoom_out_report.md)) | `IZO-N1` (Altitude do plano técnico, env vars, link/resumo `ADR-008`) | **M3**, **M5**, **M9**, **N1** |
| Estágio 9 ([implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)) | `IR-B1`, `CD-B1` (Contratos dos 4 domínios, `ignored_filenames`, `caminho_drive`) | **B3**, **M1** |
| Estágio 9 ([implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)) | `IR-B2` (DDL `sqlite3` incompleto, FK, ciclo de boot) | **B1** |
| Estágio 9 ([implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)) | `IR-B3`, `CD-M4` (Critérios de divergência N:1, `/drive_projects` vazio, `ingested: true`) | **B4** |
| Estágio 9 ([implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)) | `IR-B4`, `CD-M2` (Contratos JSON e HTTP codes dos endpoints REST) | **B5** |
| Estágio 9 ([implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)) | `CD-B2`, `IR-M1` (Quebra do parser YAML, `write_markdown_note`, `test_infra_scanner.py`) | **B6** |
| Estágio 9 ([implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)) | `CD-M1` (Ausência de `Phasing & Checkpoints`) | **M7** |
| Estágio 9 ([implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)) | `IR-M2..M6`, `CD-M3`, `CD-M5..M7`, `STY9-M1..M5` (`do_OPTIONS`, env vars, SPA `switchDomain`, `ci.yml`/legados, `Verification Plan`) | **B2**, **M5**, **M6**, **M7**, **M8**, **M9** |
| Estágio 9 ([implementation_readiness_report.md](file:///C:/Docker/nexus-cockpit/implementation_readiness_report.md)) | `IR-N1..N2`, `CD-N1..N2`, `STY9-N1..N5` (UTF-8 PS 5.1, `last_commit_iso`, labels, `/vault`, links, rodapé) | **N2**, **N3**, **N4** |
