#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Проверка JSON-геометрий Bedrock / Blockbench.
По умолчанию проверяет все *.json в папке models/blocks рядом со скриптом.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


# Ключи, допустимые в используемом формате геометрий.
# Если используешь дополнительные поля Blockbench/Bedrock — добавь их сюда.
ALLOWED_KEYS = {
    "format_version", "minecraft:geometry",
    "description", "identifier",
    "texture_width", "texture_height",
    "visible_bounds_width", "visible_bounds_height", "visible_bounds_offset",
    "bones", "name", "pivot", "rotation", "parent",
    "cubes", "origin", "size", "uv", "uv_size",
    "mirror", "inflate", "material_instance",
    "locators", "poly_mesh", "debug",
    # Названия граней в объектной UV-развёртке:
    "north", "south", "east", "west", "up", "down",
}

# Для этих полей ожидаются массивы из двух чисел.
TWO_NUMBER_ARRAY_KEYS = {"uv", "uv_size"}

# Для этих полей ожидаются массивы из трёх чисел.
THREE_NUMBER_ARRAY_KEYS = {
    "pivot", "rotation", "origin", "size", "visible_bounds_offset"
}

# Имена граней в объектной UV-развёртке.
FACE_KEYS = {"north", "south", "east", "west", "up", "down"}

# Ключи внутри описания грани (объектная UV-развёртка).
FACE_DESC_KEYS = {"uv", "uv_size", "material_instance"}

RUSSIAN_RE = re.compile(r"[А-Яа-яЁё]")


class GeometryChecker:
    def __init__(self, path: Path):
        self.path = path
        self.text = path.read_text(encoding="utf-8-sig")
        self.errors: list[tuple[int, int, str]] = []
        self.search_from = 0

    def add_error(self, line: int, column: int, message: str) -> None:
        self.errors.append((line, column, message))

    def position_for(self, token: str) -> tuple[int, int]:
        """Находит ближайшее следующее вхождение токена в исходном тексте."""
        pos = self.text.find(token, self.search_from)
        if pos < 0:
            pos = self.text.find(token)
        if pos < 0:
            return 1, 1

        self.search_from = pos + len(token)
        line = self.text.count("\n", 0, pos) + 1
        last_newline = self.text.rfind("\n", 0, pos)
        column = pos - last_newline
        return line, column

    def check_russian_letters(self) -> None:
        for match in RUSSIAN_RE.finditer(self.text):
            line = self.text.count("\n", 0, match.start()) + 1
            last_newline = self.text.rfind("\n", 0, match.start())
            column = match.start() - last_newline
            self.add_error(line, column, f"Обнаружена русская буква: {match.group()!r}")

    def check_allowed_keys(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key not in ALLOWED_KEYS:
                    line, column = self.position_for(json.dumps(key, ensure_ascii=False))
                    self.add_error(
                        line, column,
                        f"Неизвестный ключ {key!r}. Проверь написание или добавь его в ALLOWED_KEYS."
                    )
                self.check_allowed_keys(child)
        elif isinstance(value, list):
            for child in value:
                self.check_allowed_keys(child)

    # ------------------------------------------------------------------
    # Проверка числовых массивов с учётом объектной UV-развёртки
    # ------------------------------------------------------------------

    def _check_number_array(
        self, key: str, value: Any, expected: int, context: str = ""
    ) -> bool:
        """
        Проверяет, что value — массив ровно из expected чисел.
        Возвращает True, если всё ок (или если проверка не применима).
        """
        line, column = self.position_for(json.dumps(key))
        if not isinstance(value, list):
            self.add_error(
                line, column,
                f'Поле "{key}"{context} должно быть массивом из {expected} чисел.'
            )
            return False
        if len(value) != expected:
            self.add_error(
                line, column,
                f'Поле "{key}"{context} содержит {len(value)} значений, ожидалось {expected}.'
            )
            return False
        if any(isinstance(n, bool) or not isinstance(n, (int, float)) for n in value):
            self.add_error(
                line, column,
                f'Массив "{key}"{context} должен содержать только числа.'
            )
            return False
        return True

    def _check_face_object(self, face_name: str, face_value: Any) -> None:
        """
        Проверяет одну грань объектной UV-развёртки:
        {"uv": [x, y], "uv_size": [w, h], "material_instance": "..."} 
        """
        if not isinstance(face_value, dict):
            line, column = self.position_for(json.dumps(face_name))
            self.add_error(
                line, column,
                f'Грань "{face_name}" должна быть объектом с полями uv/uv_size.'
            )
            return

        for sub_key, sub_value in face_value.items():
            if sub_key not in FACE_DESC_KEYS:
                line, column = self.position_for(json.dumps(sub_key))
                self.add_error(
                    line, column,
                    f'Неизвестный ключ {sub_key!r} в описании грани "{face_name}".'
                )
                continue

            if sub_key in ("uv", "uv_size"):
                self._check_number_array(
                    sub_key, sub_value, 2, context=f' (грань "{face_name}")'
                )
            elif sub_key == "material_instance":
                if not isinstance(sub_value, str):
                    line, column = self.position_for(json.dumps(sub_key))
                    self.add_error(
                        line, column,
                        f'"material_instance" в грани "{face_name}" должно быть строкой.'
                    )

    def _check_uv_value(self, uv_value: Any) -> None:
        """
        Проверяет значение поля "uv" у куба. Оно может быть:
          1) массивом из 2 чисел: [x, y];
          2) объектом с гранями: {"north": {...}, "east": {...}, ...}.
        """
        if isinstance(uv_value, dict):
            # Объектная UV-развёртка — это НЕ ошибка.
            if not uv_value:
                line, column = self.position_for('"uv"')
                self.add_error(
                    line, column,
                    'Объектная UV-развёртка "uv" пуста.'
                )
                return

            for face_name, face_value in uv_value.items():
                if face_name in FACE_KEYS:
                    self._check_face_object(face_name, face_value)
                elif face_name == "material_instance":
                    # Допустим вариант, когда material_instance стоит на уровне uv
                    # (некоторые генераторы так делают).
                    if not isinstance(face_value, str):
                        line, column = self.position_for(json.dumps(face_name))
                        self.add_error(
                            line, column,
                            '"material_instance" в uv должно быть строкой.'
                        )
                else:
                    line, column = self.position_for(json.dumps(face_name))
                    self.add_error(
                        line, column,
                        f'Неизвестная грань {face_name!r} в объектной UV-развёртке. '
                        f'Ожидались: north, south, east, west, up, down.'
                    )
            return

        # Иначе — обычный массив [x, y]
        self._check_number_array("uv", uv_value, 2)

    def check_numeric_arrays(self, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "uv":
                    # Особый случай: uv может быть массивом ИЛИ объектом граней.
                    self._check_uv_value(child)
                else:
                    expected = None
                    if key in TWO_NUMBER_ARRAY_KEYS:
                        expected = 2
                    elif key in THREE_NUMBER_ARRAY_KEYS:
                        expected = 3

                    if expected is not None:
                        self._check_number_array(key, child, expected)

                # Рекурсивно идём глубже (важно: для объектной uv
                # дальше проверять нечего, но для остальных полей — нужно).
                if key != "uv" or not isinstance(child, dict):
                    self.check_numeric_arrays(child)

        elif isinstance(value, list):
            for child in value:
                self.check_numeric_arrays(child)

    def check_geometry_names(self, data: Any) -> None:
        if not isinstance(data, dict):
            self.add_error(1, 1, "Корневой элемент JSON должен быть объектом.")
            return

        geometries = data.get("minecraft:geometry")
        if not isinstance(geometries, list):
            line, column = self.position_for('"minecraft:geometry"')
            self.add_error(
                line, column,
                'Ожидался массив "minecraft:geometry".'
            )
            return

        if not geometries:
            line, column = self.position_for('"minecraft:geometry"')
            self.add_error(line, column, 'Массив "minecraft:geometry" пуст.')

        seen: set[str] = set()
        for index, geometry in enumerate(geometries):
            if not isinstance(geometry, dict):
                self.add_error(1, 1, f"Геометрия №{index + 1} должна быть объектом.")
                continue

            description = geometry.get("description")
            if not isinstance(description, dict):
                self.add_error(1, 1, f"У геометрии №{index + 1} отсутствует объект description.")
                continue

            identifier = description.get("identifier")
            if not isinstance(identifier, str) or not identifier.strip():
                line, column = self.position_for('"description"')
                self.add_error(
                    line, column,
                    f"У геометрии №{index + 1} отсутствует корректный identifier."
                )
                continue

            if identifier in seen:
                line, column = self.position_for(json.dumps(identifier))
                self.add_error(
                    line, column,
                    f"Повторяется identifier геометрии: {identifier!r}."
                )
            seen.add(identifier)

            bones = geometry.get("bones")
            if not isinstance(bones, list):
                line, column = self.position_for('"bones"')
                self.add_error(
                    line, column,
                    f'У геометрии "{identifier}" поле bones должно быть массивом.'
                )

        print(f"Геометрий найдено: {len(geometries)}")
        print("Идентификаторы геометрий:")
        for identifier in sorted(seen):
            print(f"  - {identifier}")

    def check(self) -> None:
        print(f"\nПроверка: {self.path}")

        self.check_russian_letters()

        try:
            data = json.loads(self.text)
        except json.JSONDecodeError as exc:
            self.add_error(
                exc.lineno, exc.colno,
                f"Ошибка JSON: {exc.msg}"
            )
            self.print_errors()
            return
        except Exception as exc:
            self.add_error(1, 1, f"Не удалось прочитать JSON: {exc}")
            self.print_errors()
            return

        self.check_allowed_keys(data)
        self.check_numeric_arrays(data)
        self.check_geometry_names(data)
        self.print_errors()

    def print_errors(self) -> None:
        if not self.errors:
            print("Ошибок не найдено.")
            return

        print(f"\nНайдено ошибок: {len(self.errors)}")
        for line, column, message in sorted(self.errors):
            lines = self.text.splitlines()
            source_line = lines[line - 1] if 0 < line <= len(lines) else ""
            start = max(0, column - 1 - 10)
            end = min(len(source_line), column - 1 + 10)
            excerpt = source_line[start:end]
            print(f"\n[{line}:{column}] {message}")
            print(f"    ...{excerpt}...")


def main() -> None:
    script_dir = Path(__file__).resolve().parent
    target_dir = script_dir / "FallingDirt" / "models" / "blocks"

    # Если скрипт лежит непосредственно внутри FallingDirt, используем этот путь.
    if not target_dir.is_dir():
        target_dir = script_dir / "models" / "blocks"

    if not target_dir.is_dir():
        print("Не найдена папка models/blocks.")
        print("Положи скрипт рядом с папкой FallingDirt либо внутрь FallingDirt.")
        input("\nНажми Enter для выхода...")
        return

    files = sorted(target_dir.rglob("*.json"))
    if not files:
        print(f"В папке нет JSON-файлов: {target_dir}")
        input("\nНажми Enter для выхода...")
        return

    print(f"Найдено JSON-файлов: {len(files)}")
    total_errors = 0

    for file_path in files:
        checker = GeometryChecker(file_path)
        checker.check()
        total_errors += len(checker.errors)

    print("\n" + "=" * 60)
    print(f"Проверено файлов: {len(files)}")
    print(f"Всего ошибок: {total_errors}")
    print("=" * 60)
    input("\nПроверка завершена. Нажми Enter для выхода...")


if __name__ == "__main__":
    main()