"""
Dispensa Planejada Santos — FastAPI Application Entrypoint
PI em Computação II - UNIVESP 2026.2
Powered by SQLite SGBD Relacional + FTS5
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from db import DB_PATH
from importar_json_para_sqlite import run_etl
from models import (
    BuscaResponse,
    CalculoRequest,
    CalculoResponse,
    CategoriaOut,
    MarcaOut,
    ProdutoOut,
)
from services.product_service import (
    get_brands,
    get_categories,
    get_product_by_id,
    search_products,
)
from services.price_service import calculate_basket_prices

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("dispensa.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando backend Dispensa Planejada FastAPI SGBD...")
    if not DB_PATH.exists():
        logger.info("Banco de dados dispensa.db não encontrado. Executando ETL...")
        try:
            run_etl()
        except Exception as e:
            logger.error(f"Erro ao executar ETL na inicialização: {e}")
    else:
        logger.info(f"SGBD SQLite conectado com sucesso em: {DB_PATH}")
    yield
    logger.info("Encerrando backend...")


app = FastAPI(
    title="Dispensa Planejada Santos API (SGBD SQL)",
    description="API de alta performance alimentada por SGBD Relacional SQLite3 + FTS5 para comparação de preços em Santos/SP",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for web clients (Vercel, GitHub Pages, Localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {
        "status": "online",
        "app": "Dispensa Planejada Santos API",
        "sgbd": "SQLite3 + FTS5 (Relacional)",
        "versao": "2.0.0",
        "docs": "/docs",
    }


@app.get("/api/produtos", response_model=BuscaResponse)
def api_search_products(
    q: Optional[str] = Query(None, description="Termo de busca (Full-Text Search FTS5)"),
    categoria: Optional[str] = Query(None, description="Filtro de categoria"),
    marca: Optional[str] = Query(None, description="Filtro de marca"),
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(20, ge=1, le=100, description="Itens por página"),
):
    total, current_page, page_limit, total_pages, items = search_products(
        q=q, categoria=categoria, marca=marca, page=page, limit=limit
    )
    return BuscaResponse(
        total=total,
        page=current_page,
        limit=page_limit,
        total_pages=total_pages,
        produtos=items,
    )


@app.get("/api/produtos/{product_id}", response_model=ProdutoOut)
def api_get_product(product_id: int):
    prod = get_product_by_id(product_id)
    if not prod:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")
    return prod


@app.get("/api/categorias", response_model=list[CategoriaOut])
def api_list_categories():
    return get_categories()


@app.get("/api/marcas", response_model=list[MarcaOut])
def api_list_brands(categoria: Optional[str] = Query(None, description="Filtrar por categoria")):
    return get_brands(categoria=categoria)


@app.post("/api/calcular", response_model=CalculoResponse)
def api_calculate(request: CalculoRequest):
    return calculate_basket_prices(request)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
