#!/usr/bin/env python3
"""
Diagnóstico rápido de cobertura Soudaki — reproduzível localmente.
Lê os JSONs em webapp/ (ou /tmp se clonado via FETCH_HEAD) e emite tabela.

Uso:
  python docs/diagnostico_soudaki.py
  python docs/diagnostico_soudaki.py --json  # saída JSON para CI
"""
import json, pathlib, collections, sys, argparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Tenta webapp/ local, senão /tmp (para diagnóstico em arena)
candidates = [ROOT/"webapp/precos_soudaki_ampliado.json", pathlib.Path("/tmp/soudaki.json")]
SOUDAKI = next((p for p in candidates if p.exists()), None)
ATACADAO = ROOT/"webapp/precos_atacadao_ampliado.json"
CARREFOUR = ROOT/"webapp/precos_carrefour_ampliado.json"
PAO = ROOT/"webapp/precos_pao_de_acucar_ampliado.json"
PRODUTOS = pathlib.Path("/tmp/produtos.json") if pathlib.Path("/tmp/produtos.json").exists() else ROOT/"webapp/produtos_ampliado.json"

def load_json(path):
    if not path or not path.exists(): return []
    return json.loads(path.read_text(encoding="utf-8"))

def stats(path, nome):
    data = load_json(path)
    if not data: return {"loja": nome, "total": 0, "em_estoque": 0, "pct_estoque": 0, "cnt789": 0, "pct789": 0, "datas": {}, "path": str(path) if path else ""}
    em = sum(1 for x in data if x.get("em_estoque"))
    # distribuição por data_coleta
    from collections import Counter
    datas = Counter(x.get("data_coleta") for x in data)
    # EANs 789
    cnt789 = sum(1 for x in data if str(x.get("gtin_ean","")).startswith("789"))
    return {
        "loja": nome,
        "total": len(data),
        "em_estoque": em,
        "pct_estoque": round(em/len(data)*100,1) if data else 0,
        "cnt789": cnt789,
        "pct789": round(cnt789/len(data)*100,1) if data else 0,
        "datas": dict(datas.most_common(3)),
        "path": str(path)
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # Tenta carregar produtos para cobertura %
    produtos = load_json(PRODUTOS)
    if isinstance(produtos, dict): produtos = produtos.get("produtos", [])
    total_prod = len(produtos) if produtos else None

    lojas = [
        (CARREFOUR, "Carrefour"),
        (PAO, "Pão de Açúcar"),
        (ATACADAO, "Atacadão"),
        (SOUDAKI, "Soudaki"),
    ]
    rows = [stats(p,n) for p,n in lojas]
    for r in rows:
        if total_prod:
            r["cobertura_pct"] = round(r["total"]/total_prod*100,2)

    if args.json:
        print(json.dumps({"total_produtos": total_prod, "lojas": rows}, ensure_ascii=False, indent=2))
        return

    print("="*72)
    print("DIAGNÓSTICO SOUDAKI — Cobertura por loja")
    print("="*72)
    if total_prod:
        print(f"Catálogo (produtos_ampliado.json): {total_prod} EANs\n")
    print(f"{'Loja':<16} {'Total':>7} {'Cobertura':>9} {'Em estoque':>11} {'789%':>6}  Datas")
    print("-"*72)
    for r in rows:
        cob = f"{r.get('cobertura_pct',0):.2f}%" if total_prod else "?"
        print(f"{r['loja']:<16} {r['total']:>7} {cob:>9} {r['em_estoque']:>5} ({r['pct_estoque']}%) {r['pct789']:>5}%  {r['datas']}")
    print("\nSoudaki detalhe (seção -> qtd):")
    soud = load_json(SOUDAKI)
    if soud:
        sec = collections.Counter(x.get("secao") for x in soud)
        for k,v in sec.most_common():
            print(f"  {k!r:20} {v:>4}")
        # EANs internos
        gtins = [str(x.get("gtin_ean","")) for x in soud]
        from collections import Counter as C
        lens = C(len(g) for g in gtins)
        print("\nTamanho GTIN (Soudaki):", dict(lens.most_common(6)))
        print(f"Exemplos EAN falso (150...): {[g for g in gtins if g.startswith('150')][:3]}")
    print("\nDiagnóstico completo em docs/DIAGNOSTICO_SOUDAKI.md")

if __name__ == "__main__":
    main()
