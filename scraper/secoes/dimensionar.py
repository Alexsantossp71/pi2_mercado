# -*- coding: utf-8 -*-
import json, math, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

for nome in ['folhas_carrefour.json', 'folhas_atacadao.json']:
    d = json.load(open(nome, encoding='utf-8'))
    folhas = d['folhas']
    itens_coletaveis = 0
    paginas = 0
    for f in folhas:
        n = f['itens_estimados']
        if n is None:
            continue
        nc = min(n, 2500)
        itens_coletaveis += nc
        paginas += math.ceil(nc / 50)
    print(f'{nome}: {len(folhas)} folhas | itens_coletáveis: {itens_coletaveis:,} | páginas(50): {paginas:,}')

# Atacadão sem medição: aproximar 49.345 resources -> ~1000 paginas + folhas vazias
print()
print('Atacadão (sem contagem): ~1.000 páginas estimadas (49.345 resources / 50)')
print()
print('Estimativas de tempo por sleep (inclui folhas vazias + retries):')
for nome, pag in [('Carrefour', 32400), ('Atacadão', 1100)]:
    for sleep in [0.3, 0.5, 1.0]:
        print(f'  {nome} sleep={sleep}s -> {pag * sleep / 3600:.1f}h')
