# -*- coding: utf-8 -*-
"""
Coletor de produtos "Matinais" do Carrefour via API VTEX.

Usa as categorias reais da árvore "Padaria e Matinais > Cereal Matinal"
(Cereais, Aveia e Granolas) — o termo de busca "matinais" retornava ruído
(livros, canecas, itens usados).

Gera dois JSONs na raiz do projeto:
  - produtos_matinais.json        (cadastro estático, dedup por EAN)
  - precos_carrefour_matinais.json (preço/estoque)

Uso:
    python coletar_matinais.py
"""

import json
import os
import re
import time
from datetime import date

import requests

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------
# Categorias reais de matinais no Carrefour (árvore: Padaria e Matinais > Cereal Matinal)
CATEGORIAS = [
    "padaria-e-matinais/cereal-matinal/cereais",
    "padaria-e-matinais/cereal-matinal/aveia",
    "padaria-e-matinais/cereal-matinal/granolas",
]
PAGINA_TAMANHO = 50
INTERVALO_SLEEP = 1.5
TIMEOUT = 15
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

ARQUIVO_PRODUTOS = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "produtos_matinais.json"
)
ARQUIVO_PRECOS = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "precos_carrefour_matinais.json"
)

# Regex para extrair apresentação: ex. "500g", "1kg", "200 ml", "200ml", "1 L", "12 un", "12un"
RE_APRESENTACAO = re.compile(
    r"""
    (\d+(?:[.,]\d+)?)\s*       # quantidade (número com opcional decimal)
    (g|kg|ml|l|un|unid|unidade)  # unidade (case-insensitive)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def normalizar_unidade(un: str) -> str:
    un = un.lower().strip()
    if un in ("unid", "unidade"):
        return "un"
    return un


def extrair_apresentacao(nome: str) -> dict | None:
    """Extrai quantidade e unidade do nome do produto via regex."""
    match = RE_APRESENTACAO.search(nome)
    if not match:
        return None
    qtd_str = match.group(1).replace(",", ".")
    unidade = normalizar_unidade(match.group(2))
    try:
        qtd = float(qtd_str)
        if qtd.is_integer():
            qtd = int(qtd)
    except ValueError:
        return None
    return {"quantidade": qtd, "unidade_medida": unidade}


def ean_valido(ean: str | None) -> bool:
    if not ean:
        return False
    ean = str(ean).strip()
    return ean.isdigit() and len(ean) == 13


def carregar_existentes(caminho: str) -> dict:
    """Carrega JSON existente e retorna {gtin_ean: registro}."""
    if not os.path.exists(caminho):
        return {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(dados, list):
        return {}
    return {p.get("gtin_ean"): p for p in dados if p.get("gtin_ean")}


def salvar_json(caminho: str, dados: list) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Requisição paginada
# ---------------------------------------------------------------------------
def buscar_pagina(categoria: str, offset: int, limit: int) -> list:
    params = {"_from": offset, "_to": offset + limit - 1}
    headers = {"User-Agent": USER_AGENT}
    url = f"https://www.carrefour.com.br/api/catalog_system/pub/products/search/{categoria}"
    resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Transformação VTEX -> Modelo
# ---------------------------------------------------------------------------
def extrair_ean(produto: dict) -> str | None:
    """Tenta pegar EAN de items[0].ean, senão alternateIds, senão None."""
    items = produto.get("items")
    if items:
        ean = items[0].get("ean")
        if ean_valido(ean):
            return str(ean).strip()
    # Fallback: alternateIds (lista de dicts com type=EAN)
    for alt in produto.get("alternateIds") or []:
        if alt.get("type") == "EAN" and ean_valido(alt.get("value")):
            return str(alt["value"]).strip()
    return None


def extrair_preco(produto: dict) -> dict | None:
    """Pega a melhor oferta do primeiro item (prioriza disponível e com preço real)."""
    items = produto.get("items")
    if not items:
        return None
    item = items[0]
    sellers = item.get("sellers") or []
    ofertas_validas = []
    for s in sellers:
        of = s.get("commertialOffer") or {}
        if "Price" not in of:
            continue
        preco = float(of.get("Price", 0) or 0)
        list_price = float(of.get("ListPrice", 0) or 0)
        disp = bool(of.get("IsAvailable", False))
        if preco <= 0:
            continue
        ofertas_validas.append(
            {
                "preco_regular": round(list_price if list_price else preco, 2),
                "preco_promocional": round(preco, 2),
                "em_estoque": disp,
                "seller_default": s.get("sellerDefault", False),
            }
        )
    if not ofertas_validas:
        return None
    # Prioriza: disponível em estoque > seller_default > maior preço regular
    ofertas_validas.sort(
        key=lambda x: (x["em_estoque"], x["seller_default"], x["preco_regular"]),
        reverse=True,
    )
    return ofertas_validas[0]


def transformar_produto(produto: dict, ean: str, hoje: str) -> dict:
    apresentacao = extrair_apresentacao(produto.get("productName", "")) or {}
    return {
        "gtin_ean": ean,
        "secao": "Matinais",
        "nome_completo": produto.get("productName", "").strip(),
        "marca": (produto.get("brand") or "Não Informada").strip(),
        "apresentacao": apresentacao,
        "imagem_url": (
            produto.get("image_front_url")
            or produto.get("image_url")
            or (produto.get("items") or [{}])[0].get("images", [{}])[0].get("imageUrl")
        ),
        "data_cadastro": hoje,
    }


def transformar_preco(ean: str, oferta: dict, hoje: str) -> dict:
    return {
        "gtin_ean": ean,
        "supermercado": "Carrefour",
        "preco_regular": oferta["preco_regular"],
        "preco_promocional": oferta["preco_promocional"],
        "em_estoque": oferta["em_estoque"],
        "data_coleta": hoje,
    }


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def main() -> None:
    hoje = date.today().isoformat()
    print(f"=== Coletor Matinais Carrefour (VTEX) ===")
    print(f"Data da coleta: {hoje}")
    print(f"Categorias: {', '.join(CATEGORIAS)}")
    print("-" * 70)

    # Carrega catálogo existente e remove produtos antigos do Carrefour
    # (mantém produtos de outras lojas, ex. Pão de Açúcar)
    produtos_antes = carregar_existentes(ARQUIVO_PRODUTOS)
    produtos_outras_lojas = {
        ean: p for ean, p in produtos_antes.items()
        if "carrefourbr" not in (p.get("imagem_url") or "")
    }
    removidos = len(produtos_antes) - len(produtos_outras_lojas)
    print(f"Catálogo existente: {len(produtos_antes)} | Carrefour removidos p/ recálculo: {removidos} | preservados (outras lojas): {len(produtos_outras_lojas)}")

    # Preços do Carrefour são recalculados do zero
    precos_exist: dict = {}
    # EANs já tratados nesta execução (dedup intra-run e contra catálogo)
    vistos_execucao: set[str] = set()

    novos_produtos = 0
    novos_precos = 0
    ignorados_sem_ean = 0
    ignorados_duplicados = 0

    for categoria in CATEGORIAS:
        offset = 0
        total_paginas = 0
        while True:
            total_paginas += 1
            print(f"[{categoria.split('/')[-1]} | Página {total_paginas}] Offset {offset}..{offset + PAGINA_TAMANHO - 1} ... ", end="", flush=True)

            try:
                produtos = buscar_pagina(categoria, offset, PAGINA_TAMANHO)
            except requests.exceptions.RequestException as err:
                print(f"ERRO: {type(err).__name__} - {err}")
                break

            if not produtos:
                print("lista vazia -> fim da paginação")
                break

            print(f"{len(produtos)} produtos")

            for prod in produtos:
                ean = extrair_ean(prod)
                if not ean:
                    ignorados_sem_ean += 1
                    continue

                # Produto já tratado nesta execução (mesma categoria ou anterior)
                if ean in vistos_execucao:
                    ignorados_duplicados += 1
                    continue
                vistos_execucao.add(ean)

                # A API devolve muitos itens inativos (kits desativados, preço 0).
                # Só entram produtos com preço real.
                oferta = extrair_preco(prod)
                if not oferta:
                    ignorados_sem_ean += 1
                    continue

                # Produto de outra loja já cadastrado: mantém o cadastro,
                # apenas registra o preço do Carrefour para este EAN
                if ean in produtos_outras_lojas:
                    precos_exist[ean] = transformar_preco(ean, oferta, hoje)
                    novos_precos += 1
                    continue

                # Produto novo: cadastra e registra preço
                prod_novo = transformar_produto(prod, ean, hoje)
                produtos_outras_lojas[ean] = prod_novo
                novos_produtos += 1

                precos_exist[ean] = transformar_preco(ean, oferta, hoje)
                novos_precos += 1

            offset += PAGINA_TAMANHO
            time.sleep(INTERVALO_SLEEP)

    # Salva
    salvar_json(ARQUIVO_PRODUTOS, list(produtos_outras_lojas.values()))
    salvar_json(ARQUIVO_PRECOS, list(precos_exist.values()))

    print("-" * 70)
    print(f"Produtos válidos com EAN-13: {novos_produtos + ignorados_duplicados}")
    print(f"  -> Novos cadastrados: {novos_produtos}")
    print(f"  -> Duplicados ignorados (mesma categoria/anterior): {ignorados_duplicados}")
    print(f"  -> Sem EAN válido: {ignorados_sem_ean}")
    print(f"Preços Carrefour salvos: {len(precos_exist)} (novos: {novos_precos})")
    print(f"Arquivos:")
    print(f"  {ARQUIVO_PRODUTOS}")
    print(f"  {ARQUIVO_PRECOS}")
    print("-" * 70)


if __name__ == "__main__":
    main()