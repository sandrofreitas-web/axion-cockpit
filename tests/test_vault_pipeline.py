#!/usr/bin/env python3
"""
test_vault_pipeline.py — Suíte isolada de testes unitários e de integração para:
- ui/vault_parser.py (BOM, escapes, listas, blocos | e >, YAML malformado/aninhado)
- ui/vault_observer.py (validação por domínio, snapshot imutável, privacidade 05_Areas, N:1 e matriz binária)
- ui/app.py (endpoints /api/status, /api/vault/*, /api/infra/config, ausência de CORS *, proteção CSRF)
Executa 100% em tempfile.TemporaryDirectory() sem depender de G:\\Meu Drive.
"""

import http.client
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "ui"))

import app
import scanner
import vault_observer
import vault_parser


SAMPLE_SCHEMA = {
    "schema_version": "1.0.0",
    "entities": ["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV"],
    "allowed_entity_values": [
        "Pessoal",
        "Axion Skill",
        "SIAE BR",
        "Igreja ICENV",
        "Todas",
        "SIAE BR & Pessoal",
    ],
    "global_rules": {
        "allowed_extensions": [".md"],
        "max_file_bytes": 524288,
        "forbid_empty_bytes": True,
        "forbid_absolute_wikilink_regex": r"\[\[[A-Za-z]:[\\/].*?\]\]",
        "ignore_code_blocks_for_wikilinks": True,
    },
    "domains": {
        "01_Projetos": {
            "domain_key": "projects",
            "recursive": True,
            "ignored_filenames": ["README.md", "_Template_Projeto.md"],
            "ignored_prefixes": ["_Template_"],
            "non_frontmatter_policy": "error",
            "required_fields": ["projeto", "entidade", "status"],
            "optional_fields": ["repositorio_local", "portas", "cockpit_id"],
            "allowed_enums": {
                "status": ["Produção", "Producao", "Em Desenvolvimento", "Planejamento", "Arquivado"],
                "entidade": ["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV", "Todas", "SIAE BR & Pessoal"],
            },
        },
        "02_Recursos_e_Infra": {
            "domain_key": "infra",
            "recursive": True,
            "ignored_filenames": ["README.md"],
            "spec_doc_filenames": ["HOME_LAB_SPECIFICATIONS.md", "Oracle.md"],
            "spec_doc_required_fields": ["titulo", "tipo", "entidade"],
            "ignored_prefixes": ["_Template_"],
            "non_frontmatter_policy": "error",
            "required_fields": ["recurso", "tipo", "entidade", "status"],
            "optional_fields": ["host", "os", "servicos_ativos"],
            "allowed_enums": {
                "status": ["Ativo / Produção", "Ativo / Desenvolvimento", "Ativo / PaaS Pronto", "Ativo"],
                "entidade": ["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV", "Todas", "SIAE BR & Pessoal"],
            },
        },
        "04_Arquitetura_ADRs": {
            "domain_key": "adrs",
            "recursive": True,
            "ignored_filenames": ["README.md"],
            "ignored_prefixes": ["_Template_"],
            "non_frontmatter_policy": "error",
            "required_fields": ["adr", "titulo", "data", "status", "entidade", "contexto"],
            "optional_fields": ["tags", "substituida_por"],
            "allowed_enums": {
                "status": ["Proposto", "Aprovado / Implementado", "Substituído"],
                "entidade": ["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV", "Todas", "SIAE BR & Pessoal"],
            },
            "require_superseding_ref_when_status": "Substituído",
        },
        "05_Areas": {
            "domain_key": "areas",
            "recursive": True,
            "ignored_filenames": ["README.md", "00_INDICE_AREAS.md"],
            "ignored_prefixes": ["_Template_"],
            "non_frontmatter_policy": "warning_non_contract",
            "required_fields": ["area", "entidade", "tipo", "caminho_drive"],
            "optional_fields": ["cliente", "status", "status_conta"],
            "allowed_enums": {
                "entidade": ["Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV", "Todas", "SIAE BR & Pessoal"],
            },
        },
    },
}


def _init_git_repo(repo_dir: Path, make_dirty: bool = False) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(repo_dir), capture_output=True, check=True)
    (repo_dir / "README.md").write_text("# Repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=str(repo_dir), capture_output=True, check=True)
    if make_dirty:
        (repo_dir / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")


class TestVaultParser(unittest.TestCase):
    def test_bom_unescape_inline_and_block_scalars(self):
        raw = (
            '\ufeff---\n'
            'projeto: "Projeto \\"Alpha\\" #1"\n'
            'repositorio_local: "C:\\\\Docker\\\\projects\\\\Project_Siaebr" # comentario externo\n'
            "nota_simples: 'Texto ''entre'' aspas e \\\\ literal'\n"
            'tags: ["um", "dois, com virgula", 3]\n'
            "resumo: |\n"
            "  Linha 1\n"
            "  Linha 2\n"
            "---\n"
            "Corpo da nota."
        )
        data, status, err, body = vault_parser.parse_frontmatter_strict(raw)
        self.assertEqual(status, "ok")
        self.assertIsNone(err)
        self.assertEqual(data["projeto"], 'Projeto "Alpha" #1')
        self.assertEqual(data["repositorio_local"], r"C:\Docker\projects\Project_Siaebr")
        self.assertEqual(data["nota_simples"], r"Texto 'entre' aspas e \\ literal")
        self.assertEqual(data["tags"], ["um", "dois, com virgula", 3])
        self.assertEqual(data["resumo"], "Linha 1\nLinha 2")
        self.assertEqual(body, "Corpo da nota.")

    def test_nested_yaml_and_unclosed_rejected_in_strict(self):
        nested = "---\nchave:\n  subchave: valor\n---\n"
        data, status, err, _ = vault_parser.parse_frontmatter_strict(nested)
        self.assertEqual(status, "malformed")
        self.assertEqual(err, "unsupported_nested_yaml")
        self.assertEqual(data, {})


class TestVaultPipelineAndRestAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()

        self.vault_root = self.base / "main_vault"
        for dom in ("01_Projetos", "02_Recursos_e_Infra", "04_Arquitetura_ADRs", "05_Areas"):
            (self.vault_root / dom).mkdir(parents=True, exist_ok=True)
        (self.vault_root / "scripts" / "harness").mkdir(parents=True, exist_ok=True)

        # Pastas sensíveis que devem ser ignoradas mesmo existindo no disco
        (self.vault_root / ".agents").mkdir(parents=True, exist_ok=True)
        (self.vault_root / ".agents" / "segredo.md").write_text("---\nprojeto: X\n---\n", encoding="utf-8")
        (self.vault_root / "02_Recursos_e_Infra" / "chaves_ssh").mkdir(parents=True, exist_ok=True)
        (self.vault_root / "02_Recursos_e_Infra" / "chaves_ssh" / "id_rsa.md").write_text("---\nrecurso: X\n---\n", encoding="utf-8")

        self.schema_path = self.vault_root / "scripts" / "harness" / "vault_schemas.json"
        self.schema_path.write_text(json.dumps(SAMPLE_SCHEMA, ensure_ascii=False, indent=2), encoding="utf-8")

        # Repositórios Git sintéticos
        self.repos_root = self.base / "repos"
        self.repo_siaebr = self.repos_root / "Project_Siaebr"
        _init_git_repo(self.repo_siaebr, make_dirty=False)
        (self.repo_siaebr / "docker-compose.yml").write_text(
            "services:\n  web:\n    ports:\n      - '8501:8501'\n  api:\n    ports:\n      - '8000:8000'\n  db:\n    ports:\n      - '5432:5432'\n",
            encoding="utf-8",
        )

        self.repo_archived_active = self.repos_root / "Legacy_Active"
        _init_git_repo(self.repo_archived_active, make_dirty=True)

        self.repo_orphan = self.repos_root / "Orphan_Repo"
        _init_git_repo(self.repo_orphan, make_dirty=False)

        # 01_Projetos: N:1 SIAEBR (união de portas: 8501, 8000 + 5432 == compose [8501, 8000, 5432] -> sem port_mismatch!)
        siae_path_escaped = str(self.repo_siaebr).replace("\\", "\\\\")
        (self.vault_root / "01_Projetos" / "SIAEBR_Project.md").write_text(
            f'---\nprojeto: "Project SIAEBR"\nentidade: "SIAE BR"\nstatus: "Produção"\nrepositorio_local: "{siae_path_escaped}"\nportas:\n  - 8501\n  - 8000\n---\n',
            encoding="utf-8",
        )
        (self.vault_root / "01_Projetos" / "SIAEBR_MatPlan.md").write_text(
            f'---\nprojeto: "MatPlan SIAEBR"\nentidade: "SIAE BR"\nstatus: "Produção"\nrepositorio_local: "{siae_path_escaped}"\nportas:\n  - 8501\n  - 5432\n---\n',
            encoding="utf-8",
        )
        # Projeto incorporado (non_path_reference) -> sem divergência
        (self.vault_root / "01_Projetos" / "Categorizador_Code.md").write_text(
            '---\nprojeto: "Categorizador"\nentidade: "Pessoal"\nstatus: "Arquivado"\nrepositorio_local: "Incorporado em G:\\\\Meu Drive\\\\01 Projetos\\\\Finaceiro_pessoal"\nportas: []\n---\n',
            encoding="utf-8",
        )
        # Projeto Arquivado porém com repo exclusivo ativo (archived_active_repo)
        legacy_escaped = str(self.repo_archived_active).replace("\\", "\\\\")
        (self.vault_root / "01_Projetos" / "Legacy_Active.md").write_text(
            f'---\nprojeto: "Legacy Active"\nentidade: "Pessoal"\nstatus: "Arquivado"\nrepositorio_local: "{legacy_escaped}"\n---\n',
            encoding="utf-8",
        )
        # Projeto ingested: true reconciliado por entry.path
        (self.vault_root / "01_Projetos" / "Financeiro_Pessoal.md").write_text(
            '---\nprojeto: "Financeiro Pessoal"\nentidade: "Pessoal"\nstatus: "Em Desenvolvimento"\nrepositorio_local: "G:\\\\Meu Drive\\\\01 Projetos\\\\Finaceiro_pessoal"\nportas:\n  - 3050\n---\n',
            encoding="utf-8",
        )

        # 02_Recursos_e_Infra: host + spec doc
        (self.vault_root / "02_Recursos_e_Infra" / "HomeLab_Notebook.md").write_text(
            '---\nrecurso: "Home Lab"\ntipo: "Server"\nentidade: "Pessoal"\nstatus: "Ativo / Produção"\nservicos_ativos:\n  - "Cockpit (:9090)"\n---\n',
            encoding="utf-8",
        )
        (self.vault_root / "02_Recursos_e_Infra" / "Oracle.md").write_text(
            '---\ntitulo: "Spec OCI"\ntipo: "Especificação Técnica"\nentidade: "Todas"\n---\n',
            encoding="utf-8",
        )

        # 04_Arquitetura_ADRs: ADR aprovada + ADR substituída com referência + wikilink dentro de código ignorado
        (self.vault_root / "04_Arquitetura_ADRs" / "ADR-004.md").write_text(
            '---\nadr: "ADR-004"\ntitulo: "Triplice"\ndata: "2026-01-01"\nstatus: "Substituído"\nentidade: "Todas"\ncontexto: "Antiga"\n---\nSubstituída pela ADR-008.\nExemplo proibido em bloco de código: `[[C:\\nao_deve_falhar]]`',
            encoding="utf-8",
        )

        # 05_Areas: ficha com dados sensíveis no corpo + nota auxiliar sem frontmatter + binário .pdf
        (self.vault_root / "05_Areas" / "ICENV_Memoria.md").write_text(
            '---\narea: "02_Igreja"\nentidade: "Igreja ICENV"\ntipo: "Memorial"\ncaminho_drive: "I:\\\\Meu Drive"\nstatus: "Ativo"\n---\nSEGREDO_BANCARIO_CNPJ_CONTA_CORRENTE_NAO_VAZAR',
            encoding="utf-8",
        )
        (self.vault_root / "05_Areas" / "One_Pager_Auxiliar.md").write_text(
            "# Documento Comercial Sem Frontmatter\nSEGREDO_AUXILIAR_NAO_VAZAR",
            encoding="utf-8",
        )
        (self.vault_root / "05_Areas" / "Apresentacao.pdf").write_bytes(b"%PDF-1.4 dummy")

        # Diretório data/ isolado
        self.data_dir = self.base / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        projects_payload = [
            {
                "id": "project-siaebr",
                "name": "Project Siaebr",
                "path": str(self.repo_siaebr),
                "resolved_path": str(self.repo_siaebr),
            },
            {
                "id": "finaceiro-pessoal",
                "name": "Personal Finance Cockpit",
                "path": "G:\\Meu Drive\\01 Projetos\\Finaceiro_pessoal",
                "resolved_path": "/app/data/ingested/finaceiro-pessoal",
                "ingested": True,
            },
            {
                "id": "orphan-proj",
                "name": "Orphan Project",
                "path": str(self.repo_orphan),
                "resolved_path": str(self.repo_orphan),
            },
        ]
        (self.data_dir / "projects.json").write_text(
            json.dumps(projects_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Inicia servidor HTTP em porta efêmera
        self.httpd = app.create_server(
            host="127.0.0.1",
            port=0,
            data_dir=self.data_dir,
            vault_root=self.vault_root,
            schema_path=self.schema_path,
            drive_projects_dir=self.base / "empty_drive_mount",
            warmup=True,
            background_warmup=False,
        )
        self.port = self.httpd.server_address[1]
        self.server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.server_thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def _request(self, method: str, path: str, body: dict = None, headers: dict = None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        req_headers = dict(headers or {})
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=payload, headers=req_headers)
        resp = conn.getresponse()
        raw = resp.read().decode("utf-8", errors="replace")
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        data = json.loads(raw) if raw else None
        return resp.status, resp_headers, data

    def test_status_and_no_cors_wildcard(self):
        status, headers, data = self._request("GET", "/api/status")
        self.assertEqual(status, 200)
        self.assertNotIn("access-control-allow-origin", headers)
        self.assertEqual(data["app"], "Nexus Cockpit")
        self.assertEqual(data["vault"]["vault_status"], "available")

        opt_status, opt_headers, _ = self._request("OPTIONS", "/api/vault/reindex")
        self.assertEqual(opt_status, 204)
        self.assertNotIn("access-control-allow-origin", opt_headers)

    def test_entities_and_overview_privacy_05_areas(self):
        status, _, ent_data = self._request("GET", "/api/vault/entities")
        self.assertEqual(status, 200)
        names = [e["name"] for e in ent_data["entities"]]
        self.assertEqual(names, ["Todas", "Pessoal", "Axion Skill", "SIAE BR", "Igreja ICENV"])

        status, _, ov_data = self._request("GET", "/api/vault/overview?entity=Todas")
        self.assertEqual(status, 200)
        raw_dump = json.dumps(ov_data, ensure_ascii=False)
        self.assertNotIn("SEGREDO_BANCARIO_CNPJ_CONTA_CORRENTE_NAO_VAZAR", raw_dump)
        self.assertNotIn("SEGREDO_AUXILIAR_NAO_VAZAR", raw_dump)

        area_nodes = [n for n in ov_data["vault_nodes"] if n["domain"] == "areas"]
        self.assertEqual(len(area_nodes), 2)
        for anode in area_nodes:
            self.assertNotIn("body", anode)
            self.assertNotIn("content", anode)
            self.assertNotIn("caminho_drive", anode)
            self.assertLessEqual(set(anode.keys()), set(vault_observer.AREAS_SAFE_FIELDS))

    def test_n_to_1_reconciliation_and_divergence_matrix(self):
        status, _, ov_data = self._request("GET", "/api/vault/overview?entity=Todas")
        self.assertEqual(status, 200)
        links_by_title = {l["project_title"]: l for l in ov_data["project_repo_links"]}

        # N:1 SIAEBR: ambos vinculados a project-siaebr e união de portas bate com compose -> sem port_mismatch
        self.assertEqual(links_by_title["Project SIAEBR"]["cockpit_project_id"], "project-siaebr")
        self.assertEqual(links_by_title["MatPlan SIAEBR"]["cockpit_project_id"], "project-siaebr")
        self.assertEqual(links_by_title["Project SIAEBR"]["sibling_modules_count"], 2)
        self.assertEqual(links_by_title["Project SIAEBR"]["divergence_flags"], [])
        self.assertEqual(links_by_title["MatPlan SIAEBR"]["divergence_flags"], [])

        # Categorizador incorporado -> non_path_reference sem divergência
        self.assertEqual(links_by_title["Categorizador"]["link_state"], "non_path_reference")
        self.assertEqual(links_by_title["Categorizador"]["divergence_flags"], [])

        # Legacy Active -> archived_active_repo
        self.assertIn("archived_active_repo", links_by_title["Legacy Active"]["divergence_flags"])

        # Financeiro Pessoal (ingested: true) -> reconciliado com finaceiro-pessoal sem virar órfão
        self.assertEqual(links_by_title["Financeiro Pessoal"]["cockpit_project_id"], "finaceiro-pessoal")

        # Orphan Project -> unlinked_cockpit_project
        self.assertIn("unlinked_cockpit_project", links_by_title["Orphan Project"]["divergence_flags"])

    def test_csrf_and_forbidden_path_hardening(self):
        # Bloqueio CSRF por Sec-Fetch-Site: cross-site
        status, _, _ = self._request(
            "POST",
            "/api/vault/reindex",
            body={"force": True},
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(status, 403)

        # Bloqueio CSRF por Origin externa
        status, _, _ = self._request(
            "POST",
            "/api/vault/reindex",
            body={"force": True},
            headers={"Origin": "https://evil.example.com"},
        )
        self.assertEqual(status, 403)

        # Bloqueio Content-Type inválido
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/vault/reindex", body=b"force=true", headers={"Content-Type": "text/plain"})
        resp = conn.getresponse()
        resp.read()
        conn.close()
        self.assertEqual(resp.status, 415)

        # Bloqueio de .agents e chaves_ssh em POST /api/infra/config
        status_agents, _, _ = self._request(
            "POST",
            "/api/infra/config",
            body={"vault_path": str(self.vault_root / ".agents")},
        )
        self.assertEqual(status_agents, 400)

        status_ssh, _, _ = self._request(
            "POST",
            "/api/infra/config",
            body={"vault_path": str(self.vault_root / "02_Recursos_e_Infra" / "chaves_ssh")},
        )
        self.assertEqual(status_ssh, 400)

    def test_graceful_degradation_preserves_snapshot(self):
        # Snapshot inicial válido possui nós
        _, _, before = self._request("GET", "/api/vault/overview?entity=Todas")
        self.assertGreater(len(before["vault_nodes"]), 0)

        # Aponta o observer para caminho inexistente e reindexa
        app.VAULT_OBSERVER._custom_vault_root = self.base / "inexistente"
        status, _, reidx = self._request("POST", "/api/vault/reindex", body={"force": True})
        self.assertEqual(status, 200)
        self.assertEqual(reidx["vault_status"], "unavailable")
        self.assertEqual(reidx["files_total"], len(before["vault_nodes"]))

        _, _, after = self._request("GET", "/api/vault/overview?entity=Todas")
        self.assertEqual(after["vault_status"], "unavailable")
        self.assertEqual(len(after["vault_nodes"]), len(before["vault_nodes"]))


if __name__ == "__main__":
    unittest.main()
