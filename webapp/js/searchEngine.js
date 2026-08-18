/* ================================================================
   searchEngine.js — Motor de busca com autocomplete
   Dispensa Planejada Santos
   ================================================================ */

import { getBaseDados, getBaseIndices } from './dataLoader.js';

/**
 * Busca produtos por texto, categoria e marca.
 * Usa word-boundary regex para evitar falsos positivos (ex: "camil" ≠ "camila").
 * Ordena por relevância + match de marca + posição no nome.
 *
 * @param {string} texto - Termo de busca
 * @param {string} [categoriaFiltro] - Categoria selecionada
 * @param {string} [marcaFiltro] - Marca selecionada
 * @param {number} [limite=200] - Máximo de resultados
 * @returns {Array} Produtos filtrados e ordenados
 */
export function buscarProdutos(texto, categoriaFiltro = '', marcaFiltro = '', limite = 200) {
  const baseDados = getBaseDados();
  const baseIndices = getBaseIndices();

  const t = texto.trim().toLowerCase();
  const catF = categoriaFiltro.toLowerCase();
  const marcaF = marcaFiltro.toLowerCase();

  if (!t && !catF && !marcaF) return [];

  // Word-boundary regex para busca precisa
  const escaped = t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = t
    ? new RegExp('(^|[^a-z0-9áéíóúâêôãõçü])' + escaped + '($|[^a-z0-9áéíóúâêôãõçü])', 'i')
    : null;

  const resultados = [];

  for (let i = 0; i < baseDados.length; i++) {
    const idx = baseIndices[i];

    // Filtros de categoria e marca
    if (catF && idx.cat !== catF) continue;
    if (marcaF && idx.marca !== marcaF) continue;

    // Filtro de texto
    if (t) {
      if (!idx.nome.includes(t) && !idx.cat.includes(t) && !idx.marca.includes(t)) continue;
      if (re && !re.test(idx.nome) && !re.test(idx.cat) && !re.test(idx.marca)) continue;
    }

    resultados.push(baseDados[i]);
  }

  // Ranking: relevância + marca exata + início do nome + palavra no meio
  resultados.sort((a, b) => {
    const ra = a.relevancia || 0;
    const rb = b.relevancia || 0;

    if (t) {
      const aMarca = (a.marca || '').toLowerCase() === t ? 60 : 0;
      const bMarca = (b.marca || '').toLowerCase() === t ? 60 : 0;
      const aStart = a.nome.toLowerCase().startsWith(t) ? 30 : 0;
      const bStart = b.nome.toLowerCase().startsWith(t) ? 30 : 0;
      const aMid = (!aStart && a.nome.toLowerCase().includes(' ' + t)) ? 8 : 0;
      const bMid = (!bStart && b.nome.toLowerCase().includes(' ' + t)) ? 8 : 0;
      return (rb + bMarca + bStart + bMid) - (ra + aMarca + aStart + aMid);
    }

    return rb - ra;
  });

  return resultados.slice(0, limite);
}
