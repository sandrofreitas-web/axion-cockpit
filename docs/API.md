# Referência da API REST — Nexus Cockpit

O servidor HTTP do **Nexus Cockpit** escuta na porta `4100` (vinculada a `127.0.0.1:4100` no host) e responde com payloads JSON (`application/json; charset=utf-8`).

---

## 🔒 Convenções de Segurança

- **Sem CORS Wildcard**: O servidor não emite `Access-Control-Allow-Origin: *`.
- **Proteção Anti-CSRF em Rotas Mutáveis (`POST`, `PUT`, `DELETE`)**:
  - Requisições com cabeçalho `Sec-Fetch-Site: cross-site` são bloqueadas com `403 Forbidden`.
  - Requisições com cabeçalho `Origin` que não corresponda a `localhost`, `127.0.0.1` ou `[::1]` são bloqueadas com `403 Forbidden`.
  - Requisições com corpo exigem `Content-Type: application/json` (retornando `415 Unsupported Media Type` caso contrário).

---

## 1. Saúde e Status do Sistema

### `GET /api/status`
Endpoint leve de healthcheck (sem invocação de subprocessos Git) que retorna o estado do servidor e o resumo do snapshot atual do `VaultObserver`.

**Resposta `200 OK`:**
```json
{
  "status": "online",
  "app": "Nexus Cockpit",
  "timestamp": "2026-11-14T09:50:00+00:00",
  "vault": {
    "vault_status": "available",
    "vault_error": null,
    "last_indexed_at": "2026-11-14T09:49:55Z",
    "files_total": 49,
    "errors_count": 0,
    "divergences_count": 3
  }
}
```

---

## 2. Observabilidade do Main Vault & Visão por Entidade

### `GET /api/vault/entities`
Retorna o estado do índice do `main_vault` e a lista de entidades (`Todas`, `Pessoal`, `Axion Skill`, `SIAE BR`, `Igreja ICENV`) com contadores por domínio, erros de contrato e divergências.

**Resposta `200 OK`:**
```json
{
  "vault_status": "available",
  "last_indexed_at": "2026-11-14T09:49:55Z",
  "entities": [
    {
      "name": "Todas",
      "projects": 11,
      "infra": 8,
      "adrs": 8,
      "areas": 22,
      "contract_errors": 0,
      "divergences": 3
    },
    {
      "name": "Pessoal",
      "projects": 6,
      "infra": 5,
      "adrs": 6,
      "areas": 12,
      "contract_errors": 0,
      "divergences": 1
    }
  ]
}
```

### `GET /api/vault/overview?entity=<nome>`
Retorna a visão consolidada da entidade selecionada (padrão: `Todas`), incluindo KPIs (`summary`), nós indexados (`vault_nodes`), vínculos N:1 com matriz binária de divergências (`project_repo_links`) e eventos de auditoria de schema (`scan_errors`).

**Parâmetros de Query:**
- `entity` (opcional): `Todas`, `Pessoal`, `Axion Skill`, `SIAE BR` ou `Igreja ICENV`. Retorna `400 Bad Request` se for informada uma entidade desconhecida.

**Resposta `200 OK`:**
```json
{
  "vault_status": "available",
  "vault_error": null,
  "schema_version": "1.0.0",
  "last_indexed_at": "2026-11-14T09:49:55Z",
  "entity": "Todas",
  "summary": {
    "total_nodes": 49,
    "contract_errors": 0,
    "warnings": 3,
    "divergences": 3
  },
  "vault_nodes": [
    {
      "rel_path": "05_Areas/Pessoal/Financas.md",
      "domain": "areas",
      "entity": "Pessoal",
      "title": "Financas",
      "area": "Finanças",
      "doc_type": "area_operacional",
      "status": "Ativo",
      "frontmatter_status": "ok",
      "links_status": "valid",
      "validation_errors": [],
      "size_bytes": 1420,
      "doc_date": "2026-11-01",
      "indexed_at": "2026-11-14T09:49:55Z"
    }
  ],
  "project_repo_links": [
    {
      "project_title": "Nexus Cockpit",
      "entity": "Pessoal",
      "vault_rel_path": "01_Projetos/Axion_Cockpit.md",
      "vault_status": "Ativo",
      "cockpit_project_id": "nexus-cockpit",
      "link_state": "linked_local",
      "raw_repo_ref": "C:\\Docker\\nexus-cockpit",
      "sibling_modules_count": 1,
      "git": {
        "is_repo": true,
        "branch": "main",
        "is_dirty": false,
        "uncommitted_count": 0,
        "last_commit_date": "2026-11-14T06:50:00-03:00"
      },
      "declared_ports": [4100],
      "compose_ports": [4100],
      "divergence_flags": []
    }
  ],
  "scan_errors": []
}
```
> **Garantia de Privacidade (`05_Areas`)**: Os elementos de `vault_nodes` com `domain == "areas"` contêm exclusivamente as 13 chaves de `AREAS_SAFE_FIELDS`. O conteúdo textual (`body`/`content`) e `caminho_drive` nunca são incluídos.

### `POST /api/vault/reindex`
Aciona a reconstrução imediata do snapshot em memória do `main_vault` e limpa o cache de infraestrutura.

**Corpo da Requisição:** `{"force": true}` (ou `{}`)

**Resposta `200 OK`:**
```json
{
  "status": "ok",
  "vault_status": "available",
  "vault_error": null,
  "last_indexed_at": "2026-11-14T09:51:00Z",
  "files_total": 49,
  "errors_count": 0,
  "warnings_count": 3,
  "divergences_count": 3
}
```

---

## 3. Catálogo de Infraestrutura Global

### `GET /api/infra`
Retorna os recursos de infraestrutura declarados em `02_Recursos_e_Infra`, métricas agregadas (`by_type`, `by_os`, `by_entity`) e a matriz de portas com detecção de colisões (`ports`).
- Suporta `?refresh=true` para forçar a atualização imediata do cache TTL (30s).

### `POST /api/infra/config`
Atualiza o caminho configurado para a pasta de recursos em `data/config.json`. Rejeita diretórios proibidos (`chaves_ssh`, `.obsidian`, `.git`, caminhos de sistema).
- **Payload**: `{"vault_path": "G:\\Meu Drive\\main_vault\\02_Recursos_e_Infra"}`

---

## 4. Frota de Projetos Locais & Ledger de Melhorias

### `GET /api/projects`
Lista todos os projetos registrados em `data/projects.json`, enriquecidos com telemetria Git e status de acessibilidade física no disco.

### `GET /api/projects/discover`
Descobre automaticamente diretórios de projetos disponíveis em `/projects` (`C:\Docker`) ainda não registrados.

### `GET /api/system/browse?path=<subpath>`
Navega pelas subpastas do workspace para seleção visual de diretórios.

### `GET /api/projects/<id>/docs`
Extrai sob demanda a documentação Markdown consolidada, indicadores de ambiente, diagramas Mermaid (`workflows` e `database`) e telemetria Git do projeto `<id>`.

### `POST /api/projects`
Registra um projeto local existente pelo caminho ou pasta descoberta.
- **Payload**: `{"name": "Meu Projeto", "path": "C:\\Docker\\meu-projeto", "current_version": "v1.0.0", "tags": ["python", "docker"]}`

### `POST /api/projects/ingest`
Ingere os arquivos documentais (`.md`, `Dockerfile`, `docker-compose.yml`, etc.) selecionados via navegador para `data/ingested/<id>/` e registra o projeto no catálogo.

### `DELETE /api/projects/<id>`
Remove o vínculo do projeto de `data/projects.json` (preservando intocados os arquivos originais no disco).

### `POST /api/projects/<id>/version`
Homologa uma nova versão canônica para o projeto (`{"version": "v1.1.0"}`).

### `GET /api/projects/<id>/notes`
Lista todas as notas do Ledger de Melhorias do projeto (`data/notes/<id>/*.md`).

### `POST /api/projects/<id>/notes`
Cria uma nova nota de melhoria no Ledger do projeto.

### `PUT /api/projects/<id>/notes/<note_id>`
Atualiza o título, estágio (`idea`, `planned`, `in_review`, `incorporated`), versão-alvo, arquivos impactados ou conteúdo de uma nota.

### `DELETE /api/projects/<id>/notes/<note_id>`
Exclui uma nota do Ledger de Melhorias do projeto.
