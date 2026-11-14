# Guia de Operação Docker — Nexus Cockpit

O **Nexus Cockpit** executa em um container leve baseado em `python:3.12-slim` e expõe sua interface exclusivamente no endereço de loopback do host (`127.0.0.1:4100`).

---

## 1. Build e Inicialização

Na raiz do projeto (`C:\Docker\nexus-cockpit`):

```powershell
docker compose up -d --build
```

Para recriar o container forçando a atualização de mounts e portas:

```powershell
docker compose up -d --build --force-recreate
```

Verificação de saúde e bind de porta:

```powershell
docker inspect --format="{{.State.Health.Status}}" nexus-cockpit
docker port nexus-cockpit 4100
```

Saída esperada:
- Status de saúde: `healthy`
- Mapeamento de porta: `127.0.0.1:4100`

---

## 2. Mapeamento de Volumes (`docker-compose.yml`)

| Origem no Host | Destino no Container | Modo | Finalidade |
| :--- | :--- | :---: | :--- |
| `./ui` | `/app/ui` | `ro` | Código-fonte Python da API e ativos estáticos SPA (`index.html`, `app.js`, `styles.css`) |
| `./data` | `/app/data` | `rw` | Persistência local do Cockpit (`projects.json`, `config.json`, `notes/`, `ingested/`) |
| `${PROJECTS_HOST_DIR:-..}` (`C:\Docker`) | `/projects` | `ro` | Inspeção somente leitura da frota de projetos locais |
| `${NEXUS_VAULT_HOST_DIR:-G:/Meu Drive/main_vault}` | `/main_vault` | `ro` | Leitura somente leitura dos 4 domínios permitidos do `main_vault` |
| `${DRIVE_PROJECTS_HOST_DIR:-G:/Meu Drive/01 Projetos}` | `/drive_projects` | `ro` | Inspeção somente leitura de repositórios Git residentes no Google Drive |

---

## 3. Variáveis de Ambiente

| Variável | Valor Padrão | Descrição |
| :--- | :--- | :--- |
| `HOST` | `0.0.0.0` | Interface de escuta interna do processo Python no container |
| `PORT` | `4100` | Porta HTTP interna e externa (restrita a `127.0.0.1` no host) |
| `NEXUS_VAULT_ROOT` | `/main_vault` | Caminho da raiz do `main_vault` dentro do container |
| `NEXUS_VAULT_HOST_DIR` | `G:/Meu Drive/main_vault` | Caminho no host Windows montado em `/main_vault:ro` |
| `PROJECTS_HOST_DIR` | `..` (`C:\Docker`) | Diretório raiz de projetos no host montado em `/projects:ro` |
| `DRIVE_PROJECTS_DIR` | `/drive_projects` | Ponto de montagem interno para projetos no Google Drive |
| `DRIVE_PROJECTS_HOST_DIR` | `G:/Meu Drive/01 Projetos` | Caminho no host Windows montado em `/drive_projects:ro` |

---

## 4. Comportamento com Google Drive Desktop (`G:\`) no Windows / WSL2

O Google Drive Desktop no Windows monta a unidade `G:\` como um sistema de arquivos virtual (`WinFsp`) no contexto da sessão do usuário:

1. **Ordem de Inicialização**: Se o Docker Desktop (WSL2) iniciar antes do Google Drive Desktop montar a letra `G:\`, a VM Linux do Docker não enxergará os subdiretórios reais de `G:\Meu Drive\main_vault`.
2. **Detecção Segura e Degradação Graciosa**: Quando isso ocorre, o `VaultObserver` detecta que os 4 domínios obrigatórios não estão presentes em `/main_vault`, retorna `vault_status: "unavailable"` (ou preserva o último snapshot válido em memória com `vault_status: "degraded"`) e exibe um callout explicativo na interface web sem interromper o funcionamento do Cockpit.
3. **Como Sincronizar o Mount no Docker Desktop**:
   - Certifique-se de que o Google Drive Desktop está aberto e a unidade `G:\` está acessível no Windows Explorer.
   - Reinicie o Docker Desktop (ou execute `uv run python ui/app.py` diretamente no host Windows para leitura nativa direta de `G:\Meu Drive\main_vault`).

---

## 5. Healthcheck Nativo

Tanto o `Dockerfile` quanto o `docker-compose.yml` utilizam o endpoint rápido `GET /api/status` via biblioteca padrão do Python:

```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:4100/api/status').read()\""]
  interval: 30s
  timeout: 5s
  retries: 3
  start_period: 5s
```
