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
        new_content = content.replace("146/146", "147/147").replace("146 tests", "147 tests").replace("146 Pruebas", "147 Pruebas").replace("146 pruebas", "147 pruebas")
        if new_content != content:
            with open(rel_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"Updated {rel_path}")
        else:
            print(f"No changes in {rel_path}")

print("Harmonization script completed.")

