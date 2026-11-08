#!/usr/bin/env python3
"""
infra_scanner.py — Motor de inspeção estática e catalogação passiva de infraestrutura e subsistemas.
Executa 100% na biblioteca padrão do Python (sem PyYAML nem requests).
Lê fichas declarativas no Obsidian Vault e manifestos locais de contêineres sob demanda.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from scanner import resolve_cross_platform_path
except ImportError:
    from ui.scanner import resolve_cross_platform_path

# Regex determinística para extrair portas de serviços do vault (ex: "Cockpit (:9090)", "App (:3080 / :8080)")
VAULT_PORT_REGEX = re.compile(r':(\d{2,5})\b')

# Regex determinística para extrair portas de serviços no docker-compose.yml
# Trata short syntax: "8080:80", 5432:5432, "127.0.0.1:9090:9090", "3000", com/sem sufixo de protocolo
COMPOSE_PORT_REGEX = re.compile(
    r'^\s*-\s*["\']?(?:(?:[\d.]+):)?(\d{2,5})(?::(\d{2,5}))?(?:/(?:tcp|udp))?["\']?\s*$'
)

# Estado global de cache em memória (TTL: 30 segundos)
_CACHE: Dict[str, Any] = {
    "data": None,
    "timestamp": 0.0,
}


def invalidate_cache() -> None:
    """Invalida o cache em memória forçando releitura na próxima requisição."""
    global _CACHE
    _CACHE["data"] = None
    _CACHE["timestamp"] = 0.0


def parse_yaml_frontmatter(content: str) -> Dict[str, Any]:
    """
    Parser determinístico de Frontmatter YAML para a biblioteca padrão do Python.
    Lê atributos escalares e listas entre os delimitadores '---' sem requerer PyYAML.
    """
    if not content or not content.startswith("---"):
        return {}

    lines = content.splitlines()
    if len(lines) < 2 or lines[0].strip() != "---":
        return {}

    # Localiza o delimitador de fechamento
    end_idx = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx == -1:
        return {}

    frontmatter_lines = lines[1:end_idx]
    data: Dict[str, Any] = {
        "status": "Desconhecido",
        "servicos_ativos": [],
        "tags": [],
    }

    current_list_key: Optional[str] = None

    for raw_line in frontmatter_lines:
        # Remove comentários inline pós-hashtag se houver (mas protege dentro de aspas simples/duplas)
        line = raw_line
        if "#" in line:
            parts = line.split("#", 1)
            # Se não estiver entre aspas, corta
            if parts[0].count('"') % 2 == 0 and parts[0].count("'") % 2 == 0:
                line = parts[0]
        
        line = line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        # Verifica se é item de lista ('- item' ou '  - item')
        if stripped.startswith("- ") and current_list_key:
            item_val = stripped[2:].strip()
            # Remove aspas ao redor se houver
            if (item_val.startswith('"') and item_val.endswith('"')) or (item_val.startswith("'") and item_val.endswith("'")):
                item_val = item_val[1:-1].strip()
            if current_list_key not in data or not isinstance(data[current_list_key], list):
                data[current_list_key] = []
            data[current_list_key].append(item_val)
            continue

        # Verifica se é uma chave escalar ou início de bloco ('chave: valor' ou 'chave:')
        if ":" in stripped:
            key_part, val_part = stripped.split(":", 1)
            key = key_part.strip()
            val = val_part.strip()

            # Se for array inline no formato [item1, item2]
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                items = []
                if inner:
                    for raw_item in inner.split(","):
                        item = raw_item.strip()
                        if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                            item = item[1:-1].strip()
                        if item:
                            items.append(item)
                data[key] = items
                current_list_key = None
            elif not val:
                # Início de lista multilinha
                data[key] = []
                current_list_key = key
            else:
                # Valor escalar
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1].strip()
                data[key] = val
                current_list_key = None

    return data


def extract_ports_from_services(services: List[str]) -> List[int]:
    """Extrai números de porta de uma lista de strings livres de serviços."""
    ports: set = set()
    for svc in services:
        if not svc or not isinstance(svc, str):
            continue
        matches = VAULT_PORT_REGEX.findall(svc)
        for m in matches:
            try:
                ports.add(int(m))
            except ValueError:
                pass
    return sorted(list(ports))


def extract_compose_ports_from_content(
    content: str, source_id: str, source_label: str = ""
) -> List[Dict[str, Any]]:
    """
    Varre o conteúdo de um docker-compose.yml e extrai portas expostas
    utilizando parsing determinístico de linhas de mapeamento de portas.
    """
    results: List[Dict[str, Any]] = []
    in_ports_block = False
    current_service = "service"

    for line in content.splitlines():
        # Heurística de indentação para nome de serviço (2 espaços)
        service_match = re.match(r'^  ([a-zA-Z0-9_-]+):\s*$', line)
        if service_match:
            current_service = service_match.group(1)
            in_ports_block = False
            continue

        # Identifica bloco 'ports:'
        if re.match(r'^\s*ports:\s*$', line):
            in_ports_block = True
            continue

        # Se mudou de seção no mesmo nível de indentação
        if in_ports_block and re.match(r'^\s{2,4}[a-zA-Z0-9_-]+:\s*$', line) and not line.strip().startswith("-"):
            in_ports_block = False
            continue

        # Se estamos dentro de um bloco ports ou em linha de lista
        if in_ports_block and line.strip().startswith("-"):
            clean = line.strip()[1:].strip().strip('"').strip("'")
            # Remove sufixo de protocolo /tcp ou /udp
            if "/" in clean:
                clean = clean.split("/", 1)[0].strip()

            parts = clean.split(":")
            host_port: Optional[int] = None
            container_port: Optional[int] = None

            try:
                if len(parts) == 1 and parts[0].isdigit():
                    host_port = int(parts[0])
                    container_port = int(parts[0])
                elif len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    host_port = int(parts[0])
                    container_port = int(parts[1])
                elif len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                    # Formato IP:host_port:container_port (ex: 127.0.0.1:9090:9090)
                    host_port = int(parts[1])
                    container_port = int(parts[2])
            except ValueError:
                pass

            if host_port is not None and container_port is not None:
                label = source_label or source_id
                results.append({
                    "host_port": host_port,
                    "container_port": container_port,
                    "protocol": "tcp",
                    "source_type": "project_compose",
                    "source_id": source_id,
                    "source_label": f"{label} ({current_service})",
                })

    return results


def detect_port_collisions(
    vault_resources: List[Dict[str, Any]],
    project_ports: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Cruza as portas declaradas nos recursos do vault com as portas dos projetos locais,
    gerando a matriz consolidada de alocação de portas e detectando colisões.
    """
    bindings_by_port: Dict[int, List[Dict[str, Any]]] = {}

    # 1. Registra portas do Vault
    for res in vault_resources:
        res_label = res.get("recurso") or res.get("id") or "Host Desconhecido"
        for p in res.get("ports", []):
            entry = {
                "host_port": p,
                "container_port": p,
                "protocol": "tcp",
                "source_type": "infra_vault",
                "source_id": res.get("id", "vault"),
                "source_label": f"{res_label}",
            }
            bindings_by_port.setdefault(p, []).append(entry)

    # 2. Registra portas dos projetos locais
    for pp in project_ports:
        p = pp["host_port"]
        bindings_by_port.setdefault(p, []).append(pp)

    # 3. Consolidação e detecção de colisões
    all_bindings: List[Dict[str, Any]] = []
    collisions: List[Dict[str, Any]] = []

    for port, sources in sorted(bindings_by_port.items()):
        is_collision = len(sources) > 1
        conflicting_names = [s["source_label"] for s in sources]
        
        entry = {
            "host_port": port,
            "sources": sources,
            "source_labels": conflicting_names,
            "collision_count": len(sources),
            "is_collision": is_collision,
            "conflicting_sources": conflicting_names if is_collision else [],
        }
        all_bindings.append(entry)
        if is_collision:
            collisions.append(entry)

    return {
        "bindings": all_bindings,
        "collision_count": len(collisions),
        "collisions": collisions,
    }


def resolve_vault_path(custom_path: Optional[str] = None) -> Tuple[Optional[Path], str]:
    """
    Resolve o caminho base do vault de infraestrutura seguindo a cascata de prioridades:
    1. Parâmetro explícito / custom_path
    2. Variável de ambiente AXION_VAULT_PATH
    3. Persistência em data/config.json
    4. Caminho padrão Windows (G:/Meu Drive/main_vault/02_Recursos_e_Infra)
    5. Montagem no container Docker (/vault)
    6. Formato WSL (/mnt/g/Meu Drive/...)
    """
    candidates = []

    if custom_path and custom_path.strip():
        candidates.append(custom_path.strip())

    env_path = os.environ.get("AXION_VAULT_PATH")
    if env_path and env_path.strip():
        candidates.append(env_path.strip())

    # Lê config.json se existir
    data_dir = Path(__file__).resolve().parent.parent / "data"
    cfg_file = data_dir / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                if "vault_path" in cfg and cfg["vault_path"]:
                    candidates.append(cfg["vault_path"].strip())
        except Exception:
            pass

    # Padrões do ecossistema
    local_vault = data_dir / "vault"
    if local_vault.exists() and local_vault.is_dir():
        candidates.append(str(local_vault))

    candidates.extend([
        "G:\\Meu Drive\\main_vault\\02_Recursos_e_Infra",
        "G:/Meu Drive/main_vault/02_Recursos_e_Infra",
        "/app/data/vault",
        "/vault",
        "/mnt/g/Meu Drive/main_vault/02_Recursos_e_Infra",
    ])

    for raw in candidates:
        try:
            resolved = resolve_cross_platform_path(raw)
            if resolved and resolved.exists() and resolved.is_dir():
                return resolved, str(resolved)
        except Exception:
            pass

    return None, "not_configured"


def scan_infrastructure_directory(
    vault_dir: Path,
    force_refresh: bool = False,
    projects: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Varre os arquivos .md do diretório de infraestrutura, extrai metadados,
    inspeciona manifestos de projetos e gera a matriz consolidada de portas e métricas.
    """
    global _CACHE

    now = time.time()
    if not force_refresh and _CACHE["data"] is not None and (now - _CACHE["timestamp"] < 30.0):
        return _CACHE["data"]

    resources: List[Dict[str, Any]] = []
    metrics = {
        "total_hosts": 0,
        "by_type": {},
        "by_os": {},
        "by_entity": {},
    }

    ignored_files = {"readme.md", "home_lab_specifications.md", "oracle.md"}

    try:
        for item in sorted(vault_dir.iterdir()):
            if item.is_file() and item.suffix.lower() == ".md" and not item.name.startswith("."):
                if item.name.lower() in ignored_files:
                    continue

                try:
                    content = item.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                frontmatter = parse_yaml_frontmatter(content)
                if not frontmatter:
                    continue

                # Garante identificadores seguros
                res_id = item.stem.lower().replace("_", "-").replace(" ", "-")
                recurso = frontmatter.get("recurso") or item.stem.replace("_", " ")
                tipo = frontmatter.get("tipo") or "Não informado"
                entidade = frontmatter.get("entidade") or "Geral"
                host = str(frontmatter.get("host") or "")
                os_name = frontmatter.get("os") or "Não informado"
                status = frontmatter.get("status") or "Ativo"
                servicos = frontmatter.get("servicos_ativos") or []
                if isinstance(servicos, str):
                    servicos = [servicos]

                tags = frontmatter.get("tags") or []
                if isinstance(tags, str):
                    tags = [tags]

                ports = extract_ports_from_services(servicos)

                # Atualiza contadores de métricas
                metrics["total_hosts"] += 1
                metrics["by_type"][tipo] = metrics["by_type"].get(tipo, 0) + 1
                metrics["by_os"][os_name] = metrics["by_os"].get(os_name, 0) + 1
                metrics["by_entity"][entidade] = metrics["by_entity"].get(entidade, 0) + 1

                try:
                    mtime_iso = time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(item.stat().st_mtime)
                    )
                except Exception:
                    mtime_iso = ""

                resource_entry = {
                    "id": res_id,
                    "recurso": recurso,
                    "tipo": tipo,
                    "entidade": entidade,
                    "host": host,
                    "os": os_name,
                    "hardware": frontmatter.get("hardware", ""),
                    "status": status,
                    "servicos_ativos": servicos,
                    "ports": ports,
                    "tags": tags,
                    "filepath": str(item.resolve()),
                    "updated_at": mtime_iso,
                }
                resources.append(resource_entry)

    except Exception:
        pass

    # Inspeciona manifestos dos projetos cadastrados
    project_ports: List[Dict[str, Any]] = []
    if projects:
        for proj in projects:
            p_path_str = proj.get("path") or proj.get("resolved_path") or ""
            if not p_path_str:
                continue
            try:
                proj_path = resolve_cross_platform_path(p_path_str)
                if proj_path and proj_path.exists() and proj_path.is_dir():
                    compose_file = proj_path / "docker-compose.yml"
                    if not compose_file.exists():
                        compose_file = proj_path / "docker-compose.yaml"

                    if compose_file.exists():
                        content = compose_file.read_text(encoding="utf-8", errors="replace")
                        extracted = extract_compose_ports_from_content(
                            content,
                            source_id=proj.get("id", proj_path.name),
                            source_label=proj.get("name", proj_path.name),
                        )
                        project_ports.extend(extracted)
            except Exception:
                pass

    ports_data = detect_port_collisions(resources, project_ports)

    result_payload = {
        "vault_status": "ok",
        "vault_path": str(vault_dir),
        "resources": resources,
        "ports": ports_data,
        "metrics": metrics,
    }

    _CACHE["data"] = result_payload
    _CACHE["timestamp"] = now
    return result_payload


def get_infrastructure_catalog(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Ponto de entrada central para o backend: resolve o vault, obtém projetos e
    retorna o catálogo consolidado.
    """
    vault_path, status_str = resolve_vault_path()
    if not vault_path:
        return {
            "vault_status": "not_configured",
            "vault_path": "",
            "resources": [],
            "ports": {"bindings": [], "collision_count": 0, "collisions": []},
            "metrics": {"total_hosts": 0, "by_type": {}, "by_os": {}, "by_entity": {}},
        }

    # Carrega projetos de data/projects.json
    projects_file = Path(__file__).resolve().parent.parent / "data" / "projects.json"
    projects: List[Dict[str, Any]] = []
    if projects_file.exists():
        try:
            with open(projects_file, "r", encoding="utf-8") as f:
                projects = json.load(f)
        except Exception:
            projects = []

    return scan_infrastructure_directory(vault_path, force_refresh=force_refresh, projects=projects)
