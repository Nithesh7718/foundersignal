import glob
import os
import socket
import sys
from urllib.parse import quote_plus, urlsplit

# Auto-add virtualenv site-packages if psycopg is not in system python
try:
    import psycopg
except ImportError:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    site_packages = glob.glob(os.path.join(base_dir, "backend", ".venv", "lib", "python3.*", "site-packages"))
    if site_packages:
        sys.path.insert(0, site_packages[0])
    try:
        import psycopg
    except ImportError:
        psycopg = None

def test_dns_and_socket(host: str, port: int):
    print(f"  [1/2] Testing TCP & DNS connectivity to {host}:{port}...")
    try:
        ip = socket.gethostbyname(host)
        print(f"        -> Resolved {host} to IP: {ip}")
    except Exception as e:
        print(f"        -> DNS Resolution FAILED for {host}: {e}")
        return False
        
    try:
        with socket.create_connection((host, port), timeout=5) as s:
            print(f"        -> TCP connection to {host}:{port} SUCCESSFUL!")
        return True
    except Exception as e:
        print(f"        -> TCP connection to {host}:{port} FAILED: {e}")
        return False

def test_database_connection(name: str, conn_str: str):
    print(f"\n=======================================================")
    print(f"Testing {name}")
    print(f"=======================================================")
    
    # Parse URL
    parsed = urlsplit(conn_str)
    host = parsed.hostname
    port = parsed.port or 5432
    
    print(f"Parsed Hostname: {host}")
    print(f"Parsed Port:     {port}")
    print(f"Parsed Username: {parsed.username}")
    print(f"Parsed Database: {parsed.path.lstrip('/')}")
    
    # Step 1: Network & DNS check
    network_ok = test_dns_and_socket(host, port)
    if not network_ok:
        return False
        
    # Step 2: PostgreSQL protocol & auth check
    print(f"  [2/2] Testing PostgreSQL Authentication with psycopg...")
    if psycopg is None:
        print("        -> Warning: psycopg library not found, skipped SQL query test.")
        print("        -> (TCP/DNS check above confirmed host is reachable).")
        return True
        
    try:
        clean_url = conn_str.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(clean_url, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
                print(f"        -> AUTHENTICATION SUCCESSFUL!")
                print(f"        -> Database: {version[:50]}...")
                
                cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';")
                tables = cur.fetchone()[0]
                print(f"        -> Public Tables Count: {tables}")
        return True
    except Exception as e:
        print(f"        -> PostgreSQL Connection Error: {e}")
        return False

if __name__ == "__main__":
    password = "founderSignal@7718"
    encoded_pw = quote_plus(password)
    
    # 1. Supabase Session Pooler (IPv4 compatible, recommended for Render)
    pooler_host = "aws-0-ap-northeast-2.pooler.supabase.com"
    pooler_user = "postgres.pbwxiagywimporzlymfj"
    pooler_url = f"postgresql+psycopg://{pooler_user}:{encoded_pw}@{pooler_host}:5432/postgres"
    
    # 2. Supabase Direct Connection (port 5432)
    direct_host = "db.pbwxiagywimporzlymfj.supabase.co"
    direct_user = "postgres"
    direct_url = f"postgresql+psycopg://{direct_user}:{encoded_pw}@{direct_host}:5432/postgres"
    
    res_pooler = test_database_connection("Supabase Session Pooler (Port 5432)", pooler_url)
    res_direct = test_database_connection("Supabase Direct Connection (Port 5432)", direct_url)
    
    print("\n================== VERIFICATION SUMMARY ==================")
    if res_pooler:
        print("\n>>> USE THIS EXACT VALUE IN RENDER:")
        print(f"DATABASE_URL={pooler_url}")
    elif res_direct:
        print("\n>>> DIRECT CONNECTION WORKED, USE THIS:")
        print(f"DATABASE_URL={direct_url}")
    else:
        print("\nBoth connection attempts failed.")
