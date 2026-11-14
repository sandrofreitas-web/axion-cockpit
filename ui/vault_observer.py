#!/usr/bin/env python3
"""
vault_observer.py — Observador read-only do main_vault com validação de contratos (vault_schemas.json),
snapshot imutável em memória sob threading.Lock e reconciliação N:1 com matriz binária de divergência.
"""

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import infra_scanner
    import scanner
    import vault_parser
except ImportError:
    from ui import infra_scanner, scanner, vault_parser


ALLOWED_VAULT_DOMAINS: Tuple[str, ...] = (
    "01_Projetos",
    "02_Recursos_e_Infra",
    "04_Arquitetura_ADRs",
    "05_Areas",
)

FORBIDDEN_DIR_NAMES: Set[str] = {
    "chaves_ssh",
    ".obsidian",
    ".git",
    ".agents",
    ".vscode",
    ".ssh",
}

AREAS_SAFE_FIELDS: Tuple[str, ...] = (
    "rel_path",
    "domain",
    "entity",
    "title",
    "area",
    "doc_type",
    "status",
    "frontmatter_status",
    "links_status",
    "validation_errors",
    "size_bytes",
    "doc_date",
    "indexed_at",
)

CODE_BLOCK_FENCED_RE = re.compile(r"```.*?```", re.DOTALL)
CODE_BLOCK_INLINE_RE = re.compile(r"`[^`]*`")
ADR_REF_RE = re.compile(r"ADR-\d{3}", re.IGNORECASE)
WINDOWS_OR_POSIX_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|/)")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_code_blocks(text: str) -> str:
    return CODE_BLOCK_INLINE_RE.sub("", CODE_BLOCK_FENCED_RE.sub("", text))


def _entity_matches(note_entity: str, filter_entity: str) -> bool:
    """
    Avalia se o campo entidade da nota pertence ao filtro solicitado.
    - Filtro 'Todas' inclui todas as notas.
    - Notas com entidade 'Todas' pertencem a todas as visões de entidade.
    - Notas compostas como 'SIAE BR & Pessoal' pertencem a ambas as entidades individuais.
    """
    if not filter_entity or filter_entity == "Todas":
        return True
    if not note_entity:
        return False
    if note_entity == "Todas" or note_entity == filter_entity:
        return True
    parts = [p.strip() for p in re.split(r"[&,/]", note_entity) if p.strip()]
    return filter_entity in parts


def _parse_iso_datetime(iso_str: str) -> Optional[datetime]:
    if not iso_str or not isinstance(iso_str, str):
        return None
    s = iso_str.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def resolve_main_vault_root(custom_root: Optional[Path] = None) -> Tuple[Optional[Path], str]:
    """
    Resolve a raiz do main_vault seguindo a precedência:
    1. custom_root explícito (testes)
    2. NEXUS_VAULT_ROOT / NEXUS_VAULT_HOST_DIR
    3. /main_vault (mount padrão no container)
    4. G:/Meu Drive/main_vault ou /mnt/g/Meu Drive/main_vault
    5. Fallback legado AXION_VAULT_HOST_DIR / AXION_VAULT_PATH (apenas se apontar para raiz contendo os 4 domínios)
    """
    if custom_root is not None:
        try:
            if custom_root.exists() and custom_root.is_dir():
                if all((custom_root / dom).exists() for dom in ALLOWED_VAULT_DOMAINS):
                    return custom_root.resolve(), "available"
        except Exception:
            pass
        return None, "unavailable"

    candidates: List[Path] = []

    for env_key in ("NEXUS_VAULT_ROOT", "NEXUS_VAULT_HOST_DIR"):
        val = os.environ.get(env_key)
        if val and val.strip():
            candidates.append(Path(val.strip()))

    candidates.extend(
        [
            Path("/main_vault"),
            Path("G:/Meu Drive/main_vault"),
            Path("/mnt/g/Meu Drive/main_vault"),
        ]
    )

    for legacy_key in ("AXION_VAULT_HOST_DIR", "AXION_VAULT_PATH"):
        val = os.environ.get(legacy_key)
        if val and val.strip():
            p = Path(val.strip())
            if p.name.lower() == "02_recursos_e_infra":
                candidates.append(p.parent)
            else:
                candidates.append(p)

    for cand in candidates:
        try:
            if cand.exists() and cand.is_dir():
                if all((cand / dom).exists() for dom in ALLOWED_VAULT_DOMAINS):
                    return cand.resolve(), "available"
        except Exception:
            pass

    return None, "unavailable"


class VaultObserver:
    """
    Gerencia o snapshot imutável em memória do main_vault e a reconciliação N:1 com repositórios.
    """

    def __init__(
        self,
        vault_root: Optional[Path] = None,
        schema_path: Optional[Path] = None,
        projects_file: Optional[Path] = None,
        ingested_dir: Optional[Path] = None,
        drive_projects_dir: Optional[Path] = None,
    ) -> None:
        self._custom_vault_root = vault_root
        self._custom_schema_path = schema_path
        self._projects_file = projects_file
        self._ingested_dir = ingested_dir
        self._drive_projects_dir = drive_projects_dir

        self._lock = threading.Lock()
        self._file_parse_cache: Dict[str, Dict[str, Any]] = {}
        self._last_composite_signature: str = ""

        self._snapshot: Dict[str, Any] = {
            "vault_status": "initializing",
            "vault_error": None,
            "schema_version": "1.0.0",
            "schema_hash": "",
            "last_indexed_at": None,
            "entities": ["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV"],
            "vault_nodes": [],
            "project_repo_links": [],
            "scan_errors": [],
            "git_by_project_id": {},
        }

    def start_background_warmup(self) -> None:
        """Dispara o primeiro carregamento em background para não bloquear o boot HTTP."""
        t = threading.Thread(target=self.reindex, kwargs={"force": False}, daemon=True)
        t.start()

    def _compute_composite_signature(
        self,
        vault_root: Path,
        schema_bytes: bytes,
        projects_list: List[Dict[str, Any]],
    ) -> Tuple[str, List[Tuple[str, str, Path, os.stat_result]]]:
        """
        Calcula assinatura composta cobrindo:
        - vault_schemas.json (SHA-256)
        - todos os arquivos .md nos 4 domínios (rel_path, size_bytes, mtime_ns)
        - data/projects.json
        - docker-compose.yml/yaml e .git/HEAD + .git/index dos repositórios locais
        """
        hasher = hashlib.sha256()
        hasher.update(schema_bytes)
        hasher.update(json.dumps(projects_list, sort_keys=True, ensure_ascii=False).encode("utf-8"))

        discovered_files: List[Tuple[str, str, Path, os.stat_result]] = []
        real_vault_root = vault_root.resolve()

        for dom_folder in ALLOWED_VAULT_DOMAINS:
            dom_dir = real_vault_root / dom_folder
            if not dom_dir.exists() or not dom_dir.is_dir():
                continue

            for root_str, dirs, files in os.walk(dom_dir, followlinks=False):
                # Filtra diretórios proibidos ou ocultos in-place
                dirs[:] = sorted(
                    d
                    for d in dirs
                    if d.lower() not in FORBIDDEN_DIR_NAMES and not d.startswith(".")
                )
                root_path = Path(root_str)
                for fname in sorted(files):
                    if fname.startswith(".") or fname.lower().startswith(".env"):
                        continue
                    fpath = root_path / fname
                    if fpath.is_symlink():
                        continue
                    try:
                        real_f = fpath.resolve()
                        if not real_f.is_relative_to(real_vault_root):
                            continue
                        if scanner.has_forbidden_segments(str(real_f.relative_to(real_vault_root))):
                            continue
                        st = real_f.stat()
                    except Exception:
                        continue

                    rel_posix = real_f.relative_to(real_vault_root).as_posix()
                    discovered_files.append((dom_folder, rel_posix, real_f, st))
                    hasher.update(f"{rel_posix}:{st.st_size}:{st.st_mtime_ns}|".encode("utf-8"))

        # Inclui mtime de docker-compose e .git dos projetos cadastrados
        for proj in projects_list:
            raw_p = proj.get("path") or proj.get("resolved_path") or ""
            if not raw_p:
                continue
            try:
                res_p = scanner.resolve_cross_platform_path(raw_p)
                if res_p and res_p.exists() and res_p.is_dir():
                    for marker in ("docker-compose.yml", "docker-compose.yaml", ".git/HEAD", ".git/index"):
                        mp = res_p / marker
                        if mp.exists():
                            mst = mp.stat()
                            hasher.update(f"{mp}:{mst.st_size}:{mst.st_mtime_ns}|".encode("utf-8"))
            except Exception:
                pass

        return hasher.hexdigest(), discovered_files

    def _load_projects_list(self) -> List[Dict[str, Any]]:
        pfile = self._projects_file or (Path(__file__).resolve().parent.parent / "data" / "projects.json")
        if not pfile.exists():
            return []
        try:
            return json.loads(pfile.read_text(encoding="utf-8"))
        except Exception:
            return []

    def reindex(self, force: bool = False) -> Dict[str, Any]:
        """
        Executa varredura e validação do main_vault sob single-flight lock.
        Se o vault ou schema estiver inacessível/inválido, preserva o último snapshot válido.
        """
        with self._lock:
            vault_root, root_status = resolve_main_vault_root(self._custom_vault_root)
            if not vault_root or root_status != "available":
                self._snapshot = {
                    **self._snapshot,
                    "vault_status": "unavailable",
                    "vault_error": "main_vault_not_accessible",
                }
                return self._snapshot

            schema_file = (
                self._custom_schema_path
                or (Path(os.environ["NEXUS_SCHEMA_PATH"]) if os.environ.get("NEXUS_SCHEMA_PATH") else None)
                or (vault_root / "scripts" / "harness" / "vault_schemas.json")
            )
            if not schema_file.exists() or not schema_file.is_file():
                self._snapshot = {
                    **self._snapshot,
                    "vault_status": "schema_error",
                    "vault_error": "schema_file_missing",
                }
                return self._snapshot

            try:
                schema_bytes = schema_file.read_bytes()
                schema = json.loads(schema_bytes.decode("utf-8-sig"))
                if not isinstance(schema, dict) or "domains" not in schema or "entities" not in schema:
                    raise ValueError("invalid_schema_structure")
            except Exception as exc:
                self._snapshot = {
                    **self._snapshot,
                    "vault_status": "schema_error",
                    "vault_error": f"schema_parse_error: {type(exc).__name__}",
                }
                return self._snapshot

            projects_list = self._load_projects_list()
            composite_sig, discovered_files = self._compute_composite_signature(
                vault_root, schema_bytes, projects_list
            )

            if (
                not force
                and self._snapshot.get("vault_status") == "available"
                and composite_sig == self._last_composite_signature
            ):
                return self._snapshot

            schema_hash = hashlib.sha256(schema_bytes).hexdigest()
            schema_version = str(schema.get("schema_version", "1.0.0"))
            entities: List[str] = list(schema.get("entities", ["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV"]))
            global_rules = schema.get("global_rules", {})
            allowed_exts = {e.lower() for e in global_rules.get("allowed_extensions", [".md"])}
            max_file_bytes = int(global_rules.get("max_file_bytes", 524288))
            forbid_empty = bool(global_rules.get("forbid_empty_bytes", True))
            wikilink_pattern = re.compile(
                global_rules.get("forbid_absolute_wikilink_regex", r"\[\[[A-Za-z]:[\\/].*?\]\]")
            )

            indexed_at = _utc_now_iso()
            vault_nodes: List[Dict[str, Any]] = []
            scan_errors: List[Dict[str, Any]] = []
            project_notes_for_reconcile: List[Dict[str, Any]] = []

            for dom_folder, rel_posix, real_f, st in discovered_files:
                if real_f.suffix.lower() not in allowed_exts:
                    continue

                dom_cfg = schema["domains"].get(dom_folder, {})
                dom_key = dom_cfg.get("domain_key", dom_folder.lower())

                ignored_names = {n.lower() for n in dom_cfg.get("ignored_filenames", [])}
                if real_f.name.lower() in ignored_names:
                    continue

                ignored_prefixes = dom_cfg.get("ignored_prefixes", [])
                if any(real_f.name.lower().startswith(p.lower()) for p in ignored_prefixes):
                    continue

                # Cache de parsing por arquivo (size, mtime_ns, sha256, schema_hash)
                cached = self._file_parse_cache.get(rel_posix)
                parsed_info: Optional[Dict[str, Any]] = None
                if (
                    not force
                    and cached
                    and cached.get("size_bytes") == st.st_size
                    and cached.get("mtime_ns") == st.st_mtime_ns
                    and cached.get("schema_hash") == schema_hash
                ):
                    parsed_info = cached["parsed_info"]
                else:
                    try:
                        parsed_info = vault_parser.parse_vault_file(real_f, max_bytes=max_file_bytes)
                        raw_bytes = real_f.read_bytes() if st.st_size <= max_file_bytes else b""
                        content_sha256 = hashlib.sha256(raw_bytes).hexdigest()
                        parsed_info["content_sha256"] = content_sha256
                        self._file_parse_cache[rel_posix] = {
                            "size_bytes": st.st_size,
                            "mtime_ns": st.st_mtime_ns,
                            "content_sha256": content_sha256,
                            "schema_hash": schema_hash,
                            "parsed_info": parsed_info,
                        }
                    except Exception as exc:
                        scan_errors.append(
                            {
                                "rel_path": rel_posix,
                                "domain": dom_key,
                                "severity": "error",
                                "error_type": "read_error",
                                "detail": f"file_read_failed: {type(exc).__name__}",
                                "occurred_at": indexed_at,
                            }
                        )
                        continue

                fm = parsed_info["frontmatter"]
                fm_status = parsed_info["frontmatter_status"]
                err_detail = parsed_info.get("error_detail")
                body = parsed_info.get("body", "")
                raw_content = parsed_info.get("raw_content", "")

                node_errors: List[str] = []

                if forbid_empty and st.st_size == 0:
                    node_errors.append("empty_file_zero_bytes")
                    scan_errors.append(
                        {
                            "rel_path": rel_posix,
                            "domain": dom_key,
                            "severity": "error",
                            "error_type": "empty_file",
                            "detail": "empty_file_zero_bytes",
                            "occurred_at": indexed_at,
                        }
                    )
                elif err_detail == "file_too_large":
                    node_errors.append("file_too_large")
                    scan_errors.append(
                        {
                            "rel_path": rel_posix,
                            "domain": dom_key,
                            "severity": "error",
                            "error_type": "file_too_large",
                            "detail": f"exceeds_max_bytes: {max_file_bytes}",
                            "occurred_at": indexed_at,
                        }
                    )
                elif fm_status != "ok":
                    policy = dom_cfg.get("non_frontmatter_policy", "error")
                    if fm_status == "missing" and policy == "warning_non_contract":
                        scan_errors.append(
                            {
                                "rel_path": rel_posix,
                                "domain": dom_key,
                                "severity": "warning",
                                "error_type": "non_contract_markdown",
                                "detail": "missing_frontmatter_warning",
                                "occurred_at": indexed_at,
                            }
                        )
                    else:
                        code = err_detail or f"frontmatter_{fm_status}"
                        node_errors.append(code)
                        scan_errors.append(
                            {
                                "rel_path": rel_posix,
                                "domain": dom_key,
                                "severity": "error",
                                "error_type": "frontmatter_error",
                                "detail": code.split(":", 1)[0],
                                "occurred_at": indexed_at,
                            }
                        )
                else:
                    # Validação de campos obrigatórios
                    spec_docs = {n.lower() for n in dom_cfg.get("spec_doc_filenames", [])}
                    if real_f.name.lower() in spec_docs and dom_cfg.get("spec_doc_required_fields"):
                        req_fields = dom_cfg.get("spec_doc_required_fields", [])
                    else:
                        req_fields = dom_cfg.get("required_fields", [])

                    for req in req_fields:
                        val = fm.get(req)
                        if val is None or (isinstance(val, str) and not val.strip()):
                            err_code = f"missing_required_field: {req}"
                            node_errors.append(err_code)
                            scan_errors.append(
                                {
                                    "rel_path": rel_posix,
                                    "domain": dom_key,
                                    "severity": "error",
                                    "error_type": "missing_required_field",
                                    "detail": err_code,
                                    "occurred_at": indexed_at,
                                }
                            )

                    # Validação de enums
                    allowed_enums = dom_cfg.get("allowed_enums", {})
                    for enum_field, allowed_vals in allowed_enums.items():
                        val = fm.get(enum_field)
                        if val is not None and str(val).strip() != "":
                            if str(val).strip() not in allowed_vals:
                                err_code = f"invalid_enum_value: {enum_field}"
                                node_errors.append(err_code)
                                scan_errors.append(
                                    {
                                        "rel_path": rel_posix,
                                        "domain": dom_key,
                                        "severity": "error",
                                        "error_type": "invalid_enum_value",
                                        "detail": err_code,
                                        "occurred_at": indexed_at,
                                    }
                                )

                    # Regra ADR Substituído
                    sup_status = dom_cfg.get("require_superseding_ref_when_status")
                    if sup_status and str(fm.get("status", "")).strip() == sup_status:
                        has_ref = bool(
                            (fm.get("substituida_por") and str(fm.get("substituida_por")).strip())
                            or ADR_REF_RE.search(body)
                        )
                        if not has_ref:
                            scan_errors.append(
                                {
                                    "rel_path": rel_posix,
                                    "domain": dom_key,
                                    "severity": "warning",
                                    "error_type": "missing_superseding_ref",
                                    "detail": "missing_superseding_ref: status=Substituído",
                                    "occurred_at": indexed_at,
                                }
                            )

                    # Validação sintática de caminho_drive em 05_Areas
                    if dom_key == "areas" and fm.get("caminho_drive"):
                        cd_val = str(fm.get("caminho_drive")).strip()
                        if not WINDOWS_OR_POSIX_PATH_RE.match(cd_val):
                            err_code = "invalid_drive_path_syntax: caminho_drive"
                            node_errors.append(err_code)
                            scan_errors.append(
                                {
                                    "rel_path": rel_posix,
                                    "domain": dom_key,
                                    "severity": "error",
                                    "error_type": "invalid_field_syntax",
                                    "detail": err_code,
                                    "occurred_at": indexed_at,
                                }
                            )

                # Checagem global de wikilinks absolutos fora de blocos de código
                if raw_content:
                    stripped_md = _strip_code_blocks(raw_content)
                    if wikilink_pattern.search(stripped_md):
                        err_code = "forbidden_absolute_wikilink"
                        node_errors.append(err_code)
                        scan_errors.append(
                            {
                                "rel_path": rel_posix,
                                "domain": dom_key,
                                "severity": "error",
                                "error_type": "forbidden_absolute_wikilink",
                                "detail": err_code,
                                "occurred_at": indexed_at,
                            }
                        )

                # Monta metadados normalizados do nó
                title = (
                    fm.get("projeto")
                    or fm.get("recurso")
                    or fm.get("titulo")
                    or fm.get("cliente")
                    or fm.get("area")
                    or real_f.stem.replace("_", " ")
                )
                entity_val = str(fm.get("entidade") or ("Pessoal" if dom_key == "areas" else "Todas")).strip()
                status_val = str(fm.get("status") or fm.get("status_conta") or ("Auxiliar" if fm_status == "missing" else "")).strip()
                doc_type_val = str(fm.get("tipo") or ("ADR" if dom_key == "adrs" else "")).strip()
                doc_date_val = str(fm.get("data")).strip() if fm.get("data") else None

                ports_list: List[int] = []
                if dom_key == "projects":
                    raw_ports = fm.get("portas") or []
                    if not isinstance(raw_ports, list):
                        raw_ports = [raw_ports]
                    ports_list = infra_scanner.extract_ports_from_services(raw_ports)
                elif dom_key == "infra":
                    raw_svcs = fm.get("servicos_ativos") or []
                    if not isinstance(raw_svcs, list):
                        raw_svcs = [raw_svcs]
                    ports_list = infra_scanner.extract_ports_from_services(raw_svcs)

                links_status = "not_applicable"
                if dom_key == "areas":
                    cd_str = str(fm.get("caminho_drive") or "").strip()
                    if not cd_str:
                        links_status = "non_path_reference"
                    elif os.name == "nt":
                        links_status = "accessible" if Path(cd_str).exists() else "not_mounted_in_runtime"
                    else:
                        links_status = "not_mounted_in_runtime"

                node_entry: Dict[str, Any] = {
                    "rel_path": rel_posix,
                    "domain": dom_key,
                    "entity": entity_val,
                    "title": str(title),
                    "doc_type": doc_type_val,
                    "status": status_val,
                    "frontmatter_status": fm_status,
                    "validation_errors": node_errors,
                    "links_status": links_status,
                    "ports": ports_list,
                    "size_bytes": st.st_size,
                    "doc_date": doc_date_val,
                    "indexed_at": indexed_at,
                }

                if dom_key == "adrs":
                    node_entry["adr"] = str(fm.get("adr") or real_f.stem.split("_")[0])
                    node_entry["contexto"] = str(fm.get("contexto") or "")
                elif dom_key == "infra":
                    node_entry["host"] = str(fm.get("host") or fm.get("ip_publico") or "")
                    node_entry["os"] = str(fm.get("os") or "")
                elif dom_key == "areas":
                    node_entry["area"] = str(fm.get("area") or real_f.parent.name)
                    # Projeção fechada garantida em Python para 05_Areas
                    node_entry = {k: node_entry.get(k) for k in AREAS_SAFE_FIELDS}
                elif dom_key == "projects":
                    raw_repo = str(fm.get("repositorio_local") or "").strip()
                    node_entry["repositorio_local"] = raw_repo
                    node_entry["deploy_target"] = str(fm.get("deploy_target") or "")
                    project_notes_for_reconcile.append(
                        {
                            "node_ref": node_entry,
                            "rel_path": rel_posix,
                            "title": str(title),
                            "entity": entity_val,
                            "status": status_val,
                            "raw_repo_ref": raw_repo,
                            "cockpit_id": str(fm.get("cockpit_id") or "").strip(),
                            "ports": ports_list,
                        }
                    )

                vault_nodes.append(node_entry)

            # Reconciliação N:1 e Matriz de Divergência
            project_repo_links, git_by_project_id = self._reconcile_projects(
                project_notes_for_reconcile, projects_list, indexed_at
            )

            self._last_composite_signature = composite_sig
            self._snapshot = {
                "vault_status": "available",
                "vault_error": None,
                "schema_version": schema_version,
                "schema_hash": schema_hash,
                "last_indexed_at": indexed_at,
                "entities": entities,
                "vault_nodes": vault_nodes,
                "project_repo_links": project_repo_links,
                "scan_errors": scan_errors,
                "git_by_project_id": git_by_project_id,
            }
            return self._snapshot

    def _classify_repo_path(self, raw_repo_ref: str) -> Tuple[str, Optional[Path]]:
        """
        Determina link_state ('accessible', 'not_mounted_in_runtime', 'non_path_reference', 'missing_on_disk')
        e o caminho resolvido quando acessível.
        """
        clean = scanner.sanitize_input_path(raw_repo_ref)
        if scanner.is_non_path_repo_reference(clean):
            return "non_path_reference", None

        norm_slash = clean.replace("\\", "/")

        # Verifica caminhos em drives não montados (ex.: I:\, G:\ em container Linux sem /drive_projects populado)
        if re.match(r"^[gG]:/meu drive/01 projetos(?:/|$)", norm_slash, re.IGNORECASE):
            if os.name == "nt":
                drive_root = Path("G:/Meu Drive/01 Projetos")
                if not scanner.is_mount_populated(drive_root):
                    return "not_mounted_in_runtime", None
                target = Path(clean)
                return ("accessible", target.resolve()) if target.exists() and target.is_dir() else ("missing_on_disk", None)
            else:
                dp_root = self._drive_projects_dir or Path(os.environ.get("DRIVE_PROJECTS_DIR", "/drive_projects"))
                if not scanner.is_mount_populated(dp_root):
                    return "not_mounted_in_runtime", None
                rel_after = re.sub(r"^[gG]:/meu drive/01 projetos/?", "", norm_slash, flags=re.IGNORECASE).strip("/")
                target = dp_root / rel_after
                return ("accessible", target.resolve()) if target.exists() and target.is_dir() else ("missing_on_disk", None)

        if re.match(r"^[d-zD-Z]:/", norm_slash):
            if os.name == "nt":
                drive_letter = f"{norm_slash[0]}:/"
                if not Path(drive_letter).exists():
                    return "not_mounted_in_runtime", None
                target = Path(clean)
                return ("accessible", target.resolve()) if target.exists() and target.is_dir() else ("missing_on_disk", None)
            return "not_mounted_in_runtime", None

        # C:\Docker ou caminhos locais
        if os.name != "nt" and re.match(r"^[cC]:/docker(?:/|$)", norm_slash, re.IGNORECASE):
            proj_mount = Path(os.environ.get("PROJECTS_CONTAINER_DIR", "/projects"))
            if not scanner.is_mount_populated(proj_mount):
                return "not_mounted_in_runtime", None

        resolved = scanner.resolve_cross_platform_path(clean)
        if resolved and resolved.exists() and resolved.is_dir():
            return "accessible", resolved
        return "missing_on_disk", None

    def _reconcile_projects(
        self,
        vault_projects: List[Dict[str, Any]],
        cockpit_projects: List[Dict[str, Any]],
        indexed_at: str,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """
        Executa reconciliação determinística N:1 entre fichas de 01_Projetos e data/projects.json
        e avalia as 4 condições binárias de divergência.
        """
        cockpit_by_id: Dict[str, Dict[str, Any]] = {}
        cockpit_by_key: Dict[str, Dict[str, Any]] = {}
        matched_cockpit_ids: Set[str] = set()
        git_by_project_id: Dict[str, Dict[str, Any]] = {}

        for cp in cockpit_projects:
            cid = str(cp.get("id") or "").strip()
            if not cid:
                continue
            cockpit_by_id[cid] = cp
            # Para projetos ingested: true, usa SEMPRE cp["path"] na chave de matching
            primary_path = str(cp.get("path") or "")
            key = scanner.normalize_repo_key(primary_path)
            if not key and not cp.get("ingested"):
                key = scanner.normalize_repo_key(str(cp.get("resolved_path") or ""))
            if key:
                cockpit_by_key[key] = cp

        # Agrupa fichas por normalized_repo_key para avaliar regras N:1 (portas e status Arquivado)
        notes_by_repo_key: Dict[str, List[Dict[str, Any]]] = {}
        for vp in vault_projects:
            rkey = scanner.normalize_repo_key(vp["raw_repo_ref"])
            vp["repo_key"] = rkey
            if rkey:
                notes_by_repo_key.setdefault(rkey, []).append(vp)

        # Coleta telemetria Git e portas do docker-compose uma única vez por repositório acessível
        repo_inspection_cache: Dict[str, Dict[str, Any]] = {}
        now_utc = datetime.now(timezone.utc)

        links_out: List[Dict[str, Any]] = []

        for vp in vault_projects:
            rkey = vp["repo_key"]
            matched_cp: Optional[Dict[str, Any]] = None
            if vp["cockpit_id"] and vp["cockpit_id"] in cockpit_by_id:
                matched_cp = cockpit_by_id[vp["cockpit_id"]]
            elif rkey and rkey in cockpit_by_key:
                matched_cp = cockpit_by_key[rkey]

            if matched_cp:
                matched_cockpit_ids.add(str(matched_cp.get("id")))

            link_state, resolved_dir = self._classify_repo_path(vp["raw_repo_ref"])
            vp["node_ref"]["links_status"] = link_state

            cache_key = str(resolved_dir) if resolved_dir else rkey
            if link_state == "accessible" and resolved_dir is not None:
                if cache_key not in repo_inspection_cache:
                    git_info = scanner.get_git_telemetry(resolved_dir)
                    compose_ports_set: Set[int] = set()
                    for cname in ("docker-compose.yml", "docker-compose.yaml"):
                        cfile = resolved_dir / cname
                        if cfile.exists() and cfile.is_file():
                            try:
                                ctext = cfile.read_text(encoding="utf-8", errors="replace")
                                extracted = infra_scanner.extract_compose_ports_from_content(
                                    ctext, source_id=resolved_dir.name
                                )
                                for item in extracted:
                                    compose_ports_set.add(int(item["host_port"]))
                            except Exception:
                                pass
                            break
                    repo_inspection_cache[cache_key] = {
                        "git": git_info,
                        "compose_ports": sorted(compose_ports_set),
                    }
                inspected = repo_inspection_cache[cache_key]
            else:
                inspected = {
                    "git": {
                        "is_repo": False,
                        "branch": "",
                        "is_dirty": False,
                        "uncommitted_count": 0,
                        "last_commit": "",
                        "last_commit_iso": "",
                    },
                    "compose_ports": [],
                }

            git_info = inspected["git"]
            compose_ports: List[int] = inspected["compose_ports"]

            if matched_cp and git_info.get("is_repo"):
                git_by_project_id[str(matched_cp.get("id"))] = git_info

            # Avaliação das 4 flags binárias de divergência
            divergence_flags: List[str] = []
            sibling_notes = notes_by_repo_key.get(rkey, [vp]) if rkey else [vp]

            # 1. archived_active_repo (somente quando TODAS as notas ligadas ao repo são Arquivado e há commit <= 30d ou is_dirty)
            if vp["status"] == "Arquivado" and link_state == "accessible" and git_info.get("is_repo"):
                all_archived = all(n["status"] == "Arquivado" for n in sibling_notes)
                if all_archived:
                    commit_dt = _parse_iso_datetime(git_info.get("last_commit_iso", ""))
                    recent_commit = bool(commit_dt and (now_utc - commit_dt) <= timedelta(days=30))
                    if recent_commit or bool(git_info.get("is_dirty")):
                        divergence_flags.append("archived_active_repo")

            # 2. expected_repo_missing (Produção ou Em Desenvolvimento com missing_on_disk sob mount ativo)
            if vp["status"] in ("Produção", "Producao", "Em Desenvolvimento") and link_state == "missing_on_disk":
                divergence_flags.append("expected_repo_missing")

            # 3. port_mismatch (união das portas declaradas nas notas N:1 vs portas do docker-compose do repo)
            if link_state == "accessible" and compose_ports:
                union_declared: Set[int] = set()
                for sib in sibling_notes:
                    union_declared.update(sib.get("ports", []))
                if union_declared and union_declared != set(compose_ports):
                    divergence_flags.append("port_mismatch")

            links_out.append(
                {
                    "vault_rel_path": vp["rel_path"],
                    "project_title": vp["title"],
                    "entity": vp["entity"],
                    "vault_status": vp["status"],
                    "cockpit_project_id": matched_cp.get("id") if matched_cp else None,
                    "raw_repo_ref": vp["raw_repo_ref"],
                    "normalized_repo_key": rkey,
                    "sibling_modules_count": len(sibling_notes),
                    "link_state": link_state,
                    "declared_ports": vp["ports"],
                    "compose_ports": compose_ports,
                    "git": git_info,
                    "git_checked_at": indexed_at if link_state == "accessible" else None,
                    "divergence_flags": divergence_flags,
                }
            )

        # 4. unlinked_cockpit_project (entradas em data/projects.json sem ficha correspondente em 01_Projetos)
        for cp in cockpit_projects:
            cid = str(cp.get("id") or "").strip()
            if not cid or cid in matched_cockpit_ids:
                continue
            raw_p = str(cp.get("path") or cp.get("resolved_path") or "")
            lstate, res_dir = self._classify_repo_path(raw_p)
            git_info = (
                scanner.get_git_telemetry(res_dir)
                if lstate == "accessible" and res_dir
                else {
                    "is_repo": False,
                    "branch": "",
                    "is_dirty": False,
                    "uncommitted_count": 0,
                    "last_commit": "",
                    "last_commit_iso": "",
                }
            )
            git_by_project_id[cid] = git_info
            links_out.append(
                {
                    "vault_rel_path": None,
                    "project_title": str(cp.get("name") or cid),
                    "entity": "Não vinculado",
                    "vault_status": "Sem Ficha no Vault",
                    "cockpit_project_id": cid,
                    "raw_repo_ref": raw_p,
                    "normalized_repo_key": scanner.normalize_repo_key(raw_p),
                    "sibling_modules_count": 0,
                    "link_state": lstate,
                    "declared_ports": [],
                    "compose_ports": [],
                    "git": git_info,
                    "git_checked_at": indexed_at if lstate == "accessible" else None,
                    "divergence_flags": ["unlinked_cockpit_project"],
                }
            )

        return links_out, git_by_project_id

    def get_snapshot(self, ensure_loaded: bool = True) -> Dict[str, Any]:
        if ensure_loaded and self._snapshot.get("vault_status") == "initializing":
            return self.reindex(force=False)
        return self._snapshot

    def get_status_summary(self) -> Dict[str, Any]:
        """Resumo ultra-rápido para GET /api/status (sem bloquear em I/O)."""
        snap = self._snapshot
        nodes = snap.get("vault_nodes", [])
        errors = [e for e in snap.get("scan_errors", []) if e.get("severity") == "error"]
        divergences = [l for l in snap.get("project_repo_links", []) if l.get("divergence_flags")]
        return {
            "vault_status": snap.get("vault_status", "initializing"),
            "vault_error": snap.get("vault_error"),
            "last_indexed_at": snap.get("last_indexed_at"),
            "files_total": len(nodes),
            "errors_count": len(errors),
            "divergences_count": len(divergences),
        }

    def get_entities_summary(self) -> Dict[str, Any]:
        snap = self.get_snapshot(ensure_loaded=True)
        configured_entities: List[str] = list(snap.get("entities", ["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV"]))
        all_filter_names = ["Todas"] + configured_entities
        nodes = snap.get("vault_nodes", [])
        links = snap.get("project_repo_links", [])

        out_entities: List[Dict[str, Any]] = []
        for ent_name in all_filter_names:
            ent_nodes = [n for n in nodes if _entity_matches(str(n.get("entity", "")), ent_name)]
            ent_links = [
                l
                for l in links
                if (ent_name == "Todas") or _entity_matches(str(l.get("entity", "")), ent_name)
            ]
            out_entities.append(
                {
                    "name": ent_name,
                    "projects": sum(1 for n in ent_nodes if n.get("domain") == "projects"),
                    "infra": sum(1 for n in ent_nodes if n.get("domain") == "infra"),
                    "adrs": sum(1 for n in ent_nodes if n.get("domain") == "adrs"),
                    "areas": sum(1 for n in ent_nodes if n.get("domain") == "areas"),
                    "contract_errors": sum(1 for n in ent_nodes if n.get("validation_errors")),
                    "divergences": sum(1 for l in ent_links if l.get("divergence_flags")),
                }
            )

        return {
            "vault_status": snap.get("vault_status"),
            "last_indexed_at": snap.get("last_indexed_at"),
            "entities": out_entities,
        }

    def get_overview(self, entity_filter: str = "Todas") -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        snap = self.get_snapshot(ensure_loaded=True)
        allowed_filters = ["Todas"] + list(snap.get("entities", []))
        target_entity = (entity_filter or "Todas").strip()
        if target_entity not in allowed_filters:
            return None, f"Entidade inválida: '{target_entity}'."

        nodes = [
            n
            for n in snap.get("vault_nodes", [])
            if _entity_matches(str(n.get("entity", "")), target_entity)
        ]
        node_paths = {n["rel_path"] for n in nodes}

        links = [
            l
            for l in snap.get("project_repo_links", [])
            if target_entity == "Todas" or _entity_matches(str(l.get("entity", "")), target_entity)
        ]

        errors = [
            e
            for e in snap.get("scan_errors", [])
            if target_entity == "Todas" or e.get("rel_path") in node_paths
        ]

        contract_errors_count = sum(1 for e in errors if e.get("severity") == "error")
        warnings_count = sum(1 for e in errors if e.get("severity") == "warning")
        divergences_count = sum(1 for l in links if l.get("divergence_flags"))

        return {
            "vault_status": snap.get("vault_status"),
            "vault_error": snap.get("vault_error"),
            "schema_version": snap.get("schema_version", "1.0.0"),
            "last_indexed_at": snap.get("last_indexed_at"),
            "entity": target_entity,
            "summary": {
                "total_nodes": len(nodes),
                "contract_errors": contract_errors_count,
                "warnings": warnings_count,
                "divergences": divergences_count,
            },
            "vault_nodes": nodes,
            "project_repo_links": links,
            "scan_errors": errors,
        }, None
