import glob
import os
import sys
from urllib.parse import quote_plus

# Ensure backend .venv packages are available
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.join(base_dir, "backend")
site_packages = glob.glob(os.path.join(backend_dir, ".venv", "lib", "python3.*", "site-packages"))
if site_packages:
    sys.path.insert(0, site_packages[0])
sys.path.insert(0, backend_dir)

def run_migrations():
    # The actual password verified in test_supabase_connection.py
    password = "founderSignal@7718"
    encoded_pw = quote_plus(password)
    pooler_host = "aws-0-ap-northeast-2.pooler.supabase.com"
    pooler_user = "postgres.pbwxiagywimporzlymfj"
    pooler_url = f"postgresql+psycopg://{pooler_user}:{encoded_pw}@{pooler_host}:5432/postgres"

    print("==================================================")
    print("Applying Alembic Migrations to Supabase...")
    print(f"Target Pooler: {pooler_host}:5432")
    print(f"Database User: {pooler_user}")
    print("==================================================")

    # Change to backend directory so alembic.ini and env.py are loaded
    os.chdir(backend_dir)
    os.environ["DATABASE_URL"] = pooler_url

    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config("alembic.ini")

    try:
        command.upgrade(alembic_cfg, "head")
        print("\nSUCCESS! All database migrations applied successfully to Supabase.")
    except Exception as exc:
        print(f"\nMigration failed with error: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()
