#!/usr/bin/env python3
"""
Axion Cockpit — Local Management Dashboard Server.
Backend REST API leve para visualização arquitetural e gestão operacional da frota de projetos.
Executa 100% na biblioteca padrão do Python (sem dependências externas de pip).
"""

import argparse
import http.server
import json
import mimetypes
import os
import re
import socketserver
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

# Garante saída UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UI_ROOT = Path(__file__).resolve().parent
LIBRARY_ROOT = UI_ROOT.parent
DATA_DIR = LIBRARY_ROOT / "data"
PROJECTS_FILE = DATA_DIR / "projects.json"
NOTES_BASE_DIR = DATA_DIR / "notes"

# Garante existência dos diretórios de dados
DATA_DIR.mkdir(parents=True, exist_ok=True)
NOTES_BASE_DIR.mkdir(parents=True, exist_ok=True)

if not PROJECTS_FILE.exists():
    PROJECTS_FILE.write_text("[]", encoding="utf-8")

# Adiciona UI_ROOT ao sys.path para importar scanner
sys.path.insert(0, str(UI_ROOT))
import scanner


# ==============================================================================
# Funções Utilitárias de Armazenamento e Notas
# ==============================================================================

def load_projects() -> List[Dict[str, Any]]:
    if not PROJECTS_FILE.exists():
        return []
    try:
        return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_projects(projects: List[Dict[str, Any]]) -> None:
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")


def get_project_by_id(project_id: str) -> Optional[Dict[str, Any]]:
    for p in load_projects():
        if p.get("id") == project_id:
            return p
    return None


def parse_markdown_note(file_path: Path) -> Dict[str, Any]:
    """Lê um arquivo de nota Markdown e extrai frontmatter YAML simples."""
    content = file_path.read_text(encoding="utf-8", errors="replace")
    meta: Dict[str, Any] = {
        "id": file_path.stem,
        "title": file_path.stem,
        "status": "idea",
        "created_at": datetime.fromtimestamp(os.path.getmtime(str(file_path)), timezone.utc).isoformat(),
        "target_files": [],
        "version_target": "",
    }
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            body = parts[2].strip()
            # Parser leve de chave-valor para evitar dependência de PyYAML
            current_list_key = None
            for line in fm_text.splitlines():
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    continue
                if line_str.startswith("- ") and current_list_key:
                    val = line_str[2:].strip().strip("\"'")
                    meta[current_list_key].append(val)
                elif ":" in line_str:
                    k, v = line_str.split(":", 1)
                    k = k.strip()
                    v = v.split("#")[0].strip().strip("\"'")
                    if not v:
                        current_list_key = k
                        meta[k] = []
                    else:
                        current_list_key = None
                        meta[k] = v

    meta["content"] = body
    return meta


def write_markdown_note(file_path: Path, meta: Dict[str, Any], body: str) -> None:
    lines = ["---"]
    lines.append(f"id: {meta.get('id', file_path.stem)}")
    lines.append(f"title: \"{meta.get('title', file_path.stem)}\"")
    lines.append(f"status: {meta.get('status', 'idea')}")
    lines.append(f"created_at: {meta.get('created_at', datetime.now(timezone.utc).isoformat())}")
    lines.append(f"version_target: \"{meta.get('version_target', '')}\"")
    target_files = meta.get("target_files", [])
    if isinstance(target_files, list) and target_files:
        lines.append("target_files:")
        for tf in target_files:
            lines.append(f"  - \"{tf}\"")
    else:
        lines.append("target_files: []")
    lines.append("---")
    lines.append("")
    lines.append(body.strip())
    lines.append("")
    file_path.write_text("\n".join(lines), encoding="utf-8")


# ==============================================================================
# Handler de Requisições HTTP REST
# ==============================================================================

class ProjectOSHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_ROOT), **kwargs)

    def log_message(self, format, *args):
        # Log simplificado
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {self.command} {self.path}\n")

    def send_json(self, data: Any, status: int = 200) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def send_error_json(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message, "status": status}, status=status)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def read_json_body(self) -> Optional[Dict[str, Any]]:
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                return {}
            raw_bytes = self.rfile.read(content_length)
            try:
                raw_data = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                raw_data = raw_bytes.decode("latin-1", errors="replace")
            return json.loads(raw_data)
        except Exception:
            return None

    # --------------------------------------------------------------------------
    # Roteamento GET
    # --------------------------------------------------------------------------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Rota de Status da API
        if path == "/api/status":
            self.send_json({
                "status": "online",
                "app": "Axion Cockpit",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        # Listar Projetos: GET /api/projects
        if path == "/api/projects":
            projects = load_projects()
            enriched = []
            for p in projects:
                p_copy = dict(p)
                valid, resolved_path, _ = scanner.is_valid_project_path(p.get("path", ""))
                p_copy["accessible"] = valid
                if valid and resolved_path:
                    p_copy["git"] = scanner.get_git_telemetry(resolved_path)
                    p_copy["env"] = scanner.get_env_indicators(resolved_path)
                else:
                    p_copy["git"] = {"is_repo": False, "branch": "", "is_dirty": False, "uncommitted_count": 0}
                    p_copy["env"] = {}
                enriched.append(p_copy)
            self.send_json(enriched)
            return

        # Documentos e Diagramas: GET /api/projects/{id}/docs
        m_docs = re.match(r"^/api/projects/([^/]+)/docs$", path)
        if m_docs:
            project_id = m_docs.group(1)
            proj = get_project_by_id(project_id)
            if not proj:
                self.send_error_json("Projeto não encontrado", 404)
                return
            valid, resolved_path, err = scanner.is_valid_project_path(proj.get("path", ""))
            if not valid or not resolved_path:
                self.send_error_json(err or "Caminho do projeto inacessível", 400)
                return
            docs_payload = scanner.scan_project_docs(resolved_path)
            self.send_json(docs_payload)
            return

        # Telemetria Git: GET /api/projects/{id}/git-telemetry
        m_git = re.match(r"^/api/projects/([^/]+)/git-telemetry$", path)
        if m_git:
            project_id = m_git.group(1)
            proj = get_project_by_id(project_id)
            if not proj:
                self.send_error_json("Projeto não encontrado", 404)
                return
            valid, resolved_path, err = scanner.is_valid_project_path(proj.get("path", ""))
            if not valid or not resolved_path:
                self.send_error_json(err or "Caminho inacessível", 400)
                return
            self.send_json(scanner.get_git_telemetry(resolved_path))
            return

        # Notas de Melhoria: GET /api/projects/{id}/notes
        m_notes = re.match(r"^/api/projects/([^/]+)/notes$", path)
        if m_notes:
            project_id = m_notes.group(1)
            proj = get_project_by_id(project_id)
            if not proj:
                self.send_error_json("Projeto não encontrado", 404)
                return
            proj_notes_dir = NOTES_BASE_DIR / project_id
            notes_list = []
            if proj_notes_dir.exists() and proj_notes_dir.is_dir():
                for nf in proj_notes_dir.glob("*.md"):
                    try:
                        notes_list.append(parse_markdown_note(nf))
                    except Exception:
                        pass
            notes_list.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            self.send_json(notes_list)
            return

        # Servir Arquivos Estáticos (index.html, static/*)
        super().do_GET()

    # --------------------------------------------------------------------------
    # Roteamento POST
    # --------------------------------------------------------------------------
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self.read_json_body()
        if body is None:
            self.send_error_json("Corpo da requisição JSON inválido", 400)
            return

        # Registrar Projeto: POST /api/projects
        if path == "/api/projects":
            name = (body.get("name") or "").strip()
            raw_path = (body.get("path") or "").strip()
            tags = body.get("tags", [])
            version = (body.get("version") or "v1.0.0").strip()

            valid, resolved_path, err_msg = scanner.is_valid_project_path(raw_path)
            if not valid or not resolved_path:
                self.send_error_json(err_msg or "Caminho de projeto inválido.", 400)
                return

            if not name:
                name = resolved_path.name

            projects = load_projects()
            # Gera ID seguro
            clean_id = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower()).strip("-")
            project_id = clean_id or "project"
            counter = 1
            existing_ids = {p.get("id") for p in projects}
            while project_id in existing_ids:
                project_id = f"{clean_id}-{counter}"
                counter += 1

            new_proj = {
                "id": project_id,
                "name": name,
                "path": str(resolved_path),
                "current_version": version,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "tags": tags if isinstance(tags, list) else [],
            }
            projects.append(new_proj)
            save_projects(projects)

            # Cria diretório de notas correspondente
            (NOTES_BASE_DIR / project_id).mkdir(parents=True, exist_ok=True)
            self.send_json(new_proj, 201)
            return

        # Criar Nota: POST /api/projects/{id}/notes
        m_add_note = re.match(r"^/api/projects/([^/]+)/notes$", path)
        if m_add_note:
            project_id = m_add_note.group(1)
            proj = get_project_by_id(project_id)
            if not proj:
                self.send_error_json("Projeto não encontrado", 404)
                return

            title = (body.get("title") or "Nova Melhoria").strip()
            status = (body.get("status") or "idea").strip().lower()
            if status not in ("idea", "planned", "in_review", "incorporated"):
                status = "idea"
            content = body.get("content") or ""
            target_files = body.get("target_files", [])
            version_target = (body.get("version_target") or "").strip()

            proj_notes_dir = NOTES_BASE_DIR / project_id
            proj_notes_dir.mkdir(parents=True, exist_ok=True)

            ts_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
            title_slug = re.sub(r"[^a-zA-Z0-9_-]", "-", title.lower())[:30].strip("-")
            note_filename = f"{ts_slug}_{title_slug}.md" if title_slug else f"{ts_slug}.md"
            note_file = proj_notes_dir / note_filename

            meta = {
                "id": note_file.stem,
                "title": title,
                "status": status,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "target_files": target_files if isinstance(target_files, list) else [],
                "version_target": version_target,
            }
            write_markdown_note(note_file, meta, content)
            meta["content"] = content
            self.send_json(meta, 201)
            return

        # Atualizar Versão do Projeto: POST /api/projects/{id}/version
        m_version = re.match(r"^/api/projects/([^/]+)/version$", path)
        if m_version:
            project_id = m_version.group(1)
            new_version = (body.get("version") or "").strip()
            if not new_version:
                self.send_error_json("Versão não informada", 400)
                return

            projects = load_projects()
            updated = False
            for p in projects:
                if p.get("id") == project_id:
                    p["current_version"] = new_version
                    p["updated_at"] = datetime.now(timezone.utc).isoformat()
                    updated = True
                    break

            if not updated:
                self.send_error_json("Projeto não encontrado", 404)
                return

            save_projects(projects)
            self.send_json({"id": project_id, "current_version": new_version})
            return

        self.send_error_json("Rota POST não encontrada", 404)

    # --------------------------------------------------------------------------
    # Roteamento PUT
    # --------------------------------------------------------------------------
    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self.read_json_body()
        if body is None:
            self.send_error_json("Corpo da requisição JSON inválido", 400)
            return

        # Atualizar Nota: PUT /api/projects/{id}/notes/{note_id}
        m_put_note = re.match(r"^/api/projects/([^/]+)/notes/([^/]+)$", path)
        if m_put_note:
            project_id = m_put_note.group(1)
            note_id = m_put_note.group(2)
            proj = get_project_by_id(project_id)
            if not proj:
                self.send_error_json("Projeto não encontrado", 404)
                return

            note_file = NOTES_BASE_DIR / project_id / f"{note_id}.md"
            if not note_file.exists():
                self.send_error_json("Nota não encontrada", 404)
                return

            current_note = parse_markdown_note(note_file)
            if "title" in body:
                current_note["title"] = str(body["title"]).strip()
            if "status" in body:
                st = str(body["status"]).strip().lower()
                if st in ("idea", "planned", "in_review", "incorporated"):
                    current_note["status"] = st
            if "target_files" in body and isinstance(body["target_files"], list):
                current_note["target_files"] = body["target_files"]
            if "version_target" in body:
                current_note["version_target"] = str(body["version_target"]).strip()
            content = body.get("content", current_note.get("content", ""))

            write_markdown_note(note_file, current_note, content)
            current_note["content"] = content
            self.send_json(current_note, 200)
            return

        self.send_error_json("Rota PUT não encontrada", 404)

    # --------------------------------------------------------------------------
    # Roteamento DELETE
    # --------------------------------------------------------------------------
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # Remover Projeto: DELETE /api/projects/{id}
        m_del_proj = re.match(r"^/api/projects/([^/]+)$", path)
        if m_del_proj:
            project_id = m_del_proj.group(1)
            projects = load_projects()
            filtered = [p for p in projects if p.get("id") != project_id]
            if len(filtered) == len(projects):
                self.send_error_json("Projeto não encontrado", 404)
                return
            save_projects(filtered)
            self.send_json({"status": "deleted", "id": project_id})
            return

        # Remover Nota: DELETE /api/projects/{id}/notes/{note_id}
        m_del_note = re.match(r"^/api/projects/([^/]+)/notes/([^/]+)$", path)
        if m_del_note:
            project_id = m_del_note.group(1)
            note_id = m_del_note.group(2)
            note_file = NOTES_BASE_DIR / project_id / f"{note_id}.md"
            if not note_file.exists():
                self.send_error_json("Nota não encontrada", 404)
                return
            try:
                note_file.unlink()
                self.send_json({"status": "deleted", "id": note_id})
            except Exception as e:
                self.send_error_json(f"Falha ao excluir nota: {str(e)}", 500)
            return

        self.send_error_json("Rota DELETE não encontrada", 404)


# ==============================================================================
# Entrypoint de Execução do Servidor
# ==============================================================================

def run_server(port: int = 4100, host: str = "127.0.0.1") -> None:
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((host, port), ProjectOSHandler) as httpd:
        print(f"============================================================")
        print(f"  Axion Cockpit — Console Operacional e Visual de Projetos")
        print(f"  URL Local: http://{host}:{port}")
        print(f"  Modo: Observador Passivo (Zero-Dependencies)")
        print(f"============================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nEncerrando Axion Cockpit...")


if __name__ == "__main__":
    env_port = int(os.environ.get("PORT", "4100")) if os.environ.get("PORT") else 4100
    env_host = os.environ.get("HOST", "127.0.0.1")
    parser = argparse.ArgumentParser(description="Axion Cockpit Local Server")
    parser.add_argument("--port", type=int, default=env_port, help=f"Porta TCP (padrão: {env_port})")
    parser.add_argument("--host", type=str, default=env_host, help=f"Host bind (padrão: {env_host})")
    args = parser.parse_args()
    run_server(port=args.port, host=args.host)
