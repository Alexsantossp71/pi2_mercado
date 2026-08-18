# -*- coding: utf-8 -*-
"""Construtor do cadastro 'produtos.json' a partir do Open Food Facts Brasil.

Uso:
    python construir_produtos.py

Dependência única: requests (pip install requests)
"""

import json
import os
import time
from datetime import date

import requests

# ---------------------------------------------------------------------------
# Configurações
# ---------------------------------------------------------------------------
ARQUIVO_SAIDA = "produtos.json"
USER_AGENT = "DispensaPlanejada_Santos_AcademicProject/1.0 (contato@dispensaplanejada.local)"
TIMEOUT = 10
INTERVALO_SLEEP = 1.2  # segundos entre requisições (rate limiting)

URL_BASE = "https://br.openfoodfacts.org/api/v0/product/{gtin_ean}.json"

# ---------------------------------------------------------------------------
# Lista de EANs reais do mercado brasileiro (cesta básica)
# ---------------------------------------------------------------------------
EANS_ESENCIAIS = [
    "7891000100103",  # Leite Ninho Integral 380g
    "7896036090123",  # Óleo de Soja Liza 900ml
    "7896017200015",  # Açúcar Refinado União 1kg
    "7896089000030",  # Café Pilão Tradicional 500g
    "7896036090024",  # Óleo de Soja Soya 900ml
    "7896063490017",  # Arroz Branco Tio João 5kg
    "7891000251659",  # Feijão Carioca Camil 1kg
    "7891150053999",  # Sabão em Pó Omo 1kg
    "7891024101502",  # Detergente Ypê 500ml
    "7896020772286",  # Papel Higiênico Neve 12 rolos
    "7891000100110",  # Leite Ninho Integral 800g
    "7896006736684",  # Leite Condensado Moça 395g
    "7896016800013",  # Farinha de Trigo Dona Benta 1kg
    "7891910000197",  # Cerveja Skol Lata 350ml
    "7894900010022",  # Guaraná Antarctica 2L
    "7891080123039",  # Açúcar Cristal União 5kg
    "7896011105053",  # Biscoito Água e Sal Marilan 400g
    "7896292302493",  # Café Melitta Tradicional 500g
    "7891000055144",  # Macarrão Espaguete Renata 500g
    "7891141990435",  # Sal Refinado Cisne 1kg
]

# ---------------------------------------------------------------------------
# Validações / transformação
# ---------------------------------------------------------------------------
def nome_produto(dados: dict, ean: str) -> str:
    """Prioriza product_name_pt, depois product_name, abbreviated_product_name."""
    produto = dados.get("product", {})
    for campo in ("product_name_pt", "product_name", "abbreviated_product_name"):
        valor = produto.get(campo)
        if valor and str(valor).strip():
            return str(valor).strip()
    return f"Produto sem nome registrado (EAN: {ean})"


def marca(dados: dict) -> str:
    """Pega 'brands' (primeira marca se houver múltiplas)."""
    produto = dados.get("product", {})
    valor = produto.get("brands")
    if not valor or not str(valor).strip():
        return "Não Informada"
    return str(valor).split(",")[0].strip()


def categoria(dados: dict) -> str:
    """Pega primeiro item de categories_tags ou categories, limpando prefixos pt:/en:."""
    produto = dados.get("product", {})
    tags = produto.get("categories_tags") or produto.get("categories") or []
    if not tags:
        return "Geral"
    primeiro = str(tags[0]).strip()
    for prefixo in ("pt:", "en:", "fr:", "es:"):
        if primeiro.startswith(prefixo):
            return primeiro[len(prefixo):]
    return primeiro


def imagem(dados: dict):
    """Prioriza image_front_url, depois image_url; senão None."""
    produto = dados.get("product", {})
    for campo in ("image_front_url", "image_url"):
        valor = produto.get(campo)
        if valor and str(valor).strip():
            return str(valor).strip()
    return None


def extrair_produto(dados: dict, ean: str) -> dict:
    """Converte a resposta da API no modelo cadastral."""
    return {
        "gtin_ean": ean,
        "nome": nome_produto(dados, ean),
        "marca": marca(dados),
        "categoria": categoria(dados),
        "imagem_url": imagem(dados),
        "data_cadastro": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# Persistência (evita duplicatas)
# ---------------------------------------------------------------------------
def carregar_existentes() -> dict:
    """Carrega produtos.json e devolve {gtin_ean: produto}."""
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


# ---------------------------------------------------------------------------
# Requisição individual com tratamento de exceções
# ---------------------------------------------------------------------------
def buscar_ean(ean: str):
    """Busca um EAN e retorna o produto extraído. Lança exceção em caso de rede."""
    url = URL_BASE.format(gtin_ean=ean)
    resp = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def processar_ean(ean: str) -> dict:
    dados = buscar_ean(ean)
    if dados.get("status") != 1:
        raise ValueError(f"produto não encontrado (status={dados.get('status')})")
    return extrair_produto(dados, ean)


# ---------------------------------------------------------------------------
# Execução principal
# ---------------------------------------------------------------------------
def main() -> None:
    existentes = carregar_existentes()
    print(f"Base existente: {len(existentes)} produto(s) em {ARQUIVO_SAIDA}")
    print("-" * 70)

    total = len(EANS_ESENCIAIS)
    sucesso = 0
    pulados = 0
    falhas = 0

    for i, ean in enumerate(EANS_ESENCIAIS, start=1):
        try:
            produto = processar_ean(ean)
            if ean in existentes:
                # Já cadastrado: apenas informa (sem duplicar)
                pulados += 1
                print(f"[{i}/{total}] EAN {ean} -> Já cadastrado: {produto['nome'][:40]}")
            else:
                existentes[ean] = produto
                sucesso += 1
                print(f"[{i}/{total}] EAN {ean} -> Sucesso: {produto['nome'][:40]}")
        except requests.exceptions.RequestException as err:
            falhas += 1
            print(f"[{i}/{total}] EAN {ean} -> ERRO de rede: {type(err).__name__}")
        except (ValueError, KeyError) as err:
            falhas += 1
            print(f"[{i}/{total}] EAN {ean} -> AVISO: {err}")
        finally:
            time.sleep(INTERVALO_SLEEP)

    salvar(existentes)
    print("-" * 70)
    print(f"Resumo: {sucesso} novos | {pulados} já existentes | {falhas} falhas")
    print(f"Total no arquivo: {len(existentes)} produtos em {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()
