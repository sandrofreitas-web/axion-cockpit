#!/usr/bin/env python3
"""
Skills OS — Local Management Dashboard Server.
Backend REST API leve para gerenciamento visual, frota de projetos e live preview multi-LLM.
"""

import argparse
import http.server
import json
import mimetypes
import os
import re
import shutil
import socketserver
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

# Garante saída UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

UI_ROOT = Path(__file__).resolve().parent
LIBRARY_ROOT = UI_ROOT.parent
SCRIPTS_DIR = LIBRARY_ROOT / "scripts"
FLEET_FILE = UI_ROOT / "fleet.json"

# Adiciona scripts ao sys.path para reutilizar funções do sync_skills
sys.path.insert(0, str(SCRIPTS_DIR))
try:
    import sync_skills
except ImportError:
    sync_skills = None


def get_fleet() -> List[Dict[str, Any]]:
    if not FLEET_FILE.exists():
        return []
    try:
        return json.loads(FLEET_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_fleet(fleet: List[Dict[str, Any]]) -> None:
    FLEET_FILE.write_text(json.dumps(fleet, indent=2, ensure_ascii=False), encoding="utf-8")


def get_catalog_data() -> Dict[str, Any]:
    cat_path = LIBRARY_ROOT / "catalog.json"
    if not cat_path.exists():
        return {}
    try:
        catalog = json.loads(cat_path.read_text(encoding="utf-8"))
        # Enriquece com o conteúdo do SKILL.md de cada entrada
        for name, meta in catalog.items():
            skill_md_path = LIBRARY_ROOT / meta.get("path", "")
            if skill_md_path.exists():
                try:
                    if sync_skills:
                        parsed = sync_skills.parse_skill_md(skill_md_path)
                        meta["frontmatter"] = parsed["frontmatter"]
                        meta["body"] = parsed["body"]
                        meta["raw"] = parsed["raw"]
                except Exception as e:
                    meta["error"] = str(e)
        return catalog
    except Exception as e:
        return {"error": str(e)}


def inspect_project(proj: Dict[str, Any]) -> Dict[str, Any]:
    p_path = Path(proj["path"]).resolve()
    result = {
        "name": proj.get("name", p_path.name),
        "path": str(p_path),
        "description": proj.get("description", ""),
        "exists": p_path.exists() and p_path.is_dir(),
        "has_lock": False,
        "locked_skills": {},
        "local_skills": [],
        "generated_status": {},
    }

    if not result["exists"]:
        return result

    # 1. Lock file
    lock_file = p_path / "skills.lock.json"
    if lock_file.exists():
        result["has_lock"] = True
        try:
            lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            result["locked_skills"] = lock_data.get("skills", {})
            result["library_path"] = lock_data.get("library_path", "")
        except Exception as e:
            result["lock_error"] = str(e)

    # 2. Local skills
    local_dir = p_path / "skills" / "local"
    if local_dir.exists() and local_dir.is_dir():
        for sdir in sorted(local_dir.iterdir()):
            if sdir.is_dir():
                sm = sdir / "SKILL.md"
                if sm.exists():
                    try:
                        if sync_skills:
                            parsed = sync_skills.parse_skill_md(sm)
                            result["local_skills"].append({
                                "name": sdir.name,
                                "frontmatter": parsed["frontmatter"],
                                "body": parsed["body"],
                                "path": str(sm),
                            })
                        else:
                            result["local_skills"].append({"name": sdir.name, "path": str(sm)})
                    except Exception as e:
                        result["local_skills"].append({"name": sdir.name, "error": str(e), "path": str(sm)})

    # 3. Status de saídas geradas
    result["generated_status"] = {
        "antigravity": (p_path / ".agents" / "skills").exists(),
        "claude": (p_path / ".claude" / "skills").exists(),
        "cursor": (p_path / ".cursor" / "rules").exists(),
        "gemini": (p_path / ".gemini" / "GEMINI.md").exists(),
        "windsurf": (p_path / ".windsurf" / "rules").exists(),
        "copilot": (p_path / ".github" / "copilot-instructions.md").exists(),
    }

    return result


class SkillsOSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(UI_ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/catalog":
            self.send_json(get_catalog_data())
            return

        if parsed.path == "/api/fleet":
            fleet_raw = get_fleet()
            fleet_data = [inspect_project(p) for p in fleet_raw]
            self.send_json(fleet_data)
            return

        if parsed.path == "/api/status":
            self.send_json({
                "status": "online",
                "library_root": str(LIBRARY_ROOT),
                "catalog_skills_count": len(get_catalog_data()),
                "fleet_count": len(get_fleet()),
            })
            return

        # Default static file serving
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            payload = {}

        if parsed.path == "/api/fleet/add":
            path_str = payload.get("path", "").strip()
            name = payload.get("name", "").strip()
            desc = payload.get("description", "").strip()

            if not path_str:
                self.send_json({"error": "Caminho do projeto é obrigatório"}, status=400)
                return

            p = Path(path_str).resolve()
            if not p.exists():
                self.send_json({"error": f"O diretório não existe: {p}"}, status=400)
                return

            fleet = get_fleet()
            # Evita duplicidade por caminho
            fleet = [item for item in fleet if Path(item["path"]).resolve() != p]
            fleet.append({
                "name": name or p.name,
                "path": str(p),
                "description": desc,
            })
            save_fleet(fleet)
            self.send_json({"success": True, "fleet": [inspect_project(item) for item in fleet]})
            return

        if parsed.path == "/api/fleet/remove":
            path_str = payload.get("path", "").strip()
            fleet = get_fleet()
            fleet = [item for item in fleet if str(Path(item["path"]).resolve()) != str(Path(path_str).resolve())]
            save_fleet(fleet)
            self.send_json({"success": True, "fleet": [inspect_project(item) for item in fleet]})
            return

        if parsed.path == "/api/lock/toggle":
            project_path = payload.get("project_path")
            skill_name = payload.get("skill_name")
            enable = payload.get("enable", True)

            p = Path(project_path).resolve()
            lock_file = p / "skills.lock.json"

            lock_data = {"library_path": ".skills-library", "skills": {}}
            if lock_file.exists():
                try:
                    lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            skills_dict = lock_data.get("skills", {})
            catalog = get_catalog_data()

            if enable:
                ver = catalog.get(skill_name, {}).get("version", "1.0.0")
                skills_dict[skill_name] = {"version": ver}
            else:
                skills_dict.pop(skill_name, None)

            lock_data["skills"] = skills_dict
            lock_file.write_text(json.dumps(lock_data, indent=2, ensure_ascii=False), encoding="utf-8")

            # Executa sync automático
            sync_result = self.run_sync(str(p))
            self.send_json({"success": True, "lock": lock_data, "sync_output": sync_result})
            return

        if parsed.path == "/api/sync":
            project_path = payload.get("project_path")
            if not project_path:
                # Sync de toda a frota
                fleet = get_fleet()
                outputs = {}
                for item in fleet:
                    outputs[item["name"]] = self.run_sync(item["path"])
                self.send_json({"success": True, "outputs": outputs})
                return
            else:
                out = self.run_sync(project_path)
                self.send_json({"success": True, "output": out})
                return

        if parsed.path == "/api/preview":
            raw_text = payload.get("raw", "")
            if not raw_text:
                self.send_json({"error": "Conteúdo raw é obrigatório"}, status=400)
                return

            try:
                fm, body = sync_skills.parse_frontmatter(raw_text)
                name = fm.get("name", "minha-skill")
                desc = fm.get("description", "")
                globs = fm.get("globs", [])
                globs_str = ", ".join(globs) if isinstance(globs, list) else str(globs)
                always_apply = "true" if fm.get("always_apply") else "false"

                # Cursor Preview
                desc_clean = " ".join(desc.split())
                cursor_preview = (
                    f"---\n"
                    f"description: {desc_clean}\n"
                    f"globs: {globs_str}\n"
                    f"alwaysApply: {always_apply}\n"
                    f"---\n\n"
                    f"{body}\n"
                )

                # Gemini Preview
                gemini_import = f"@skills/{name}.md"
                gemini_file = f"# {name}\n\n> Quando usar: {desc}\n\n{body}\n"

                # Claude Preview
                claude_preview = raw_text

                # Copilot Preview
                copilot_preview = f"## {name}\n\n{body}\n"

                # Windsurf Preview
                windsurf_preview = f"{body}\n"

                # Antigravity Preview (.agents/skills/<name>/SKILL.md & AGENTS.md entry)
                antigravity_preview = (
                    f"// [.agents/skills/{name}/SKILL.md]:\n"
                    f"{raw_text}\n\n"
                    f"// [Entrada no AGENTS.md]:\n"
                    f"## Skill: `{name}`\n> {desc}\n\nPath: `.agents/skills/{name}/SKILL.md`\n"
                )

                self.send_json({
                    "frontmatter": fm,
                    "body": body,
                    "previews": {
                        "cursor": cursor_preview,
                        "antigravity": antigravity_preview,
                        "claude": claude_preview,
                        "gemini": {"file": gemini_file, "import": gemini_import},
                        "windsurf": windsurf_preview,
                        "copilot": copilot_preview,
                    }
                })
            except Exception as e:
                self.send_json({"error": f"Erro de parsing: {e}"}, status=400)
            return

        if parsed.path == "/api/skill/save":
            raw_text = payload.get("raw", "").strip()
            if not raw_text:
                self.send_json({"error": "Conteúdo raw do SKILL.md é obrigatório"}, status=400)
                return

            try:
                fm, body = sync_skills.parse_frontmatter(raw_text)
                name = fm.get("name", "").strip()
                if not name:
                    self.send_json({"error": "O campo 'name' é obrigatório no frontmatter YAML."}, status=400)
                    return

                if not re.match(r"^[a-zA-Z0-9_-]+$", name):
                    self.send_json({"error": "O nome da skill deve conter apenas letras, números, hífens ou underscores."}, status=400)
                    return

                desc = fm.get("description", "")
                version = str(fm.get("version", "1.0.0"))
                tags = fm.get("tags", [])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]

                # Cria diretório global da skill
                skill_dir = LIBRARY_ROOT / "global" / name
                skill_dir.mkdir(parents=True, exist_ok=True)
                skill_file = skill_dir / "SKILL.md"
                skill_file.write_text(raw_text, encoding="utf-8")

                # Atualiza catalog.json
                cat_path = LIBRARY_ROOT / "catalog.json"
                catalog = {}
                if cat_path.exists():
                    try:
                        catalog = json.loads(cat_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass

                existing_entry = catalog.get(name, {})
                compatible_with = existing_entry.get("compatible_with", ["claude", "gemini", "cursor", "windsurf", "copilot"])
                used_by = existing_entry.get("used_by", [])
                status = existing_entry.get("status", "stable")

                catalog[name] = {
                    "path": f"global/{name}/SKILL.md",
                    "description": desc,
                    "tags": tags,
                    "compatible_with": compatible_with,
                    "used_by": used_by,
                    "status": status,
                    "version": version,
                }

                cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

                self.send_json({
                    "success": True,
                    "message": f"Skill '{name}' salva com sucesso em global/{name}/SKILL.md e catalog.json!",
                    "skill_name": name,
                    "catalog": get_catalog_data(),
                })
            except Exception as e:
                self.send_json({"error": f"Erro ao salvar skill: {e}"}, status=400)
            return

        if parsed.path == "/api/skill/promote":
            project_path_str = payload.get("project_path", "").strip()
            skill_name = payload.get("skill_name", "").strip()

            if not project_path_str or not skill_name:
                self.send_json({"error": "project_path e skill_name são obrigatórios"}, status=400)
                return

            p_path = Path(project_path_str).resolve()
            src_skill_dir = p_path / "skills" / "local" / skill_name
            src_skill_file = src_skill_dir / "SKILL.md"

            if not src_skill_file.exists():
                self.send_json({"error": f"Skill local não encontrada em: {src_skill_file}"}, status=404)
                return

            try:
                # 1. Lê e valida o SKILL.md da skill local
                raw_content = src_skill_file.read_text(encoding="utf-8")
                fm, body = sync_skills.parse_frontmatter(raw_content)

                dest_global_dir = LIBRARY_ROOT / "global" / skill_name
                dest_global_dir.mkdir(parents=True, exist_ok=True)

                # 2. Copia todos os arquivos (SKILL.md, scripts/, references/, etc.) para global
                shutil.copytree(src_skill_dir, dest_global_dir, dirs_exist_ok=True)

                # 3. Registra no catalog.json global
                cat_path = LIBRARY_ROOT / "catalog.json"
                catalog = {}
                if cat_path.exists():
                    try:
                        catalog = json.loads(cat_path.read_text(encoding="utf-8"))
                    except Exception:
                        pass

                existing_entry = catalog.get(skill_name, {})
                used_by = existing_entry.get("used_by", [])
                if p_path.name not in used_by:
                    used_by.append(p_path.name)

                desc = fm.get("description", "")
                version = str(fm.get("version", "1.0.0"))
                tags = fm.get("tags", ["promoted", "local"])
                if isinstance(tags, str):
                    tags = [t.strip() for t in tags.split(",") if t.strip()]

                compat = fm.get("compatible_with", ["claude", "gemini", "cursor", "windsurf", "copilot", "antigravity"])

                catalog[skill_name] = {
                    "path": f"global/{skill_name}/SKILL.md",
                    "description": desc,
                    "tags": tags,
                    "compatible_with": compat,
                    "used_by": used_by,
                    "status": "stable",
                    "version": version,
                }
                cat_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

                # 4. Remove a pasta local após migração
                shutil.rmtree(src_skill_dir)

                # 5. Registra no skills.lock.json do projeto
                lock_file = p_path / "skills.lock.json"
                lock_data = {"library_path": ".skills-library", "skills": {}}
                if lock_file.exists():
                    try:
                        lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                lock_skills = lock_data.get("skills", {})
                lock_skills[skill_name] = {"version": version}
                lock_data["skills"] = lock_skills
                lock_file.write_text(json.dumps(lock_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

                # 6. Executa sincronização do projeto
                sync_out = self.run_sync(str(p_path))

                self.send_json({
                    "success": True,
                    "message": f"Skill '{skill_name}' promovida com sucesso para global/{skill_name}/SKILL.md e sincronizada em {p_path.name}!",
                    "skill_name": skill_name,
                    "sync_output": sync_out,
                    "catalog": get_catalog_data(),
                })
            except Exception as e:
                self.send_json({"error": f"Erro ao promover skill: {e}"}, status=500)
            return

        if parsed.path == "/api/validate":
            try:
                sync_script = SCRIPTS_DIR / "sync_skills.py"
                proc = subprocess.run(
                    [sys.executable, str(sync_script), "--check", "--library-path", str(LIBRARY_ROOT)],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                self.send_json({
                    "success": proc.returncode == 0,
                    "output": proc.stdout or proc.stderr,
                })
            except Exception as e:
                self.send_json({"success": False, "output": str(e)}, status=500)
            return

        self.send_error(404, "Endpoint não encontrado")

    def run_sync(self, project_path: str) -> str:
        try:
            sync_script = SCRIPTS_DIR / "sync_skills.py"
            proc = subprocess.run(
                [sys.executable, str(sync_script), project_path, "--clean"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return proc.stdout or proc.stderr
        except Exception as e:
            return f"Erro ao executar sync: {e}"

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Skills OS Management Dashboard Server.")
    parser.add_argument("--port", "-p", type=int, default=4100, help="Porta HTTP do servidor (padrão: 4100).")
    parser.add_argument("--host", default="127.0.0.1", help="Host do servidor (padrão: 127.0.0.1).")
    args = parser.parse_args()

    server_address = (args.host, args.port)
    with socketserver.TCPServer(server_address, SkillsOSRequestHandler) as httpd:
        print("=" * 60)
        print("  🖥️  SKILLS OS — Management & Governance Dashboard")
        print("=" * 60)
        print(f"  URL Local:     http://{args.host}:{args.port}")
        print(f"  Library Root:  {LIBRARY_ROOT}")
        print("=" * 60)
        print("  Pressione Ctrl+C para encerrar o servidor.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado.")


if __name__ == "__main__":
    main()
