"""Cliente somente leitura do Redshift do lake.

Uso:
    python -I rsq.py "SELECT ..."        (ou o SQL pela entrada padrão)

- Aceita um único SELECT/WITH (ou EXPLAIN de um); recusa qualquer escrita ou DDL.
- Abre transação READ ONLY, com statement_timeout de 60 s, e sempre faz rollback.
- Imprime no máximo 200 linhas.
- Credenciais: variáveis CFG_LAKE_DB_* do .env da data-lake-api (caminho em
  RSQ_ENV_FILE, padrão abaixo). Nada de credencial neste arquivo.

Dependência: pip install redshift_connector (num venv próprio).
"""

import os
import re
import sys

import redshift_connector

ENV = os.getenv("RSQ_ENV_FILE", os.path.expanduser("~/projects/data-lake-api/.devcontainer/.env"))
FORBIDDEN = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|copy|unload|call|vacuum|analyze|comment|lock)\b",
    re.I,
)


def load_env():
    cfg = {}
    for line in open(ENV):
        line = line.strip()
        if line.startswith("CFG_LAKE_DB_") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k.replace("CFG_LAKE_DB_", "").lower()] = v.strip().strip('"').strip("'")
    return cfg


def main():
    sql = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    body = sql.strip().rstrip(";")
    if ";" in body or not re.match(r"^\s*(explain\s+)?(select|with)\b", body, re.I) or FORBIDDEN.search(body):
        sys.exit("recusado: só um único SELECT/WITH (ou EXPLAIN)")
    c = load_env()
    conn = redshift_connector.connect(
        host=c["host"], port=int(c["port"]), user=c["user"], password=c["password"], database=c["name"]
    )
    try:
        cur = conn.cursor()
        cur.execute("SET statement_timeout TO 60000")
        cur.execute("BEGIN READ ONLY")
        cur.execute(body)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(200)
        print(" | ".join(cols))
        for r in rows:
            print(" | ".join("" if v is None else str(v) for v in r))
        print(f"-- {len(rows)} linha(s)")
    finally:
        conn.rollback()
        conn.close()


if __name__ == "__main__":
    main()
