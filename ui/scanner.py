#!/usr/bin/env python3
"""
scanner.py — Motor de inspeção passiva, normalização de caminhos e telemetria Git para o Nexus Cockpit.
Executa 100% na biblioteca padrão do Python.
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
    Path("/proc").resolve(),
    Path("/sys").resolve(),
    (Path.home() / ".ssh").resolve(),
}

FORBIDDEN_PATH_SEGMENTS = {
    "chaves_ssh",
    ".obsidian",
    ".git",
    ".agents",
    ".vscode",
    ".ssh",
}


def sanitize_input_path(raw_path: str) -> str:
    """Higieniza caminhos informados pelo usuário, removendo aspas e escapes de aspas."""
    if not raw_path:
        return ""
    s = raw_path.strip()
    s = re.sub(r'^(?:\\?["\'])+|(?:\\?["\'])+$', "", s).strip()
    if s.endswith("\\") and not s.endswith(":\\"):
        s = s.rstrip("\\")
    return s.strip()


def is_mount_populated(mount_dir: Path) -> bool:
    """Retorna True somente se o ponto de montagem existir, for diretório e contiver ao menos 1 entrada."""
    try:
        if not mount_dir.exists() or not mount_dir.is_dir():
            return False
        return any(mount_dir.iterdir())
    except Exception:
        return False


def is_non_path_repo_reference(raw_ref: str) -> bool:
    """
    Identifica referências de repositorio_local que não são caminhos de diretório
    (ex.: vazio, 'Incorporado em ...', 'Notebook Dell (192.168.15.176)').
    """
    clean = sanitize_input_path(raw_ref)
    if not clean:
        return True
    low = clean.lower()
    if low.startswith("incorporado em") or low.startswith("incorporado ao"):
        return True
    if re.match(r"^[a-zA-Z]:[\\/]", clean) or clean.startswith("/"):
        return False
    if "/" in clean or "\\" in clean:
        return False
    # Strings descritivas com espaços/parênteses como "Notebook Dell (192.168.15.176)"
    if " " in clean or "(" in clean or ")" in clean:
        return True
    return False


def normalize_repo_key(raw_path: str) -> str:
    """
    Gera uma chave canônica multiplataforma para reconciliação determinística N:1
    entre fichas de 01_Projetos e entradas de data/projects.json.
    """
    clean = sanitize_input_path(raw_path).replace("\\", "/").strip()
    if not clean or is_non_path_repo_reference(clean):
        return ""

    low = clean.lower().rstrip("/")

    # Alias do próprio cockpit
    if low in ("/app", "c:/docker/nexus-cockpit", "c:/docker/axion-cockpit", "/projects/nexus-cockpit", "/projects/axion-cockpit", "nexus-cockpit", "axion-cockpit"):
        return "docker/nexus-cockpit"

    # Caminhos no Google Drive (01 Projetos)
    m_drive = re.match(r"^(?:[a-z]:/meu drive/01 projetos/|/mnt/[a-z]/meu drive/01 projetos/|/drive_projects/)(.+)$", low)
    if m_drive:
        return f"drive_projects/{m_drive.group(1).strip('/')}"

    # Caminhos em C:\Docker ou /projects
    m_docker = re.match(r"^(?:c:/docker/|/mnt/c/docker/|/projects/)(.+)$", low)
    if m_docker:
        sub = m_docker.group(1).strip("/")
        if sub == "axion-cockpit":
            sub = "nexus-cockpit"
        return f"docker/{sub}"

    # Caminhos relativos simples de data/projects.json (ex.: "igreja-crist-evan", "projects/Project_Siaebr")
    if not re.match(r"^[a-z]:/", low) and not low.startswith("/"):
        return f"docker/{low.strip('/')}"

    return low


def resolve_cross_platform_path(raw_path: str) -> Path:
    """
    Resolve caminhos de forma transparente entre Windows, Docker (volumes /projects e /drive_projects) e Linux/WSL.
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

    # 2. Se estiver rodando no Linux / Container Docker e receber caminho Windows
    if os.name != "nt":
        clean_no_drive = re.sub(r"^[a-zA-Z]:[\\/]*", "", clean).lstrip("/")
        parts = [p for p in clean_no_drive.split("/") if p]

        # Prioridade A0: Volume de projetos do Google Drive (/drive_projects)
        drive_projects_env = os.environ.get("DRIVE_PROJECTS_DIR", "/drive_projects")
        drive_projects_dir = Path(drive_projects_env)
        if re.match(r"^[gG]:/meu drive/01 projetos(?:/|$)", clean, re.IGNORECASE):
            rel_after = re.sub(r"^[gG]:/meu drive/01 projetos/?", "", clean, flags=re.IGNORECASE).strip("/")
            if is_mount_populated(drive_projects_dir):
                return (drive_projects_dir / rel_after).resolve() if rel_after else drive_projects_dir.resolve()
            return drive_projects_dir / rel_after if rel_after else drive_projects_dir

        # Prioridade A: Volume montado no Docker (/projects)
        projects_dir = Path(os.environ.get("PROJECTS_CONTAINER_DIR", "/projects"))
        if projects_dir.exists() and projects_dir.is_dir():
            for i in range(len(parts)):
                candidate = projects_dir.joinpath(*parts[i:])
                if candidate.exists():
                    return candidate.resolve()

            candidate_rel = projects_dir / clean.lstrip("/")
            if candidate_rel.exists():
                return candidate_rel.resolve()

        # Prioridade B: Diretório da própria aplicação dentro do container (/app)
        app_dir = Path("/app")
        if app_dir.exists() and parts:
            last_part = parts[-1].lower()
            if last_part in ("app", "nexus-cockpit", "axion-cockpit") or app_dir.name.lower() == last_part:
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


def has_forbidden_segments(raw_or_resolved: str) -> bool:
    """Detecta segmentos sensíveis (.agents, chaves_ssh, .obsidian, .git, .env*, etc.)."""
    norm = raw_or_resolved.replace("\\", "/")
    for seg in norm.split("/"):
        s = seg.strip()
        if not s or s in (".", ".."):
            continue
        low = s.lower()
        if low in FORBIDDEN_PATH_SEGMENTS or low.startswith(".env"):
            return True
        if s.startswith(".") and low not in (".well-known",):
            return True
    return False


def is_valid_project_path(
    raw_path: str,
    allowed_roots: Optional[List[Path]] = None,
) -> Tuple[bool, Optional[Path], Optional[str]]:
    """
    Valida e normaliza o caminho de um projeto ou diretório configurado,
    prevenindo path traversal, symlinks para áreas sensíveis e acesso a pastas restritas.
    """
    if not raw_path or not raw_path.strip():
        return False, None, "Caminho do projeto não pode ser vazio."

    clean_in = sanitize_input_path(raw_path)
    if has_forbidden_segments(clean_in):
        return False, None, "Acesso a diretório oculto ou sensível restrito."

    try:
        resolved = resolve_cross_platform_path(clean_in)
    except Exception as e:
        return False, None, f"Caminho inválido: {str(e)}"

    if not resolved.exists():
        return False, resolved, "Diretório não encontrado no sistema de arquivos local."

    if not resolved.is_dir():
        return False, resolved, "O caminho informado não é um diretório."

    try:
        real_resolved = resolved.resolve()
    except Exception:
        real_resolved = resolved

    if has_forbidden_segments(str(real_resolved)):
        return False, real_resolved, "Acesso a diretório oculto ou sensível restrito."

    for danger in DANGEROUS_SYSTEM_PATHS:
        try:
            if real_resolved == danger or resolved == danger:
                return False, real_resolved, "Acesso a diretório de sistema restrito."
        except Exception:
            pass

    # Bloqueia apontar para dentro de subpastas restritas do main_vault (fora das 4 pastas permitidas)
    vault_root_candidates: List[Path] = []
    for env_key in ("NEXUS_VAULT_ROOT", "NEXUS_VAULT_HOST_DIR"):
        val = os.environ.get(env_key)
        if val:
            try:
                p = Path(val).resolve()
                if p.exists():
                    vault_root_candidates.append(p)
            except Exception:
                pass
    if Path("/main_vault").exists():
        try:
            vault_root_candidates.append(Path("/main_vault").resolve())
        except Exception:
            pass

    allowed_vault_Subdirs = {"01_projetos", "02_recursos_e_infra", "04_arquitetura_adrs", "05_areas"}
    for vroot in vault_root_candidates:
        try:
            if real_resolved == vroot or real_resolved.is_relative_to(vroot):
                rel_parts = real_resolved.relative_to(vroot).parts
                if rel_parts and rel_parts[0].lower() not in allowed_vault_Subdirs:
                    return False, real_resolved, "Subdiretório do main_vault fora da allowlist."
        except Exception:
            pass

    if allowed_roots:
        in_allowed = False
        for root in allowed_roots:
            try:
                r_res = root.resolve()
                if real_resolved == r_res or real_resolved.is_relative_to(r_res):
                    in_allowed = True
                    break
            except Exception:
                pass
        if not in_allowed:
            return False, real_resolved, "Caminho fora das raízes permitidas."

    return True, real_resolved, None


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

    clean_sub = sanitize_input_path(subpath).replace("\\", "/").lstrip("/")
    target_dir = (base_dir / clean_sub).resolve()

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
        ".git", ".github", ".obsidian", ".vscode", ".agents", "chaves_ssh",
        "data", "backups", "node_modules", "__pycache__", "bin", "boot", "dev",
        "etc", "home", "lib", "lib64", "media", "mnt", "opt", "proc", "root",
        "run", "sbin", "srv", "sys", "tmp", "usr", "var",
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

    projects_dir = Path("/projects")
    if projects_dir.exists() and projects_dir.is_dir():
        search_dirs.append(projects_dir)
    else:
        repo_parent = Path(__file__).resolve().parent.parent.parent
        if repo_parent.exists() and repo_parent.is_dir() and repo_parent != Path("/"):
            search_dirs.append(repo_parent)

    ignored_names = {
        ".git", ".github", ".obsidian", ".vscode", ".agents", "chaves_ssh",
        "data", "backups", "node_modules", "__pycache__", "bin", "boot", "dev",
        "etc", "home", "lib", "lib64", "media", "mnt", "opt", "proc", "root",
        "run", "sbin", "srv", "sys", "tmp", "usr", "var",
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
            "last_commit_iso": "",
        }

    info: Dict[str, Any] = {
        "is_repo": True,
        "branch": "unknown",
        "is_dirty": False,
        "uncommitted_count": 0,
        "last_commit": "",
        "last_commit_iso": "",
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
            ["git", "-C", str(project_path), "log", "-1", "--format=%h - %s (%cr)%n%cI"],
            capture_output=True,
            text=True,
            timeout=1.5,
        )
        if res_c.returncode == 0 and res_c.stdout.strip():
            out_lines = [l.strip() for l in res_c.stdout.splitlines() if l.strip()]
            if out_lines:
                info["last_commit"] = out_lines[0]
            if len(out_lines) >= 2:
                info["last_commit_iso"] = out_lines[1]

    except Exception:
        pass

    return info


def get_env_indicators(project_path: Path) -> Dict[str, bool]:
    """Identifica manifestos presentes no projeto."""
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
            "code": clean_code,
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

    workflows = [b for b in all_mermaid_blocks if b["type"] in ("flowchart", "sequenceDiagram", "stateDiagram")]
    database = [b for b in all_mermaid_blocks if b["type"] == "erDiagram"]
    others = [b for b in all_mermaid_blocks if b not in workflows and b not in database]

    primary_text = ""
    for pref in [
        "ARCHITECTURE.md",
        "docs/ARCHITECTURE.md",
        "TECHSPEC.md",
        "docs/TECHSPEC.md",
        "TECSPEC.md",
        "docs/TECSPEC.md",
        "README.md",
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
