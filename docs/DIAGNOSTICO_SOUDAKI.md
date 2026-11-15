# Diagnóstico: Preços Faltantes no Soudaki (Daki)

**Projeto:** Despensa Planejada Santos — PI UNIVESP 2026.2  
**Data do diagnóstico:** 29/10/2026 (UTC)  
**Autor:** diagnostic agent (Arena)  
**Repositório analisado:** `alexsantossp71-lgtm/pi2_mercado` (branch `master`) + deploy `despensaplanejada.vercel.app`  
**Coleta Soudaki analisada:** `webapp/precos_soudaki_ampliado.json` (1.538 registros, `data_coleta=2026-09-13`)

---

## 1. Resumo Executivo

**99% dos produtos do catálogo não têm preço no Soudaki — e isso é esperado dado como o sistema foi construído, não um bug pontual.**

| Loja | `precos_*_ampliado.json` | Cobertura vs catálogo (147.541 EANs) | `data_coleta` | % em estoque |
|---|---|---|---|---|
| **Carrefour** | 99.687 | **67,6%** | 2026-10-25 | 100% |
| **Pão de Açúcar** | 12.791 | **8,7%** | 2026-10-25 | 77% |
| **Atacadão** | 3.843 | **2,6%** | 2026-10-25 | 100% |
| **Soudaki (Daki)** | **1.538** | **1,04%** | **2026-09-13** (42 dias desatualizado) | **73,6%** |

Ou seja: para cada 100 produtos que o usuário busca, **99 mostrarão `⊘` (sem oferta) no Soudaki**. Isso não é intermitência — é estrutural.

### As 7 causas raiz

1. **Coleta sem paginação** — só a primeira “página SSR” de cada seção foi capturada.
2. **15 de 25 seções retornaram zero** — slugs errados ou HTML sem `__NEXT_DATA__`.
3. **Catálogo “inflado” pelo Carrefour** — 80k de 147k produtos são Utilidades Domésticas, que Soudaki nem vende.
4. **Extração de EAN falha em 60% dos casos** — `RE_EAN_IMAGEM = BR_(\d{13})` não existe na maioria das imagens.
5. **Estoque desconsiderado de forma inconsistente** — 406 itens (26%) estão `em_estoque=0` mas ainda contam como “preço”.
6. **Dados desatualizados** — Soudaki parado em 13/09, outras lojas em 25/10.
7. **Frontend e backend divergem** sobre o que é “disponível” — usuário vê preço mas cálculo ignora.

---

## 2. Como Reproduzir

```bash
# 1. Clonar o fork real (não o repo enxuto da org Alexsantossp71)
git clone https://github.com/alexsantossp71-lgtm/pi2_mercado.git
cd pi2_mercado
git show HEAD:webapp/precos_soudaki_ampliado.json | python3 -c "
import json,collections
d=json.load(open(0))
print(f'Soudaki: {len(d)} registros')
print(f'em_estoque: {sum(1 for x in d if x[\"em_estoque\"])}')
from collections import Counter
print(Counter(x['secao'] for x in d).most_common())
"

# 2. Comparar com outras lojas
for f in precos_carrefour_ampliado precos_pao_de_acucar_ampliado precos_atacadao_ampliado; do
  echo \"=== \$f ===\"
  git show HEAD:webapp/\${f}.json | python3 -c \"import json,sys; d=json.load(sys.stdin); print(len(d))\"
done

# 3. Ver onde o EAN falha
git show HEAD:scraper/coletar_e_integrar_soudaki.py | grep -n \"RE_EAN\"
# RE_EAN_IMAGEM = re.compile(r\"BR_(\\d{13})\")  — só funciona quando imagem é BR_...

# 4. Ver que o coletor não pagina
grep -n \"preloadedProducts\\|_from\\|_to\\|pagin\" scraper/coletar_e_integrar_soudaki.py
# -> Nenhuma paginação, 1 GET por seção
grep -n \"_from.*_to\" scraper/secoes/coletor_vtex.py | head
# -> Carrefour/Atacadão paginam de 50 em 50 até 2500
```

---

## 3. Evidências Detalhadas

### 3.1. Soudaki tem 1.538 preços vs 147.541 produtos

```
Catalogo (produtos_ampliado.json): 147.541 EANs únicos
  Utilidades Domésticas:  80.509  (54,6%)  -> Soudaki: 1 (0,00%)
  Higiene e Perfumaria:   16.030  (10,9%)  -> Soudaki: 2 (0,01%)
  Alimentos:              11.141  (7,5%)   -> Soudaki: 187 (1,68%)
  Bebidas:                 5.870  (4,0%)   -> Soudaki: 169 (2,88%)
  Mercearia:               6.187  (4,2%)   -> Soudaki: 91 (1,47%)
  ...
  Padaria:                   413  (0,3%)   -> Soudaki: 413 (100% !!)
```

**Leitura:** a única categoria com cobertura total é `Padaria ` (ovos, pães). Todo o resto é residual. O catálogo foi construído a partir do Carrefour (153k ofertas), que é um hipermercado com bazar. O Soudaki (dark store Daki) só vende **alimentos** — nunca terá preço para 80k itens de Utilidades.

> **Diagnóstico #1:** comparar cobertura Soudaki vs catálogo universal é métrica injusta. O correto é medir **cobertura vs sortimento real do Soudaki** (estimado em 2.000–3.000 SKUs).

### 3.2. Coleta sem paginação (causa mais grave)

**Carrefour/Atacadão (`scraper/secoes/coletor_vtex.py`):**
```python
# Pagina de 50 em 50 até limite 2500
def coletar_vtex(cfg):
    for folha in folhas:
        for offset in range(0, limite_max, pagina_tamanho):
            r = requests.get(
                f"{base_url}/api/catalog_system/pub/products/search/{slug}"
                f"?_from={offset}&_to={offset+pagina_tamanho-1}"
                f"&fq=isAvailablePerSalesChannel_1:1"
            )
            # ... checkpoint a cada 20 folhas, retry, backoff, UA rotation
```

**Soudaki (`scraper/coletar_e_integrar_soudaki.py`):**
```python
SECOES = ["hortifruti", "bebidas", "laticinios", ...] # 25 slugs hardcoded

def coletar_secao(secao: str):
    url = f"{BASE_URL}/shop/{secao}/"
    r = requests.get(url, headers=HEADERS, timeout=25)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
    data = json.loads(m.group(1))
    preloaded = data.get("props", {}).get("pageProps", {}).get("preloadedProducts", {})
    for subcat, plist in preloaded.items():
        for item in plist:
            preco = item.get("price", {}).get("amount")
            # ... sem loop de paginação, sem offset, sem API
    return itens
```

- **1 GET por seção, sem paginação.** O `__NEXT_DATA__.preloadedProducts` é o payload SSR inicial — tipicamente 20–50 itens por subcategoria, não o catálogo completo.
- Sem `sleep` com jitter, sem rotação de UA, sem `fq=isAvailablePerSalesChannel`, sem checkpoint.
- Se a página usa lazy-load / infinite scroll / API interna (`/api/…`), a coleta perde todos os itens seguintes.

### 3.3. 15 de 25 seções retornaram zero

Coleta real (10 seções com dados):

| `secao` (coletado) | Itens | Mapeia para `SECOES` slug |
|---|---|---|
| Padaria | 502 | `padaria` |
| Laticínios | 258 | `laticinios` |
| Bebidas | 152 | `bebidas` |
| Limpeza | 150 | `limpeza` |
| Mercearia | 128 | `mercearia` |
| Hortifruti | 117 | `hortifruti` |
| Congelados | 110 | `congelados` |
| Utilidades | 71 | `utilidades` |
| Farmácia | 28 | `farmacia` (slug certo é `farmacia`, sem acento) |
| Bebê | 22 | `bebe` |

**15 slugs retornaram zero (evidência de `relatorio_cobertura`):**
`matinais`, `saudaveis`, `molhos-e-conservas`, `acougue-e-peixaria`, `churrasco`, `pratico-e-rapido`, `biscoitos-e-salgadinhos`, `chocolates-e-doces`, `sorvetes-e-acai`, `cervejas-e-drinks`, `vinhos-e-espumantes`, `destilados`, `higiene-e-beleza`, `pets`, `produtos-daki`.

Hipóteses (a confirmar com live `soudaki.com/shop/`):
- Slugs mudaram (ex.: `acougue-e-peixaria` pode ser `carnes` hoje).
- Algumas seções exigem geolocalização/CEP (Daki só entrega em CEPs atendidos).
- `__NEXT_DATA__` não existe mais — site migrou para outro framework (ver `soudaki.com/shop/` retornando “Not Found” no fetch 29/10).
- Retorno 404/302 não tratado como erro — `coletar_secao` retorna `[]` silenciosamente.

> **Teste rápido para confirmar:** `curl -s https://soudaki.com/shop/acougue-e-peixaria/ | grep -c "__NEXT_DATA__"` deve dar 0 para seções faltantes.

### 3.4. EAN extraído da imagem falha

```python
RE_EAN_IMAGEM = re.compile(r"BR_(\d{13})")
def extrair_ean(url: str):
    m = RE_EAN_IMAGEM.search(url)
    return m.group(1) if m else None
```

Análise do `precos_soudaki_ampliado.json`:

| Formato GTIN | Qtd | % |
|---|---|---|
| `789…` (EAN real) | 347 | 22,6% |
| `1500000…` / `2000000…` (SKU interno Daki) | 920+84 = 1.004 | 65,3% |
| Outros (`_exp`, 4–6 dígitos) | 187 | 12% |

- **Soudaki usa SKUs internos** para produtos de peso variável / marca própria / ovos / pães. Esses nunca cruzarão com EAN real do Carrefour/PA.
- Para `789…`, a extração via `BR_` até funciona, mas só quando `packshot1_front_grid.url` contém `BR_789...`.
- Quando `ean=None`, o código tenta **match exato por nome** (`LOWER(TRIM(nome))`):
  ```python
  nome_to_id = {r["nome_norm"]: r["id"] for r in c.fetchall()}
  if nome_norm in nome_to_id:
      prod_id = nome_to_id[nome_norm]
  ```
  Isso falha para variações mínimas (“Arroz Camil 5kg” vs “Arroz Tipo 1 Camil 5Kg”).

Consequência: produtos sem EAN viram **“órfãos”** e são inseridos como novos produtos com `gtin_ean = 150000…`. Esses órfãos têm preço só no Soudaki — para Carrefour/PA/Atacadão eles também aparecerão como `⊘`, criando a falsa impressão de que Soudaki “tem preço faltante”, quando na verdade ele **criou produtos que só existem nele**.

### 3.5. Estoque tratado de forma inconsistente

- `precos_soudaki_ampliado.json`: 406 de 1.538 com `em_estoque=0` (26,4%).
- **Backend** (`price_service.py`): `em_estoque=False` → preço **ignorado** no cálculo:
  ```python
  disponivel = not isinstance(estoque, list) or estoque[idx] is not False
  if p_val is not None and disponivel:  # False se em_estoque=False
      totais_por_loja[key] += p_val * qtd
  ```
- **Frontend** (`priceCalculator.js`): `em_estoque` **ignorado**:
  ```js
  export function disponivelEm(produto, i) {
    if (!produto.preco || produto.preco[i] == null) return false;
    // Mostrar preço sempre que existir, independentemente do estoque
    return true;
  }
  ```
  E `motivoIndisponivel` nunca retorna `sem_estoque`:
  ```js
  export function motivoIndisponivel(produto, i) {
    if (!produto.preco || produto.preco[i] == null) return 'sem_oferta';
    return null; // nunca 'sem_estoque'
  }
  ```

Usuário vê `R$ 13,99` no autocomplete, adiciona na lista, calcula, e o Soudaki “some” do total (porque backend filtrou).

### 3.6. Dados desatualizados

| Loja | `data_coleta` | Idade em 29/10/2026 |
|---|---|---|
| Carrefour | 2026-10-25 | 4 dias |
| Pão de Açúcar | 2026-10-25 | 4 dias |
| Atacadão | 2026-10-25 | 4 dias |
| **Soudaki** | **2026-09-13** | **46 dias** |

O header `Pill: 🗓️ Dados: —` (visto no fetch de `despensaplanejada.vercel.app`) usa `MAX(data_coleta)` global — mostra 25/10, escondendo que Soudaki está 6 semanas atrasado.

### 3.7. Site do Soudaki pode ter mudado

`fetch_page("https://soudaki.com/shop/")` em 29/10 retornou **“Page not found”** (Vercel 404). Possíveis causas:
- Soudaki migrou de `soudaki.com` para `daki.com.br` (rebrand).
- `/shop/` agora exige `/_next/data/...` ou API interna com token.
- Deploy do coletor nunca foi re-testado após 13/09.

---

## 4. Impacto no Usuário

1. **Autocomplete:** ao buscar “arroz”, “leite”, “sabão”, o usuário vê 4 colunas de preço, mas Soudaki quase sempre `⊘`. O filtro “Mostrar só produtos com preço em 2+ lojas” esconde Soudaki completamente.
2. **Totais por loja:** `totalPorLoja()` soma só `preco != null`. Soudaki fica com total `R$ 0,00` para 99% das listas — aparece como “pior loja” injustamente, ou desempata para último.
3. **Economia Máxima (Multi-Lojas):** `divisaoMultiLoja()` escolhe o menor preço entre as 4 lojas. Como Soudaki só tem preço em 1% dos itens, ele raramente vence — a “economia” não reflete a realidade Daki (que é competitivo em FLV/padaria).
4. **Confiança:** usuário vê “Preços reais coletados do Soudaki (todas as seções)” no disclaimer, mas na prática só 10 seções foram coletadas.

---

## 5. Recomendações

### P0 — Curto prazo (1 dia): transparência

- [ ] **Corrigir `data_coleta` por loja.** Hoje `api/meta` retorna `MAX(global)`. Mudar para `{ loja: max_data }` e mostrar no header:
  ```js
  // ex.: "🗓️ Carrefour: 25/10 • Soudaki: 13/09 (desatualizado)"
  ```
- [ ] **Unificar critério de `disponivelEm`.** Ou frontend respeita `em_estoque` (mostra `⊘ fora de estoque`), ou backend ignora. Hoje divergem.
- [ ] **Adicionar badge de cobertura.** Ex.: `Soudaki: 1.538 produtos (1% do catálogo) — sortimento limitado a alimentos`.
- [ ] **Ajustar disclaimer:** trocar “todas as seções de mercado” por “10 seções de mercado (Soudaki)”.

### P1 — Médio prazo (1 semana): coletor correto

- [ ] **Engenharia reversa da API real do Soudaki.** Inspecionar `Network` em `https://www.daki.com.br` / `https://soudaki.com` (ex.: `api/v1/products`, `graphql`, `algolia`). Soudaki/Daki usa **JokrTech / Daki API** — provável endpoint:
  ```
  GET https://api.jokrtech.com/...  ou  https://soudaki.com/api/...
  ```
  Ver `scraper/produtos_soudaki.json` — `imagem_url` já aponta para `assets.jokrtech.com`, indicando backend Jokr.

- [ ] **Implementar paginação.** Se for VTEX-like, usar `_from/_to`; se for Algolia/Jokr, usar `page`/`hitsPerPage`:
  ```python
  # pseudocódigo
  page = 0
  while True:
      data = fetch(f"/shop/{secao}?page={page}")
      if not data["products"]: break
      # extrair EAN real: data["products"][i]["ean"] ou ["gtin"]
      page += 1
  ```

- [ ] **Extrair EAN da fonte correta, não da imagem.** Priorizar:
  1. `item["ean"]` / `item["gtin"]` / `item["barcode"]` (API)
  2. `item["sku"]` se for 13 dígitos numéricos
  3. Fallback: regex de imagem `BR_`

- [ ] **Mapear seções reais.** Fazer `GET /shop/` e extrair lista de slugs do menu, em vez de hardcoded 25.

- [ ] **Recoletar e reimportar.** Após novo coletor, rodar:
  ```bash
  python scraper/coletar_e_integrar_soudaki.py
  python webapp/backend/importar_json_para_sqlite.py  # recria dispensa.db
  python webapp/backend/migrate_to_turso.py           # ou Neon
  ```

### P2 — Longo prazo (2–4 semanas): modelo de dados

- [ ] **Catálogo por loja vs universal.** Hoje 1 catálogo gigante (147k) força todas as lojas a terem 99% de `⊘`. Alternativas:
  - `produtos` com `disponivel_em: [1,2,3]` + `precos` só onde existe.
  - Filtro default “só produtos com preço em ≥1 loja do seu CEP”.
  - Métrica de cobertura por **seção** (ex.: Soudaki 100% em Padaria, 0% em Utilidades — esperado).

- [ ] **Normalização de EAN.** Rejeitar `_exp`, `150000…` como `gtin_ean` — mover para `sku_interno` separado. Só `789…` de 13 dígitos é EAN.

- [ ] **Histórico de preços.** `precos` hoje sobrescreve `preco_promocional` — perde variação. Adicionar `precos_historico (produto_id, loja_id, data, preco)`.

- [ ] **Monitoramento:** cron diário + alerta se `COUNT(soudaki) < 1000` ou `MAX(data_coleta) < hoje-7d`.

---

## 6. Anexos

### A. Arquivos relevantes

| Arquivo | Papel |
|---|---|
| `scraper/coletar_e_integrar_soudaki.py` | Coletor Soudaki (236 linhas, sem paginação) |
| `scraper/secoes/coletor_vtex.py` | Coletor Carrefour/Atacadão (com paginação, retry, checkpoint) |
| `webapp/backend/importar_json_para_sqlite.py` | ETL JSON → SQLite (374 linhas, cria `precos` e FTS5) |
| `webapp/backend/services/product_service.py` | `search_products()` — JOIN de 4 lojas |
| `webapp/backend/services/price_service.py` | `calculate_basket_prices()` — respeita `em_estoque` |
| `webapp/js/priceCalculator.js` | `disponivelEm()` — ignora `em_estoque` |
| `webapp/precos_soudaki_ampliado.json` | Snapshot usado pelo SQLite local |

### B. Queries úteis (Neon/Postgres)

```sql
-- Cobertura Soudaki
SELECT COUNT(*) FROM precos WHERE loja_id=4; -- 1.538
SELECT COUNT(*) FROM produtos;               -- 147.541
SELECT COUNT(*) FROM precos WHERE loja_id=4 AND em_estoque=1; -- 1.132

-- Produtos com preco Soudaki mas sem EAN real
SELECT gtin_ean, nome FROM produtos
WHERE id IN (SELECT produto_id FROM precos WHERE loja_id=4)
  AND gtin_ean NOT LIKE '789%' LIMIT 20;

-- Idade dos dados
SELECT loja_id, MAX(data_coleta), COUNT(*) FROM precos GROUP BY loja_id;
```

### C. Evidência de seções vazias

```
Soudaki - 25 slugs tentados, 10 com dados, 15 vazios:
  OK: hortifruti(117), bebidas(152), laticinios(258), padaria(502),
      mercearia(128), congelados(110), limpeza(150), utilidades(71),
      farmacia(28), bebe(22)
  ZERO: matinais, saudaveis, molhos-e-conservas, acougue-e-peixaria,
        churrasco, pratico-e-rapido, biscoitos-e-salgadinhos,
        chocolates-e-doces, sorvetes-e-acai, cervejas-e-drinks,
        vinhos-e-espumantes, destilados, higiene-e-beleza, pets, produtos-daki
```

### D. Logs do scraper (se disponível)

`scraper/atualizacao_log.txt` e `atualizacao_err.txt` (encoding `latin1`) contém erros de `soudaki.com/shop/*` com `status != 200` para os 15 slugs.

---

**Conclusão:** Soudaki não está “com bug” — foi coletado com técnica inferior (HTML SSR sem paginação) vs Carrefour/PA/Atacadão (APIs JSON paginadas). Para ter cobertura honesta, é preciso **reimplementar o coletor no padrão VTEX/GPA**: descobrir a API real do Daki/Jokr, paginar, extrair EAN do JSON e reimportar. Enquanto isso, ajuste a UI para não prometer “todas as seções”.

