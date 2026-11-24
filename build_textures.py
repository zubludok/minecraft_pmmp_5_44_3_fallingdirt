from pathlib import Path
from PIL import Image
import shutil
import sys


def build_textures(resource_pack: Path) -> None:

    # Папка, в которой находится build_textures.py
    project_dir = Path(__file__).resolve().parent

    # Исходные текстуры и маски находятся вне Resource Pack
    source_dir = project_dir / "textures" / "source"
    masks_dir = project_dir / "textures" / "masks"

    # Готовые текстуры сохраняются внутри Resource Pack
    output_dir = resource_pack / "textures" / "blocks"

    if not source_dir.exists():
        raise FileNotFoundError(
            f"Не найдена папка исходных текстур: {source_dir}"
        )

    if not masks_dir.exists():
        raise FileNotFoundError(
            f"Не найдена папка масок: {masks_dir}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    # Списки успешно собранных файлов (для итогового отчёта)
    masked_files: list[str] = []   # PNG, к которым применилась маска
    copied_files: list[str] = []   # файлы, скопированные без изменений

    # Обрабатываем все файлы исходных текстур.
    for source_file in source_dir.rglob("*"):

        if not source_file.is_file():
            continue

        relative_path = source_file.relative_to(source_dir)
        output_file = output_dir / relative_path

        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Маски используются только для PNG.
        if source_file.suffix.lower() == ".png":

            mask_file = masks_dir / relative_path

            if mask_file.exists():

                with Image.open(source_file) as base_image:
                    with Image.open(mask_file) as mask_image:

                        if base_image.size != mask_image.size:
                            raise ValueError(
                                f"Размеры текстуры и маски не совпадают:\n"
                                f"Текстура: {source_file} {base_image.size}\n"
                                f"Маска: {mask_file} {mask_image.size}"
                            )

                        # RGB основной текстуры.
                        result = base_image.convert("RGB").convert("RGBA")

                        # Яркость маски переносится в Alpha.
                        alpha = mask_image.convert("L")

                        result.putalpha(alpha)

                        result.save(
                            output_file,
                            format="PNG"
                        )

                masked_files.append(relative_path.as_posix())
                print(f"[MASK] {relative_path}")

            else:
                # Если маски нет — копируем оригинал.
                shutil.copy2(source_file, output_file)
                copied_files.append(relative_path.as_posix())

                print(f"[COPY] {relative_path}")

        else:
            # Копируем остальные файлы без изменений.
            shutil.copy2(source_file, output_file)
            copied_files.append(relative_path.as_posix())

            print(f"[COPY] {relative_path}")

    # Проверяем, что маски не остались без соответствующих текстур.
    for mask_file in masks_dir.rglob("*"):

        if not mask_file.is_file():
            continue

        relative_path = mask_file.relative_to(masks_dir)

        if not (source_dir / relative_path).is_file():
            raise FileNotFoundError(
                f"Для маски не найдена основная текстура: {relative_path}"
            )

    # ------------------------------------------------------------------
    # Итоговый отчёт
    # ------------------------------------------------------------------
    print()
    print("=" * 60)
    print("Обработка текстур завершена.")
    print("=" * 60)

    if masked_files:
        print(f"\nСобрано с маской ({len(masked_files)}):")
        for path in masked_files:
            print(f"  [MASK] {path}")

    if copied_files:
        print(f"\nСкопировано без изменений ({len(copied_files)}):")
        for path in copied_files:
            print(f"  [COPY] {path}")

    print()
    print(f"Всего обработано: {len(masked_files) + len(copied_files)}")
    print(f"Объединено с масками: {len(masked_files)}")
    print(f"Скопировано без изменений: {len(copied_files)}")
    print(f"Куда сохранено: {output_dir}")


if __name__ == "__main__":
    try:
        pack_path = Path(
            sys.argv[1] if len(sys.argv) > 1
            else Path(__file__).parent / "FallingDirt"
        )

        build_textures(pack_path)

    except Exception as error:
        print()
        print(f"ОШИБКА: {error}")

    finally:
        input("\nНажми Enter для выхода...")