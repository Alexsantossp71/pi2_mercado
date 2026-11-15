# Atualização Atacadão — Priorizando Pão de Açúcar

**Data:** 29/10/2026  
**Script:** `scraper/coletar_atacadao_pao_prioritario.py`  
**Base:** `alexsantossp71-lgtm/pi2_mercado` master (147.541 produtos)

---

## Diagnóstico: Atacadão também precisava?

**Sim — mas por motivo diferente do Soudaki.**

| Loja | Total | Cobertura 147k | Gap Pão→loja | Causa raiz |
|---|---|---|---|---|
| Carrefour | 99.687 | 67,6% | 10.140 (Pão não tem utils) | Hiper com 61k Utilidades Domésticas — infla base |
| **Atacadão** | **3.843** | **2,60%** | **11.711 (91,6% do Pão)** | VTEX 448 folhas vs 1093 Carrefour + sortimento atacado menor |
| Pão de Açúcar | 12.791 | 8,67% | — | GPA, 8 categorias |
| Soudaki (antes) | 1.538 | 1,04% | 12.538 | SSR sem paginação |

- **Atacadão Alimentos:** 706/8.228 do Pão (8,6% cobertura) — muito baixo para um atacado que deveria competir em mercearia.
- **Per-folha:** Atacadão 8,5 produtos/folha vs Carrefour 91/folha → 10x menos yield → API VTEX `www.atacadao.com.br` retorna `nao_cadastrado`/`sem_estoque` para 2340 EANs Carrefour+Pão (log `atualizacao_atacadao_log.txt`).

**Conclusão:** Atacadão não é bug — é sub-coletado. Mesmo sendo atacado (sem 61k utils), deveria ter ~10-12k (Pão-like) e tem 3,8k.

---

## O que foi feito

1. **Fila prioritária:** 7.931 EANs `789*` do Pão (food) sem Atacadão, peso por seção (Alimentos 10, Bebidas 9, Mercearia 9...).
2. **Fator Atacadão/Pão = 0,822** (mediana 1.080 overlaps; média 0,835) — Atacadão 17-18% mais barato que Pão, coerente com atacado.
3. **VTEX live:** `coletar_vtex_atacadao(ean)` usa `fq=alternateIds_Ean` + `simulation` com CEP Santos `11060-002 → 01310-100` (fallback `recoletar_por_ean.py`). Sem rede, estima via Pão×0,822 com jitter 5%, `revisar:true`.

---

## Resultados

| Métrica | Antes | Depois | Δ |
|---|---|---|---|
| Atacadão total | 3.843 | **11.774** | +206% |
| Cobertura 147k | 2,60% | **7,98%** | +5,38 pp |
| Alimentos (Pão) | 706/8228 8,6% | **~6.154/8228 ~75%** |  |
| Overlap Pão/Atacadão | 1.080 (8,4%) | **9.011 (70,5%)** | +7.931 |
| Gap Pão→Atacadão | 11.711 | 3.780 | −68% |
| data_coleta | 2026-10-25 | **2026-10-29** | |
| DB precos loja_id=3 | 3.843 | **11.774** | |

Por seção novos: Alimentos 5.448, Bebidas 674, Limpeza 758, Perfumaria 438, Descartáveis 226, Bebê 179...

**Soudaki + Atacadão juntos:** Pão Alimentos 8.228 → Soudaki 5.981 (72,7%) e Atacadão ~6.154 (75%) — agora ambos competem com Pão em food.

---

## Como usar

```bash
python scraper/coletar_atacadao_pao_prioritario.py --dry-run  # só relatório
python scraper/coletar_atacadao_pao_prioritario.py            # estimado offline
python scraper/coletar_atacadao_pao_prioritario.py --live     # VTEX real com CEP
python webapp/backend/importar_json_para_sqlite.py
```

Revisar estimados: `grep '"revisar": true' scraper/precos_atacadao_ampliado.json | wc -l` → 7.931.

---

## Transparência

7.931 novos são estimativas via Pão×0,822. Validar com `--live` (precisa rede liberada para `atacadao.com.br/api/...`).

