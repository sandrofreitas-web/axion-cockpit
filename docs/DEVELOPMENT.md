# Guia de Desenvolvimento — Nexus Cockpit

Este guia descreve o fluxo de desenvolvimento local, a arquitetura de testes automatizados e o contrato de paridade entre o **Nexus Cockpit** e o `main_vault`.

---

## 1. Invariantes de Engenharia

1. **Zero Dependências Externas (`stdlib` only)**:
   - O backend Python deve utilizar exclusivamente módulos nativos da biblioteca padrão do Python 3.12 (`http.server`, `socketserver`, `json`, `pathlib`, `subprocess`, `threading`, `urllib`, `datetime`, `re`, `hashlib`).
   - Não introduza pacotes de terceiros (`pip`) nem `requirements.txt`.
2. **Zero Persistent Database (`NG4`)**:
   - Não utilize `sqlite3` nem bancos relacionais/vetoriais para indexação do vault. O índice do `main_vault` vive em memória (`VaultObserver._snapshot`) e é substituído atomicamente sob `threading.Lock`.
3. **Isolamento de Privacidade (`05_Areas`)**:
   - Notas em `05_Areas` devem passar obrigatoriamente pela projeção fechada `AREAS_SAFE_FIELDS` em `ui/vault_observer.py`. Nenhum endpoint pode expor o corpo Markdown ou `caminho_drive` dessas notas.

---

## 2. Executando no Host Windows

Utilize o `uv` para executar com a instalação local do Python 3.12+:

```powershell
# Iniciar o servidor na porta 4100 lendo diretamente G:\Meu Drive\main_vault
C:\Users\salmeida\.local\bin\uv.exe run python ui/app.py
```

Opções de linha de comando suportadas por `ui/app.py`:
- `--port <numero>`: Define a porta HTTP (padrão: `4100` ou variável `PORT`).
- `--host <endereco>`: Define o endereço de escuta (padrão: `127.0.0.1` no host ou variável `HOST`).

---

## 3. Suíte de Testes Automatizados (`unittest`)

A suíte conta com **25 testes** distribuídos em 3 arquivos em `tests/`:

- [`tests/test_vault_pipeline.py`](../tests/test_vault_pipeline.py):
  - `TestVaultParser`: Testa UTF-8 BOM, unescape de strings com aspas duplas, listas inline e multilinhas, e rejeição de YAML aninhado/não fechado em modo estrito.
  - `TestVaultPipelineAndRestAPI`: Testa a paridade com `vault_schemas.json`, reconciliação N:1 e matriz binária de divergências (`status_mismatch`, `missing_workspace`, `stale_sync`), privacidade de `05_Areas` (`AREAS_SAFE_FIELDS`), degradação graciosa de snapshot (`available` → `degraded`), ausência de CORS wildcard e bloqueio anti-CSRF (`403` / `415`).
- [`tests/test_infra_scanner.py`](../tests/test_infra_scanner.py):
  - Testa o parser de fichas de infraestrutura, exclusão de arquivos isentos (`HOME_LAB_SPECIFICATIONS.md`, `Oracle.md`), extração de portas de `docker-compose.yml`, detecção de colisões e cache TTL.
- [`tests/test_server.py`](../tests/test_server.py):
  - Testa a descoberta de projetos locais, validação contra caminhos perigosos do sistema (`DANGEROUS_SYSTEM_PATHS`), extração de diagramas Mermaid, telemetria Git e persistência de notas de melhoria.

### Comandos de Execução:

```powershell
# Executar todos os testes no host via uv
C:\Users\salmeida\.local\bin\uv.exe run python -m unittest discover -s tests -p "test_*.py" -v

# Executar todos os testes dentro do container Docker
docker compose exec nexus-cockpit python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 4. Governança de Schemas com o `main_vault`

As regras de validação de frontmatter dos 4 domínios (`01_Projetos`, `02_Recursos_e_Infra`, `04_Arquitetura_ADRs`, `05_Areas`) residem em:
- `G:\Meu Drive\main_vault\scripts\harness\vault_schemas.json`

Ao atualizar qualquer regra contratual:
1. Edite `G:\Meu Drive\main_vault\scripts\harness\vault_schemas.json` e mantenha o dicionário `DEFAULT_VAULT_SCHEMAS` sincronizado em `ui/vault_parser.py`.
2. Valide o cofre real com o script PowerShell:
   ```powershell
   pwsh -NoProfile -ExecutionPolicy Bypass -File "G:\Meu Drive\main_vault\scripts\harness\Test-VaultSchemas.ps1"
   ```
3. Execute a suíte `unittest` do Nexus Cockpit para garantir 100% de aprovação.
