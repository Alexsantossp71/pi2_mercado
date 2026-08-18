# Teoria do Scraping — Dispensa Planejada (Santos)

Documento que explica **como** o scraping de preços de supermercado foi feito,
**quais técnicas** foram usadas, **por que** certas estratégias foram escolhidas,
**que resultado** foi obtido e **onde** está cada parte do código.

Todo o código atualizado citado aqui está na subpasta [`codigos/`](./codigos).

---

## 1. Contexto do problema

O Dispensa Planejada é um comparador de preços de supermercado para a cidade de Santos. Para ele funcionar de forma realista, precisávamos de dados reais e atualizados de três grandes varejistas da região:

| Loja | Plataforma | Endpoint principal |
|---|---|---|
| **Carrefour** | VTEX | `api/catalog_system/pub/products/search` |
| **Atacadão** | VTEX | `api/catalog_system/pub/products/search` |
| **Pão de Açúcar** | GPA | `api.vendas.gpa.digital/pa/search/category-page` + `v4/products/ecom/{id}` |

O desafio foi: em vez de raspar **HTML** (frágil, sujeito a mudanças no layout e lento), encontramos e exploramos as **APIs REST de backend que os próprios sites utilizam**. Isso torna a coleta muito mais rápida, estruturada, confiável e limpa.

---

## 2. Técnicas de scraping utilizadas

### 2.1 Consumo de APIs públicas (Web Scraping de JSON)
Ao inspecionar o tráfego de rede (DevTools) das lojas, identificamos os webservices que devolvem respostas em JSON.
- **Vantagens**: Uma única requisição retorna de 36 a 50 itens já estruturados com EAN, preço regular, preço promocional, estoque, marca, apresentação e URL da imagem.

### 2.2 VTEX: busca paginada por intervalo (`_from` / `_to`)
Para as lojas na plataforma VTEX (Carrefour e Atacadão), a paginação utiliza o parâmetro de intervalo:
```http
GET /api/catalog_system/pub/products/search/{slug}?_from=0&_to=49
```
O coletor faz requisições em blocos de 50 itens e avança o offset até o fim da folha ou limite máximo imposto pela API (2.500 itens).

### 2.3 Árvore de categorias como "folhas-alvo"
Extraímos a **árvore de categorias** da VTEX via API. Cada nó folha gera um `slug` de busca (ex: `bebidas/nao-alcoolicas/sucos`). O script `gerar_folhas.py` gera as listas `folhas_carrefour.json` e `folhas_atacadao.json`, ordenadas das menores para as maiores categorias.

### 2.4 Filtro de disponibilidade via `fq` (`isAvailablePerSalesChannel_1:1`)
Adicionamos o parâmetro de busca:
```http
fq=isAvailablePerSalesChannel_1:1
```
Isso força a API VTEX a devolver **apenas produtos ativos com estoque no canal de vendas online**, ignorando produtos esgotados e o marketplace irrelevante. Reduziu drasticamente o volume e tempo de coleta (ex.: Carrefour de 131 mil itens teóricos para ~15 mil ativos).

### 2.5 Auto-scraping de detalhe (Pão de Açúcar / API GPA)
A API da GPA exige um fluxo em duas etapas:
1. **Listagem** (`POST /search/category-page`): Obtém a lista de produtos da categoria. Como a API reordena itens a cada página, fazemos varreduras em loop até não descobrir novos IDs.
2. **Detalhe** (`GET /v4/products/ecom/{id}?storeId=461`): Requisição individual para extração do **EAN-13**, preço e ofertas válidas da loja de Santos.

### 2.6 Enriquecimento de dados & Regex de Apresentação
A partir do nome do produto, usamos expressões regulares para extrair a **apresentação** (`quantidade` e `unidade_medida`, ex: "500ml" → `{quantidade: 500, unidade_medida: "ml"}`) e padronizar unidades (`un`, `g`, `kg`, `ml`, `l`).

### 2.7 Checkpoints e retomada (dump `.parcial`)
Coletas extensas salvam o progresso continuamente:
- `produtos_ampliado.json.parcial`
- `precos_{loja}_ampliado.json.parcial`
- `precos_{loja}_ampliado.json.progresso.json`

Em caso de interrupção ou queda de rede, as folhas concluídas são puladas ao relançar o script.

### 2.8 Polidez e Throttle
- VTEX: `sleep = 0.2s` por página.
- GPA (PA): `sleep = 0.3s` na listagem e `0.1s` no detalhe.

---

## 3. Estratégias escolhidas e motivação

| Estratégia | Decisão | Motivo |
|---|---|---|
| **JSON REST vs. HTML** | Escolhido JSON | Alta performance, zero depender de CSS selectors, formato padronizado |
| **Filtro `isAvailablePerSalesChannel_1:1`** | Escolhido | Apenas itens em estoque; elimina lixo de marketplace e itens indisponíveis |
| **Dedup por EAN-13** | Escolhido | EAN é a chave universal para cruzar o mesmo produto entre Carrefour, PA e Atacadão |
| **Separação de Catálogo e Preços** | Escolhido | `produtos_ampliado.json` mantém a informação única do produto; arquivos `precos_{loja}_ampliado.json` guardam a oferta específica da loja |
| **Algoritmo de Relevância Híbrido** | Escolhido | Pontuação (0-100) baseada em itens da cesta básica, cobertura multi-loja e marcas conhecidas para otimizar buscas no webapp |

---

## 4. Resultado obtido

Dados consolidados e integrados ao webapp:

- **Catálogo único unificado (`produtos_ampliado.json`)**: **153.288 produtos** deduplicados por EAN.
- **Bases de preços por loja**:
  - **Carrefour**: 153.288 ofertas
  - **Pão de Açúcar**: 15.406 ofertas
  - **Atacadão**: 3.424 ofertas
- **Núcleo de Comparação Direta**: ~3.500 EANs com preços cadastrados simultaneamente em 2 ou mais lojas.

---

## 5. Mapa do código atualizado (`codigos/`)

Todos os scripts contidos em `codigos/` estão sincronizados com a versão mais recente e otimizada:

| Arquivo | Descrição |
|---|---|
| [`config_secoes.py`](./codigos/config_secoes.py) | Configuração das seções-alvo por loja e exclusão de subseções atípicas (ex: bazar, vestuário). |
| [`gerar_folhas.py`](./codigos/gerar_folhas.py) | Extrai a árvore de categorias das APIs VTEX e gera os arquivos de folhas-alvo (`folhas_*.json`). |
| [`folhas_carrefour.json`](./codigos/folhas_carrefour.json) | Mapeamento de 1.093 folhas de categorias do Carrefour. |
| [`folhas_atacadao.json`](./codigos/folhas_atacadao.json) | Mapeamento de 448 folhas de categorias do Atacadão. |
| [`coletor_vtex.py`](./codigos/coletor_vtex.py) | **Engine principal VTEX**: controle de requisições, paginação, filtros, deduplicação por EAN e checkpoints. |
| [`coletar_carrefour.py`](./codigos/coletar_carrefour.py) | Script de execução da coleta no Carrefour. |
| [`coletar_atacadao.py`](./codigos/coletar_atacadao.py) | Script de execução da coleta no Atacadão. |
| [`coletar_pa.py`](./codigos/coletar_pa.py) | **Engine e coletor GPA/Pão de Açúcar**: listagem por categoria + requisição de detalhes por produto. |
| [`relevancia.py`](./codigos/relevancia.py) | Cálculo do score de relevância (cesta básica + presença em lojas + penalização de kits/derivados). |
| [`consolidar.py`](./codigos/consolidar.py) | Une o catálogo com preços, calcula o score de relevância e copia a base pronta para a pasta do `webapp/`. |
| [`dimensionar.py`](./codigos/dimensionar.py) | Script auxiliar para estimar tempo e total de requisições por lote de folhas. |
| [`testar_coletor.py`](./codigos/testar_coletor.py) | Script de teste rápido do coletor VTEX. |
| [`testar_pa.py`](./codigos/testar_pa.py) | Script de teste para a API do Pão de Açúcar. |
| [`validar_atacadao.py`](./codigos/validar_atacadao.py) | Validação e auditoria do JSON gerado no Atacadão. |
| [`cruzar_produtos.py`](./codigos/cruzar_produtos.py) | Script de cruzamento e enrichment com a base do Open Food Facts. |

---

## 6. Modelo de dados de saída

**Produto (`produtos_ampliado.json`)**:
```json
{
  "gtin_ean": "7891035800061",
  "secao": "Limpeza e Lavanderia",
  "subsecao": "Limpa Limo",
  "nome_completo": "Limpador Veja X-14 500ml",
  "marca": "Veja",
  "apresentacao": {"quantidade": 500, "unidade_medida": "ml"},
  "imagem_url": "https://.../image-0.jpg",
  "relevancia": 85,
  "data_cadastro": "2026-08-02"
}
```

**Preço por loja (`precos_{loja}_ampliado.json`)**:
```json
{
  "gtin_ean": "7891035800061",
  "supermercado": "Carrefour",
  "preco_regular": 26.99,
  "preco_promocional": 26.99,
  "em_estoque": true,
  "data_coleta": "2026-08-02"
}
```