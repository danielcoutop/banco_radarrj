"""
html_to_csv.py

Lê todos os arquivos HTML da pasta `diarios/` (matérias do Diário Oficial) e
gera um único CSV, onde **cada HTML vira uma linha**.

Colunas do CSV de saída (mesmo formato/estilo de `radarrj_ato_limpo.csv`,
delimitador "|"):

    id         -> ID da matéria (cabeçalho e rodapé do HTML / nome do arquivo)
    dataPubli  -> data de publicação  (NÃO existe no HTML -> ver TODO abaixo)
    secao      -> seção do diário     (NÃO existe no HTML -> ver TODO abaixo)
    texto      -> texto corrido da matéria, parágrafos unidos por 4 espaços,
                  terminando em "Id: <id>" (igual ao campo `texto` do radarrj)

Uso:
    python html_to_csv.py                         # lê ./diarios  -> ./diarios.csv
    python html_to_csv.py -i diarios -o saida.csv
    python html_to_csv.py -i diarios -o saida.csv --delimitador "|"

Dependências:
    pip install beautifulsoup4 lxml
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

# Colunas do CSV final, na ordem em que aparecem em radarrj_ato_limpo.csv
COLUNAS = ["id", "dataPubli", "secao", "texto"]

# Separador usado entre "blocos" de texto dentro do campo `texto`
SEP_BLOCOS = "    "  # 4 espaços, como no radarrj_ato_limpo.csv


# ---------------------------------------------------------------------------
# 1. Parse de um HTML -> dict com as colunas
# ---------------------------------------------------------------------------
def parse_materia(caminho: Path, encoding: str = "utf-8") -> dict[str, str]:
    """Lê um HTML de matéria e devolve {id, dataPubli, secao, texto}."""
    soup = BeautifulSoup(caminho.read_text(encoding=encoding), "lxml")

    caixa = soup.select_one(".box-materia") or soup.body or soup

    id_materia = extrair_id(caixa, caminho)
    texto = extrair_texto(caixa)

    # Garante que o texto termine em "Id: <id>" (como no radarrj)
    if id_materia and not re.search(rf"Id:\s*{re.escape(id_materia)}\s*$", texto):
        texto = f"{texto}{SEP_BLOCOS}Id: {id_materia}".strip()

    return {
        "id": id_materia,
        # TODO: dataPubli não está no HTML. Preencher aqui a partir da fonte
        #       real (ex.: cruzar com radarrj_ato_limpo.csv pelo `id`, ou ler
        #       de um índice/metadados). Formato esperado: YYYY-MM-DD.
        "dataPubli": "",
        # secao = a secretaria / órgão cuja organização o ato dispõe
        # (extraída da ementa do ato).
        "secao": extrair_secao(caixa, texto),
        "texto": texto,
    }


# ---------------------------------------------------------------------------
# 2. Extração do ID
# ---------------------------------------------------------------------------
def extrair_id(caixa: Tag, caminho: Path) -> str:
    """Tenta cabeçalho -> rodapé -> nome do arquivo."""
    header = caixa.select_one(".header-materia")
    if header:
        m = re.search(r"ID DA MAT[ÉE]RIA:\s*(\d+)", header.get_text(" ", strip=True), re.I)
        if m:
            return m.group(1)

    rodape = caixa.select_one("p.direita")
    if rodape:
        m = re.search(r"Id:\s*(\d+)", rodape.get_text(" ", strip=True), re.I)
        if m:
            return m.group(1)

    m = re.search(r"(\d+)", caminho.stem)  # materia_802373 -> 802373
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# 3. Extração do texto corrido
# ---------------------------------------------------------------------------
def extrair_texto(caixa: Tag) -> str:
    """
    Percorre os filhos diretos da .box-materia (ignorando o cabeçalho) e
    monta o texto: cada parágrafo/tabela vira um bloco, blocos unidos por
    SEP_BLOCOS. Espaços/quebras internas são normalizados.
    """
    blocos: list[str] = []

    for filho in caixa.children:
        if isinstance(filho, NavigableString):
            txt = normalizar(str(filho))
            if txt:
                blocos.append(txt)
            continue

        if not isinstance(filho, Tag):
            continue

        classes = filho.get("class", [])
        if "header-materia" in classes:
            continue  # cabeçalho não faz parte do texto da matéria

        if filho.name == "table":
            txt = texto_tabela(filho)
        else:
            txt = normalizar(filho.get_text(" ", strip=True))

        if txt:
            blocos.append(txt)

    return SEP_BLOCOS.join(blocos)


def texto_tabela(tabela: Tag) -> str:
    """Achata uma tabela: células separadas por 3 espaços, linhas por SEP_BLOCOS.

    Evita o caractere "|" de propósito, para não colidir com o delimitador do CSV.
    """
    linhas: list[str] = []
    for tr in tabela.find_all("tr"):
        celulas = [
            normalizar(td.get_text(" ", strip=True))
            for td in tr.find_all(["td", "th"])
        ]
        celulas = [c for c in celulas if c]
        if celulas:
            linhas.append("   ".join(celulas))
    return SEP_BLOCOS.join(linhas)


def normalizar(texto: str) -> str:
    """Colapsa espaços, tabs e quebras de linha em um único espaço."""
    return re.sub(r"\s+", " ", texto).strip()


# ---------------------------------------------------------------------------
# 3b. Extração da "secao": o órgão cuja organização o ato dispõe
# ---------------------------------------------------------------------------
# Início possível do nome do órgão (secretaria / gabinete / poder executivo).
_ORG_INICIO = (
    r"SECRETARIA\s+(?:DE\s+ESTADO|EXTRAORDIN[ÁA]RIA)"
    r"|GABINETE\s+DE\s+SEGURAN[ÇC]A\s+INSTITUCIONAL"
    r"|PODER\s+EXECUTIVO\s+ESTADUAL"
)

# Onde o nome do órgão termina (vence a ocorrência mais à esquerda).
_ORG_FIM = (
    r",?\s*E\s+D[ÁA]\s+(?:OUTRAS\s+)?PROVID[ÊE]NCIAS"
    r"|,\s*E\s+D[ÁA]\s"
    r"|\s+QUE\s+MENCIONA"
    r"|,\s*APROVAD[AO]"
    r"|,\s*CRIAD[AO]"
    r"|,\s*ALTERAD[AO]"
    r"|,\s*MODIFICA"
    r"|,\s*BEM\s+COMO"
    r"|,\s*SEM\s+AUMENTO"
    r"|\s+E\s+SUA\s+ESTRUTURA"
    r"|,\s*QUE\s+(?:SER[ÁA]|TER[ÁA]|PASSA|DISP[ÕO]E|ALTERA|CRIOU|INSTITUIU)"
    r"|\s+PARA\s+[AO]\s"          # "...transfere X para a estrutura de Y"
    r"|(?-i:,\s+(?=[a-zà-ÿ0-9]))"  # vírgula + minúscula/dígito -> saiu do nome (case-sensitive)
    r"|\."
    r"|$"
)

_ORG_RE = re.compile(rf"(\b(?:{_ORG_INICIO}).*?)(?={_ORG_FIM})", re.IGNORECASE)

_SPLIT_ORGS = re.compile(r"\s+E\s+D[AO]\s+(?=SECRETARIA)", re.IGNORECASE)


def _limpar_org(s: str) -> str:
    s = normalizar(s)
    s = re.sub(r"\s+([,;)])", r"\1", s)   # "PECUÁRIA , PESCA" -> "PECUÁRIA, PESCA"
    s = re.sub(r"(\()\s+", r"\1", s)      # "( SEELJE)" -> "(SEELJE)"
    return s.strip(" -–—,;.")


def extrair_secao(caixa: Tag, texto: str) -> str:
    """
    Devolve a(s) secretaria(s)/órgão(s) cuja organização o ato dispõe.

    Procura primeiro na ementa (o <p> com `margin-left: 0pt`) e, se não achar,
    no texto inteiro da matéria. Quando o ato reorganiza mais de um órgão,
    devolve todos separados por "; ".
    """
    ementa = ""
    p = caixa.find("p", style=re.compile(r"margin-left:\s*0pt", re.I))
    if p:
        ementa = normalizar(p.get_text(" ", strip=True))

    for fonte in (ementa, texto):
        if not fonte:
            continue
        m = _ORG_RE.search(fonte)
        if not m:
            continue
        partes = [_limpar_org(x) for x in _SPLIT_ORGS.split(m.group(1))]
        partes = [x for x in partes if x]
        # remove duplicatas preservando a ordem
        return "; ".join(dict.fromkeys(partes))

    return ""


# ---------------------------------------------------------------------------
# 4. Percorrer a pasta e escrever o CSV
# ---------------------------------------------------------------------------
def converter_pasta(pasta: Path, saida: Path, delimitador: str = "|") -> int:
    arquivos = sorted(pasta.glob("*.html"))
    if not arquivos:
        print(f"Nenhum .html encontrado em {pasta}", file=sys.stderr)
        return 0

    with saida.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=COLUNAS,
            delimiter=delimitador,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        writer.writeheader()
        for arq in arquivos:
            try:
                writer.writerow(parse_materia(arq))
            except Exception as e:  # não deixa um arquivo ruim parar tudo
                print(f"ERRO em {arq.name}: {e}", file=sys.stderr)

    return len(arquivos)


# ---------------------------------------------------------------------------
# 5. CLI
# ---------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Converte os HTMLs de matérias (pasta diarios/) em um CSV."
    )
    parser.add_argument(
        "-i", "--input", type=Path, default=Path("materias"),
        help="Pasta com os arquivos .html (padrão: diarios)",
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=None,
        help="Arquivo CSV de saída (padrão: <pasta>.csv)",
    )
    parser.add_argument("--delimitador", default="|", help="Delimitador do CSV (padrão: |)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.input.is_dir():
        print(f"Pasta não encontrada: {args.input}", file=sys.stderr)
        return 1

    saida = args.output or args.input.with_suffix(".csv")
    total = converter_pasta(args.input, saida, delimitador=args.delimitador)

    if total:
        print(f"OK: {total} matérias -> {saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
