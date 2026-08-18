# -*- coding: utf-8 -*-
"""
Gera a lista de folhas-alvo (slugs) por loja a partir das árvores de categoria
extraídas da VTEX (dados/carrefour_full.json e dados/atacadao_full.json).

Aplica o filtro de seções-alvo e as exclusões de subseções atípicas definidas
em config_secoes.py. Para o Carrefour, cruza com dados/carrefour_folhas_dim.json
para anotar a contagem estimada de itens por folha.

Saídas:
  folhas_carrefour.json  -> {"folhas": [{"slug": ..., "itens_estimados": int|None}, ...], "resumo": {...}}
  folhas_atacadao.json   -> idem

Uso:
    python gerar_folhas.py
"""

import json
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from config_secoes import (
    SECOES_CARREFOUR,
    SECOES_ATACADAO,
    EXCLUIR_SUBSTRING,
)

BASE = os.path.dirname(os.path.abspath(__file__))
DADOS = os.path.join(BASE, "dados")


def carregar_json(nome: str):
    with open(os.path.join(DADOS, nome), encoding="utf-8") as f:
        return json.load(f)


def slug_limpo(slug: str) -> str:
    """Remove prefixo de domínio (Atacadão grava slug com URL completa)."""
    if slug.startswith("http"):
        slug = slug.split("secure.atacadao.com.br/")[-1].lstrip("/")
    return slug.strip("/")


def excluida(slug: str) -> bool:
    for sub in EXCLUIR_SUBSTRING:
        if sub in slug:
            return True
    return False


def nome_secao(arvore: list, slug: str) -> str:
    """Nome (pt-BR) da seção de nível 0 a partir do primeiro segmento do slug."""
    raiz = slug.split("/")[0]
    for n in arvore:
        if slug_limpo(n["slug"]) == raiz and n.get("lvl") == 0:
            return n.get("name") or raiz
    return raiz


def montar_folhas(arvore: list, secoes: tuple, pref) -> list:
    por_slug = {slug_limpo(n["slug"]): n for n in arvore}
    folhas = []
    for n in arvore:
        if not n.get("eh_folha"):
            continue
        slug = slug_limpo(n["slug"])
        if not slug or not slug.startswith(secoes):
            continue
        if excluida(slug):
            continue
        folhas.append({
            "slug": slug,
            "nome": n.get("name") or slug.split("/")[-1],
            "secao": nome_secao(arvore, slug),
        })
    return folhas


def gerar_carrefour() -> dict:
    arvore = carregar_json("carrefour_full.json")
    dims = carregar_json("carrefour_folhas_dim.json")
    dim_por_slug = {}
    for contagem, secao, slug in dims["grandes"] + dims["pequenas"]:
        dim_por_slug.setdefault(slug, contagem)

    folhas = montar_folhas(arvore, tuple(SECOES_CARREFOUR), "carrefour")
    for f in folhas:
        f["itens_estimados"] = dim_por_slug.get(f["slug"])

    # ordena: primeiro folhas pequenas (≤2500), depois grandes (truncam)
    folhas.sort(key=lambda x: (x["itens_estimados"] or 0) > 2500)
    return {"folhas": folhas}


def gerar_atacadao() -> dict:
    arvore = carregar_json("atacadao_full.json")
    folhas = montar_folhas(arvore, tuple(SECOES_ATACADAO), "atacadao")
    for f in folhas:
        f["itens_estimados"] = None
    return {"folhas": folhas}


def resumo(nome: str, folhas: list) -> None:
    pequenas = [f for f in folhas if (f["itens_estimados"] or 0) <= 2500]
    grandes = [f for f in folhas if (f["itens_estimados"] or 0) > 2500]
    total_items = sum(f["itens_estimados"] or 0 for f in folhas)
    print(f"=== {nome}: {len(folhas)} folhas-alvo | "
          f"pequenas: {len(pequenas)} | grandes(>2500, truncam): {len(grandes)} | "
          f"itens estimados: {total_items:,}")
    for f in grandes:
        print(f"   GRANDE [{f['itens_estimados']:,}]: {f['slug']}")


def main() -> None:
    c = gerar_carrefour()
    a = gerar_atacadao()

    for nome, dados in (("folhas_carrefour.json", c), ("folhas_atacadao.json", a)):
        caminho = os.path.join(BASE, nome)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        resumo(nome, dados["folhas"])

    print("\nArquivos salvos em", BASE)


if __name__ == "__main__":
    main()
