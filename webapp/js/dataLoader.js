/* ================================================================
   dataLoader.js — Carregamento e Indexação dos dados JSON
   Dispensa Planejada Santos
   ================================================================ */

/** Configuração das lojas */
export const LOJAS = {
  carrefour:     { nome: 'Carrefour - Ponta da Praia', icone: '🛍️', cor: '#2563eb' },
  pao_de_acucar: { nome: 'Pão de Açúcar',             icone: '🥐', cor: '#e11d48' },
  atacadao:      { nome: 'Atacadão',                    icone: '🏬', cor: '#0f766e' }
};

export const CHAVES_LOJA = ['carrefour', 'pao_de_acucar', 'atacadao'];

const ARQUIVOS_PRECOS = {
  carrefour:     'precos_carrefour_ampliado.json',
  pao_de_acucar: 'precos_pao_de_acucar_ampliado.json',
  atacadao:      'precos_atacadao_ampliado.json'
};

/** Base de dados global */
let baseDados = [];
let baseIndices = [];

/**
 * Carrega os JSONs de produtos e preços, monta o catálogo unificado.
 * @returns {Promise<boolean>} true se carregou com sucesso
 */
export async function carregarDadosReais() {
  try {
    const resProd = await fetch('produtos_ampliado.json');
    if (!resProd.ok) throw new Error('produtos_ampliado.json não encontrado');
    const produtos = await resProd.json();

    // Carrega preços de cada loja em paralelo
    const precosPromises = CHAVES_LOJA.map(async (loja) => {
      try {
        const res = await fetch(ARQUIVOS_PRECOS[loja]);
        return res.ok ? await res.json() : [];
      } catch {
        return [];
      }
    });
    const precosArrays = await Promise.all(precosPromises);

    const precosPorLoja = {};
    CHAVES_LOJA.forEach((loja, i) => { precosPorLoja[loja] = precosArrays[i]; });

    // Índice de preços por EAN
    const precoPorEan = {};
    CHAVES_LOJA.forEach(loja => {
      (precosPorLoja[loja] || []).forEach(p => {
        if (!p.gtin_ean) return;
        if (!precoPorEan[p.gtin_ean]) precoPorEan[p.gtin_ean] = {};
        precoPorEan[p.gtin_ean][loja] = p;
      });
    });

    // Catálogo unificado
    baseDados = produtos.map((prod, i) => {
      const precos = precoPorEan[prod.gtin_ean] || {};
      return {
        id: i + 1,
        gtin_ean: prod.gtin_ean,
        nome: prod.nome_completo || prod.nome || 'Produto sem nome',
        categoria: prod.secao || prod.categoria || 'Geral',
        marca: prod.marca || 'Não Informada',
        relevancia: prod.relevancia || 0,
        imagem_url: prod.imagem_url || null,
        apresentacao: prod.apresentacao || null,
        preco: CHAVES_LOJA.map(k => precos[k] ? precos[k].preco_promocional : null),
        preco_regular: CHAVES_LOJA.map(k => precos[k] ? precos[k].preco_regular : null),
        em_estoque: CHAVES_LOJA.map(k => precos[k] ? precos[k].em_estoque : false)
      };
    });

    // Índices em minúsculas para busca veloz (153k+ produtos)
    baseIndices = baseDados.map(p => ({
      nome: p.nome.toLowerCase(),
      cat: p.categoria.toLowerCase(),
      marca: p.marca.toLowerCase()
    }));

    window.BASE_DADOS = baseDados;
    const noEstoque = baseDados.filter(p => p.preco.some((v, idx) => v && p.em_estoque[idx])).length;
    console.log(`[Dispensa Planejada] ${baseDados.length} produtos carregados | ${noEstoque} com preço em estoque`);

    return true;
  } catch (err) {
    console.error('[Dispensa Planejada] Falha ao carregar dados:', err);
    return false;
  }
}

/** Retorna a base de dados carregada */
export function getBaseDados() {
  return baseDados;
}

/** Retorna os índices de busca */
export function getBaseIndices() {
  return baseIndices;
}

/**
 * Extrai todas as marcas únicas, opcionalmente filtradas por categoria.
 * @param {string} [categoriaFiltro] - Filtrar por categoria (case-insensitive)
 * @returns {string[]} marcas ordenadas alfabeticamente
 */
export function extrairMarcas(categoriaFiltro) {
  const marcasSet = new Set();
  const catSel = (categoriaFiltro || '').toLowerCase();
  for (let i = 0; i < baseDados.length; i++) {
    const p = baseDados[i];
    if (catSel && (p.categoria || '').toLowerCase() !== catSel) continue;
    const m = p.marca;
    if (!m) continue;
    const mk = m.toLowerCase();
    if (mk === 'não informado' || mk === 'não informada' || mk.includes('genérico')) continue;
    marcasSet.add(m);
  }
  return Array.from(marcasSet).sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
}
