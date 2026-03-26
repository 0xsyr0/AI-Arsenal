# AI Arsenal

> A curated collection of AI-assisted scripts for offensive security operations, penetration testing, and red team engagements.

![License](https://img.shields.io/badge/license-MIT-red.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgrey.svg)
![Context](https://img.shields.io/badge/context-authorized%20use%20only-critical.svg)

---

## Table of Contents

- [Disclaimer](#disclaimer)
- [Overview](#overview)
- [Repository Structure](#repository-structure)
- [Scripts](#scripts)
  - [dbshell.py — Interactive MariaDB Shell](#dbshellpy--interactive-mariadb-shell)
- [General Requirements](#general-requirements)
- [Contributing](#contributing)
- [License](#license)

---

## Disclaimer

This toolkit is intended **exclusively for authorized penetration testing, red team engagements, and CTF competitions**. All scripts must only be used against systems you own or have explicit written permission to test. The author assumes no liability for misuse. Unauthorized use against systems you do not own is illegal.

---

## Overview

AI Arsenal is a growing collection of purpose-built offensive security tools developed with AI assistance. Each script is designed to be minimal, portable, and practical — filling gaps where standard tooling falls short, particularly in constrained environments (no root, no package manager, limited binaries).

Scripts follow a consistent code style — clean CLI interfaces, colored output, and sensible defaults.

---

## Repository Structure

```
ai-arsenal/
├── dbshell.py          # Interactive MariaDB/MySQL shell via Docker or pymysql
└── README.md
```

---

## Scripts

### `dbshell.py` — Interactive MariaDB Shell

An interactive MariaDB/MySQL client designed for environments where no database client binary is available. Operates in two modes: **Docker exec** (no dependencies) and **pymysql direct TCP** (with SSL support). Useful during internal network pivots, container escapes, and post-exploitation database enumeration.

**Features**

- Auto-discovers MariaDB/MySQL containers by name or filesystem scan (`/var/lib/docker/containers/`)
- Extracts credentials automatically from container environment variables (`MARIADB_ROOT_PASSWORD`, `MYSQL_USER`, etc.)
- Falls back gracefully between pymysql and docker exec mode
- Colored interactive REPL with row counts and column headers
- Zero dependencies in docker exec mode; only `pymysql` needed for direct TCP

**Requirements**

```
Python 3.8+
pymysql (optional, for direct TCP mode)
docker binary (for docker exec mode)
```

**Installation**

```bash
git clone https://github.com/youruser/ai-arsenal
cd ai-arsenal

# Optional: install pymysql for direct TCP mode
# No root required
python3 -m pip install --user pymysql

# Bootstrap pip if not available
curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
python3 /tmp/get-pip.py --user
~/.local/bin/pip3 install --user pymysql
```

**Usage**

```bash
# Auto-discover container and extract credentials from env vars
python3 dbshell.py --auto-creds

# Specify container explicitly
python3 dbshell.py --container mariadb --user root --password secret

# Specify container and target database
python3 dbshell.py --container db-1 --user root --password secret --database appdb

# Direct TCP connection (pymysql mode)
python3 dbshell.py --host 172.17.0.2 --user root --password secret

# Direct TCP with specific port and database
python3 dbshell.py --host 10.10.10.50 --port 3306 --user john --password secret --database prod

# Auto-creds with explicit container name
python3 dbshell.py --container mariadb-1 --auto-creds
```

**Interactive shell example**

```
  MariaDB Shell  |  docker-exec / pymysql mode

[*] No container specified — attempting auto-discovery...
[*] Trying container name: mariadb
[+] Found container: mariadb
[*] Extracting credentials from container environment...
[+] Credentials found: user=root db=appdb
[+] Connected via pymysql -> 172.17.0.2:3306

  Type SQL queries, 'use <db>', 'exit' or 'quit' to leave.

mariadb [appdb]> SHOW TABLES;
  Tables_in_appdb
  ---------------
  users
  sessions
  tokens

  3 row(s)

mariadb [appdb]> SELECT user, password FROM users LIMIT 5;
  user      password
  --------  ----------------------------------------
  admin     $2y$10$abcdefghijklmnopqrstuvwxyz012345
  john      $2y$10$zyxwvutsrqponmlkjihgfedcba543210

  2 row(s)

mariadb [appdb]> exit
Bye.
```

**Argument reference**

| Argument | Short | Default | Description |
|---|---|---|---|
| `--container` | `-c` | auto | Container name or ID |
| `--host` | | | Direct TCP host (activates pymysql mode) |
| `--port` | | `3306` | TCP port |
| `--user` | `-u` | `root` | Database user |
| `--password` | `-p` | `` | Database password |
| `--database` | `-d` | `` | Default database |
| `--auto-creds` | | `false` | Extract credentials from container env |

---

## General Requirements

- Python 3.8+
- Linux (primary target) / Windows (where applicable)
- No root required by design — scripts are built for constrained environments

---

## Contributing

Tools should follow the existing conventions:

- Colored output (`info`, `ok`, `warn`, `err` helpers)
- Argparse CLI with sensible defaults
- Graceful fallbacks for missing dependencies
- No root required wherever possible
- Clean, commented code

---

## License

MIT — see [LICENSE](LICENSE) for details.
