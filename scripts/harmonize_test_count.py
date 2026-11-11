import os

files_to_update = [
    "AGENTS.md",
    "README.md",
    "docs/AUTONOMOUS_OPERATIONAL_MANIFESTO.md",
    "docs/MIGRACION_BIBLIOTECAS.md",
    "PROJECT_STATE.md",
    ".continuity/STATE.md",
    ".continuity/TASK.md",
]

for rel_path in files_to_update:
    if os.path.exists(rel_path):
        with open(rel_path, "r", encoding="utf-8") as f:
            content = f.read()
        new_content = content.replace("138/138", "146/146").replace("138 tests", "146 tests").replace("138 Pruebas", "146 Pruebas").replace("138 pruebas", "146 pruebas")
        if new_content != content:
            with open(rel_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Updated {rel_path}")
        else:
            print(f"No changes in {rel_path}")

print("Harmonization script completed.")
