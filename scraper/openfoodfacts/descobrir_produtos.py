# -*- coding: utf-8 -*-
"""Descoberta de EANs reais no Open Food Facts Brasil e construção do cadastro.

Como a base OFF BR tem cobertura limitada, este script busca por NOME de produto
(cesta básica) e extrai os códigos EAN realmente cadastrados, salvando em
'produtos.json' (mesma estrutura cadastral do construir_produtos.py).

Uso:
    python descobrir_produtos.py
"""

import json
import os
import time
from datetime import date

import requests

ARQUIVO_SAIDA = "produtos.json"
USER_AGENT = "DispensaPlanejada_Santos_AcademicProject/1.0 (contato@dispensaplanejada.local)"
TIMEOUT = 10
INTERVALO_SLEEP = 1.2
MAX_TENTATIVAS = 4
BACKOFF_SEGUNDOS = 3

URL_BUSCA = "https://br.openfoodfacts.org/cgi/search.pl"

TERMOS_BUSCA = [
    "arroz",
    "feijao",
    "cafe",
    "acucar",
    "oleo",
    "leite",
    "sabao em po",
    "detergente",
    "papel higienico",
    "banana",
    "tomate",
    "frango",
    "carne",
    "macarrao",
    "farinha de trigo",
    "leite condensado",
    "molho de tomate",
    "margarina",
    "queijo mussarela",
    "cerveja",
]

# Evita salvar produtos irrelevantes (ex.: 'arroz' retorna biscoitos de arroz)
PALAVRAS_CHAVE = {
    "arroz": ["arroz", "rice"],
    "feijao": ["feij", "bean"],
    "cafe": ["cafe", "coffee"],
    "acucar": ["acucar", "açúcar", "sugar"],
    "oleo": ["oleo", "óleo", "oil"],
    "leite": ["leite", "milk", "latic", "dairy"],
    "sabao em po": ["sabao", "sabão", "detergente em po"],
    "detergente": ["detergente"],
    "papel higienico": ["papel", "higi", "toilet"],
    "banana": ["banana"],
    "tomate": ["tomate", "tomato"],
    "frango": ["frango", "chicken"],
    "carne": ["carne", "beef", "bovin", "steak"],
    "macarrao": ["macarrao", "macarrão", "pasta", "spaghetti"],
    "farinha de trigo": ["farinha", "flour"],
    "leite condensado": ["condensado", "condensed"],
    "molho de tomate": ["molho", "sauce", "tomate"],
    "margarina": ["margarina", "margarine"],
    "queijo mussarela": ["queijo", "mussarela", "cheese"],
    "cerveja": ["cerveja", "beer"],
}


def carregar_existentes() -> dict:
    if not os.path.exists(ARQUIVO_SAIDA):
        return {}
    try:
        with open(ARQUIVO_SAIDA, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(dados, list):
        return {}
    return {p.get("gtin_ean"): p for p in dados if p.get("gtin_ean")}


def salvar(existentes: dict) -> None:
    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(list(existentes.values()), f, indent=2, ensure_ascii=False)


def buscar_por_termo(termo: str, pagina: int = 1, tamanho: int = 25) -> list:
    params = {
        "search_terms": termo,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": tamanho,
        "page": pagina,
    }
    ultimo_erro = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resp = requests.get(
                URL_BUSCA,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
            )
            if resp.status_code == 503:
                raise requests.exceptions.HTTPError(
                    f"503 Service Temporarily Unavailable (tentativa {tentativa})"
                )
            resp.raise_for_status()
            return resp.json().get("products", [])
        except requests.exceptions.RequestException as err:
            ultimo_erro = err
            if tentativa < MAX_TENTATIVAS:
                # Backoff progressivo: 3s, 6s, 9s...
                time.sleep(BACKOFF_SEGUNDOS * tentativa)
    raise ultimo_erro


def eh_relevante(termo: str, produto: dict) -> bool:
    palavras = PALAVRAS_CHAVE.get(termo, [termo])
    alvo = (
        str(produto.get("product_name_pt") or produto.get("product_name") or "")
        + " "
        + str(produto.get("product_name_en") or "")
    ).lower()
    return any(p in alvo for p in palavras)


def ean_valido(codigo) -> bool:
    """GTIN-13 válido: 13 dígitos numéricos."""
    if not codigo:
        return False
    codigo = str(codigo)
    return codigo.isdigit() and len(codigo) == 13


def extrair_cadastro(produto: dict) -> dict:
    nome = (
        produto.get("product_name_pt")
        or produto.get("product_name")
        or produto.get("abbreviated_product_name")
        or f"Produto sem nome registrado (EAN: {produto.get('code')})"
    )
    marcas = produto.get("brands")
    if marcas:
        marca = str(marcas).split(",")[0].strip()
    else:
        marca = "Não Informada"
    tags = produto.get("categories_tags") or produto.get("categories") or []
    categoria = "Geral"
    if tags:
        cat = str(tags[0]).strip()
        for prefixo in ("pt:", "en:", "fr:", "es:"):
            if cat.startswith(prefixo):
                cat = cat[len(prefixo):]
                break
        categoria = cat
    return {
        "gtin_ean": produto.get("code"),
        "nome": nome,
        "marca": marca,
        "categoria": categoria,
        "imagem_url": produto.get("image_front_url") or produto.get("image_url"),
        "data_cadastro": date.today().isoformat(),
    }


def main() -> None:
    existentes = carregar_existentes()
    print(f"Base existente: {len(existentes)} produto(s) em {ARQUIVO_SAIDA}")
    print("-" * 70)

    total = len(TERMOS_BUSCA)
    novos = 0
    for i, termo in enumerate(TERMOS_BUSCA, start=1):
        print(f"[{i}/{total}] Buscando: {termo}...")
        try:
            produtos = buscar_por_termo(termo)
        except requests.exceptions.RequestException as err:
            print(f"    ERRO de rede: {type(err).__name__} - {err}")
            time.sleep(INTERVALO_SLEEP)
            continue

        n_relev = 0
        n_novos = 0
        for p in produtos:
            if not ean_valido(p.get("code")) or not eh_relevante(termo, p):
                continue
            n_relev += 1
            ean = p["code"]
            if ean in existentes:
                continue
            existentes[ean] = extrair_cadastro(p)
            n_novos += 1
            novos += 1
        print(f"    {n_relev} relevantes | {n_novos} novos cadastros")
        time.sleep(INTERVALO_SLEEP)

    salvar(existentes)
    print("-" * 70)
    print(f"Resumo: {novos} novos cadastros nesta execução")
    print(f"Total no arquivo: {len(existentes)} produtos em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
