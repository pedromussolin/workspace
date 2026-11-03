"""Custo de CPU, na data-lake-api, de trocar o fundo na tela: movimentação lida
do Redis (24 fundos x ~500 dias) e estoque do cache (todos os fundos, 2 anos).
Dados sintéticos com o formato real; sem rede, sem lake.

Uso, na raiz da data-lake-api (branch da TS-4815), com o ambiente dela:
    PYTHONPATH=. python <caminho>/measure_fund_switch.py
"""
import json, random, time
from datetime import date, timedelta

from src.modules.consolidation.business.valid_movement import business_days
from src.modules.consolidation.repository import ValidDayStatus, ValidMovementStore
from src.modules.consolidation.repository.valid_source import StockMovementDay
from src.modules.valid.business import select_stock_sources, summarize_movement
from src.modules.valid.schemas import StockResponse
from tests.fake_redis import FakeRedis

random.seed(1)
end = date(2026, 10, 22); start = date(2024, 10, 22)
days = business_days(start, end)
funds = [f"{i:014d}" for i in range(24)]
amt = lambda: round(random.uniform(1e3, 5e8), 2)

store = ValidMovementStore(FakeRedis())
prev = days[0]
for d in days[1:]:
    store.queue_days([d], 600); store.start_day(d, 600)
    rows = [StockMovementDay("SRC", f, *(amt() for _ in range(8))) for f in funds]
    store.finish_day(d, ValidDayStatus.SUCCESS, previous_ref_date=prev, rows=rows)
    prev = d
size = sum(len(v) for k, v in store._redis.strings.items() if ":day:" in k)

t = time.perf_counter()
for _ in range(5):
    rows = store.get_fund_rows(funds[7], start, end)
    resp = summarize_movement(funds[7], rows, end)
mov = (time.perf_counter() - t) / 5
print(f"movimentação: {len(days)} dias, {size/1e6:.1f} MB no Redis, {mov*1000:.0f} ms (MGET+JSON+soma)")

# Estoque: 30 pares fonte x fundo (administradores + INTERNAL) x ~500 datas.
stock = [
    {"admin": "SRC" if i < 24 else "INTERNAL", "fund_legal_id": f"{i % 26:014d}",
     "reference_date": d.isoformat(), "contracts_count": 1234, "pv_total": amt(),
     "pv_matured": amt(), "pv_to_mature": amt(), "pdd_total": amt()}
    for i in range(30) for d in days
]
raw = json.dumps(stock)
t = time.perf_counter()
for _ in range(5):
    out = StockResponse.from_rows(select_stock_sources(json.loads(raw))).model_dump_json()
st = (time.perf_counter() - t) / 5
print(f"estoque: {len(stock)} linhas, {len(raw)/1e6:.1f} MB no cache, resposta {len(out)/1e6:.1f} MB, {st*1000:.0f} ms (JSON+D8+resposta)")
