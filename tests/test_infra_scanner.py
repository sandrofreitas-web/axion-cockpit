#!/usr/bin/env python3
"""
test_infra_scanner.py — Suíte de testes automatizados para o scanner de infraestrutura e subsistemas.
Valida o parser de frontmatter YAML (delegado a vault_parser), extração de portas,
detector de colisões de porta e o cache TTL in-memory.
"""

import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "ui"))

import infra_scanner


class TestInfraScanner(unittest.TestCase):
    def test_parse_frontmatter_valid(self):
        sample_md = """---
recurso: "Home Lab Notebook"
tipo: "Bare-Metal Server (24/7)"
entidade: "Pessoal"
host: 192.168.15.176
os: 'Ubuntu Server'
status: "Ativo / Produção"
servicos_ativos:
  - "Cockpit (:9090)"
  - "Portainer (:9000 / :9443)"
  - Tailscale VPN
tags:
  - recurso
  - homelab
---

# Conteúdo Markdown do host...
"""
        parsed = infra_scanner.parse_yaml_frontmatter(sample_md)
        self.assertEqual(parsed["recurso"], "Home Lab Notebook")
        self.assertEqual(parsed["tipo"], "Bare-Metal Server (24/7)")
        self.assertEqual(parsed["entidade"], "Pessoal")
        self.assertEqual(parsed["host"], "192.168.15.176")
        self.assertEqual(parsed["os"], "Ubuntu Server")
        self.assertEqual(parsed["status"], "Ativo / Produção")
        self.assertEqual(len(parsed["servicos_ativos"]), 3)
        self.assertIn("Cockpit (:9090)", parsed["servicos_ativos"])
        self.assertIn("Tailscale VPN", parsed["servicos_ativos"])
        self.assertEqual(parsed["tags"], ["recurso", "homelab"])

    def test_parse_frontmatter_unclosed(self):
        sample_md = """---
recurso: "Servidor Sem Fechamento"
host: "10.0.0.1"

Conteúdo sem o delimitador final.
"""
        parsed = infra_scanner.parse_yaml_frontmatter(sample_md)
        self.assertEqual(parsed, {})

    def test_extract_ports_from_services(self):
        services = [
            "Immich (:2283)",
            "Sistema de Obras (:3080 / :8080 / :5435)",
            "Tailscale VPN",
            "Cockpit (:9090)",
            "3050 (Frontend PWA)",
            8050,
        ]
        ports = infra_scanner.extract_ports_from_services(services)
        self.assertEqual(ports, [2283, 3050, 3080, 5435, 8050, 8080, 9090])

    def test_extract_compose_ports(self):
        sample_compose = """
version: '3.8'
services:
  web:
    image: python:3.12-slim
    ports:
      - "8080:80"
      - 5432:5432
      - "127.0.0.1:9090:9090"
      - "3000"
  worker:
    image: redis:alpine
    ports:
      - 6379:6379/tcp
"""
        ports = infra_scanner.extract_compose_ports_from_content(
            sample_compose, source_id="test-proj"
        )
        self.assertEqual(len(ports), 5)

        port_map = {p["host_port"]: p["container_port"] for p in ports}
        self.assertEqual(port_map[8080], 80)
        self.assertEqual(port_map[5432], 5432)
        self.assertEqual(port_map[9090], 9090)
        self.assertEqual(port_map[3000], 3000)
        self.assertEqual(port_map[6379], 6379)

    def test_detect_port_collisions(self):
        vault_resources = [
            {
                "id": "homelab",
                "recurso": "Homelab Notebook",
                "ports": [8080, 5432],
            }
        ]
        project_ports = [
            {
                "host_port": 8080,
                "container_port": 80,
                "source_type": "project_compose",
                "source_id": "nexus-cockpit",
                "source_label": "Nexus Cockpit (web)",
            },
            {
                "host_port": 3000,
                "container_port": 3000,
                "source_type": "project_compose",
                "source_id": "frontend-app",
                "source_label": "Frontend App (web)",
            },
        ]
        result = infra_scanner.detect_port_collisions(vault_resources, project_ports)
        self.assertEqual(result["collision_count"], 1)
        self.assertEqual(len(result["collisions"]), 1)
        collision = result["collisions"][0]
        self.assertEqual(collision["host_port"], 8080)
        self.assertEqual(collision["collision_count"], 2)
        self.assertIn("Homelab Notebook", str(collision["conflicting_sources"]))

    def test_cache_ttl_and_force_refresh_and_spec_docs_ignored(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            md_file = tmppath / "test_host.md"
            md_file.write_text(
                "---\nrecurso: Host 1\ntipo: VPS\nstatus: Ativo\nservicos_ativos:\n  - App (:8000)\n---\n",
                encoding="utf-8",
            )
            (tmppath / "Oracle.md").write_text(
                "---\ntitulo: Spec\ntipo: Especificação Técnica\nentidade: Todas\n---\n",
                encoding="utf-8",
            )

            infra_scanner.invalidate_cache()
            catalog1 = infra_scanner.scan_infrastructure_directory(tmppath)
            self.assertEqual(len(catalog1["resources"]), 1)
            self.assertEqual(catalog1["resources"][0]["recurso"], "Host 1")

            md_file.write_text(
                "---\nrecurso: Host Modificado\ntipo: VPS\nstatus: Ativo\nservicos_ativos:\n  - App (:8000)\n---\n",
                encoding="utf-8",
            )

            catalog2 = infra_scanner.scan_infrastructure_directory(
                tmppath, force_refresh=False
            )
            self.assertEqual(catalog2["resources"][0]["recurso"], "Host 1")

            catalog3 = infra_scanner.scan_infrastructure_directory(
                tmppath, force_refresh=True
            )
            self.assertEqual(catalog3["resources"][0]["recurso"], "Host Modificado")


if __name__ == "__main__":
    unittest.main()
