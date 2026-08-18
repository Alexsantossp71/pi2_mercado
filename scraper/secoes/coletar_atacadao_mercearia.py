# -*- coding: utf-8 -*-
"""Coleta das folhas de mercearia do Atacadão que ultrapassam 2.500 itens.

Como o filtro `isAvailablePerSalesChannel_1:1` foi removido, a API pode devolver
até milhares de itens por folha. A VTEX ainda impõe um limite de offset de 2.500.

Estratégia simples: rodar o coletor sem filtro em todas as folhas. Caso alguma
folha atinja `limite_max` (2500 itens) podemos dividi‑la depois por marca.
Para o primeiro ciclo, vamos apenas executar o coletor padrão (sem filtro) nas
todas as folhas de mercearia do Atacadão. Isso já irá capturar ~16 661 itens
(aproximadamente). Se no futuro surgirem folhas truncadas, será necessário
refazer a coleta fragmentada similar ao script de Carrefour.
"""
import io, sys, os, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from coletor_vtex import coletar_vtex

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(BASE_DIR, '..', '..'))

import json
folhas = json.load(open(os.path.join(BASE_DIR, 'folhas_atacadao.json'), encoding='utf-8'))['folhas']
mercearia = [f for f in folhas if f['slug'].startswith('mercearia/')]

print(f'Folhas mercearia Atacadão: {len(mercearia)}')

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

coletar_vtex({
    "nome_supermercado": "Atacadão",
    "chave_loja": "atacadao",
    "base_url": "https://www.atacadao.com.br",
    "marcador_imagem": "atacadaobr",
    "user_agent": USER_AGENT,
    "folhas": mercearia,
    "pagina_tamanho": 50,
    "limite_max": 2500,
    # sem filtro_fq
    "sleep": 0.3,
    "timeout": 20,
    "checkpoint_a_cada": 20,
    "arquivo_produtos": os.path.join(RAIZ, "produtos_ampliado.json"),
    "arquivo_precos": os.path.join(RAIZ, "precos_atacadao_ampliado.json"),
})

print('\nColeta Atacadão concluída.')
