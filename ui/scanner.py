#!/usr/bin/env python3
"""
scanner.py — Motor de inspeção passiva e extração de documentação em disco para o Axion Cockpit.
Lê repositórios locais sob demanda sem modificar arquivos nem manter caches redundantes.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DANGEROUS_SYSTEM_PATHS = {
    Path("C:\\Windows").resolve(),
    Path("C:\\").resolve(),
    Path("/").resolve(),
    Path("/etc").resolve(),
    Path("/var").resolve(),
    Path("/root").resolve(),
    Path("/boot").resolve(),
    Path.home() / ".ssh",
}


def sanitize_input_path(raw_path: str) -> str:
    """Higieniza caminhos informados pelo usuário, removendo aspas e escapes de aspas."""
    if not raw_path:
        return ""
    s = raw_path.strip()
    # Remove aspas externas (duplas ou simples) mesmo que venham escapadas (ex: \" no início/fim)
    s = re.sub(r'^(?:\\?["\'])+|(?:\\?["\'])+$', '', s).strip()
    # Se sobrou contra-barra solta no final devido a escape de aspa Windows
    if s.endswith('\\') and not s.endswith(':\\'):
        s = s.rstrip('\\')
    return s.strip()


def resolve_cross_platform_path(raw_path: str) -> Path:
    """
    Resolve caminhos de forma transparente entre Windows, Docker (volume /projects) e Linux/WSL.
    Suporta remoção automática de aspas, mapeamento do volume Docker e caminhos relativos.
    """
    clean_str = sanitize_input_path(raw_path)
    if not clean_str:
        return Path("")

    clean = clean_str.replace("\\", "/")

    # 1. Se o caminho já existir diretamente no sistema atual
    direct_path = Path(clean)
    try:
        if direct_path.exists():
            return direct_path.resolve()
    except Exception:
        pass

    # 2. Se estiver rodando no Linux / Container Docker e receber caminho Windows (ex: C:/Docker/...)
    if os.name != "nt":
        # Remove letra de unidade Windows (ex: 'C:' ou 'c:/')
        clean_no_drive = re.sub(r"^[a-zA-Z]:[\\/]*", "", clean).lstrip("/")
        parts = [p for p in clean_no_drive.split("/") if p]

        # Prioridade A: Volume montado no Docker (/projects)
        projects_dir = Path("/projects")
        if projects_dir.exists() and projects_dir.is_dir():
            # Tenta encontrar correspondência de subcaminho da direita para a esquerda:
            # Exemplo: 'C:/Docker/axion-cockpit' -> testa '/projects/Docker/axion-cockpit' e depois '/projects/axion-cockpit'
            for i in range(len(parts)):
                candidate = projects_dir.joinpath(*parts[i:])
                if candidate.exists():
                    return candidate.resolve()

            # Se for caminho relativo simples dentro de /projects
            candidate_rel = projects_dir / clean.lstrip("/")
            if candidate_rel.exists():
                return candidate_rel.resolve()

        # Prioridade B: Diretório da própria aplicação dentro do container (/app)
        app_dir = Path("/app")
        if app_dir.exists() and parts:
            last_part = parts[-1].lower()
            if last_part in ("app", "axion-cockpit") or app_dir.name.lower() == last_part:
                return app_dir.resolve()

        # Prioridade C: Ambiente WSL com /mnt/{drive}
        if len(clean) >= 2 and clean[1] == ":":
            drive = clean[0].lower()
            wsl_candidate = Path(f"/mnt/{drive}/{clean_no_drive}").resolve()
            if wsl_candidate.exists():
                return wsl_candidate
            if not projects_dir.exists():
                return wsl_candidate

        # Prioridade D: Caminho relativo no Linux
        if not clean.startswith("/"):
            if projects_dir.exists() and (projects_dir / clean).exists():
                return (projects_dir / clean).resolve()
            return (Path.cwd() / clean).resolve()

    # 3. Se estiver rodando no Windows e receber caminho no formato WSL (/mnt/c/...)
    if os.name == "nt" and clean.startswith("/mnt/"):
        parts = clean.split("/", 3)
        if len(parts) >= 3:
            drive = parts[2].upper()
            sub = parts[3] if len(parts) > 3 else ""
            return Path(f"{drive}:/{sub}").resolve()

    return Path(clean).resolve()


def browse_directory(subpath: str = "") -> Dict[str, Any]:
    """
    Navega de forma segura pelas pastas disponíveis em /projects (no Docker)
    ou no diretório pai dos repositórios (no host).
    """
    projects_dir = Path("/projects")
    if projects_dir.exists() and projects_dir.is_dir():
        base_dir = projects_dir.resolve()
        display_root = "C:\\Docker" if os.name != "nt" else str(base_dir)
    else:
        base_dir = Path(__file__).resolve().parent.parent.parent.resolve()
        display_root = str(base_dir)

    # Limpa o subpath requisitado
    clean_sub = sanitize_input_path(subpath).replace("\\", "/").lstrip("/")
    target_dir = (base_dir / clean_sub).resolve()

    # Prevenção rigorosa de path traversal
    try:
        if not target_dir.is_relative_to(base_dir):
            target_dir = base_dir
            clean_sub = ""
    except AttributeError:
        if not str(target_dir).startswith(str(base_dir)):
            target_dir = base_dir
            clean_sub = ""

    if not target_dir.exists() or not target_dir.is_dir():
        target_dir = base_dir
        clean_sub = ""

    ignored_names = {
        ".git", ".github", ".obsidian", ".vscode", "data", "backups", "node_modules",
        "__pycache__", "bin", "boot", "dev", "etc", "home", "lib", "lib64", "media",
        "mnt", "opt", "proc", "root", "run", "sbin", "srv", "sys", "tmp", "usr", "var"
    }

    folders = []
    try:
        for item in sorted(target_dir.iterdir(), key=lambda x: x.name.lower()):
            if item.is_dir() and not item.name.startswith(".") and item.name.lower() not in ignored_names:
                has_sub = False
                try:
                    for sub in item.iterdir():
                        if sub.is_dir() and not sub.name.startswith(".") and sub.name.lower() not in ignored_names:
                            has_sub = True
                            break
                except Exception:
                    pass

                rel_to_base = item.relative_to(base_dir).as_posix()
                folders.append({
                    "name": item.name,
                    "rel_path": rel_to_base,
                    "host_path": f"{display_root}\\{rel_to_base.replace('/', chr(92))}",
                    "has_subfolders": has_sub,
                })
    except Exception:
        pass

    # Calcula caminho pai para permitir "Subir Nível"
    parent_rel = None
    if target_dir != base_dir:
        parent_rel = target_dir.parent.relative_to(base_dir).as_posix()
        if parent_rel == ".":
            parent_rel = ""

    current_rel = target_dir.relative_to(base_dir).as_posix()
    if current_rel == ".":
        current_rel = ""

    current_display = display_root
    if current_rel:
        current_display = f"{display_root}\\{current_rel.replace('/', chr(92))}"

    return {
        "current_rel": current_rel,
        "current_display": current_display,
        "parent_rel": parent_rel,
        "is_root": target_dir == base_dir,
        "folders": folders,
    }


def discover_local_projects() -> List[Dict[str, str]]:
    """
    Descobre diretórios de projetos candidatos montados em /projects ou pastas vizinhas.
    """
    candidates: List[Dict[str, str]] = []
    search_dirs: List[Path] = []

    # Container Docker com volume montado
    projects_dir = Path("/projects")
    if projects_dir.exists() and projects_dir.is_dir():
        search_dirs.append(projects_dir)
    else:
        # Diretório pai do repositório se estiver rodando no host nativo (fora de Docker)
        repo_parent = Path(__file__).resolve().parent.parent.parent
        if repo_parent.exists() and repo_parent.is_dir() and repo_parent != Path("/"):
            search_dirs.append(repo_parent)

    ignored_names = {
        ".git", ".github", ".obsidian", ".vscode", "data", "backups", "node_modules",
        "__pycache__", "bin", "boot", "dev", "etc", "home", "lib", "lib64", "media",
        "mnt", "opt", "proc", "root", "run", "sbin", "srv", "sys", "tmp", "usr", "var"
    }

    seen_names = set()
    for base_dir in search_dirs:
        try:
            for item in sorted(base_dir.iterdir()):
                if item.is_dir() and not item.name.startswith(".") and item.name.lower() not in ignored_names:
                    if item.name not in seen_names:
                        seen_names.add(item.name)
                        candidates.append({
                            "name": item.name,
                            "path": item.name,
                            "full_path": str(item.resolve()),
                        })
        except Exception:
            pass

    return candidates


def is_valid_project_path(raw_path: str) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Valida e normaliza o caminho de um projeto local, prevenindo path traversal
    e protegendo diretórios críticos do sistema operacional.
    """
    if not raw_path or not raw_path.strip():
        return False, None, "Caminho do projeto não pode ser vazio."

    try:
        resolved = resolve_cross_platform_path(raw_path)
    except Exception as e:
        return False, None, f"Caminho inválido: {str(e)}"

    if not resolved.exists():
        return False, resolved, "Diretório não encontrado no sistema de arquivos local."

    if not resolved.is_dir():
        return False, resolved, "O caminho informado não é um diretório."

    # Verifica se é uma pasta de sistema perigosa
    for danger in DANGEROUS_SYSTEM_PATHS:
        try:
            if resolved == danger or resolved.resolve() == danger:
                return False, resolved, "Acesso a diretório de sistema restrito."
        except Exception:
            pass

    return True, resolved, None


def get_git_telemetry(project_path: Path) -> Dict[str, Any]:
    """Coleta telemetria do repositório Git local via chamadas rápidas a 'git'."""
    git_dir = project_path / ".git"
    if not git_dir.exists():
        return {
            "is_repo": False,
            "branch": "",
            "is_dirty": False,
            "uncommitted_count": 0,
            "last_commit": "",
        }

    info: Dict[str, Any] = {
        "is_repo": True,
        "branch": "unknown",
        "is_dirty": False,
        "uncommitted_count": 0,
        "last_commit": "",
    }

    try:
        res_b = subprocess.run(
            ["git", "-C", str(project_path), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res_b.returncode == 0 and res_b.stdout.strip():
            info["branch"] = res_b.stdout.strip()

        res_s = subprocess.run(
            ["git", "-C", str(project_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res_s.returncode == 0:
            lines = [l for l in res_s.stdout.splitlines() if l.strip()]
            info["uncommitted_count"] = len(lines)
            info["is_dirty"] = len(lines) > 0

        res_c = subprocess.run(
            ["git", "-C", str(project_path), "log", "-1", "--format=%h - %s (%cr)"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res_c.returncode == 0 and res_c.stdout.strip():
            info["last_commit"] = res_c.stdout.strip()

    except Exception:
        pass

    return info


def get_env_indicators(project_path: Path) -> Dict[str, bool]:
    """Identifica manifestos e ecossistemas presentes no projeto."""
    return {
        "has_pyproject": (project_path / "pyproject.toml").exists(),
        "has_package_json": (project_path / "package.json").exists(),
        "has_dockerfile": (project_path / "Dockerfile").exists(),
        "has_compose": (project_path / "docker-compose.yml").exists() or (project_path / "docker-compose.yaml").exists(),
        "has_prisma": (project_path / "prisma" / "schema.prisma").exists() or (project_path / "schema.prisma").exists(),
    }


def extract_mermaid_blocks(content: str) -> List[Dict[str, str]]:
    """Extrai todos os blocos de código ```mermaid de um documento Markdown."""
    pattern = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
    matches = pattern.findall(content)
    results = []
    for code in matches:
        clean_code = code.strip()
        first_line = clean_code.splitlines()[0].strip().lower() if clean_code else ""
        diagram_type = "unknown"
        if "flowchart" in first_line or "graph" in first_line:
            diagram_type = "flowchart"
        elif "erdiagram" in first_line:
            diagram_type = "erDiagram"
        elif "sequencediagram" in first_line:
            diagram_type = "sequenceDiagram"
        elif "statediagram" in first_line:
            diagram_type = "stateDiagram"

        results.append({
            "type": diagram_type,
            "code": clean_code
        })
    return results


def scan_project_docs(project_path: Path) -> Dict[str, Any]:
    """
    Varre e lê sob demanda os arquivos documentais de um projeto,
    extraindo blocos Mermaid e consolidando seções em tempo real.
    """
    candidate_relative_paths = [
        "ARCHITECTURE.md",
        "docs/ARCHITECTURE.md",
        "TECHSPEC.md",
        "docs/TECHSPEC.md",
        "TECSPEC.md",
        "docs/TECSPEC.md",
        "WORKFLOWS.md",
        "docs/WORKFLOWS.md",
        "DATABASE.md",
        "docs/DATABASE.md",
        "SCHEMA.md",
        "docs/SCHEMA.md",
        "README.md",
    ]

    # Também descobre dinamicamente arquivos .md adicionais na pasta docs/
    docs_dir = project_path / "docs"
    if docs_dir.exists() and docs_dir.is_dir():
        for f in sorted(docs_dir.glob("*.md")):
            rel_name = f"docs/{f.name}"
            if rel_name not in candidate_relative_paths:
                candidate_relative_paths.append(rel_name)

    files_found: List[Dict[str, Any]] = []
    raw_docs: Dict[str, str] = {}
    all_mermaid_blocks: List[Dict[str, str]] = []

    for rel in candidate_relative_paths:
        candidate_file = project_path / rel
        if candidate_file.exists() and candidate_file.is_file():
            try:
                # Limite de leitura para segurança: até 2MB por arquivo
                content = candidate_file.read_text(encoding="utf-8", errors="replace")
                files_found.append({
                    "relative_path": rel,
                    "size_bytes": len(content.encode("utf-8")),
                    "modified_at": os.path.getmtime(str(candidate_file)),
                })
                raw_docs[rel] = content
                blocks = extract_mermaid_blocks(content)
                for b in blocks:
                    b_copy = dict(b)
                    b_copy["source_file"] = rel
                    all_mermaid_blocks.append(b_copy)
            except Exception:
                pass

    # Separa blocos de workflow e banco de dados
    workflows = [b for b in all_mermaid_blocks if b["type"] in ("flowchart", "sequenceDiagram", "stateDiagram")]
    database = [b for b in all_mermaid_blocks if b["type"] == "erDiagram"]
    others = [b for b in all_mermaid_blocks if b not in workflows and b not in database]

    # Identifica texto principal para Visão Geral / Techspec
    primary_text = ""
    for pref in [
        "ARCHITECTURE.md", "docs/ARCHITECTURE.md",
        "TECHSPEC.md", "docs/TECHSPEC.md",
        "TECSPEC.md", "docs/TECSPEC.md",
        "README.md"
    ]:
        if pref in raw_docs:
            primary_text = raw_docs[pref]
            break

    return {
        "files_found": files_found,
        "primary_doc": primary_text,
        "workflows": workflows + others,
        "database": database,
        "raw_docs": raw_docs,
        "git": get_git_telemetry(project_path),
        "env_indicators": get_env_indicators(project_path),
    }
