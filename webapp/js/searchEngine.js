/* ================================================================
   searchEngine.js — Motor de busca com autocomplete
   Dispensa Planejada Santos
   ================================================================ */

import { buscarProdutosAPI } from './api.js';

/**
 * Busca produtos por texto, categoria e marca usando a API backend.
 *
 * @param {string} texto - Termo de busca
 * @param {string} [categoriaFiltro] - Categoria selecionada
 * @param {string} [marcaFiltro] - Marca selecionada
 * @param {number} [limite=200] - Máximo de resultados
 * @returns {Promise<Array>} Produtos filtrados e ordenados
 */
export async function buscarProdutos(texto, categoriaFiltro = '', marcaFiltro = '', limite = 200) {
  const t = texto.trim();
  if (!t && !categoriaFiltro && !marcaFiltro) return [];

  try {
    const data = await buscarProdutosAPI(t, categoriaFiltro, marcaFiltro, 1);
    return data.produtos || [];
  } catch (err) {
    console.error('[searchEngine] Erro na busca:', err);
    return [];
  }
}
