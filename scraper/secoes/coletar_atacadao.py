# -*- coding: utf-8 -*-
"""Coleta ampliada de todas as seções do Atacadão (VTEX) — versão otimizada.

Melhorias em relação à versão anterior:
  - Filtro fq=isAvailablePerSalesChannel_1:1 habilitado: retorna apenas produtos
    disponíveis no canal online, evitando desperdício de slots de paginação com
    itens de marketplace indisponíveis.
  - Todas as 448 folhas configuradas em config_secoes.py são coletadas (não
    apenas mercearia).
  - Sleep reduzido para 0.2s (seguro para a VTEX do Atacadão).
  - Checkpoint a cada 20 folhas para retomada rápida em caso de interrupção.
"""
import io
import json
import os
import sys

from coletor_vtex import coletar_vtex

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)  # g:\pi 2 - 2026\scraper

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def main() -> None:
    with open(os.path.join(AQUI, "folhas_atacadao.json"), encoding="utf-8") as f:
        folhas = json.load(f)["folhas"]

    print(f"Total de folhas Atacadão: {len(folhas)}")

    coletar_vtex({
        "nome_supermercado": "Atacadão",
        "chave_loja": "atacadao",
        "base_url": "https://www.atacadao.com.br",
        "marcador_imagem": "atacadaobr",
        "user_agent": USER_AGENT,
        "folhas": folhas,
        "pagina_tamanho": 50,
        "limite_max": 2500,
        # Filtro de disponibilidade: só produtos com estoque no canal online
        "filtro_fq": "isAvailablePerSalesChannel_1:1",
        "sleep": 0.2,
        "timeout": 20,
        "checkpoint_a_cada": 20,
        "arquivo_produtos": os.path.join(RAIZ, "produtos_atacadao.json"),
        "arquivo_precos": os.path.join(RAIZ, "precos_atacadao_ampliado.json"),
    })


if __name__ == "__main__":
    main()
