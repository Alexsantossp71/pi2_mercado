# -*- coding: utf-8 -*-
"""
Coletor de produtos "Matinais" (Cereais Matinais) do Pão de Açúcar.

O e-commerce do Pão de Açúcar usa uma plataforma própria (api.vendas.gpa.digital),
NÃO VTEX. Este script consome a API real do site, que responde em JSON:

  Lista de produtos (categoria Cereais Matinais, seção 12001):
      POST https://api.vendas.gpa.digital/pa/search/category-page
      body: {"partner":"linx","page":N,"resultsPerPage":36,"sortBy":"relevance",
             "multiCategory":"alimentos","department":"ecom","storeId":461,
             "customerPlus":true,"filters":["facetSubShelf_ss:12001_Cereais"]}

  Detalhe do produto (EAN-13, marca, imagens, preços):
      GET https://api.vendas.gpa.digital/pa/v4/products/ecom/{id}?storeId=461

Gera/atualiza na raiz do projeto:
  - produtos_matinais.json               (cadastro estático, ATUALIZADO)
  - precos_pao_de_acucar_matinais.json   (preço/estoque)

Uso:
    python scrap_pao_de_acucar.py
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
API_BASE = "https://api.vendas.gpa.digital/pa"
URL_LISTA = f"{API_BASE}/search/category-page"
URL_DETALHE = f"{API_BASE}/v4/products/ecom/{{}}"

# Categoria "Cereais Matinais" (filha da seção Alimentos/12001)
FILTRO_CATEGORIA = ["facetSubShelf_ss:12001_Cereais"]
MULTI_CATEGORY = "alimentos"
STORE_ID = 461
PAGINA_TAMANHO = 36  # cap real da API
TOTAL_ALVO = None     # preenchido a partir de totalProducts da primeira resposta

INTERVALO_SLEEP = 1.5
TIMEOUT = 20
MAX_VARREDURAS = 5   # varreduras completas para contornar paginação não determinística
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

RAIZ = os.path.dirname(os.path.dirname(__file__))
ARQUIVO_PRODUTOS = os.path.join(RAIZ, "produtos_matinais.json")
ARQUIVO_PRECOS = os.path.join(RAIZ, "precos_pao_de_acucar_matinais.json")
IMAGEM_BASE = "https://static.paodeacucar.com"

# Regex para extrair apresentação: ex. "500g", "1kg", "200 ml", "200ml", "1 L", "12 un", "12un"
RE_APRESENTACAO = re.compile(
    r"""
    (\d+(?:[.,]\d+)?)\s*       # quantidade (número com opcional decimal)
    (g|kg|ml|l|un|unid|unidade)  # unidade (case-insensitive)
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "Referer": "https://www.paodeacucar.com/",
    "Origin": "https://www.paodeacucar.com",
}


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


def ean_valido(ean) -> bool:
    if not ean:
        return False
    ean = str(ean).strip()
    return ean.isdigit() and len(ean) == 13


def carregar_lista(caminho: str) -> dict:
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
# Requisições à API
# ---------------------------------------------------------------------------
def buscar_pagina(pagina: int) -> tuple[list, int | None]:
    """Retorna (produtos, totalProducts) para a página pedida."""
    payload = {
        "partner": "linx",
        "page": pagina,
        "resultsPerPage": PAGINA_TAMANHO,
        "sortBy": "relevance",
        "multiCategory": MULTI_CATEGORY,
        "department": "ecom",
        "storeId": STORE_ID,
        "customerPlus": True,
        "filters": FILTRO_CATEGORIA,
    }
    resp = requests.post(URL_LISTA, json=payload, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    dados = resp.json()
    return dados.get("products") or [], dados.get("totalProducts")


def buscar_detalhe(produto_id: int) -> dict | None:
    """Busca o detalhe do produto (contém EAN, imagens e preços)."""
    resp = requests.get(URL_DETALHE.format(produto_id),
                        params={"storeId": STORE_ID}, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json().get("content")


# ---------------------------------------------------------------------------
# Transformação API -> Modelo
# ---------------------------------------------------------------------------
def coletar_ids_unicos() -> list[dict]:
    """
    Percorre as páginas da categoria deduplicando por id.

    A paginação da API não é determinística: cada chamada a uma página devolve
    um subconjunto rotativo de ~36 produtos. Para capturar todos, fazemos várias
    varreduras completas (1..totalPages) até que uma varredura inteira não
    adicione nenhum id novo.
    """
    global TOTAL_ALVO
    vistos: dict[int, dict] = {}
    total_paginas = None
    varreduras_sem_novidade = 0

    for varredura in range(1, MAX_VARREDURAS + 1):
        pagina = 1
        novos_na_varredura = 0
        while True:
            try:
                produtos, total = buscar_pagina(pagina)
            except requests.exceptions.RequestException as err:
                print(f"  ERRO página {pagina}: {type(err).__name__} - {err}")
                break
            if total is not None:
                TOTAL_ALVO = total
            if total_paginas is None:
                total_paginas = (produtos and TOTAL_ALVO) or 0
            if not produtos:
                break

            for p in produtos:
                if p.get("id") not in vistos:
                    vistos[p["id"]] = p
                    novos_na_varredura += 1
            pagina += 1
            time.sleep(INTERVALO_SLEEP)

        print(f"[Varredura {varredura}] total únicos: {len(vistos)}/{TOTAL_ALVO} | novos nesta varredura: {novos_na_varredura}")
        if novos_na_varredura == 0:
            varreduras_sem_novidade += 1
        else:
            varreduras_sem_novidade = 0
        if varreduras_sem_novidade >= 2:
            break
        if len(vistos) >= (TOTAL_ALVO or len(vistos)):
            break

    return list(vistos.values())


def transformar_produto(detalhe: dict, produto_lista: dict, hoje: str) -> dict:
    apresentacao = extrair_apresentacao(detalhe.get("name", "")) or {}
    imagens = detalhe.get("productImages") or []
    imagem = f"{IMAGEM_BASE}{imagens[0]}" if imagens else None
    return {
        "gtin_ean": str(detalhe.get("ean", "")).strip(),
        "secao": "Matinais",
        "nome_completo": detalhe.get("name", "").strip(),
        "marca": (detalhe.get("brand") or produto_lista.get("brand") or "Não Informada").strip(),
        "apresentacao": apresentacao,
        "imagem_url": imagem,
        "data_cadastro": hoje,
    }


def extrair_precos(detalhe: dict, produto_lista: dict) -> dict | None:
    """Extrai preços do sellInfos (com fallback para o preço do listing)."""
    sells = detalhe.get("sellInfos") or []
    em_estoque = None

    if sells:
        info = sells[0]
        regular = float(info.get("currentPrice") or info.get("sellPrice") or 0)
        promocional = regular

        # Promoção ativa no período atual
        hoje_iso = date.today().isoformat()
        for promo in info.get("productPromotions") or []:
            ini = (promo.get("startDate") or "")[:10]
            fim = (promo.get("endDate") or "")[:10]
            ativa = bool((not ini or ini <= hoje_iso) and (not fim or fim >= hoje_iso))
            if ativa:
                preco_promo = float(promo.get("unitPrice") or 0)
                if preco_promo and (promocional == regular or preco_promo < promocional):
                    promocional = preco_promo

        em_estoque = bool(info.get("stock")) and (info.get("stockQuantity") or 0) > 0
    else:
        # Fallback: listing carrega price/stock mesmo quando o detalhe não tem sellInfos
        regular = float(produto_lista.get("price") or 0)
        promocional = regular
        em_estoque = bool(produto_lista.get("stock"))

    if not regular or regular <= 0:
        return None
    return {
        "preco_regular": round(regular, 2),
        "preco_promocional": round(promocional, 2),
        "em_estoque": bool(em_estoque),
    }


def transformar_preco(ean: str, precos: dict, hoje: str) -> dict:
    return {
        "gtin_ean": ean,
        "supermercado": "Pão de Açúcar",
        "preco_regular": precos["preco_regular"],
        "preco_promocional": precos["preco_promocional"],
        "em_estoque": precos["em_estoque"],
        "data_coleta": hoje,
    }


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def main() -> None:
    hoje = date.today().isoformat()
    print("=== Coletor Matinais Pão de Açúcar (API GPA) ===")
    print(f"Data da coleta: {hoje}")
    print(f"Endpoint: {URL_LISTA}")
    print(f"Filtro: {FILTRO_CATEGORIA[0]}")
    print("-" * 70)

    produtos_exist = carregar_lista(ARQUIVO_PRODUTOS)
    precos_exist = carregar_lista(ARQUIVO_PRECOS)
    eans_existentes = set(produtos_exist.keys())

    print("Coletando IDs únicos da categoria...")
    produtos_unicos = coletar_ids_unicos()
    print(f"Produtos únicos encontrados: {len(produtos_unicos)}")
    print("-" * 70)

    novos_produtos = 0
    precos_coletados = 0
    precos_atualizados = 0
    ignorados_sem_ean = 0
    ignorados_sem_preco = 0

    for i, prod_lista in enumerate(produtos_unicos, 1):
        pid = prod_lista["id"]
        try:
            detalhe = buscar_detalhe(pid)
        except requests.exceptions.RequestException as err:
            print(f"  [skip] produto {pid} erro no detalhe: {type(err).__name__} - {err}")
            continue

        if not detalhe:
            continue

        ean = str(detalhe.get("ean") or "").strip()
        if not ean_valido(ean):
            ignorados_sem_ean += 1
            print(f"  [skip] {pid} sem EAN-13 válido: {ean!r}")
            continue

        # A) Cadastro: adiciona ao catálogo apenas se o EAN ainda não existe
        if ean not in eans_existentes:
            produtos_exist[ean] = transformar_produto(detalhe, prod_lista, hoje)
            eans_existentes.add(ean)
            novos_produtos += 1

        # B) Preço: sempre monta/atualiza o registro do Pão de Açúcar
        precos = extrair_precos(detalhe, prod_lista)
        if precos and precos["preco_regular"] > 0:
            if ean in precos_exist:
                precos_atualizados += 1
            else:
                precos_coletados += 1
            precos_exist[ean] = transformar_preco(ean, precos, hoje)
        else:
            ignorados_sem_preco += 1

        if i % 10 == 0 or i == len(produtos_unicos):
            print(f"  [{i}/{len(produtos_unicos)}] processados | novos catálogo: {novos_produtos} | preços: {precos_coletados} novos / {precos_atualizados} atualizados")

        time.sleep(INTERVALO_SLEEP)

    salvar_json(ARQUIVO_PRODUTOS, list(produtos_exist.values()))
    salvar_json(ARQUIVO_PRECOS, list(precos_exist.values()))

    print("-" * 70)
    print(f"Produtos únicos na categoria: {len(produtos_unicos)}")
    print(f"Novos produtos cadastrados: {novos_produtos}")
    print(f"Sem EAN-13 válido: {ignorados_sem_ean}")
    print(f"Sem preço válido: {ignorados_sem_preco}")
    print(f"Preços Pão de Açúcar: {len(precos_exist)} (novos: {precos_coletados}, atualizados: {precos_atualizados})")
    print(f"Arquivos:")
    print(f"  {ARQUIVO_PRODUTOS}")
    print(f"  {ARQUIVO_PRECOS}")
    print("-" * 70)


if __name__ == "__main__":
    main()
