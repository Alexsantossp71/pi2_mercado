# -*- coding: utf-8 -*-
"""Cruza o cadastro Open Food Facts (BR) com o catálogo Carrefour (VTEX).

Gera 'catalogo_unificado.json' com a melhor informação de cada fonte:

- Base: OFF (293 produtos com nome/marca/categoria/imagem completos)
- Enriquecimento: produtos Carrefour que não existem no OFF (150), que trazem
  preço e disponibilidade reais (precos_carrefour.json)
- Interseção (10 EANs): mescla cadastro OFF + preço Carrefour

Uso:
    python cruzar_produtos.py
"""

import json
import os
from datetime import date

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
OFF_DIR = os.path.join(BASE, "openfoodfacts")
CAR_DIR = os.path.join(BASE, "carrefour")

ARQUIVO_OFF = os.path.join(OFF_DIR, "produtos.json")
ARQUIVO_CAR = os.path.join(CAR_DIR, "produtos.json")
ARQUIVO_PRECOS = os.path.join(CAR_DIR, "precos_carrefour.json")
ARQUIVO_SAIDA = os.path.join(BASE, "catalogo_unificado.json")


def carregar(caminho: str) -> list:
    if not os.path.exists(caminho):
        return []
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
    return dados if isinstance(dados, list) else []


# ---------------------------------------------------------------------------
# Normalização de categoria (OFF usa termos em inglês)
# ---------------------------------------------------------------------------
MAPA_CATEGORIAS_PT = {
    "plant-based-foods-and-beverages": "Alimentos e Bebidas à Base de Plantas",
    "dairies": "Laticínios",
    "beverages-and-beverages-preparations": "Bebidas",
    "meals": "Refeições",
    "snacks": "Lanches",
    "meats-and-their-products": "Carnes",
    "frozen-foods": "Congelados",
    "seafood": "Frutas do Mar",
    "breakfast-cereals": "Cereais Matinais",
    "confectioneries": "Confeitaria",
    "sugary-snacks": "Lanches Doces",
    "salty-snacks": "Lanches Salgados",
}


def categoria_pt(categoria: str) -> str:
    if not categoria:
        return "Geral"
    cat = categoria.strip().lower()
    return MAPA_CATEGORIAS_PT.get(cat, cat.capitalize())


# ---------------------------------------------------------------------------
# Cruzamento
# ---------------------------------------------------------------------------
def cruzar() -> dict:
    off = carregar(ARQUIVO_OFF)
    car = carregar(ARQUIVO_CAR)
    precos = carregar(ARQUIVO_PRECOS)

    # Índice de preços por EAN (última coleta)
    precos_por_ean = {}
    for p in precos:
        ean = p.get("gtin_ean")
        if ean and p.get("disponivel") and p.get("preco", 0) > 0:
            precos_por_ean[ean] = {
                "preco": p["preco"],
                "id_loja": p.get("id_loja"),
                "data_coleta": p.get("data_coleta"),
            }

    por_ean = {}
    eans_off = set()
    eans_car = set()

    # Passo 1: OFF entra primeiro (cadastro mais rico)
    for p in off:
        ean = p.get("gtin_ean")
        if not ean:
            continue
        por_ean[ean] = {
            "gtin_ean": ean,
            "nome": p.get("nome", ""),
            "marca": p.get("marca", "Não Informada"),
            "categoria": categoria_pt(p.get("categoria", "Geral")),
            "imagem_url": p.get("imagem_url"),
            "fonte_cadastro": "open_food_facts",
        }
        eans_off.add(ean)

    # Passo 2: Carrefour completa o que não existe no OFF
    for p in car:
        ean = p.get("gtin_ean")
        if not ean:
            continue
        eans_car.add(ean)
        if ean not in por_ean:
            por_ean[ean] = {
                "gtin_ean": ean,
                "nome": p.get("nome", ""),
                "marca": p.get("marca", "Não Informada"),
                "categoria": p.get("categoria", "Geral"),
                "imagem_url": None,
                "fonte_cadastro": "carrefour",
            }
        else:
            # Marca "Não Informado" do Carrefour melhora com OFF
            marca_atual = por_ean[ean].get("marca", "")
            if marca_atual.lower() in ("não informada", "não informado", ""):
                if p.get("marca") and p["marca"].lower() not in ("não informado",):
                    por_ean[ean]["marca"] = p["marca"]

    # Passo 3: injeta preço/disponibilidade do Carrefour
    for ean, item in por_ean.items():
        if ean in precos_por_ean:
            item["preco_carrefour"] = precos_por_ean[ean]["preco"]
            item["data_coleta_preco"] = precos_por_ean[ean]["data_coleta"]
        else:
            item["preco_carrefour"] = None
            item["data_coleta_preco"] = None

    # Ordena por nome para facilitar consulta
    lista = sorted(por_ean.values(), key=lambda x: x["nome"].lower())
    return {
        "produtos": lista,
        "estatisticas": {
            "total": len(lista),
            "com_preco_carrefour": sum(1 for x in lista if x["preco_carrefour"]),
            "fonte_off": sum(1 for x in lista if x["fonte_cadastro"] == "open_food_facts"),
            "fonte_carrefour": sum(1 for x in lista if x["fonte_cadastro"] == "carrefour"),
            "interseccao_eans": len(eans_off & eans_car),
            "data_geracao": date.today().isoformat(),
        },
    }


def main() -> None:
    resultado = cruzar()
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(resultado, f, indent=2, ensure_ascii=False)

    e = resultado["estatisticas"]
    print("=== Catálogo Unificado ===")
    print(f"Total de produtos: {e['total']}")
    print(f"  Fonte OFF: {e['fonte_off']}")
    print(f"  Fonte Carrefour: {e['fonte_carrefour']}")
    print(f"  Interseção (mesmo EAN): {e['interseccao_eans']}")
    print(f"  Com preço Carrefour: {e['com_preco_carrefour']}")
    print(f"Arquivo salvo: {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
