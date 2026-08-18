# -*- coding: utf-8 -*-
import json, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, '.')
from coletor_vtex import coletar_vtex

AQUI = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(AQUI, 'folhas_atacadao.json'), encoding='utf-8') as f:
    folhas = json.load(f)['folhas'][:6]

tmp = r'C:\Users\arpt1\AppData\Local\Temp\opencode\teste_vtex'
os.makedirs(tmp, exist_ok=True)

coletar_vtex({
    'nome_supermercado': 'Atacadão',
    'base_url': 'https://www.atacadao.com.br',
    'marcador_imagem': 'atacadaobr',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36',
    'folhas': folhas,
    'pagina_tamanho': 50,
    'limite_max': 2500,
    'filtro_fq': 'isAvailablePerSalesChannel_1:1',
    'sleep': 0.2,
    'timeout': 20,
    'checkpoint_a_cada': 3,
    'arquivo_produtos': os.path.join(tmp, 'produtos_ampliado.json'),
    'arquivo_precos': os.path.join(tmp, 'precos_atacadao_ampliado.json'),
})
