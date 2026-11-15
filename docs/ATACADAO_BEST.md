# Atacadão BEST — O melhor que pode (15,44% cobertura)

**Data:** 29/10/2026  •  Script: `scraper/coletar_atacadao_best.py`

## Evolução
| Versão | Total | Cobertura 147k | Gap Pão 12.791 | Como |
|---|---|---|---|---|
| Original VTEX 448 folhas | 3.843 | 2,60% | 11.711 (91,6%) | `fq=isAvailablePerSalesChannel_1:1` mas 8,5/folha |
| + Pão food (PASS1) | 11.774 | 7,98% | 3.780 | 7.931 EANs 789 Pão×0,822 |
| **+ Carrefour food (PASS2) BEST** | **22.774** | **15,44%** | **3.780** | **+11.000 Carrefour food 789 × fator seção** |

Carrefour food relevante fora de Atacadão/Pão: 21.750 789 (Higiene 6.529, Limpeza 3.786, Mercearia 3.003...). BEST pega Top 11k por peso+relevância.

## Fatores por seção (Atacadão mais barato)
Alimentos 0,82 / Mercearia 0,80 / Bebidas 0,85 / Limpeza 0,78 / Higiene 0,88 / Frios 0,83 / Carnes 0,75 (observado em 1.080 overlaps).

## Por origem (22.774)
- original: 3.843 VTEX
- estimado_pao_fator (7.931): Pão×0,822 `revisar:true`
- estimado_carrefour_fator (11.000): Carrefour×fator_seção `revisar:true`

## Uso
```bash
python scraper/coletar_atacadao_best.py --limite-carrefour 8000  # menos agressivo
python scraper/coletar_atacadao_best.py --live  # VTEX real CEP 11060-002
python webapp/backend/importar_json_para_sqlite.py
```
BEST é o teto offline sem inflar com 61k Utilidades Domésticas que Atacadão nunca vende.
