from __future__ import annotations

from pathlib import Path

from dv_agent.parser.options import ParseOptions


def discover_sql_paths(path: Path, options: ParseOptions) -> list[Path]:
    """
    Найти SQL-файлы по пути:
    - один файл .sql / .ddl
    - каталог (плоский или рекурсивный)
    - glob-паттерн в имени (например /data/**/*.sql)
    """
    path = path.expanduser().resolve()

    if path.is_file():
        if path.suffix.lower() in {".sql", ".ddl"}:
            return [path]
        raise ValueError(f"Не SQL-файл: {path}")

    if path.is_dir():
        files: list[Path] = []
        for pattern in options.patterns:
            globber = path.rglob if options.recursive else path.glob
            files.extend(globber(pattern))
        return sorted({f.resolve() for f in files if f.is_file()})

    # glob в строке пути
    if any(ch in str(path) for ch in "*?[]"):
        return sorted(p.resolve() for p in Path().glob(str(path)) if p.is_file())

    raise FileNotFoundError(f"Путь не найден: {path}")
