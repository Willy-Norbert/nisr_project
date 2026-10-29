"""Write a data dictionary (every dataset, row count, variables and labels) to datasets/processed/.

Run from the backend folder:  python -m scripts.build_data_dictionary
"""

import json

from app.core.config import get_settings
from app.data.loader import read_metadata
from app.data.registry import DATASETS


def main() -> None:
    settings = get_settings()
    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)

    dictionary = {}
    lines = ["# Analiza - Data dictionary", ""]
    for ds in DATASETS.values():
        if not ds.path.exists():
            print(f"MISSING  {ds.id}: {ds.path}")
            continue
        meta = read_metadata(ds)
        variables = meta.column_names_to_labels
        dictionary[ds.id] = {
            "description": ds.description,
            "path": ds.relative_path,
            "rows": meta.number_rows,
            "columns": meta.number_columns,
            "variables": variables,
        }
        print(f"OK       {ds.id}: {meta.number_rows} rows x {meta.number_columns} cols")
        lines += [f"## {ds.id}", "", f"{ds.description} - {meta.number_rows} rows, {meta.number_columns} columns", ""]
        lines += ["| Variable | Label |", "|---|---|"]
        lines += [f"| `{name}` | {(label or '').replace('|', '/')} |" for name, label in variables.items()]
        lines.append("")

    (settings.processed_data_dir / "data_dictionary.json").write_text(json.dumps(dictionary, indent=2), encoding="utf-8")
    (settings.processed_data_dir / "data_dictionary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote data dictionary for {len(dictionary)} datasets to {settings.processed_data_dir}")


if __name__ == "__main__":
    main()
