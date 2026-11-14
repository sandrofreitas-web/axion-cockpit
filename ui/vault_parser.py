#!/usr/bin/env python3
"""
vault_parser.py — Parser YAML unificado para frontmatter Markdown usando apenas Python stdlib.

Suporta:
- Remoção de UTF-8 BOM (\\ufeff)
- Delimitação estrita de bloco '---'
- Desescape de \\\\ e \\" em strings entre aspas duplas e '' em aspas simples
- Isolamento de comentários '#' fora de strings
- Listas inline ([a, b]) e listas multiline (- item)
- Escalares de bloco ('|' e '>')
- Detecção explícita de frontmatter ausente, não fechado ou com chaves aninhadas não suportadas
- Preservação de campos ausentes (sem defaults artificiais no modo estrito)
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


KEY_REGEX = re.compile(r"^([A-Za-z0-9_.-]+)\s*:\s*(.*)$")


def escape_yaml_double_quoted(value: Any) -> str:
    """Escapa barras invertidas e aspas duplas para gravação simétrica em frontmatter YAML."""
    text = "" if value is None else str(value)
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _strip_inline_comment(line: str) -> str:
    """Remove comentários '# ...' apenas quando '#' estiver fora de aspas simples ou duplas."""
    in_single = False
    in_double = False
    escaped = False
    for idx, ch in enumerate(line):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and in_double:
            escaped = True
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif ch == "#" and not in_single and not in_double:
            if idx == 0 or line[idx - 1].isspace():
                return line[:idx].rstrip()
    return line.rstrip()


def _parse_scalar_token(raw_val: str) -> Any:
    """Converte um token escalar YAML (string com/sem aspas, bool ou int simples)."""
    val = raw_val.strip()
    if not val:
        return ""

    if len(val) >= 2 and val.startswith('"') and val.endswith('"'):
        inner = val[1:-1]
        out: List[str] = []
        i = 0
        while i < len(inner):
            ch = inner[i]
            if ch == "\\" and i + 1 < len(inner):
                nxt = inner[i + 1]
                if nxt in ('\\', '"'):
                    out.append(nxt)
                elif nxt == "n":
                    out.append("\n")
                elif nxt == "t":
                    out.append("\t")
                else:
                    out.append(nxt)
                i += 2
            else:
                out.append(ch)
                i += 1
        return "".join(out)

    if len(val) >= 2 and val.startswith("'") and val.endswith("'"):
        return val[1:-1].replace("''", "'")

    low = val.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~"):
        return None

    if re.fullmatch(r"-?\d+", val):
        try:
            return int(val)
        except ValueError:
            return val

    return val


def _split_inline_array(inner: str) -> List[Any]:
    """Divide os elementos de uma lista inline '[a, b]' respeitando aspas e escapes."""
    if not inner.strip():
        return []
    items: List[Any] = []
    buf: List[str] = []
    in_single = False
    in_double = False
    escaped = False

    for ch in inner:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\" and in_double:
            buf.append(ch)
            escaped = True
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
        elif ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
        elif ch == "," and not in_single and not in_double:
            token = "".join(buf).strip()
            if token:
                items.append(_parse_scalar_token(token))
            buf = []
        else:
            buf.append(ch)

    last = "".join(buf).strip()
    if last:
        items.append(_parse_scalar_token(last))
    return items


def parse_frontmatter_strict(
    content: str,
) -> Tuple[Dict[str, Any], str, Optional[str], str]:
    """
    Analisa o frontmatter YAML em modo estrito sem injetar defaults artificiais.

    Retorna:
        (data, frontmatter_status, error_detail, body)
        onde frontmatter_status pertence a ("ok", "missing", "malformed").
    """
    if not content:
        return {}, "missing", "empty_content", ""

    clean = content[1:] if content.startswith("\ufeff") else content
    lines = clean.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, "missing", None, clean

    end_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break

    if end_idx == -1:
        return {}, "malformed", "unclosed_frontmatter_delimiter", ""

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1 :]).strip()

    data: Dict[str, Any] = {}
    current_list_key: Optional[str] = None
    block_scalar_key: Optional[str] = None
    block_scalar_style: Optional[str] = None
    block_scalar_lines: List[str] = []
    block_scalar_indent: Optional[int] = None

    def flush_block_scalar() -> None:
        nonlocal block_scalar_key, block_scalar_style, block_scalar_lines, block_scalar_indent
        if block_scalar_key is not None:
            if block_scalar_style == ">":
                data[block_scalar_key] = " ".join(
                    s.strip() for s in block_scalar_lines if s.strip()
                )
            else:
                data[block_scalar_key] = "\n".join(block_scalar_lines).rstrip("\n")
        block_scalar_key = None
        block_scalar_style = None
        block_scalar_lines = []
        block_scalar_indent = None

    for raw_line in fm_lines:
        if block_scalar_key is not None:
            if not raw_line.strip():
                block_scalar_lines.append("")
                continue
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            if indent > 0:
                if block_scalar_indent is None:
                    block_scalar_indent = indent
                cut = min(indent, block_scalar_indent)
                block_scalar_lines.append(raw_line[cut:])
                continue
            flush_block_scalar()

        line_no_comment = _strip_inline_comment(raw_line)
        stripped = line_no_comment.strip()
        if not stripped:
            continue

        indent = len(line_no_comment) - len(line_no_comment.lstrip(" "))

        if stripped.startswith("- ") or stripped == "-":
            if not current_list_key:
                return {}, "malformed", "orphan_list_item", body
            item_raw = stripped[2:].strip() if len(stripped) >= 2 else ""
            if not isinstance(data.get(current_list_key), list):
                data[current_list_key] = []
            data[current_list_key].append(_parse_scalar_token(item_raw))
            continue

        if indent > 0:
            return {}, "malformed", "unsupported_nested_yaml", body

        m_key = KEY_REGEX.match(stripped)
        if not m_key:
            return {}, "malformed", f"invalid_yaml_line: {stripped[:40]}", body

        key = m_key.group(1).strip()
        val = m_key.group(2).strip()

        if val in ("|", ">", "|-", ">-"):
            block_scalar_key = key
            block_scalar_style = ">" if val.startswith(">") else "|"
            block_scalar_lines = []
            block_scalar_indent = None
            current_list_key = None
            continue

        if val.startswith("[") and val.endswith("]"):
            data[key] = _split_inline_array(val[1:-1])
            current_list_key = None
        elif val == "":
            data[key] = []
            current_list_key = key
        else:
            data[key] = _parse_scalar_token(val)
            current_list_key = None

    flush_block_scalar()
    return data, "ok", None, body


def parse_frontmatter(content: str) -> Dict[str, Any]:
    """
    Parser de frontmatter YAML compatível com o contrato de dict plano legado.
    Retorna {} quando o frontmatter estiver ausente ou malformado.
    """
    data, status, _, _ = parse_frontmatter_strict(content)
    if status != "ok":
        return {}
    return data


def parse_vault_file(path: Path, max_bytes: int = 524288) -> Dict[str, Any]:
    """
    Lê um arquivo Markdown do vault respeitando o limite de bytes e retorna
    metadados de parsing estruturados.
    """
    st = path.stat()
    if st.st_size == 0:
        return {
            "frontmatter": {},
            "frontmatter_status": "missing",
            "error_detail": "empty_file_zero_bytes",
            "body": "",
            "size_bytes": 0,
            "mtime_ns": st.st_mtime_ns,
        }
    if st.st_size > max_bytes:
        return {
            "frontmatter": {},
            "frontmatter_status": "malformed",
            "error_detail": "file_too_large",
            "body": "",
            "size_bytes": st.st_size,
            "mtime_ns": st.st_mtime_ns,
        }

    content = path.read_text(encoding="utf-8")
    fm, status, err_detail, body = parse_frontmatter_strict(content)
    return {
        "frontmatter": fm,
        "frontmatter_status": status,
        "error_detail": err_detail,
        "body": body,
        "raw_content": content,
        "size_bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns,
    }
