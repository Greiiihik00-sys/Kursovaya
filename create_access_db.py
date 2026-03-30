from pathlib import Path
import msaccessdb

base = Path(__file__).resolve().parent
db_dir = base / "data"
db_dir.mkdir(exist_ok=True)
db_path = db_dir / "autoflow.accdb"

if db_path.exists():
    print(f"Access DB already exists: {db_path}")
else:
    msaccessdb.create(str(db_path))
    print(f"Access DB created: {db_path}")
    