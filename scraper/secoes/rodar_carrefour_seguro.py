# -*- coding: utf-8 -*-
"""
Executor seguro para coleta completa (Carrefour e Pão de Açúcar).
Salva checkpoints continuamente para que nada seja perdido.
"""
import io
import json
import os
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

from coletor_vtex import coletar_vtex

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

def rodar_carrefour():
    print("=== INICIANDO COLETA CARREFOUR ===")
    with open(os.path.join(AQUI, "folhas_carrefour.json"), encoding="utf-8") as f:
        folhas = json.load(f)["folhas"]
        
    coletar_vtex({
        "nome_supermercado": "Carrefour",
        "chave_loja": "carrefour",
        "base_url": "https://www.carrefour.com.br",
        "marcador_imagem": "carrefourbr",
        "user_agent": USER_AGENT,
        "folhas": folhas,
        "pagina_tamanho": 50,
        "limite_max": 2500,
        "filtro_fq": "isAvailablePerSalesChannel_1:1",
        "sleep": 0.2,
        "timeout": 20,
        "checkpoint_a_cada": 15,
        "arquivo_produtos": os.path.join(RAIZ, "produtos_ampliado.json"),
        "arquivo_precos": os.path.join(RAIZ, "precos_carrefour_ampliado.json"),
    })

if __name__ == "__main__":
    rodar_carrefour()
