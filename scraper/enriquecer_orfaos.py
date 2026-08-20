# -*- coding: utf-8 -*-
"""
Enriquece produtos órfãos consultando as APIs dos supermercados.

Produtos "órfãos" = EANs que existem em precos_*_ampliado.json mas não têm
cadastro completo em produtos_ampliado.json.

Fontes de enriquecimento (em ordem de prioridade):
  1. VTEX (Carrefour / Atacadão) — consulta por EAN via API de busca
  2. GPA (Pão de Açúcar) — já cobre o catálogo, mas verifica faltantes
  3. Open Food Facts — fallback para EANs que nenhuma loja retornou

Uso:
    python enriquecer_orfaos.py
"""

import json
import os
import re
import sys
import time
from datetime import date

import requests

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
RAIZ = os.path.dirname(os.path.abspath(__file__))
ARQ_PRODUTOS = os.path.join(RAIZ, "produtos_ampliado.json")
ARQ_PRECOS = {
    "carrefour": os.path.join(RAIZ, "precos_carrefour_ampliado.json"),
    "atacadao": os.path.join(RAIZ, "precos_atacadao_ampliado.json"),
    "pao_de_acucar": os.path.join(RAIZ, "precos_pao_de_acucar_ampliado.json"),
}
ARQ_CHECKPOINT = os.path.join(RAIZ, "enriquecimento_progresso.json")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

RE_APRESENTACAO = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(g|kg|ml|l|un|unid|unidade)\b", re.IGNORECASE
)

HOJE = date.today().isoformat()


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def carregar_json(caminho: str) -> list:
    if not os.path.exists(caminho):
        return []
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
    return dados if isinstance(dados, list) else []


def salvar_json(caminho: str, dados) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def extrair_apresentacao(nome: str) -> dict | None:
    match = RE_APRESENTACAO.search(nome)
    if not match:
        return None
    qtd_str = match.group(1).replace(",", ".")
    unidade = match.group(2).lower().strip()
    if unidade in ("unid", "unidade"):
        unidade = "un"
    try:
        qtd = float(qtd_str)
        if qtd.is_integer():
            qtd = int(qtd)
    except ValueError:
        return None
    return {"quantidade": qtd, "unidade_medida": unidade}


# ---------------------------------------------------------------------------
# Fonte 1: VTEX (Carrefour / Atacadão)
# ---------------------------------------------------------------------------
VTEX_CONFIGS = {
    "carrefour": {
        "base_url": "https://www.carrefour.com.br",
        "marcador": "carrefourbrfood",
    },
    "atacadao": {
        "base_url": "https://www.atacadao.com.br",
        "marcador": "atacadaobr",
    },
}


def buscar_vtex_por_ean(ean: str, loja: str) -> dict | None:
    """Consulta a API VTEX de busca por EAN."""
    cfg = VTEX_CONFIGS.get(loja)
    if not cfg:
        return None
    url = f"{cfg['base_url']}/api/catalog_system/pub/products/search"
    params = {"fq": f"alternateIds_Ean:{ean}"}
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        dados = resp.json()
        if not dados:
            return None
        prod = dados[0]
        nome = (prod.get("productName") or "").strip()
        if not nome:
            return None
        imagem_url = None
        items = prod.get("items") or [{}]
        imgs = items[0].get("images") or [{}]
        if imgs:
            imagem_url = imgs[0].get("imageUrl")
        return {
            "gtin_ean": ean,
            "nome_completo": nome,
            "marca": (prod.get("brand") or "Não Informada").strip(),
            "secao": (prod.get("categories") or ["Geral"])[0].split("/")[-2] if prod.get("categories") else "Geral",
            "subsecao": "",
            "apresentacao": extrair_apresentacao(nome),
            "imagem_url": imagem_url,
            "data_cadastro": HOJE,
            "fonte_enriquecimento": f"vtex_{loja}",
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Fonte 2: Open Food Facts (fallback global)
# ---------------------------------------------------------------------------
def buscar_off_por_ean(ean: str) -> dict | None:
    """Consulta a API do Open Food Facts."""
    url = f"https://world.openfoodfacts.org/api/v2/product/{ean}.json"
    headers = {"User-Agent": f"DispensaPlanejada/1.0 ({USER_AGENT})"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("status") != 1:
            return None
        prod = data.get("product", {})
        nome = (
            prod.get("product_name_pt")
            or prod.get("product_name_pt_br")
            or prod.get("product_name")
            or ""
        ).strip()
        if not nome:
            return None
        marca = (prod.get("brands") or "Não Informada").split(",")[0].strip()
        categorias = prod.get("categories_tags") or []
        categoria = "Geral"
        if categorias:
            # Pega a categoria mais específica
            cat = categorias[-1].replace("en:", "").replace("pt:", "").replace("-", " ").title()
            categoria = cat
        return {
            "gtin_ean": ean,
            "nome_completo": nome,
            "marca": marca,
            "secao": categoria,
            "subsecao": "",
            "apresentacao": extrair_apresentacao(nome),
            "imagem_url": prod.get("image_front_url"),
            "data_cadastro": HOJE,
            "fonte_enriquecimento": "open_food_facts",
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("Enriquecimento de produtos orfaos")
    print("=" * 72)

    # Carrega catálogo atual
    produtos = carregar_json(ARQ_PRODUTOS)
    gtins_catalogo = {p["gtin_ean"] for p in produtos if p.get("gtin_ean")}
    print(f"Catalogo atual: {len(produtos):,} produtos ({len(gtins_catalogo):,} EANs)")

    # Identifica órfãos
    orfaos = set()
    orfao_lojas = {}  # EAN -> lista de lojas onde aparece
    for loja, arq in ARQ_PRECOS.items():
        precos = carregar_json(arq)
        for p in precos:
            ean = p.get("gtin_ean")
            if ean and ean not in gtins_catalogo:
                orfaos.add(ean)
                orfao_lojas.setdefault(ean, []).append(loja)

    print(f"EANs orfaos a enriquecer: {len(orfaos):,}")

    if not orfaos:
        print("Nenhum orfao encontrado. Nada a fazer.")
        return

    # Carrega progresso anterior (retomada)
    ja_tentados = set()
    if os.path.exists(ARQ_CHECKPOINT):
        with open(ARQ_CHECKPOINT, "r", encoding="utf-8") as f:
            checkpoint = json.load(f)
            ja_tentados = set(checkpoint.get("tentados", []))
        print(f"Retomando: {len(ja_tentados):,} EANs ja tentados")

    pendentes = sorted(orfaos - ja_tentados)
    print(f"Pendentes nesta execucao: {len(pendentes):,}")
    print("-" * 72)

    novos = []
    encontrados_vtex = 0
    encontrados_off = 0
    nao_encontrados = 0
    erros = 0

    for i, ean in enumerate(pendentes, 1):
        resultado = None
        lojas = orfao_lojas.get(ean, [])

        # Tenta VTEX (Carrefour primeiro, depois Atacadão)
        for loja in ["carrefour", "atacadao"]:
            resultado = buscar_vtex_por_ean(ean, loja)
            if resultado:
                encontrados_vtex += 1
                break
            time.sleep(0.15)

        # Fallback: Open Food Facts
        if not resultado:
            resultado = buscar_off_por_ean(ean)
            if resultado:
                encontrados_off += 1
            time.sleep(0.3)

        if resultado:
            novos.append(resultado)
        else:
            nao_encontrados += 1

        ja_tentados.add(ean)

        # Progresso e checkpoint a cada 100
        if i % 100 == 0 or i == len(pendentes):
            salvar_json(ARQ_CHECKPOINT, {
                "tentados": sorted(ja_tentados),
                "encontrados_vtex": encontrados_vtex,
                "encontrados_off": encontrados_off,
                "nao_encontrados": nao_encontrados,
            })
            pct = i / len(pendentes) * 100
            print(
                f"  [{i:,}/{len(pendentes):,}] ({pct:.1f}%) "
                f"VTEX={encontrados_vtex} OFF={encontrados_off} "
                f"sem_dados={nao_encontrados} | novos={len(novos)}"
            )

    # Merge com catálogo existente
    if novos:
        produtos.extend(novos)
        salvar_json(ARQ_PRODUTOS, produtos)
        print(f"\n{len(novos):,} produtos adicionados ao catalogo!")

    # Remove checkpoint ao finalizar com sucesso
    if os.path.exists(ARQ_CHECKPOINT):
        os.remove(ARQ_CHECKPOINT)

    print("-" * 72)
    print(f"Catalogo final: {len(produtos):,} produtos")
    print(f"  Encontrados via VTEX: {encontrados_vtex:,}")
    print(f"  Encontrados via OFF:  {encontrados_off:,}")
    print(f"  Sem dados (EAN only): {nao_encontrados:,}")
    print("=" * 72)


if __name__ == "__main__":
    main()
