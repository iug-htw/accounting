import subprocess
import os
from datetime import datetime

PROJECT_DIR = "/home/klntama/individuelles-tempo"
DB_FILE = "db.sqlite3"
BACKUP_BRANCH = "db-backup"
MAIN_BRANCH = "branch1"

def run(command):
    result = subprocess.run(command, cwd=PROJECT_DIR, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Fehler bei: {command}\n{result.stderr}")
        exit(1)
    return result.stdout

print("Starte einfaches DB-Backup...")

# 1. Sicherstellen, dass branch1 aktuell ist
run(f"git checkout {MAIN_BRANCH}")
run(f"git pull origin {MAIN_BRANCH}")

# 2. In Backup-Branch wechseln & Datei kopieren
run(f"git checkout {BACKUP_BRANCH}")
run(f"git pull origin {BACKUP_BRANCH}")

# 3. Kopieren
source_path = os.path.join(PROJECT_DIR, DB_FILE)
target_path = os.path.join(PROJECT_DIR, DB_FILE)
run(f"git checkout {MAIN_BRANCH} -- {DB_FILE}")

# 4. Commit + Push
commit_message = f"DB-Backup {datetime.now().strftime('%Y-%m-%d %H:%M')}"
run(f"git add {DB_FILE}")
run(f'git commit -m "{commit_message}"')
run(f"git push origin {BACKUP_BRANCH}")

print("Backup abgeschlossen.")
