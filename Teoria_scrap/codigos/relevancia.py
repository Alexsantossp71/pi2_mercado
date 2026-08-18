# -*- coding: utf-8 -*-
"""
Relevância dos produtos para o Dispensa Planejada (estratégia híbrida).

Score 0..100 por produto, calculado na consolidação:

  relevancia = curado(0-100) * 0,70
             + cobertura_lojas(0-100) * 0,20
             + desempate * 0,10

- curado: o nome do produto bate com um item da cesta básica / mais consumidos
  (lista manual com pesos). É o sinal dominante.
- cobertura: quantas lojas (Carrefour, PA, Atacadão) vendem o mesmo EAN.
- desempate: normal (1.0); kits/multipacks e marcas desconhecidas perdem
  pontos (0,6); marcas conhecidas ganham (1,1).
"""

import re

# ---------------------------------------------------------------------------
# Lista curada: itens essenciais / mais consumidos no Brasil (cesta básica).
# Peso 100 = altíssimo consumo diário; 60 = consumo frequente; 40 = comum.
# Cada entrada é (termo_pesquisa, peso, seção_sugerida)
# ---------------------------------------------------------------------------
CURADOS = [
    # Mercearia básica
    ("arroz", 100), ("feijão", 100), ("feijao", 100), ("açúcar", 100), ("acucar", 100),
    ("sal", 80), ("óleo de soja", 100), ("oleo de soja", 100), ("óleo", 70), ("oleo", 70),
    ("macarrão", 80), ("macarrao", 80), ("espaguete", 60), ("massa", 55),
    ("café", 95), ("cafe", 95), ("farofa", 60), ("farinha", 60),
    ("molho de tomate", 60), ("molho de pimenta", 40), ("ketchup", 55), ("maionese", 55),
    ("mostarda", 40), ("sardinha", 50), ("atum", 50), ("milho verde", 50),
    ("ervilha", 50), ("extrato de tomate", 50), ("tempero", 40), ("vinagre", 45),
    # Bebidas
    ("leite", 100), ("leite integral", 100), ("refrigerante", 85), ("coca-cola", 85),
    ("coca cola", 85), ("suco", 65), ("água mineral", 75), ("agua mineral", 75),
    ("cerveja", 70), ("guaraná", 60), ("guarana", 60), ("água", 50), ("agua", 50),
    ("café solúvel", 75), ("cafe soluvel", 75), ("achocolatado", 60), ("nescau", 60),
    # Hortifruti
    ("banana", 70), ("tomate", 70), ("cebola", 65), ("alho", 65), ("batata", 70),
    ("cenoura", 60), ("alface", 55), ("maçã", 60), ("maca", 60), ("laranja", 55),
    ("limão", 55), ("limao", 55), ("ovos", 75), ("ovo", 70),
    # Frios / Padaria / Matinais
    ("pão", 90), ("pao", 90), ("pão de forma", 90), ("pao de forma", 90),
    ("manteiga", 75), ("margarina", 70), ("queijo", 75), ("presunto", 70),
    ("iogurte", 65), ("leite condensado", 65), ("creme de leite", 65),
    # Carnes / Açougue
    ("frango", 80), ("carne", 70), ("picanha", 75), ("alcatra", 65),
    ("patinho", 60), ("contrafilé", 65), ("contrafile", 65), ("linguiça", 65),
    ("linguica", 65), ("salsicha", 60), ("bacon", 60), ("peito de frango", 75),
    # Limpeza
    ("sabão em pó", 75), ("sabao em po", 75), ("detergente", 70), ("água sanitária", 70),
    ("agua sanitaria", 70), ("desinfetante", 65), ("sabonete", 65), ("shampoo", 60),
    ("papel higiênico", 75), ("papel higienico", 75), ("creme dental", 60),
    ("pasta de dente", 60), ("esponja", 40), ("amaciante", 60), ("álcool 70", 60),
    ("alcool 70", 60), ("saco de lixo", 50), ("luva", 40),
    # Pet
    ("ração", 70), ("racao", 70), ("ração para cachorro", 70), ("areia para gato", 50),
    # Higiene pessoal
    ("fralda", 65), ("absorvente", 50), ("fralda descartável", 65),
]

# Seções/termos atípicos que NUNCA devem ser priorizados na busca
# (kits, multipacks, refis de baixo valor, brindes, amostras)
PADROES_KIT = re.compile(
    r"\bkit\b|\bpack\b|^\s*x\s*\d|\bcom\s+\d+\s*(un|unid|unidade|g|kg|ml|l)\b|\bx\s*\d+\b",
    re.IGNORECASE,
)
PALAVRAS_BAIXA_RELEVANCIA = (
    "reservado", "amostra", "brinde", "geladeira", "mobília", "movel", "móvel",
    "peruca", "maquiagem", "esmalte", "luminária", "luminaria", "cortina",
)


def peso_curado(nome: str) -> int:
    """Maior peso da lista curada que bate com o nome do produto."""
    n = (nome or "").lower()
    melhor = 0
    for termo, peso in CURADOS:
        # termo pode ter acento; normaliza comparação sem acento
        t = termo.lower().replace("ç", "c").replace("ã", "a").replace("é", "e").replace("á", "a").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ê", "e").replace("ô", "o")
        nc = n.replace("ç", "c").replace("ã", "a").replace("é", "e").replace("á", "a").replace("í", "i").replace("ó", "o").replace("ú", "u").replace("ê", "e").replace("ô", "o")
        if t in nc and peso > melhor:
            melhor = peso
    return melhor


# Derivados que NÃO são o produto principal do termo (ex.: ao buscar "leite",
# "leite condensado", "creme de leite", "leite de coco" são produtos DIFERENTES
# e devem pontuar menos). Cada entrada é (substring, penalidade).
DERIVADOS = [
    ("condensado", 40),
    ("creme de leite", 45),
    ("de coco", 35),
    ("vegetal", 30),
    ("de amêndoas", 30),
    ("de aveia", 30),
    ("de soja", 30),
    ("de castanha", 30),
    ("em pó", 15),
    ("em po", 15),
    ("de cabra", 25),
    ("de colostro", 30),
]


def penalidade_derivado(nome: str) -> int:
    """Desconto por derivado (produto que contém o termo mas não É o termo)."""
    n = (nome or "").lower()
    pior = 0
    for sub, pen in DERIVADOS:
        if sub in n and pen > pior:
            pior = pen
    return pior


# Reforços por "tipo principal" de produtos com nome genérico:
# quem começa com o termo E tem a palavra-chave logo adiante ganha pontos.
TIPO_PRINCIPAL = [
    ("leite", ("integral", "desnatado", "semidesnatado", "zero", "uht", "longa vida"), 12),
    ("arroz", ("tipo 1", "tipo 1", "branco", "parboilizado", "integral"), 8),
    ("café", ("torrado", "moído", "moido", "extra forte", "tradicional"), 8),
    ("cafe", ("torrado", "moído", "moido", "extra forte", "tradicional"), 8),
    ("pão", ("de forma", "francês", "frances", "integral", "centeio"), 8),
    ("pao", ("de forma", "francês", "frances", "integral", "centeio"), 8),
]


def bonus_tipo_principal(nome: str) -> int:
    """Soma bônus quando o nome começa com o termo E contém a palavra-chave."""
    n = (nome or "").lower()
    for base, chaves, bonus in TIPO_PRINCIPAL:
        if n.startswith(base):
            for c in chaves:
                if c in n:
                    return bonus
    return 0


def eh_kit(nome: str) -> bool:
    return bool(PADROES_KIT.search(nome or ""))


def tem_palavra_baixa(nome: str) -> bool:
    n = (nome or "").lower()
    return any(p in n for p in PALAVRAS_BAIXA_RELEVANCIA)


MARCAS_CONHECIDAS = (
    "nestlé", "nestle", "coca", "pepsi", "danone", "heinz", "kiaora", "campo largo",
    "tio joão", "tio joao", "camil", "bom gosto", "urso", "sadia", "perdigão",
    "perdigao", "seara", "aurora", "president", "polenghi", "frimesa", "lacta",
    "garoto", "hershey", "ferrero", "nutella", "nescau", "toddy", "itambe",
    "piracanjuba", "ccgl", "lactalis", "águia", "aguia", "arbor", "camil", "vilma",
    "renata", "adria", "galo", "bom dia", "piraquê", "piraque", "nissin", "maggi",
    "knorr", "fugini", "hemmer", "pomarola", "elefante", "dragão", "dragao",
)


def desempate(nome: str) -> float:
    """Fator 0,6..1,2 para desempate entre produtos do mesmo peso."""
    if tem_palavra_baixa(nome):
        return 0.3
    if eh_kit(nome):
        return 0.6
    n = (nome or "").lower()
    if any(m in n for m in MARCAS_CONHECIDAS):
        return 1.2
    return 1.0


def cobertura_score(n_lojas: int) -> float:
    """Quanto mais lojas vendem o produto, mais consumido/confiável é."""
    return min(n_lojas, 3) / 3.0 * 100


def calcular_relevancia(nome: str, n_lojas: int) -> int:
    curado = peso_curado(nome)
    if curado == 0:
        # sem match curado: relevância baixa, só pequeno bônus de cobertura
        return max(5, int(cobertura_score(n_lojas) * 0.25))
    score = curado * 0.70 + cobertura_score(n_lojas) * 0.20 + desempate(nome) * 10
    score -= penalidade_derivado(nome)
    score += bonus_tipo_principal(nome)
    return int(min(100, max(5, score)))
