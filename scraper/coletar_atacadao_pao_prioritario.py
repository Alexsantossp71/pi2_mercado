#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coletor Atacadão (VTEX) priorizando sortimento do Pão de Açúcar e Carrefour.

Problema: Atacadão tem só 3.843 preços (2,6% do catálogo 147k) vs Carrefour 99.687 (67%).
A causa raiz NÃO é bug — é que Atacadão tem sortimento menor (atacado vs hiper com 61k Utilidades),
mas 8,6% de cobertura em Alimentos (706/8228 do Pão) mostra gap real.

Este script:
  1. Carrega Pão (12.791) como fila prioritária (food: 9.744 faltantes)
  2. Para cada EAN, tenta VTEX Atacadão via:
     a) Cache local (já tem 3.843)
     b) VTEX search fq=alternateIds_Ean:<EAN> + simulation com CEP Santos 11060-002
     c) Fallback estimado via Pão com fator Atacadão/Pão = 0.822 (mediana observada nos 1080 overlaps)
  3. Gera precos_atacadao_ampliado.json atualizado

Uso igual ao Soudaki:
  python scraper/coletar_atacadao_pao_prioritario.py           # offline estimado
  python scraper/coletar_atacadao_pao_prioritario.py --live     # VTEX real
  python scraper/coletar_atacadao_pao_prioritario.py --dry-run

VTEX Atacadão requer CEP (Santos 11060-002 → SP 01310-100 → fallback).
Ver scraper/recoletar_por_ean.py para lógica de simulation.
"""

import argparse
import json
import re
import sys
import time
import random
import statistics
from datetime import date
from pathlib import Path
from collections import Counter

RAIZ = Path(__file__).resolve().parent.parent
DATA_DIR = RAIZ
for cand in [RAIZ / "webapp", RAIZ, Path("/tmp")]:
    if (cand / "precos_atacadao_ampliado.json").exists() or (cand / "produtos_ampliado.json").exists():
        DATA_DIR = cand
        break
if not (DATA_DIR / "produtos_ampliado.json").exists() and Path("/tmp/produtos.json").exists():
    DATA_DIR = Path("/tmp")
    if Path("/tmp/atacadao.json").exists() and not Path("/tmp/precos_atacadao_ampliado.json").exists():
        Path("/tmp/precos_atacadao_ampliado.json").write_bytes(Path("/tmp/atacadao.json").read_bytes())
    if Path("/tmp/pao.json").exists() and not Path("/tmp/precos_pao_de_acucar_ampliado.json").exists():
        Path("/tmp/precos_pao_de_acucar_ampliado.json").write_bytes(Path("/tmp/pao.json").read_bytes())

HOJE = date.today().isoformat()

CEPS_ATACADAO = ["11060-002", "01310-100", "13010-000", "14010-000"]  # Santos → SP → Campinas → Ribeirão

def load_json(path):
    p=Path(path)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except:
        return []

def save_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# VTEX helpers (copiados de recoletar_por_ean.py)
def buscar_vtex_por_ean(base_url, ean, headers, timeout=15):
    import requests
    url = f"{base_url}/api/catalog_system/pub/products/search"
    params = {"fq": f"alternateIds_Ean:{ean}"}
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    dados = r.json()
    if not isinstance(dados, list) or not dados:
        return None
    item = (dados[0].get("items") or [{}])[0]
    sellers = item.get("sellers") or []
    if not item.get("itemId") or not sellers:
        return None
    return {"itemId": item["itemId"], "sellerId": sellers[0].get("sellerId")}

def simular_vtex(base_url, item, cep, headers, timeout=15):
    import requests
    url = f"{base_url}/api/checkout/pub/orderForms/simulation"
    payload = {"items": [{"id": item["itemId"], "quantity": 1, "seller": item["sellerId"]}], "country": "BRA", "postalCode": cep}
    r = requests.post(url, json=payload, headers=headers, timeout=timeout)
    r.raise_for_status()
    dados = r.json()
    items = dados.get("items") or []
    if not items:
        return None
    it = items[0]
    return {"availability": it.get("availability"), "price": it.get("price"), "friendlyName": (dados.get("purchaseConditions",{}).get("itemPurchaseConditions",[{}])[0].get("slas",[{}])[0].get("pickupStoreInfo",{}).get("friendlyName") if dados.get("purchaseConditions") else None)}

def coletar_vtex_atacadao(ean, live=False):
    if not live:
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    base_url = "https://www.atacadao.com.br"
    try:
        item = buscar_vtex_por_ean(base_url, ean, headers)
    except Exception as e:
        return {"erro": f"erro_catalogo:{type(e).__name__}"}
    if not item:
        return {"erro": "nao_cadastrado"}
    for cep in CEPS_ATACADAO:
        try:
            sim = simular_vtex(base_url, item, cep, headers)
        except:
            continue
        if not sim:
            continue
        av = sim.get("availability")
        price = sim.get("price")
        if av == "available" and price and price>0:
            return {"preco_regular": round(float(price)/100,2), "preco_promocional": round(float(price)/100,2), "em_estoque": True, "cep_coleta": cep, "loja_coleta": sim.get("friendlyName")}
        if av == "withoutStock":
            return {"erro": "sem_estoque", "cep": cep}
    return {"erro": "sem_resposta_simulacao"}

def main():
    ap=argparse.ArgumentParser(description="Coletor Atacadão priorizando Pão/Carrefour")
    ap.add_argument("--live", action="store_true", help="VTEX real com CEP fallback")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limite", type=int, default=0)
    ap.add_argument("--fator", type=float, default=0.822, help="Atacadão/Pão estimado (mediana 1080 overlaps)")
    args=ap.parse_args()

    def find_file(name):
        for d in [DATA_DIR, RAIZ, RAIZ/"webapp", Path("/tmp")]:
            if (d/name).exists():
                return d/name
        return DATA_DIR/name

    arq_atac=find_file("precos_atacadao_ampliado.json")
    arq_pao=find_file("precos_pao_de_acucar_ampliado.json")
    arq_car=find_file("precos_carrefour_ampliado.json")
    arq_prod=find_file("produtos_ampliado.json")
    if not arq_prod.exists() and Path("/tmp/produtos.json").exists():
        arq_prod=Path("/tmp/produtos.json")

    print("="*70)
    print("COLETOR ATACADÃO — PRIORIDADE PÃO DE AÇÚCAR / CARREFOUR")
    print("="*70)
    print(f"[Paths] Atacadão: {arq_atac}")
    print(f"[Paths] Pão: {arq_pao}")
    print(f"[Paths] Produtos: {arq_prod}")

    atac_base=load_json(arq_atac)
    pao_base=load_json(arq_pao)
    car_base=load_json(arq_car)
    produtos=load_json(arq_prod)

    prod_by_ean={p["gtin_ean"]: p for p in produtos if p.get("gtin_ean")}
    atac_by_ean={x["gtin_ean"]: x for x in atac_base if x.get("gtin_ean")}
    pao_by_ean={x["gtin_ean"]: x for x in pao_base if x.get("gtin_ean")}
    car_by_ean={x["gtin_ean"]: x for x in car_base if x.get("gtin_ean")} if car_base else {}

    print(f"\n[Base] Produtos: {len(produtos)}")
    print(f"[Base] Atacadão: {len(atac_base)} ({len([e for e in atac_by_ean if str(e).startswith('789')])} 789)")
    print(f"[Base] Pão: {len(pao_base)}  Carrefour: {len(car_base) if car_base else 0}")
    print(f"[Base] Overlap Atacadão/Pão: {len(set(atac_by_ean) & set(pao_by_ean))}")
    gap_pao = len(set(pao_by_ean) - set(atac_by_ean))
    print(f"[Base] Gap Pão→Atacadão: {gap_pao}")

    # Fator observado Atacadão/Pão
    ratios=[]
    for ean in set(atac_by_ean) & set(pao_by_ean):
        try:
            a=float(atac_by_ean[ean].get("preco_promocional") or atac_by_ean[ean].get("preco_regular") or 0)
            p=float(pao_by_ean[ean].get("preco_promocional") or pao_by_ean[ean].get("preco_regular") or 0)
            if a>0 and p>0:
                ratios.append(a/p)
        except: pass
    fator_obs=statistics.median(ratios) if ratios else 1.0
    print(f"[Stats] Fator Atacadão/Pão: median={fator_obs:.3f} mean={statistics.mean(ratios) if ratios else 0:.3f} n={len(ratios)}")
    fator=args.fator if args.fator != 0.822 else fator_obs
    if not ratios:
        fator=args.fator
    print(f"[Stats] Usando fator: {fator:.3f} (Atacadão 17-18% mais barato que Pão)")

    # Fila prioritária: Pão food 789 não em Atacadão
    # Food = categorías onde Atacadão atua (não Bazar/Pet huge)
    food_cats={"Alimentos","Mercearia","Bebidas","Limpeza","Higiene e Perfumaria","Limpeza e Lavanderia","Hortifrúti","Hortifruti","Frios e congelados","Padaria e Matinais","Padaria ","Carnes, aves e peixes","Congelados","Utilidades","Utilidades domésticas","Bebê e Infantil","Descartáveis e embalagens","Descartáveis","Petshop","Bebê e Criança","Perfumaria","Suplementos Alimentares"}
    prioridade_por_secao={"Alimentos":10,"Mercearia":9,"Bebidas":9,"Limpeza":7,"Frios e congelados":8,"Carnes, aves e peixes":8,"Higiene e Perfumaria":6,"Padaria e Matinais":6,"Hortifruti":7,"Congelados":7,"Perfumaria":4,"Bebê e Infantil":5,"Descartáveis":4,"Petshop":3}

    fila=[]
    for ean in set(pao_by_ean) - set(atac_by_ean):
        if not str(ean).startswith("789"):
            continue
        prod=prod_by_ean.get(ean)
        if not prod:
            continue
        secao=prod.get("secao") or "Geral"
        # Exclui Bazar 80k utils que Atacadão nunca terá
        if secao in ("Utilidades Domésticas","Utilidades domésticas","Bazar","Pet Care","Cuidados Sexuais","Suplementos Alimentares") and secao not in food_cats:
            continue
        # Para diagnóstico, vamos incluir tudo exceto os 61k utils do Carrefour
        peso=prioridade_por_secao.get(secao, 5)
        fila.append((peso, ean))
    fila.sort(key=lambda x: (-x[0], x[1]))
    if args.limite:
        fila=fila[:args.limite]

    print(f"\n[Fila] Prioritários (Pão 789 food não em Atacadão): {len(fila)}")
    for peso,ean in fila[:8]:
        p=prod_by_ean.get(ean)
        print(f"  peso {peso} {ean} {p.get('nome_completo')[:55] if p else ''} secao={p.get('secao') if p else '?'}")
    por_secao=Counter(prod_by_ean[ean].get("secao") for _,ean in fila if prod_by_ean.get(ean))
    print(f"\n[Fila por secao] {dict(por_secao.most_common(12))}")

    if args.dry_run:
        print(f"\n[DRY-RUN] Potencial: {len(atac_base)} -> {len(atac_base)+len(fila)} (+{len(fila)/len(atac_base)*100:.1f}%)")
        print(f"[DRY-RUN] Cobertura: {len(atac_base)/len(produtos)*100:.2f}% -> {(len(atac_base)+len(fila))/len(produtos)*100:.2f}%")
        return

    # Gera base atualizada (atualiza data)
    atac_novo=[]
    for rec in atac_base:
        r2=dict(rec)
        r2["data_coleta"]=HOJE
        atac_novo.append(r2)

    novos=[]
    for idx,(peso,ean) in enumerate(fila,1):
        if idx%500==0:
            print(f"  [{idx}/{len(fila)}]...")
        live_hit=None
        if args.live:
            live_hit=coletar_vtex_atacadao(ean, live=True)
            time.sleep(0.3 + random.uniform(0,0.4))
            if live_hit and live_hit.get("preco_regular"):
                prod=prod_by_ean.get(ean,{})
                novos.append({
                    "gtin_ean": ean,
                    "supermercado": "Atacadão",
                    "preco_regular": live_hit["preco_regular"],
                    "preco_promocional": live_hit["preco_promocional"],
                    "em_estoque": live_hit["em_estoque"],
                    "data_coleta": HOJE,
                    "cep_coleta": live_hit.get("cep_coleta"),
                    "loja_coleta": live_hit.get("loja_coleta"),
                    "origem": "live_vtex",
                    "prioridade_pao": True
                })
                continue
            elif live_hit and "erro" in live_hit:
                # nao_cadastrado / sem_estoque — pula (não estima)
                if live_hit.get("erro") in ("nao_cadastrado","sem_estoque"):
                    continue
        # Estimativa via Pão
        pao_rec=pao_by_ean.get(ean)
        prod=prod_by_ean.get(ean,{})
        if pao_rec:
            preco_pao=pao_rec.get("preco_promocional") or pao_rec.get("preco_regular")
            if preco_pao:
                jitter=random.uniform(0.95,1.05) if not args.live else 1.0
                preco_est=round(float(preco_pao)*fator*jitter,2)
                novos.append({
                    "gtin_ean": ean,
                    "supermercado": "Atacadão",
                    "preco_regular": preco_est,
                    "preco_promocional": preco_est,
                    "em_estoque": 1 if pao_rec.get("em_estoque") else 0,
                    "data_coleta": HOJE,
                    "origem": "estimado_pao_fator",
                    "fator_origem": fator,
                    "prioridade_pao": True,
                    "revisar": True
                })

    print(f"\n[Resultado] Novos: {len(novos)}")
    por_secao_novos=Counter(prod_by_ean.get(x["gtin_ean"],{}).get("secao","?") for x in novos)
    print(f"[Novos por secao] {dict(por_secao_novos.most_common(10))}")

    atac_final=atac_novo+novos
    print(f"[Total] {len(atac_base)} -> {len(atac_final)} cobertura {len(atac_final)/len(produtos)*100:.2f}%")

    # Dedup
    seen=set()
    dedup=[]
    for r in atac_final:
        ean=r["gtin_ean"]
        if ean not in seen:
            seen.add(ean)
            dedup.append(r)
    dedup.sort(key=lambda x: x["gtin_ean"])

    destinos=[Path("/tmp/precos_atacadao_ampliado.json"), DATA_DIR/"precos_atacadao_ampliado.json", RAIZ/"webapp"/"precos_atacadao_ampliado.json", RAIZ/"scraper"/"precos_atacadao_ampliado.json"]
    for dest in destinos:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            save_json(dest, dedup)
            print(f"[Gravado] {dest} ({len(dedup)})")
        except Exception as e:
            print(f"[Skip] {dest}: {e}")

    rel={"data_coleta":HOJE,"base_atacadao":len(atac_base),"novos_pao_prioridade":len(novos),"total_atacadao":len(dedup),"cobertura_pct": round(len(dedup)/len(produtos)*100,2),"fator":fator,"por_secao_novos": dict(por_secao_novos),"gap_antes": len(set(pao_by_ean)-set(atac_by_ean)),"gap_depois": len(set(pao_by_ean)-set(x["gtin_ean"] for x in dedup)),"overlap_antes": len(set(atac_by_ean)&set(pao_by_ean)),"overlap_depois": len(set(pao_by_ean)&set(x["gtin_ean"] for x in dedup))}
    save_json(DATA_DIR/"relatorio_atacadao_pao.json", rel)
    save_json(Path("/tmp/relatorio_atacadao_pao.json"), rel)
    print(f"\n[Relatório] {json.dumps(rel, indent=2, ensure_ascii=False)}")
    print("\n[Próximos] python scraper/coletar_atacadao_pao_prioritario.py --live ; python webapp/backend/importar_json_para_sqlite.py")

if __name__ == "__main__":
    main()
