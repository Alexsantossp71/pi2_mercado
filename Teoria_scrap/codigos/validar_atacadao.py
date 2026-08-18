# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
RAIZ = 'G:/pi 2 - 2026/scraper/'
for f in ['produtos_ampliado.json', 'precos_atacadao_ampliado.json']:
    d = json.load(open(RAIZ + f, encoding='utf-8'))
    print('====', f, len(d), 'registros')
    if d:
        print('  exemplo:', json.dumps(d[0], ensure_ascii=False)[:400])

# resumo por secao
d = json.load(open(RAIZ + 'produtos_ampliado.json', encoding='utf-8'))
from collections import Counter
c = Counter(p.get('secao') for p in d)
print('\nProdutos por seção (Atacadão):')
for k, v in c.most_common():
    print(f'  {k}: {v}')
