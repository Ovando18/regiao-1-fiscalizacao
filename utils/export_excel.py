"""Exportação dos contratos da Área 1 para .xlsx formatado (openpyxl)."""
from __future__ import annotations

import io
from datetime import date, datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

AZUL = "004B87"
VERDE = "007A33"
AMARELO = "F2A900"
ZEBRA = "F4F6F9"
BORDA = "DCE3EC"

FMT_MOEDA = '"R$" #,##0.00'  # o Excel pt-BR exibe R$ 1.234,56
FMT_DATA = "DD/MM/YYYY"

_borda = Border(*(Side(style="thin", color=BORDA),) * 4)

COLUNAS_CONTRATOS = [
    # (cabeçalho, chave no DataFrame, largura, tipo)
    ("Município", "Município", 20, "txt"),
    ("Nº Contrato", "Nº Contrato", 14, "txt"),
    ("Data Assinatura", "Data Assinatura", 14, "data"),
    ("Empresa Contratada", "Contratada", 38, "txt"),
    ("CNPJ", "CNPJ", 20, "txt"),
    ("Objeto", "Objeto", 70, "txt"),
    ("Valor (R$)", "Valor (R$)", 18, "moeda"),
    ("Vigência", "Vigência", 16, "txt"),
    ("Área Técnica", "Área Técnica", 28, "txt"),
    ("Contrato Celebrado", "📄 Contrato", 20, "link"),
    ("Ordem de Serviço (OS)", "📋 Ordem de Serviço", 20, "link"),
    ("Empenho / Pagamentos", "💰 Empenho", 20, "link"),
    ("Portal Municipal", "🌐 Portal", 20, "link"),
]

ROTULO_LINK = {
    "📄 Contrato": "Abrir Contrato",
    "📋 Ordem de Serviço": "Abrir OS",
    "💰 Empenho": "Abrir Empenho",
    "🌐 Portal": "Abrir Portal",
}


def _titulo(ws, texto: str, subtitulo: str, ncols: int) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
    c = ws.cell(1, 1, texto)
    c.font = Font(bold=True, size=14, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=AZUL)
    c.alignment = Alignment(vertical="center", indent=1)
    s = ws.cell(2, 1, subtitulo)
    s.font = Font(italic=True, size=9, color="FFFFFF")
    s.fill = PatternFill("solid", fgColor=VERDE)
    s.alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 16


def _cabecalho(ws, linha: int, nomes: list[str]) -> None:
    for j, nome in enumerate(nomes, 1):
        c = ws.cell(linha, j, nome)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(bottom=Side(style="medium", color=AMARELO))
    ws.row_dimensions[linha].height = 30


def _para_data(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
        return None
    if isinstance(v, pd.Timestamp):
        return v.date()
    if isinstance(v, (date, datetime)):
        return v
    return None


def gerar_xlsx(df: pd.DataFrame, periodo: tuple[date, date], exercicio: int = 2026) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = f"Contratos_Area1_{exercicio}"
    ncols = len(COLUNAS_CONTRATOS)
    sub = (f"Crea-MS • Área 1 de Fiscalização • Período {periodo[0]:%d/%m/%Y} a {periodo[1]:%d/%m/%Y} • "
           f"Gerado em {datetime.now():%d/%m/%Y %H:%M} • Fonte: Portais da Transparência municipais")
    _titulo(ws, f"FiscalizaObras-MS | Área 1 — Contratos de Engenharia, Agronomia e Geociências {exercicio}", sub, ncols)
    lin_cab = 4
    _cabecalho(ws, lin_cab, [c[0] for c in COLUNAS_CONTRATOS])

    for i, (_, row) in enumerate(df.iterrows()):
        r = lin_cab + 1 + i
        fill = PatternFill("solid", fgColor=ZEBRA) if i % 2 else None
        for j, (_, chave, _, tipo) in enumerate(COLUNAS_CONTRATOS, 1):
            v = row.get(chave)
            c = ws.cell(r, j)
            if tipo == "data":
                c.value = _para_data(v)
                c.number_format = FMT_DATA
                c.alignment = Alignment(horizontal="center", vertical="top")
            elif tipo == "moeda":
                c.value = None if v is None or pd.isna(v) else float(v)
                c.number_format = FMT_MOEDA
                c.alignment = Alignment(vertical="top")
            elif tipo == "link":
                if isinstance(v, str) and v.startswith("http"):
                    c.value = ROTULO_LINK.get(chave, "Abrir")
                    c.hyperlink = v
                    c.style = "Hyperlink"
                else:
                    c.value = "Não disponibilizado"
                    c.font = Font(italic=True, color="98A2B3")
                c.alignment = Alignment(horizontal="center", vertical="top")
            else:
                c.value = "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
                c.alignment = Alignment(vertical="top", wrap_text=(chave == "Objeto"))
            if fill:
                c.fill = fill
            c.border = _borda

    for j, (_, _, larg, _) in enumerate(COLUNAS_CONTRATOS, 1):
        ws.column_dimensions[get_column_letter(j)].width = larg
    ws.freeze_panes = ws.cell(lin_cab + 1, 3)
    if len(df):
        ws.auto_filter.ref = f"A{lin_cab}:{get_column_letter(ncols)}{lin_cab + len(df)}"
        tot = lin_cab + len(df) + 1
        ws.cell(tot, 6, "TOTAL GERAL").font = Font(bold=True, color=AZUL)
        t = ws.cell(tot, 7, f"=SUM(G{lin_cab + 1}:G{tot - 1})")
        t.number_format = FMT_MOEDA
        t.font = Font(bold=True, color=AZUL)
        t.border = Border(top=Side(style="medium", color=AMARELO))

    # ---------------- Aba 2: resumo por município ----------------
    ws2 = wb.create_sheet("Resumo_Area1")
    _titulo(ws2, "Resumo por Município — Área 1", sub, 5)
    _cabecalho(ws2, 4, ["Município", "Qtd. Contratos", "Valor Total (R$)", "Com Documentação Completa", "% do Valor da Área 1"])
    if len(df):
        resumo = (df.assign(_completo=df["Docs"].eq(3))
                    .groupby("Município", as_index=False)
                    .agg(qtd=("Nº Contrato", "count"), valor=("Valor (R$)", "sum"), completos=("_completo", "sum"))
                    .sort_values("valor", ascending=False))
    else:
        resumo = pd.DataFrame(columns=["Município", "qtd", "valor", "completos"])
    primeira = 5
    ultima = primeira + len(resumo) - 1
    for i, (_, row) in enumerate(resumo.iterrows()):
        r = primeira + i
        vals = [row["Município"], int(row["qtd"]), float(row["valor"] or 0), int(row["completos"]),
                f"=IF(SUM($C${primeira}:$C${ultima})=0,0,C{r}/SUM($C${primeira}:$C${ultima}))"]
        for j, v in enumerate(vals, 1):
            c = ws2.cell(r, j, v)
            c.border = _borda
            if i % 2:
                c.fill = PatternFill("solid", fgColor=ZEBRA)
        ws2.cell(r, 3).number_format = FMT_MOEDA
        ws2.cell(r, 5).number_format = "0.0%"
    tot = primeira + len(resumo)
    ws2.cell(tot, 1, "TOTAL ÁREA 1").font = Font(bold=True, color=AZUL)
    if len(resumo):
        for j, col in ((2, "B"), (3, "C"), (4, "D")):
            c = ws2.cell(tot, j, f"=SUM({col}{primeira}:{col}{ultima})")
            c.font = Font(bold=True, color=AZUL)
            c.border = Border(top=Side(style="medium", color=AMARELO))
        ws2.cell(tot, 3).number_format = FMT_MOEDA
    for j, larg in enumerate((28, 16, 22, 26, 20), 1):
        ws2.column_dimensions[get_column_letter(j)].width = larg
    ws2.freeze_panes = "A5"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
