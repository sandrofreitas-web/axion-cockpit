#!/usr/bin/env python3
"""
sync_skills.py — Compilador e sincronizador de Skills multi-LLM.
Gera os formatos nativos de cada IDE/ferramenta (.claude, .cursor, .gemini,
.windsurf, .github) a partir dos SKILL.md canônicos.

Uso:
    python3 sync_skills.py <caminho-do-projeto> [opções]

Exemplos:
    python3 sync_skills.py project-example
    python3 sync_skills.py project-example --clean --library-path ../skills-library
    python3 sync_skills.py project-example --check
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Garante saída UTF-8 no Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def parse_yaml_fallback(raw_yaml: str) -> Dict[str, Any]:
    """
    Parser YAML resiliente em Python puro (sem dependências externas).
    Suporta strings simples, strings multiline (> e |), listas inline [a, b],
    listas com traço (- item), booleanos e comentários.
    """
    result: Dict[str, Any] = {}
    lines = raw_yaml.splitlines()
    i = 0
    num_lines = len(lines)

    while i < num_lines:
        line = lines[i]
        stripped = line.strip()

        # Pula linhas vazias e comentários
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        if ":" not in line:
            i += 1
            continue

        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        # 1. Trata bloco multiline folded (>) ou literal (|)
        if val in (">", "|", ">-", "|-", ">+", "|+"):
            multiline_lines = []
            i += 1
            while i < num_lines:
                curr = lines[i]
                # Se a linha estiver indentada, pertence ao bloco
                if curr.startswith(" ") or curr.startswith("\t") or not curr.strip():
                    multiline_lines.append(curr.strip())
                    i += 1
                else:
                    break
            if val.startswith(">"):
                # Folded: junta com espaços
                result[key] = " ".join(multiline_lines).strip()
            else:
                # Literal: preserva quebras de linha
                result[key] = "\n".join(multiline_lines).strip()
            continue

        # 2. Trata listas em bloco (- item)
        if val == "" and i + 1 < num_lines and lines[i + 1].strip().startswith("-"):
            items = []
            i += 1
            while i < num_lines and lines[i].strip().startswith("-"):
                item_val = lines[i].strip()[1:].strip().strip('"').strip("'")
                items.append(item_val)
                i += 1
            result[key] = items
            continue

        # 3. Trata lista inline [a, b, c]
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            if not inner:
                result[key] = []
            else:
                result[key] = [
                    v.strip().strip('"').strip("'")
                    for v in inner.split(",")
                    if v.strip()
                ]
            i += 1
            continue

        # 4. Trata valores booleanos
        val_lower = val.lower()
        if val_lower in ("true", "yes", "on"):
            result[key] = True
        elif val_lower in ("false", "no", "off"):
            result[key] = False
        else:
            # 5. Valor escalar simples (remove aspas externas e comentários inline)
            # Remove comentário inline se existir
            if " #" in val:
                val = val.split(" #")[0].strip()
            result[key] = val.strip('"').strip("'")

        i += 1

    return result


def parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """Extrai frontmatter YAML e o corpo Markdown de um arquivo."""
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError("Arquivo sem frontmatter YAML delimitado por '---'.")

    raw_yaml = m.group(1)
    body = m.group(2).strip()

    # Tenta usar PyYAML se disponível, senão usa o fallback resiliente
    try:
        import yaml  # type: ignore

        fm = yaml.safe_load(raw_yaml)
        if not isinstance(fm, dict):
            fm = {}
    except ImportError:
        fm = parse_yaml_fallback(raw_yaml)

    return fm, body


def parse_skill_md(skill_path: Path) -> Dict[str, Any]:
    """Lê e processa um arquivo SKILL.md."""
    text = skill_path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)

    # Garante campos mínimos essenciais
    name = fm.get("name") or skill_path.parent.name
    fm["name"] = name

    # Normaliza globs
    globs = fm.get("globs", [])
    if isinstance(globs, str):
        globs = [g.strip() for g in globs.split(",") if g.strip()]
    fm["globs"] = globs

    # Normaliza always_apply
    fm["always_apply"] = bool(fm.get("always_apply", False))

    return {
        "frontmatter": fm,
        "body": body,
        "raw": text,
        "dir_path": skill_path.parent,
        "file_path": skill_path,
    }


def resolve_library_root(project_dir: Path, cli_override: Optional[str] = None) -> Path:
    """Descobre o caminho do repositório skills-library."""
    if cli_override:
        p = Path(cli_override).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Caminho de library especificado não existe: {cli_override}")

    env_path = os.getenv("SKILLS_LIBRARY_PATH")
    if env_path:
        p = Path(env_path).resolve()
        if p.exists():
            return p

    lock_file = project_dir / "skills.lock.json"
    if lock_file.exists():
        try:
            lock = json.loads(lock_file.read_text(encoding="utf-8"))
            if "library_path" in lock:
                p = (project_dir / lock["library_path"]).resolve()
                if p.exists():
                    return p
        except Exception:
            pass

    # Tenta diretório pai relativo ao script
    script_parent = Path(__file__).resolve().parent.parent
    if (script_parent / "catalog.json").exists():
        return script_parent

    # Tenta .skills-library ou skills-library no projeto
    for candidate in [project_dir / ".skills-library", project_dir / "skills-library", project_dir.parent / "skills-library"]:
        if (candidate / "catalog.json").exists():
            return candidate.resolve()

    return script_parent


def load_catalog(library_root: Path) -> Dict[str, Any]:
    catalog_path = library_root / "catalog.json"
    if not catalog_path.exists():
        return {}
    try:
        return json.loads(catalog_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [AVISO] Erro ao carregar catalog.json em {catalog_path}: {e}")
        return {}


def collect_skills(project_dir: Path, library_root: Path) -> list[Dict[str, Any]]:
    skills = []
    catalog = load_catalog(library_root)

    # 1. Skills Locais
    local_dir = project_dir / "skills" / "local"
    if local_dir.exists():
        for skill_dir in sorted(local_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                try:
                    parsed = parse_skill_md(skill_md)
                    parsed.update({"source": str(skill_md), "scope": "local"})
                    skills.append(parsed)
                except Exception as e:
                    print(f"  [ERRO] Falha ao processar skill local {skill_md}: {e}")

    # 2. Skills Globais declaradas no skills.lock.json
    lock_path = project_dir / "skills.lock.json"
    if lock_path.exists():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            locked_skills = lock.get("skills", {})

            for name, meta in locked_skills.items():
                entry = catalog.get(name)
                if not entry:
                    print(f"  [AVISO] '{name}' declarado no lock file mas não encontrado no catalog.json.")
                    continue

                if entry.get("status") == "deprecated":
                    print(f"  [DEPRECATED] A skill global '{name}' está marcada como depreciada.")

                skill_md = library_root / entry["path"]
                if not skill_md.exists():
                    print(f"  [ERRO] Arquivo da skill global não encontrado: {skill_md}")
                    continue

                try:
                    parsed = parse_skill_md(skill_md)
                    parsed.update({
                        "source": str(skill_md),
                        "scope": "global",
                        "catalog_meta": entry,
                        "lock_meta": meta if isinstance(meta, dict) else {},
                    })
                    skills.append(parsed)
                except Exception as e:
                    print(f"  [ERRO] Falha ao processar skill global {skill_md}: {e}")

        except Exception as e:
            print(f"  [ERRO] Falha ao ler skills.lock.json: {e}")

    return skills


def supports(skill: Dict[str, Any], tool: str) -> bool:
    compat = skill["frontmatter"].get("compatible_with")
    if compat is None and "catalog_meta" in skill:
        compat = skill["catalog_meta"].get("compatible_with")
    if not compat:
        return True
    if tool == "antigravity":
        return "antigravity" in compat or "claude" in compat or "gemini" in compat
    return tool in compat


def copy_skill_resources(src_dir: Path, dest_dir: Path):
    """Copia pastas anexas (scripts, references, assets, etc.) se existirem."""
    for item in src_dir.iterdir():
        if item.is_dir() and not item.name.startswith("."):
            target_sub = dest_dir / item.name
            if target_sub.exists():
                shutil.rmtree(target_sub)
            shutil.copytree(item, target_sub)


def clean_target_directories(project_dir: Path):
    """Limpa artefatos previamente gerados para evitar arquivos órfãos/zumbis."""
    targets = [
        project_dir / ".claude" / "skills",
        project_dir / ".cursor" / "rules",
        project_dir / ".windsurf" / "rules",
        project_dir / ".gemini" / "skills",
        project_dir / ".agents" / "skills",
    ]
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)


def write_claude(skills: List[Dict[str, Any]], project_dir: Path) -> int:
    out_dir = project_dir / ".claude" / "skills"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for skill in skills:
        if not supports(skill, "claude"):
            continue
        name = skill["frontmatter"]["name"]
        dest = out_dir / name
        dest.mkdir(parents=True, exist_ok=True)

        # Escreve o SKILL.md canônico
        (dest / "SKILL.md").write_text(skill["raw"], encoding="utf-8")

        # Copia recursos complementares (scripts, references, assets)
        copy_skill_resources(skill["dir_path"], dest)
        count += 1

    return count


def write_antigravity(skills: List[Dict[str, Any]], project_dir: Path) -> int:
    """Gera o formato nativo do Google Antigravity (.agents/skills/<nome>/SKILL.md) e AGENTS.md."""
    out_dir = project_dir / ".agents" / "skills"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    agents_sections = [
        "# AGENTS.md — Global & Local Workspace Skills\n<!-- Gerado por sync_skills.py — não edite manualmente -->\n"
    ]

    for skill in skills:
        if not supports(skill, "antigravity"):
            continue
        name = skill["frontmatter"]["name"]
        dest = out_dir / name
        dest.mkdir(parents=True, exist_ok=True)

        # Escreve o SKILL.md canônico
        (dest / "SKILL.md").write_text(skill["raw"], encoding="utf-8")

        # Copia recursos complementares (scripts, references, assets)
        copy_skill_resources(skill["dir_path"], dest)

        desc = skill["frontmatter"].get("description", "")
        agents_sections.append(f"## Skill: `{name}`\n> {desc}\n\nPath: `.agents/skills/{name}/SKILL.md`\n")
        count += 1

    (project_dir / "AGENTS.md").write_text("\n".join(agents_sections), encoding="utf-8")
    return count


def write_gemini(skills: List[Dict[str, Any]], project_dir: Path) -> int:
    skills_dir = project_dir / ".gemini" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    imports = []
    count = 0

    for skill in skills:
        if not supports(skill, "gemini"):
            continue
        name = skill["frontmatter"]["name"]
        desc = skill["frontmatter"].get("description", "")
        content = f"# {name}\n\n> Quando usar: {desc}\n\n{skill['body']}\n"
        dest_file = skills_dir / f"{name}.md"
        dest_file.write_text(content, encoding="utf-8")
        imports.append(f"@skills/{name}.md")
        count += 1

    gemini_md = "# Contexto do projeto (gerado por sync_skills.py — não edite manualmente)\n\n"
    if imports:
        gemini_md += "\n".join(imports) + "\n"
    (project_dir / ".gemini" / "GEMINI.md").write_text(gemini_md, encoding="utf-8")

    return count


def write_cursor(skills: List[Dict[str, Any]], project_dir: Path) -> int:
    out_dir = project_dir / ".cursor" / "rules"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for skill in skills:
        if not supports(skill, "cursor"):
            continue
        name = skill["frontmatter"]["name"]
        desc = skill["frontmatter"].get("description", "")
        # Remove quebras de linha da descrição para formato .mdc limpo
        desc_clean = " ".join(desc.split())

        globs_list = skill["frontmatter"].get("globs", [])
        globs_str = ", ".join(globs_list) if globs_list else ""
        always_apply = "true" if skill["frontmatter"].get("always_apply") else "false"

        mdc = (
            f"---\n"
            f"description: {desc_clean}\n"
            f"globs: {globs_str}\n"
            f"alwaysApply: {always_apply}\n"
            f"---\n\n"
            f"{skill['body']}\n"
        )
        (out_dir / f"{name}.mdc").write_text(mdc, encoding="utf-8")
        count += 1

    return count


def write_windsurf(skills: List[Dict[str, Any]], project_dir: Path) -> int:
    out_dir = project_dir / ".windsurf" / "rules"
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for skill in skills:
        if not supports(skill, "windsurf"):
            continue
        name = skill["frontmatter"]["name"]
        (out_dir / f"{name}.md").write_text(skill["body"] + "\n", encoding="utf-8")
        count += 1

    return count


def write_copilot(skills: List[Dict[str, Any]], project_dir: Path) -> int:
    out_path = project_dir / ".github" / "copilot-instructions.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sections = [
        "<!-- gerado por sync_skills.py — não edite manualmente -->\n"
    ]
    count = 0

    for skill in skills:
        if not supports(skill, "copilot"):
            continue
        name = skill["frontmatter"]["name"]
        sections.append(f"## {name}\n\n{skill['body']}\n")
        count += 1

    out_path.write_text("\n".join(sections), encoding="utf-8")
    return count


def validate_workspace(project_dir: Path, library_root: Path) -> bool:
    """Valida a consistência de catálogo, lockfile e sintaxe de skills."""
    print("=== [VALIDAÇÃO / CHECK] ===")
    has_errors = False

    # 1. Catálogo
    catalog_file = library_root / "catalog.json"
    if not catalog_file.exists():
        print(f"[ERRO] catalog.json não encontrado em {catalog_file}")
        return False
    catalog = load_catalog(library_root)
    print(f"✓ catalog.json carregado ({len(catalog)} skills registradas)")

    for name, entry in catalog.items():
        skill_path = library_root / entry.get("path", "")
        if not skill_path.exists():
            print(f"[ERRO] Skill no catálogo '{name}' aponta para caminho inexistente: {skill_path}")
            has_errors = True
        else:
            try:
                parse_skill_md(skill_path)
            except Exception as e:
                print(f"[ERRO] Sintaxe inválida em {skill_path}: {e}")
                has_errors = True

    # 2. Lock file
    lock_file = project_dir / "skills.lock.json"
    if lock_file.exists():
        try:
            lock_data = json.loads(lock_file.read_text(encoding="utf-8"))
            for name, meta in lock_data.get("skills", {}).items():
                if name not in catalog:
                    print(f"[ERRO] Skill '{name}' no lockfile não existe no catalog.json")
                    has_errors = True
                else:
                    cat_version = catalog[name].get("version")
                    lock_version = meta.get("version") if isinstance(meta, dict) else meta
                    if cat_version and lock_version and str(cat_version) != str(lock_version):
                        print(f"[AVISO] Versão diferente para '{name}': lockfile={lock_version}, catálogo={cat_version}")
        except Exception as e:
            print(f"[ERRO] Falha ao processar skills.lock.json: {e}")
            has_errors = True

    if not has_errors:
        print("✓ Toda a validação passou com sucesso.")
    return not has_errors


def main():
    parser = argparse.ArgumentParser(
        description="Compilador e sincronizador de Skills para IDEs e LLMs."
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        default=".",
        help="Caminho do diretório do projeto a sincronizar (padrão: diretório atual).",
    )
    parser.add_argument(
        "--library-path",
        "-l",
        default=None,
        help="Caminho explícito para a pasta skills-library.",
    )
    parser.add_argument(
        "--clean",
        "-c",
        action="store_true",
        default=True,
        help="Limpa saídas antigas antes de sincronizar para remover órfãos (padrão: True).",
    )
    parser.add_argument(
        "--no-clean",
        action="store_false",
        dest="clean",
        help="Não limpa saídas antigas antes de sincronizar.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Apenas valida o catálogo, o lockfile e a sintaxe das skills sem gerar arquivos.",
    )

    args = parser.parse_args()

    project_dir = Path(args.project_path).resolve()
    if not project_dir.exists() or not project_dir.is_dir():
        print(f"Erro: Diretório de projeto não encontrado: {project_dir}")
        sys.exit(1)

    library_root = resolve_library_root(project_dir, args.library_path)

    if args.check:
        ok = validate_workspace(project_dir, library_root)
        sys.exit(0 if ok else 1)

    print(f"📁 Projeto: {project_dir}")
    print(f"📚 Skills Library: {library_root}")

    if args.clean:
        clean_target_directories(project_dir)

    skills = collect_skills(project_dir, library_root)
    local_count = sum(1 for s in skills if s.get("scope") == "local")
    global_count = sum(1 for s in skills if s.get("scope") == "global")

    print(f"\nColetadas {len(skills)} skills ({local_count} locais, {global_count} globais):")
    for s in skills:
        name = s["frontmatter"]["name"]
        scope = s.get("scope")
        print(f"  • {name} [{scope}]")

    print("\nGerando artefatos:")
    c_claude = write_claude(skills, project_dir)
    print(f"  ✓ .claude/skills/             -> {c_claude} skills (com subpastas de recursos)")

    c_antigravity = write_antigravity(skills, project_dir)
    print(f"  ✓ .agents/skills/ & AGENTS.md -> {c_antigravity} skills (Antigravity)")

    c_gemini = write_gemini(skills, project_dir)
    print(f"  ✓ .gemini/GEMINI.md           -> {c_gemini} skills importadas")

    c_cursor = write_cursor(skills, project_dir)
    print(f"  ✓ .cursor/rules/*.mdc         -> {c_cursor} regras com globs e triggers")

    c_windsurf = write_windsurf(skills, project_dir)
    print(f"  ✓ .windsurf/rules/*.md        -> {c_windsurf} regras")

    c_copilot = write_copilot(skills, project_dir)
    print(f"  ✓ .github/copilot-instructions.md -> {c_copilot} seções")

    print("\n✨ Sincronização concluída com sucesso!")
    print("💡 Lembre-se: edite os SKILL.md de origem e execute o sync novamente.")


if __name__ == "__main__":
    main()
