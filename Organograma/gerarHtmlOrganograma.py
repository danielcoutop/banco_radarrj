"""
Gera organograma.html: lê os JSONs de estrutura (jsons_diarios/estrutura_*.json)
e embute os dados no template organograma_template.html. O HTML resultante
abre direto no navegador, sem servidor (uma aba por estrutura).
"""

import json
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
PASTA_JSONS = "../jsons_diarios"            # saída do extrairOrganograma.py
PREFIXO_ARQUIVO = "estrutura_"              # só esses arquivos viram abas
TEMPLATE = "organograma_template.html"
HTML_SAIDA = "organograma.html"
MARCADOR = "__DADOS_ESTRUTURAS__"           # onde o JSON é inserido no template


def _resolver_caminho(caminho):
    caminho = Path(caminho)
    return caminho if caminho.is_absolute() else Path(__file__).resolve().parent / caminho


def carregar_estruturas(pasta_jsons=PASTA_JSONS):
    """Lista de estruturas com o id do ato (tirado do nome do arquivo), ordenada pelo id."""
    estruturas = []
    for caminho in _resolver_caminho(pasta_jsons).glob(f"{PREFIXO_ARQUIVO}*.json"):
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        estruturas.append({"id": caminho.stem.removeprefix(PREFIXO_ARQUIVO), **dados})
    return sorted(estruturas, key=lambda e: (not e["id"].isdigit(), int(e["id"]) if e["id"].isdigit() else 0, e["id"]))


def gerar_html(pasta_jsons=PASTA_JSONS, template=TEMPLATE, html_saida=HTML_SAIDA):
    estruturas = carregar_estruturas(pasta_jsons)
    dados = json.dumps(estruturas, ensure_ascii=False, separators=(",", ":"))
    dados = dados.replace("</", "<\\/")      # não fecha o <script> antes da hora

    html = _resolver_caminho(template).read_text(encoding="utf-8")
    assert html.count(MARCADOR) == 1, f"o template precisa ter {MARCADOR} exatamente uma vez"
    saida = _resolver_caminho(html_saida)
    saida.write_text(html.replace(MARCADOR, dados), encoding="utf-8")
    print(f"{len(estruturas)} estruturas -> {saida}")
    return saida


if __name__ == "__main__":
    gerar_html()
