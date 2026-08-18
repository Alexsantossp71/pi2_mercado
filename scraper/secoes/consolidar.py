# -*- coding: utf-8 -*-
"""
Consolida a coleta ampliada e integra no webapp.

Gera/copia para a raiz do scraper e para o webapp:
  - produtos_ampliado.json              (cadastro unificado, dedup por EAN)
  - precos_{carrefour,pao_de_acucar,atacadao}_ampliado.json

Após todas as coletas concluídas, use:
    python consolidar.py
"""

import io
import json
import os
import shutil
import sys
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from relevancia import calcular_relevancia

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBAPP = os.path.join(os.path.dirname(RAIZ), "webapp")

ARQ_PRODUTOS = os.path.join(RAIZ, "produtos_ampliado.json")
LOJAS = {
    "carrefour": ("precos_carrefour_ampliado.json", "Carrefour"),
    "pao_de_acucar": ("precos_pao_de_acucar_ampliado.json", "Pão de Açúcar"),
    "atacadao": ("precos_atacadao_ampliado.json", "Atacadão"),
}


def carregar(caminho: str) -> list:
    if not os.path.exists(caminho):
        return []
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return d if isinstance(d, list) else []


def calcular_cobertura() -> dict:
    """EAN -> número de lojas que vendem (0..3)."""
    eans_por_loja = []
    for chave, (arquivo, nome) in LOJAS.items():
        precos = carregar(os.path.join(RAIZ, arquivo))
        eans = {p.get("gtin_ean") for p in precos if p.get("gtin_ean") and p.get("em_estoque")}
        eans_por_loja.append(eans)
    cobertura = {}
    for ean in set().union(*eans_por_loja) if eans_por_loja else set():
        cobertura[ean] = sum(1 for s in eans_por_loja if ean in s)
    return cobertura


def main() -> None:
    produtos = carregar(ARQ_PRODUTOS)
    print("=== Consolidador Dispensa Planejada (ampliado) ===")
    print(f"Catálogo (produtos_ampliado.json): {len(produtos):,} produtos")

    total_precos = 0
    for chave, (arquivo, nome) in LOJAS.items():
        precos = carregar(os.path.join(RAIZ, arquivo))
        print(f"  {nome}: {len(precos):,} preços")
        total_precos += len(precos)

    # --- Relevância (lista curada + cobertura de lojas) ---
    cobertura = calcular_cobertura()
    com_relevancia = 0
    for p in produtos:
        n_lojas = cobertura.get(p.get("gtin_ean"), 0)
        p["relevancia"] = calcular_relevancia(p.get("nome_completo") or "", n_lojas)
        if p["relevancia"] > 0:
            com_relevancia += 1

    # Copia para o webapp (catálogo com relevância)
    os.makedirs(WEBAPP, exist_ok=True)
    with open(os.path.join(WEBAPP, "produtos_ampliado.json"), "w", encoding="utf-8") as f:
        json.dump(produtos, f, indent=2, ensure_ascii=False)
    for chave, (arquivo, nome) in LOJAS.items():
        origem = os.path.join(RAIZ, arquivo)
        if os.path.exists(origem):
            shutil.copy(origem, os.path.join(WEBAPP, arquivo))

    # Resumo por seção
    if produtos:
        secs = Counter(p.get("secao") for p in produtos)
        print("\nProdutos por seção:")
        for k, v in secs.most_common():
            print(f"  {k}: {v:,}")

    print("\nArquivos copiados para", WEBAPP)
    print("Próximo passo: apontar o webapp/index.html para os arquivos *_ampliado.json")


if __name__ == "__main__":
    main()
