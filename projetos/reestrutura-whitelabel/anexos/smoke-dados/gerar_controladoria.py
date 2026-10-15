import json, math, datetime as dt, random, sys
random.seed(7)
out = {}

def month_ends(n, last=dt.date(2026, 9, 30)):
    ds = []
    y, m = last.year, last.month
    for _ in range(n):
        nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
        ds.append(nxt - dt.timedelta(days=1))
        m -= 1
        if m == 0: y, m = y - 1, 12
    return list(reversed(ds))

FUNDS = [
    ('FIDC Aurora Crédito', '11111111000101'),
    ('FIDC Horizonte Consignado', '22222222000102'),
    ('FIDC Vale Verde Recebíveis', '33333333000103'),
    ('FIDC Estrela do Sul', '44444444000104'),
]

# Performance: 12 fechamentos mensais
months = month_ends(12) + [dt.date(2026, 10, 14)]
recv, acq, liq = [], [], []
for i, d in enumerate(months):
    vp = 180_000_000 + i * 6_500_000 + 4_000_000 * math.sin(i)
    pdd = vp * (0.045 + 0.002 * i)
    recv.append({'date': d.isoformat(), 'vp': round(vp, 2), 'pdd': round(pdd, 2), 'type': 'monthly',
                 'fund_legal_id': FUNDS[0][1], 'fund_name': FUNDS[0][0]})
    acq.append({'date': d.isoformat(), 'acquisition_amount': round(22_000_000 + 3_000_000 * math.cos(i * 0.8), 2),
                'contracts': 1800 + i * 40, 'type': 'monthly', 'fund_legal_id': FUNDS[0][1], 'fund_name': FUNDS[0][0]})
    liq.append({'date': d.isoformat(), 'liquidation_amount': round(15_500_000 + 2_500_000 * math.sin(i * 0.7), 2),
                'payments': 2600 + i * 25, 'type': 'monthly', 'fund_legal_id': FUNDS[0][1], 'fund_name': FUNDS[0][0]})
out['controllership/portfolio/funds'] = [
    {'id': i + 1, 'name': n, 'legal_id': l, 'products': [{'id': 'prd-consig', 'name': 'Consignado'}]} for i, (n, l) in enumerate(FUNDS)]
out['controllership/portfolio/receivables'] = recv
out['controllership/portfolio/acquisition_amount'] = acq
out['controllership/portfolio/liquidation_amount'] = liq

# CERC: 10 dias úteis, dois fundos
days = [dt.date(2026, 9, 29) + dt.timedelta(days=k) for k in range(15)]
days = [d for d in days if d.weekday() < 5][:10]
items = []
for j, (name, legal) in enumerate(FUNDS[:2]):
    for i, d in enumerate(days):
        qty = 120 + 15 * i + 40 * j
        amount = round(qty * (4_850 + 120 * j), 2)
        reg_ratio = [1.0, 0.97, 0.92, 1.0, 0.88, 0.99, 0.95, 1.0, 0.9, 0.97][i]
        unknown = (j == 1 and i == 6)
        items.append({'date': d.isoformat(), 'fund_legal_id': legal, 'fund_name': name,
                      'cession_amount': None if unknown else amount,
                      'cession_quantity': None if unknown else qty,
                      'registered_amount': round(amount * reg_ratio, 2),
                      'registered_quantity': round(qty * reg_ratio)})
out['controllership/cerc/funds'] = {'funds': [{'id': i + 1, 'name': n, 'legal_id': l} for i, (n, l) in enumerate(FUNDS[:2])],
                                    'registros_data_available': True}
out['controllership/cerc/reconciliation'] = items

# PDD
pdd_months = month_ends(12)
spd = []
for i, d in enumerate(pdd_months):
    pv = 420_000_000 + i * 9_000_000
    matured = pv * (0.12 + 0.006 * i)
    pdd_total = pv * (0.051 + 0.0018 * i)
    contracts = 51_000 + i * 900
    spd.append({'reference_date': d.isoformat(), 'contracts_count': contracts, 'pv_total': round(pv, 2),
                'pv_matured': round(matured, 2), 'pv_to_mature': round(pv - matured, 2),
                'pdd_total': round(pdd_total, 2), 'pdd_pv_ratio': round(pdd_total / pv, 6), 'ticket': round(pv / contracts, 2)})
out['controllership/valid/funds'] = [
    {'id': i + 1, 'name': n, 'legal_id': l, 'products': [{'id': 'prd-consig', 'name': 'Consignado'}]} for i, (n, l) in enumerate(FUNDS)]
out['controllership/valid/stock'] = {
    'selected_stock': {'admin': 'Administradora Fictícia S.A.', 'fund_legal_id': FUNDS[0][1], 'stock_per_date': spd},
    'other_stocks_summary': [
        {'reference_date': pdd_months[-1].isoformat(), 'admin': 'Administradora Fictícia S.A.', 'fund_legal_id': l,
         'pv_total': pv, 'pdd_total': round(pv * r, 2)}
        for (n, l), pv, r in zip(FUNDS, [250_000_000, 140_000_000, 92_000_000, 37_000_000], [0.05, 0.072, 0.061, 0.11])],
}
RATINGS = [('AA', 0, 0, 0.005), ('A', 1, 14, 0.01), ('B', 15, 30, 0.03), ('C', 31, 60, 0.1),
           ('D', 61, 90, 0.3), ('E', 91, 120, 0.5), ('F', 121, 150, 0.7), ('G', 151, 9999, 1.0)]
def product(pid, name, total_pv, shares):
    rates = []
    for (rating, a, b, rate), share in zip(RATINGS, shares):
        pv = round(total_pv * share, 2)
        rates.append({'rating': rating, 'aging_from': a, 'aging_to': b, 'contract_count': max(1, int(pv / 8_000)),
                      'pv': pv, 'pdd': round(pv * rate, 2), 'pdd_pv_ratio': rate})
    return {'product': {'id': pid, 'name': name}, 'pdd_rate': rates}
out['controllership/valid/pdd'] = [
    product('prd-consig', 'Consignado', 310_000_000, [0.62, 0.14, 0.08, 0.06, 0.04, 0.03, 0.02, 0.01]),
    product('prd-cartao', 'Cartão de crédito', 120_000_000, [0.45, 0.17, 0.11, 0.09, 0.07, 0.05, 0.04, 0.02]),
    product('prd-pessoal', 'Crédito pessoal', 88_000_000, [0.38, 0.2, 0.12, 0.1, 0.08, 0.06, 0.04, 0.02]),
]

# Consolidado de caixa
def info(amount, pct):
    return {'amount': round(amount, 2), 'net_asset_value_percentage': round(pct, 2)}
def health(name, legal, base, pl):
    return {'fund_name': name, 'fund_legal_id': legal, 'updated_at': '2026-10-14T00:00:00Z',
            'last_cash_position': info(base, base / pl * 100),
            'opening_cash': info(base * 1.04, base * 1.04 / pl * 100),
            'available_cash': info(base * 0.91, base * 0.91 / pl * 100),
            'indirect_cash': info(base * 0.35, base * 0.35 / pl * 100)}
cash_funds = FUNDS + [('FIDC Lagoa Azul Multicedentes', '55555555000105')]
out['management/funds-health/funds'] = [{'name': n, 'legal_id': l} for n, l in cash_funds] + [
    {'name': 'FIC Master Caixa I', 'legal_id': None}, {'name': 'FIC Master Caixa II', 'legal_id': None}]
out['management/funds-health'] = {
    'funds': [health(n, l, b, pl) for (n, l), b, pl in zip(cash_funds, [18_400_000, 7_950_000, 12_300_000, 3_150_000, 9_870_000],
                                                           [250_000_000, 140_000_000, 92_000_000, 37_000_000, 110_000_000])],
    'master_funds': [health('FIC Master Caixa I', '66666666000106', 41_000_000, 410_000_000),
                     health('FIC Master Caixa II', '77777777000107', 26_500_000, 300_000_000)],
}
def amt(a, p): return {'amount': a, 'net_asset_value_percentage': p}
out['management/funds-health/details'] = {
    'closing_cash': {'updated_at': '2026-10-14T00:00:00Z', 'cash_fund': amt(9_800_000, 3.92), 'checking_account': amt(420_000, 0.17),
                     'government_bonds': amt(6_100_000, 2.44), 'agreements': amt(2_080_000, 0.83)},
    'asset_movements': {'acquisitions': amt(-3_200_000, -1.28), 'sales': amt(850_000, 0.34)},
    'liability_movements': {'subscriptions': amt(5_000_000, 2.0), 'redemptions': amt(-1_750_000, -0.7)},
    'maturity': {'amortizations': amt(2_300_000, 0.92), 'interest': amt(640_000, 0.26), 'fees': amt(-95_000, -0.04)},
    'provisioned_expenses': {'administration_fee': amt(-48_000, -0.02), 'management_fee': amt(-112_000, -0.04), 'performance_fee': amt('', '')},
    'movements': {'date': '2026-10-15T00:00:00Z', 'redemptions': amt(-900_000, -0.36), 'subscriptions': amt(1_200_000, 0.48),
                  'maturities': amt(780_000, 0.31), 'trades': amt(-410_000, -0.16)},
}

json.dump(out, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
print(len(out), 'caminhos')
