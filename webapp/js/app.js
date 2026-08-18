/* ================================================================
   app.js — Orquestrador Principal
   Dispensa Planejada Santos
   Inicializa todos os módulos na ordem correta.
   ================================================================ */

import { carregarDadosReais, getBaseDados, extrairMarcas } from './dataLoader.js';
import { buscarProdutos } from './searchEngine.js';
import { onListaChange, restaurarDoStorage } from './shoppingList.js';
import { initUI, popularMarcas, renderLista } from './ui.js';

/**
 * Expõe módulos no window para acesso cross-module em event handlers
 * (necessário enquanto não migramos para bundler/framework)
 */
window._dp_modules = {
  getBaseDados,
  onListaChange
};

/**
 * Ponto de entrada da aplicação.
 */
async function init() {
  console.log('[Dispensa Planejada] Inicializando...');

  // Mostra loading state
  const loading = document.getElementById('loadingOverlay');
  if (loading) loading.classList.remove('hidden');

  // 1. Carrega dados dos JSONs
  const ok = await carregarDadosReais();

  // Esconde loading
  if (loading) loading.classList.add('hidden');

  if (!ok) {
    alert('Falha ao carregar os dados. Verifique se os arquivos JSON estão na mesma pasta do index.html.');
    return;
  }

  // 2. Popula filtro de marcas
  popularMarcas();

  // 3. Restaura lista do localStorage
  restaurarDoStorage((id) => getBaseDados().find(p => p.id === id));

  // 4. Inicializa event bindings da UI
  initUI();

  // 5. Render inicial
  renderLista();

  // 6. Registra Service Worker (PWA)
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('./sw.js').catch((err) => {
      console.warn('[PWA] Service Worker registration skipped or failed:', err);
    });
  }

  console.log('[Dispensa Planejada] Pronto!');
}

// Inicia quando o DOM estiver pronto
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
