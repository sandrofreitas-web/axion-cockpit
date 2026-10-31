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


def resolve_cross_platform_path(raw_path: str) -> Path:
    """Resolve caminhos de forma transparente entre Windows e Linux/WSL."""
    clean = raw_path.strip().replace("\\", "/")
    # Se estiver rodando no Linux/WSL e receber caminho no formato Windows (ex: C:/Docker/...)
    if os.name != "nt" and len(clean) >= 2 and clean[1] == ":":
        drive = clean[0].lower()
        sub = clean[2:].lstrip("/")
        return Path(f"/mnt/{drive}/{sub}").resolve()
    # Se estiver rodando no Windows e receber caminho no formato WSL (ex: /mnt/c/Docker/...)
    if os.name == "nt" and clean.startswith("/mnt/"):
        parts = clean.split("/", 3)
        if len(parts) >= 3:
            drive = parts[2].upper()
            sub = parts[3] if len(parts) > 3 else ""
            return Path(f"{drive}:/{sub}").resolve()
    return Path(clean).resolve()


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
        "WORKFLOWS.md",
        "docs/WORKFLOWS.md",
        "DATABASE.md",
        "docs/DATABASE.md",
        "SCHEMA.md",
        "docs/SCHEMA.md",
        "README.md",
    ]

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
    for pref in ["ARCHITECTURE.md", "docs/ARCHITECTURE.md", "TECHSPEC.md", "docs/TECHSPEC.md", "README.md"]:
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
