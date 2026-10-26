import cessao.app  # noqa: F401
from cessao.app import app
from cessao.extensions import db
from sqlalchemy import text

NEEDED = ["produto", "produto_config", "fundo", "contrato_processo", "contrato", "contrato_parcela",
          "liquidacao_processo", "liquidacao_pagamento", "liquidacao_lote_processo",
          "liquidacao_lote_log", "liquidacao_lote_vigente"]
with app.app_context():
    engine = db.engine
    with engine.begin() as c:
        c.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
    failed = []
    for table in db.metadata.sorted_tables:
        try:
            table.create(bind=engine, checkfirst=True)
        except Exception as exc:
            failed.append((table.name, str(exc).splitlines()[0][:100]))
    with engine.connect() as c:
        existing = {r[0] for r in c.execute(text("select table_name from information_schema.tables where table_schema='public'"))}
    print("criadas:", len(existing), "falharam:", len(failed))
    print("faltando do fechamento:", [t for t in NEEDED if t not in existing])
    for name, err in failed[:8]:
        print(" -", name, err)
