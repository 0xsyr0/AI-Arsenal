#!/usr/bin/env python3
"""
dbshell.py — Interactive MariaDB client via Docker exec
Usage: python3 dbshell.py [--container NAME] [--host HOST] [--port PORT]
                          [--user USER] [--password PASS] [--database DB]
"""

import argparse
import subprocess
import sys
import os
import shlex

# ── Optional: direct TCP connection via pymysql ─────────────────────────────
try:
    import pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False


# ── Helpers ─────────────────────────────────────────────────────────────────

def banner():
    print("""
  ██████╗ ██████╗ ███████╗██╗  ██╗███████╗██╗     ██╗
  ██╔══██╗██╔══██╗██╔════╝██║  ██║██╔════╝██║     ██║
  ██║  ██║██████╔╝███████╗███████║█████╗  ██║     ██║
  ██║  ██║██╔══██╗╚════██║██╔══██║██╔══╝  ██║     ██║
  ██████╔╝██████╔╝███████║██║  ██║███████╗███████╗███████╗
  ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝
  MariaDB Shell  |  docker-exec / pymysql mode
""")


def color(text, code):
    return f"\033[{code}m{text}\033[0m"

def info(msg):  print(color(f"[*] {msg}", "34"))
def ok(msg):    print(color(f"[+] {msg}", "32"))
def err(msg):   print(color(f"[-] {msg}", "31"), file=sys.stderr)
def warn(msg):  print(color(f"[!] {msg}", "33"))


# ── Container discovery ──────────────────────────────────────────────────────

def find_container_ids():
    """Read container IDs from /var/lib/docker/containers/ if accessible."""
    base = "/var/lib/docker/containers"
    if not os.path.isdir(base):
        return []
    return [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]


def inspect_container(cid_or_name):
    """Run docker inspect and return parsed JSON."""
    import json
    try:
        out = subprocess.check_output(
            ["docker", "inspect", cid_or_name],
            stderr=subprocess.DEVNULL
        )
        return json.loads(out)
    except Exception:
        return None


def guess_container(candidates=None):
    """Try common names, then fall back to filesystem discovery."""
    common_names = ["mariadb", "mysql", "db", "database", "mariadb-db",
                    "mysql-db", "app-db", "db-1", "mariadb-1", "mysql-1"]

    # Try guessable names first
    for name in (candidates or common_names):
        info(f"Trying container name: {name}")
        data = inspect_container(name)
        if data:
            ok(f"Found container: {name}")
            return name

    # Fallback: filesystem scan
    ids = find_container_ids()
    if not ids:
        return None

    import json
    for cid in ids:
        cfg_path = f"/var/lib/docker/containers/{cid}/config.v2.json"
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
            image = cfg.get("Config", {}).get("Image", "")
            if any(k in image.lower() for k in ["mariadb", "mysql"]):
                ok(f"Found via filesystem: {cid[:12]} ({image})")
                return cid
        except Exception:
            continue

    return None


def extract_env_creds(container):
    """Pull DB credentials from container environment variables."""
    data = inspect_container(container)
    if not data:
        return {}

    env_list = data[0].get("Config", {}).get("Env", [])
    creds = {}
    key_map = {
        "MARIADB_ROOT_PASSWORD": "password",
        "MYSQL_ROOT_PASSWORD":   "password",
        "MARIADB_PASSWORD":      "password",
        "MYSQL_PASSWORD":        "password",
        "MARIADB_USER":          "user",
        "MYSQL_USER":            "user",
        "MARIADB_DATABASE":      "database",
        "MYSQL_DATABASE":        "database",
    }
    for entry in env_list:
        k, _, v = entry.partition("=")
        if k in key_map and key_map[k] not in creds:
            creds[key_map[k]] = v

    return creds


# ── Docker-exec mode ─────────────────────────────────────────────────────────

def docker_exec_query(container, user, password, database, query):
    """Execute a single query via docker exec, return stdout."""
    cmd = [
        "docker", "exec", container,
        "mariadb", "-u", user, f"-p{password}",
        "--batch", "--silent",
    ]
    if database:
        cmd += [database]
    cmd += ["-e", query]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return "", "Query timed out."
    except FileNotFoundError:
        return "", "docker binary not found."


def shell_docker(container, user, password, database):
    """Interactive REPL using docker exec for each query."""
    ok(f"Connected via docker exec → {container}")
    if database:
        info(f"Default database: {database}")
    print(color("  Type SQL queries, 'use <db>', 'exit' or 'quit' to leave.\n", "90"))

    current_db = database

    while True:
        prompt = color(f"mariadb [{current_db or 'none'}]> ", "36")
        try:
            query = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", r"\q"):
            print("Bye.")
            break

        # Handle USE locally to track current DB
        if query.lower().startswith("use "):
            current_db = query.split()[1].rstrip(";")

        stdout, stderr = docker_exec_query(container, user, password, current_db, query)

        if stderr and "using a password" not in stderr.lower():
            err(stderr.strip())
        if stdout:
            print(stdout, end="" if stdout.endswith("\n") else "\n")


# ── pymysql direct TCP mode ──────────────────────────────────────────────────

def get_container_ip(container):
    """Extract the first bridge IP from docker inspect."""
    data = inspect_container(container)
    if not data:
        return None
    networks = data[0].get("NetworkSettings", {}).get("Networks", {})
    for net in networks.values():
        ip = net.get("IPAddress")
        if ip:
            return ip
    return None


def shell_pymysql(host, port, user, password, database):
    """Interactive REPL using a persistent pymysql connection."""
    try:
        conn = pymysql.connect(
            host=host, port=port,
            user=user, password=password,
            database=database or None,
            autocommit=True,
            connect_timeout=5,
        )
    except pymysql.err.OperationalError as e:
        err(f"Connection failed: {e}")
        sys.exit(1)

    ok(f"Connected via pymysql → {host}:{port}")
    print(color("  Type SQL queries, 'exit' or 'quit' to leave.\n", "90"))

    cursor = conn.cursor()

    while True:
        db_name = conn.db.decode() if isinstance(conn.db, bytes) else (conn.db or "none")
        prompt = color(f"mariadb [{db_name}]> ", "36")
        try:
            query = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not query:
            continue
        if query.lower() in ("exit", "quit", r"\q"):
            print("Bye.")
            break

        try:
            cursor.execute(query)
            if cursor.description:
                # Print column headers
                headers = [d[0] for d in cursor.description]
                rows = cursor.fetchall()
                col_widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0))
                              for i, h in enumerate(headers)]
                fmt = "  " + "  ".join(f"{{:<{w}}}" for w in col_widths)
                sep = "  " + "  ".join("-" * w for w in col_widths)
                print(color(fmt.format(*headers), "33"))
                print(color(sep, "90"))
                for row in rows:
                    print(fmt.format(*[str(c) for c in row]))
                print(color(f"\n  {len(rows)} row(s)", "90"))
            else:
                print(color(f"  Query OK, {cursor.rowcount} row(s) affected", "32"))

            # Sync current DB after USE
            if query.lower().startswith("use "):
                conn.select_db(query.split()[1].rstrip(";"))

        except pymysql.err.Error as e:
            err(str(e))

    cursor.close()
    conn.close()


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    banner()

    parser = argparse.ArgumentParser(description="Interactive MariaDB shell via Docker or pymysql")
    parser.add_argument("--container", "-c",  help="Container name or ID (skips auto-discovery)")
    parser.add_argument("--host",             help="Direct TCP host (activates pymysql mode)")
    parser.add_argument("--port",      type=int, default=3306)
    parser.add_argument("--user",      "-u", default="root")
    parser.add_argument("--password",  "-p", default="")
    parser.add_argument("--database",  "-d", default="")
    parser.add_argument("--auto-creds", action="store_true",
                        help="Extract credentials from container env vars")
    args = parser.parse_args()

    # ── Direct TCP mode (pymysql) ────────────────────────────────────────────
    if args.host:
        if not PYMYSQL_AVAILABLE:
            err("pymysql not installed. Run: pip3 install pymysql")
            sys.exit(1)
        shell_pymysql(args.host, args.port, args.user, args.password, args.database)
        return

    # ── Docker exec mode ─────────────────────────────────────────────────────
    container = args.container
    if not container:
        info("No container specified — attempting auto-discovery...")
        container = guess_container()
        if not container:
            err("Could not find a MariaDB/MySQL container. Specify with --container.")
            sys.exit(1)

    user     = args.user
    password = args.password
    database = args.database

    if args.auto_creds or (not password):
        info("Extracting credentials from container environment...")
        creds = extract_env_creds(container)
        if creds:
            ok(f"Credentials found: user={creds.get('user', 'root')} db={creds.get('database', '')}")
            user     = creds.get("user", user)
            password = creds.get("password", password)
            database = creds.get("database", database)
        else:
            warn("No credentials found in env. Using provided/default values.")

    # Try pymysql via container IP if available
    if PYMYSQL_AVAILABLE and not args.host:
        ip = get_container_ip(container)
        if ip:
            info(f"Container IP detected: {ip} — attempting pymysql connection...")
            try:
                shell_pymysql(ip, args.port, user, password, database)
                return
            except SystemExit:
                warn("pymysql failed, falling back to docker exec mode...")

    shell_docker(container, user, password, database)


if __name__ == "__main__":
    main()
