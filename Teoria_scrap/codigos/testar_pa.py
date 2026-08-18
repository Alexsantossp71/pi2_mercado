# -*- coding: utf-8 -*-
import io, json, os, sys, time
sys.path.insert(0, '.')
from datetime import date
from coletar_pa import (
    coletar_ids_subcat, processar_detalhe, salvar_json,
    CATEGORIAS, RAIZ, ARQUIVO_PRODUTOS, ARQUIVO_PRECOS,
)

# roda fase 1 e 2 para petshop (4 subcats, 236 produtos)
multi, secao, subcats = CATEGORIAS[-1]
print(f'Teste: {multi} ({secao})')

produtos = {}
precos = {}
for filtro in subcats:
    sub = filtro.split('_', 1)[-1].replace('+', ' ').title()
    prods = coletar_ids_subcat(multi, filtro, secao)
    print(f'  {sub}: {len(prods)} ids')
    for p in prods[:60]:  # limita a 60 por subcat p/ teste rápido
        r = processar_detalhe(p, secao, sub, date.today().isoformat())
        if r:
            produtos[r['produto']['gtin_ean']] = r['produto']
            precos[r['produto']['gtin_ean']] = r['preco']
        time.sleep(0.05)

print(f'Produtos com EAN+preço: {len(produtos)}')
print('ex:', json.dumps(list(produtos.values())[:1], ensure_ascii=False))
print('ex preco:', json.dumps(list(precos.values())[:1], ensure_ascii=False))
