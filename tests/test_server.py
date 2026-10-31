#!/usr/bin/env python3
"""
test_server.py — Suíte de testes automatizados para o Axion Cockpit.
Valida o scanner de diretórios, extração de blocos Mermaid, proteção contra path traversal
e persistência de notas em Markdown com frontmatter.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Adiciona o diretório ui/ ao sys.path
TEST_DIR = Path(__file__).resolve().parent
REPO_ROOT = TEST_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "ui"))

import scanner
import app


class TestProjectOSScanner(unittest.TestCase):
    def test_path_validation_empty(self):
        valid, resolved, err = scanner.is_valid_project_path("")
        self.assertFalse(valid)
        self.assertIn("vazio", err.lower())

    def test_path_validation_non_existent(self):
        valid, resolved, err = scanner.is_valid_project_path("C:/caminho_inexistente_12345")
        self.assertFalse(valid)
        self.assertIn("não encontrado", err.lower())

    def test_path_validation_valid_directory(self):
        valid, resolved, err = scanner.is_valid_project_path(str(REPO_ROOT))
        self.assertTrue(valid)
        self.assertIsNone(err)
        self.assertIsNotNone(resolved)
        self.assertTrue(resolved.is_dir())

    def test_path_validation_dangerous_system_paths(self):
        for danger in scanner.DANGEROUS_SYSTEM_PATHS:
            if danger.exists():
                valid, resolved, err = scanner.is_valid_project_path(str(danger))
                self.assertFalse(valid, f"Caminho restrito não foi bloqueado: {danger}")
                self.assertIn("restrito", err.lower())

    def test_mermaid_extraction(self):
        sample_md = """
# Arquitetura

```mermaid
flowchart TD
    A --> B
```

Texto intermediário

```mermaid
erDiagram
    USER ||--o{ ORDER : places
```
"""
        blocks = scanner.extract_mermaid_blocks(sample_md)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["type"], "flowchart")
        self.assertIn("A --> B", blocks[0]["code"])
        self.assertEqual(blocks[1]["type"], "erDiagram")
        self.assertIn("USER", blocks[1]["code"])

    def test_git_telemetry_keys(self):
        telemetry = scanner.get_git_telemetry(REPO_ROOT)
        self.assertIn("is_repo", telemetry)
        self.assertIn("branch", telemetry)
        self.assertIn("is_dirty", telemetry)
        self.assertIn("uncommitted_count", telemetry)


class TestProjectOSNotesStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_note_roundtrip(self):
        note_file = self.test_path / "test_note.md"
        meta = {
            "id": "test_note",
            "title": "Minha Nota de Teste",
            "status": "planned",
            "version_target": "v1.2.0",
            "target_files": ["app.py", "scanner.py"],
        }
        body = "### Descrição\nEsta é uma nota de teste automatizado."

        app.write_markdown_note(note_file, meta, body)
        self.assertTrue(note_file.exists())

        parsed = app.parse_markdown_note(note_file)
        self.assertEqual(parsed["id"], "test_note")
        self.assertEqual(parsed["title"], "Minha Nota de Teste")
        self.assertEqual(parsed["status"], "planned")
        self.assertEqual(parsed["version_target"], "v1.2.0")
        self.assertEqual(parsed["target_files"], ["app.py", "scanner.py"])
        self.assertIn("Esta é uma nota de teste automatizado.", parsed["content"])


if __name__ == "__main__":
    unittest.main()
