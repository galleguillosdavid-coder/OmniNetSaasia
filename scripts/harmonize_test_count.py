import os
import sys

files_to_update = [
    "AGENTS.md",
    "README.md",
    "docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md",
    "docs/MIGRACION_BIBLIOTECAS.md",
    "PROJECT_STATE.md",
    ".continuity/STATE.md",
    ".continuity/TASK.md",
]

old_count = sys.argv[1] if len(sys.argv) > 1 else "155"
new_count = sys.argv[2] if len(sys.argv) > 2 else "156"

for rel_path in files_to_update:
    if os.path.exists(rel_path):
        with open(rel_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = (
            content.replace(f"{old_count}/{old_count}", f"{new_count}/{new_count}")
            .replace(f"{old_count} tests", f"{new_count} tests")
            .replace(f"{old_count} Pruebas", f"{new_count} Pruebas")
            .replace(f"{old_count} pruebas", f"{new_count} pruebas")
        )
        if new_content != content:
            with open(rel_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Updated {rel_path}: {old_count} -> {new_count}")
        else:
            print(f"No changes in {rel_path}")

print("Harmonization script completed.")

