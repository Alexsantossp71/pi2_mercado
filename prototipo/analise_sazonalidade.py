# -*- coding: utf-8 -*-
"""
Protótipo de análise de sazonalidade de preços usando dados do IBGE (IPCA/SIDRA).
Fonte: API legada SIDRA (apisidra.ibge.gov.br) - tabela 7060 (IPCA), variável 63 (variação mensal).
"""

import csv
import json
import math
import os
import sys
import urllib.request
import urllib.parse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_URL = "https://apisidra.ibge.gov.br/values/t/7060/n1/all/v/63/p/all/c315/{}"

PRODUTOS = {
    "arroz": {"codigo": "7173", "rotulo": "Arroz"},
    "tomate": {"codigo": "7212", "rotulo": "Tomate"},
    "leite": {"codigo": "12393", "rotulo": "Leite longa vida"},
}


def baixar_serie(codigo_item):
    """Baixa a série de variação mensal do IPCA para um item específico."""
    url = BASE_URL.format(codigo_item)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    serie = []
    for linha in dados:
        if "V" in linha and linha.get("V", "Valor") not in ("Valor", None):
            try:
                mes = linha["D3C"]  # ex: 202001
                var = float(linha["V"])
                serie.append({"mes": mes, "ano": int(mes[:4]), "mes_num": int(mes[4:6]), "variacao": var})
            except (ValueError, KeyError):
                continue
    return serie


def reconstruir_indice(serie, base=100.0):
    """Converte variação mensal (%) em um índice de preço (nível)."""
    serie.sort(key=lambda x: x["mes"])
    nivel = base
    for i, registro in enumerate(serie):
        if i == 0:
            nivel = base
        else:
            nivel *= 1.0 + registro["variacao"] / 100.0
        registro["indice"] = nivel
    return serie


def calcular_sazonalidade(serie):
    """
    Calcula a média do índice de preço por mês do calendário (jan a dez).
    Retorna o ranking do mês mais barato (1) ao mais caro (12).
    """
    medias = {}
    for m in range(1, 13):
        valores = [r["indice"] for r in serie if r["mes_num"] == m]
        medias[m] = sum(valores) / len(valores) if valores else None
    ordenado = sorted((m for m, v in medias.items() if v is not None), key=lambda m: medias[m])
    ranking = {m: posicao + 1 for posicao, m in enumerate(ordenado)}
    return medias, ranking


NOMES_MESES = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
               "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def gerar_relatorio(resultados, pasta_saida):
    """Gera o relatório em texto e o CSV com os resultados."""
    linhas_txt = [
        "=" * 60,
        "ANÁLISE DE SAZONALIDADE DE PREÇOS - Fonte: IBGE (IPCA/SIDRA)",
        "Série de variação mensal acumulada em índice (base 100 no 1º mês).",
        "=" * 60,
        "",
    ]
    with open(os.path.join(pasta_saida, "sazonalidade.csv"), "w", newline="", encoding="utf-8-sig") as fcsv:
        writer = csv.writer(fcsv)
        writer.writerow(["produto", "mes_num", "mes", "indice_medio", "ranking"])

        for produto, dados in resultados.items():
            linhas_txt.append(f"\n### {dados['rotulo']} ###")
            linhas_txt.append(f"Período: {dados['inicio']} a {dados['fim']}  ({dados['n_meses']} meses)")
            linhas_txt.append(f"Faixa de preço (índice): {dados['min_indice']:.1f} - {dados['max_indice']:.1f} "
                              f"(amplitude {dados['amplitude']:.1f})")
            linhas_txt.append("")
            linhas_txt.append(f"{'Mês':<12} {'Índice médio':>14}  {'Melhor mês?'}")
            linhas_txt.append("-" * 50)
            for m in range(1, 13):
                if dados["medias"][m] is None:
                    continue
                marca = "  << MELHOR" if dados["ranking"][m] == 1 else ""
                linhas_txt.append(f"{NOMES_MESES[m]:<12} {dados['medias'][m]:>14.2f}{marca}")
                writer.writerow([produto, m, NOMES_MESES[m], round(dados["medias"][m], 2), dados["ranking"][m]])

            melhor_mes = next(m for m, pos in dados["ranking"].items() if pos == 1)
            linhas_txt.append(f"\n>>> Melhor mês para comprar {dados['rotulo'].lower()}: {NOMES_MESES[melhor_mes]}")

    with open(os.path.join(pasta_saida, "relatorio.txt"), "w", encoding="utf-8") as ftxt:
        ftxt.write("\n".join(linhas_txt))

    return "\n".join(linhas_txt)


def gerar_grafico(resultados, pasta_saida):
    """Gera o gráfico de sazonalidade dos três produtos."""
    fig, ax = plt.subplots(figsize=(10, 6))
    cores = {"arroz": "#2e86ab", "tomate": "#d64550", "leite": "#5b9279"}

    for produto, dados in resultados.items():
        meses = list(range(1, 13))
        valores = [dados["medias"][m] for m in meses]
        ax.plot(meses, valores, marker="o", label=dados["rotulo"], color=cores[produto], linewidth=2)
        melhor = next(m for m, pos in dados["ranking"].items() if pos == 1)
        ax.annotate(f"{NOMES_MESES[melhor]}",
                    xy=(melhor, dados["medias"][melhor]),
                    xytext=(melhor, dados["medias"][melhor] + max(dados["medias"].values()) * 0.02),
                    ha="center", color=cores[produto], fontsize=9, fontweight="bold")

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([NOMES_MESES[m] for m in range(1, 13)], rotation=45, ha="right")
    ax.set_ylabel("Índice de preço (base 100 no 1º mês da série)")
    ax.set_title("Sazonalidade de preços - quando comprar? (IBGE/IPCA)")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend()
    fig.tight_layout()
    caminho = os.path.join(pasta_saida, "grafico_sazonalidade.png")
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    return caminho


def main():
    pasta_saida = os.path.dirname(os.path.abspath(__file__))
    resultados = {}
    for produto, info in PRODUTOS.items():
        print(f"Baixando dados de {info['rotulo']}...")
        serie = baixar_serie(info["codigo"])
        if not serie:
            print(f"  ERRO: sem dados para {info['rotulo']}")
            continue
        serie = reconstruir_indice(serie)
        medias, ranking = calcular_sazonalidade(serie)
        resultados[produto] = {
            "rotulo": info["rotulo"],
            "inicio": serie[0]["mes"],
            "fim": serie[-1]["mes"],
            "n_meses": len(serie),
            "medias": medias,
            "ranking": ranking,
            "min_indice": min(r["indice"] for r in serie),
            "max_indice": max(r["indice"] for r in serie),
            "amplitude": max(r["indice"] for r in serie) - min(r["indice"] for r in serie),
        }

    if not resultados:
        print("Nenhum dado obtido. Verifique a conexão com a API SIDRA.")
        sys.exit(1)

    relatorio = gerar_relatorio(resultados, pasta_saida)
    print(relatorio)
    caminho_grafico = gerar_grafico(resultados, pasta_saida)
    print(f"\nArquivos gerados em {pasta_saida}:")
    print("  - sazonalidade.csv")
    print("  - relatorio.txt")
    print(f"  - {os.path.basename(caminho_grafico)}")


if __name__ == "__main__":
    main()
