import subprocess
import sys

def run(cmd):
    print(f">> Running: {cmd}")
    p = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if p.stdout:
        print(p.stdout)
    if p.returncode != 0:
        print(f"ERROR: {p.stderr}", file=sys.stderr)
        sys.exit(p.returncode)

if __name__ == "__main__":
    run("git add -A")
    run("git commit -m \"feat: integracion de Centro de Herramientas y diagnosticos al iniciar la app (138 tests OK)\"")
    run("git push origin main")
    run("git push upstream-operador main")
    print("ALL GIT COMMANDS COMPLETED SUCCESSFULLY.")

