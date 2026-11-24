#!/usr/bin/env python3
"""
Скрипт форматирования geometry-файлов Bedrock.

- Рекурсивно находит все *.geo.json в папке ./geo
- В каждом файле находит все объекты вида {"origin": ... }
- Переформатирует их "в одну строку" (без переносов и лишних пробелов)
- Остальной JSON остаётся отформатированным как раньше (с отступами)

Запуск:
    python format_geo.py
    python format_geo.py --dir /path/to/geo --indent 2 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Компактная сериализация
# ---------------------------------------------------------------------------

def compact_dump(obj: Any) -> str:
    """
    Сериализует объект в максимально компактную строку:
    - без пробелов после ':' и ','
    - без пробелов внутри [] и {}
    - без переносов строк
    """
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Обход JSON и замена нужных объектов
# ---------------------------------------------------------------------------

def transform(node: Any, *, counter: list[int]) -> Any:
    """
    Рекурсивно обходит дерево JSON.
    Если встречает dict с ключом "origin" — заменяет его на специальный
    маркер-строку, которая потом будет вставлена как есть (без отступов).

    Возвращает новое дерево, где такие объекты заменены на RawJson.
    """
    if isinstance(node, dict):
        if "origin" in node:
            # Нашли целевой объект — сериализуем компактно и помечаем как raw
            counter[0] += 1
            return RawJson(compact_dump(node))
        return {k: transform(v, counter=counter) for k, v in node.items()}
    if isinstance(node, list):
        return [transform(v, counter=counter) for v in node]
    return node


class RawJson:
    """Обёртка над уже сериализованной строкой, чтобы вставить её в вывод как есть."""
    __slots__ = ("text",)

    def __init__(self, text: str) -> None:
        self.text = text


# ---------------------------------------------------------------------------
# Кастомный pretty-printer, понимающий RawJson
# ---------------------------------------------------------------------------

def pretty_dump(node: Any, indent: int = "\t", level: int = 0) -> str:
    """
    Печатает JSON с отступами, но объекты RawJson вставляет как есть (одной строкой).
    """
    pad = indent * level
    pad_inner = indent * (level + 1)

    if isinstance(node, RawJson):
        return node.text

    if isinstance(node, dict):
        if not node:
            return "{}"
        items = []
        for k, v in node.items():
            key = json.dumps(k, ensure_ascii=False)
            val = pretty_dump(v, indent=indent, level=level + 1)
            items.append(f"{pad_inner}{key}: {val}")
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"

    if isinstance(node, list):
        if not node:
            return "[]"
        items = []
        for v in node:
            val = pretty_dump(v, indent=indent, level=level + 1)
            items.append(f"{pad_inner}{val}")
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"

    return json.dumps(node, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Обработка одного файла
# ---------------------------------------------------------------------------

def process_file(path: Path, indent: int, dry_run: bool) -> int:
    try:
        original = path.read_text(encoding="utf-8")
        data = json.loads(original)
    except json.JSONDecodeError as e:
        print(f"[SKIP] {path}: JSON error: {e}", file=sys.stderr)
        return 0

    counter = [0]
    transformed = transform(data, counter=counter)

    if counter[0] == 0:
        # Ничего не нашли — файл не трогаем
        return 0

    new_text = pretty_dump(transformed, indent="\t") + "\n"

    # На всякий случай убедимся, что результат — валидный JSON
    try:
        json.loads(new_text)
    except json.JSONDecodeError as e:
        print(f"[ERROR] {path}: результат невалиден: {e}", file=sys.stderr)
        return 0

    if dry_run:
        print(f"[DRY] {path}: найдено объектов origin = {counter[0]}")
        return counter[0]

    if new_text != original:
        path.write_text(new_text, encoding="utf-8")
        print(f"[OK]  {path}: переформатировано origin-объектов = {counter[0]}")
    else:
        print(f"[=]   {path}: без изменений ({counter[0]} origin)")
    return counter[0]


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Форматирует объекты {\"origin\": ...} в *.geo.json в одну строку."
    )
    parser.add_argument(
        "--dir", default="geo", help="Папка с .geo.json (по умолчанию: ./geo)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Только показать, что будет сделано"
    )
    args = parser.parse_args()

    root = Path(args.dir)
    if not root.is_dir():
        print(f"[ERROR] Папка не найдена: {root}", file=sys.stderr)
        return 1

    files = sorted(root.rglob("*.geo.json"))
    if not files:
        print(f"[WARN] В {root} не найдено *.geo.json", file=sys.stderr)
        return 0

    total = 0
    for f in files:
        total += process_file(f, indent="\t", dry_run=args.dry_run)

    print(f"\nГотово. Файлов: {len(files)}, origin-объектов: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())