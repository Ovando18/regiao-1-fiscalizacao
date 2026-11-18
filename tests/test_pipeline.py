"""Testes ponta a ponta com planilha e portal simulados (sem acesso à internet).

Execute:  python -m pytest -q
"""
from __future__ import annotations

import http.server
import json
import socket
import threading
from datetime import date
from functools import partial

import pytest
from openpyxl import Workbook, load_workbook

from config.planilha import ler_planilha
from config.provedores import BETHA_CLOUD, FIORILLI, OUTRO, detectar_por_url
from scrapers.collector import STATUS_INSTAVEL, STATUS_MANUAL, STATUS_ONLINE, coletar
from scrapers.keywords import classificar_areas, eh_objeto_tecnico
from scrapers.parsers import parse_data, parse_valor

# --------------------------------------------------------------------------- #
# Portal simulado
# --------------------------------------------------------------------------- #
HOME = """<html><body><nav><a href="/contratos.html">Contratos</a><a href="/lic.html">Licitações</a></nav>
<p>Portal da Transparência</p><footer>Desenvolvido por Quality Sistemas</footer></body></html>"""
CONTRATOS = """<html><body><table><thead><tr><th>Nº Contrato</th><th>Data Assinatura</th><th>Contratada</th>
<th>CPF/CNPJ</th><th>Objeto</th><th>Valor</th><th>Vigência</th><th>Ações</th></tr></thead><tbody>
<tr><td>012/2026</td><td>15/03/2026</td><td>Construtora Alfa Ltda</td><td>12345678000190</td>
<td>Pavimentação asfáltica e drenagem de vias urbanas</td><td>R$ 1.250.000,50</td><td>15/03/2026 a 14/03/2027</td>
<td><a href="/detalhe/12">Detalhes</a></td></tr>
<tr><td>013/2026</td><td>20/04/2026</td><td>Papelaria Beta</td><td>98765432000155</td>
<td>Aquisição de material de expediente</td><td>R$ 8.000,00</td><td>12 meses</td><td></td></tr>
<tr><td>001/2025</td><td>10/12/2025</td><td>Topo Geo ME</td><td>11222333000144</td>
<td>Serviço de topografia e georreferenciamento</td><td>R$ 45.000,00</td><td>6 meses</td><td></td></tr>
<tr><td>020/2026</td><td>02/06/2026</td><td>Eletro Gama</td><td>55666777000188</td>
<td>Manutenção da iluminação pública</td><td>R$ 99.900,00</td><td>12 meses</td>
<td><a href="/arquivos/contrato20.pdf">Contrato</a></td></tr>
</tbody></table></body></html>"""
DETALHE = """<html><body><h1>Contrato 012/2026</h1><a href="/arquivos/contrato12.pdf">Contrato assinado</a>
<a href="/arquivos/os12.pdf">Ordem de Serviço</a><a href="/empenhos?contrato=12">Empenhos e pagamentos</a></body></html>"""
SPA = """<html><head><script src="/app.js"></script></head><body><app-root></app-root></body></html>"""

# Fiorilli SCPI: a tela de contratos só responde com sessão e o export JSON é um postback.
FIORILLI_HOME = "<html><body><footer>Fiorilli S/C Ltda - SCPI</footer></body></html>"
FIORILLI_CONTRATOS = """<html><body><form method="post" action="./InformacoesContratos.ASPX">
<input type="hidden" name="__VIEWSTATE" value="abc"/><input type="hidden" name="__EVENTVALIDATION" value="xyz"/>
<input type="image" name="ASPxPageControl1$btnExportarJSON" src="x.png"/>
<table id="ASPxPageControl1_gridContratosLista_DXMainTable"></table></form></body></html>"""
FIORILLI_JSON = json.dumps([
    {"CODIGO": "0049/26", "ANO": 2026, "FORNECEDOR": "ECOL ENGENHARIA LTDA", "VALCON": 4254888.0,
     "VIGENI": "2026-06-02T00:00:00", "VENCIMENTO_ATUAL": "2027-09-02T00:00:00", "INSMF": "15.428.774/0001-95",
     "OBJETO_COMPLETO": "Contratação de empresa de engenharia para pavimentação asfáltica"},
    {"CODIGO": "0010/26", "ANO": 2026, "FORNECEDOR": "Mercado X", "VALCON": 900.0,
     "VIGENI": "2026-02-01T00:00:00", "OBJETO_COMPLETO": "Aquisição de gêneros alimentícios"},
    {"CODIGO": "0099/25", "ANO": 2025, "FORNECEDOR": "Obras Y", "VALCON": 1.0,
     "VIGENI": "2025-12-01T00:00:00", "OBJETO_COMPLETO": "Reforma de escola"},
])

PAGINAS = {"/": HOME, "/contratos.html": CONTRATOS, "/detalhe/12": DETALHE, "/spa": SPA,
           "/transparencia/": FIORILLI_HOME}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = self.rfile.read(tamanho).decode()
        ok = "btnExportarJSON.x" in corpo and "SESSAO=1" in (self.headers.get("Cookie") or "")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=UTF-8" if ok else "text/html")
        self.end_headers()
        self.wfile.write((FIORILLI_JSON if ok else "<html>erro</html>").encode())

    def do_GET(self):  # noqa: N802
        if self.path.lower() == "/transparencia/informacoescontratos.aspx":
            tem_sessao = "SESSAO=1" in (self.headers.get("Cookie") or "")
            self.send_response(200 if tem_sessao else 500)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write((FIORILLI_CONTRATOS if tem_sessao else "erro de sessão").encode())
            return
        corpo = PAGINAS.get(self.path)
        self.send_response(200 if corpo else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if self.path == "/transparencia/":
            self.send_header("Set-Cookie", "SESSAO=1; Path=/")
        self.end_headers()
        self.wfile.write((corpo or "404").encode())

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def portal():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def _porta_fechada() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


# --------------------------------------------------------------------------- #
# Testes
# --------------------------------------------------------------------------- #
def test_planilha_layout_livre(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Municípios"
    ws.append(["Relação de municípios por área de fiscalização"])
    ws.append([])
    ws.append(["Área", "Município", "Portal da Transparência", "Observação"])
    ws.append(["Área 1", "Prefeitura Municipal de Cidade A", "https://transparencia.betha.cloud/#/abc", ""])
    ws.append(["1", "Cidade B - MS", "Clique aqui", ""])
    ws["C5"].hyperlink = "http://cidadeb.ms.gov.br:8079/transparencia/"
    ws.append(["2", "Cidade C", "https://cidadec.ms.gov.br", ""])
    ws.append(["Área 1", "Cidade D", "www.cidaded.ms.gov.br/transparencia", ""])
    caminho = tmp_path / "Area1.xlsx"
    wb.save(caminho)

    municipios, avisos = ler_planilha(caminho)
    nomes = [m["municipio"] for m in municipios]
    assert nomes == ["Cidade A", "Cidade B", "Cidade D"]  # Cidade C é da Área 2
    por = {m["municipio"]: m for m in municipios}
    assert por["Cidade A"]["provedor"] == BETHA_CLOUD
    assert por["Cidade B"]["url"] == "http://cidadeb.ms.gov.br:8079/transparencia/"  # hiperlink embutido
    assert por["Cidade B"]["provedor"] == FIORILLI
    assert por["Cidade D"]["url"].startswith("https://www.")
    assert any("Área/Região 1" in a for a in avisos)


def test_planilha_coluna_regiao_e_hash_betha(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["cidade", "link", "Região"])
    ws.append(["Angélica", "https://transparencia.betha.cloud/#/3CsimkdlAFWc2SxNasIRBA==", 1])
    ws["B2"].hyperlink = "https://transparencia.betha.cloud/"  # Excel descarta a rota '#/...'
    ws.append(["Bonito", "http://45.188.183.155:8079/transparencia/", 3])
    ws.append(["Campo Grande", "https://transparencia.campogrande.ms.gov.br/", None])
    ws.append(["Glória de Dourados", "http://177.73.106.211:5656/Transparencia/", 1])
    caminho = tmp_path / "regiao_1.xlsx"
    wb.save(caminho)
    municipios, _ = ler_planilha(caminho)
    assert [m["municipio"] for m in municipios] == ["Angélica", "Glória de Dourados"]
    assert municipios[0]["url"].endswith("#/3CsimkdlAFWc2SxNasIRBA==")
    assert municipios[1]["provedor"] == FIORILLI
    assert municipios[1]["url_contratos"] == "http://177.73.106.211:5656/Transparencia/"


def test_deteccao_provedor():
    assert detectar_por_url("https://e-gov.betha.com.br/transparencia/01037-064/") == "Betha e-Gov"
    assert detectar_por_url("https://www.qualitysistemas.com.br/x") == "Quality Sistemas"
    assert detectar_por_url("https://cidade.ms.gov.br/") == OUTRO


def test_palavras_chave():
    assert eh_objeto_tecnico("CONTRATAÇÃO DE EMPRESA PARA PAVIMENTAÇÃO ASFÁLTICA")
    assert "Geociências/Topografia" in classificar_areas("Levantamento topográfico e georreferenciamento")
    assert not eh_objeto_tecnico("Aquisição de gêneros alimentícios para merenda escolar")
    assert not eh_objeto_tecnico("Encaminhamento de projeto de lei à câmara")


def test_conversoes():
    assert parse_valor("R$ 1.234.567,89") == pytest.approx(1234567.89)
    assert parse_valor("1234.5") == pytest.approx(1234.5)
    assert parse_data("Assinado em 05/02/2026") == date(2026, 2, 5)
    assert parse_data("2026-07-01T00:00:00") == date(2026, 7, 1)


def test_coleta_ponta_a_ponta(portal):
    municipios = [
        {"municipio": "Simulado HTML", "url": portal + "/", "provedor": OUTRO, "url_contratos": portal + "/"},
        {"municipio": "Simulado SPA", "url": portal + "/spa", "provedor": OUTRO, "url_contratos": portal + "/spa"},
        {"municipio": "Fora do Ar", "url": f"http://127.0.0.1:{_porta_fechada()}/", "provedor": OUTRO,
         "url_contratos": ""},
    ]
    eventos = []
    contratos, diags = coletar(municipios, date(2026, 1, 1), date(2026, 11, 18),
                               progress_cb=lambda i, t, d: eventos.append(i))
    assert sorted(eventos) == [1, 2, 3]
    st = {d["municipio"]: d for d in diags}
    assert st["Simulado HTML"]["status"] == STATUS_ONLINE
    assert st["Simulado HTML"]["provedor"] == "Quality Sistemas"  # refinado pela assinatura HTML
    assert st["Simulado SPA"]["status"] == STATUS_MANUAL
    assert st["Fora do Ar"]["status"] == STATUS_INSTAVEL

    nums = {c["numero"]: c for c in contratos}
    assert set(nums) == {"012/2026", "020/2026"}  # material de expediente e contrato de 2025 descartados
    c12 = nums["012/2026"]
    assert c12["valor"] == pytest.approx(1250000.50)
    assert c12["cnpj"] == "12.345.678/0001-90"
    assert c12["link_contrato"].endswith("/arquivos/contrato12.pdf")
    assert c12["link_os"].endswith("/arquivos/os12.pdf")
    assert "empenhos" in c12["link_empenho"]
    assert nums["020/2026"]["link_os"] is None


def test_xlsx_formatado(tmp_path):
    import pandas as pd

    from utils.export_excel import FMT_DATA, FMT_MOEDA, gerar_xlsx
    df = pd.DataFrame([{
        "Município": "Simulado", "Nº Contrato": "012/2026", "Data Assinatura": pd.Timestamp("2026-03-15"),
        "Contratada": "Construtora Alfa", "CNPJ": "12.345.678/0001-90", "Objeto": "Pavimentação",
        "Valor (R$)": 1250000.5, "Vigência": "12 meses", "Área Técnica": "Engenharia Civil/Obras",
        "📄 Contrato": "http://x/c.pdf", "📋 Ordem de Serviço": None, "💰 Empenho": "http://x/e",
        "🌐 Portal": "http://x/", "Docs": 2,
    }])
    caminho = tmp_path / "out.xlsx"
    caminho.write_bytes(gerar_xlsx(df, (date(2026, 1, 1), date(2026, 11, 18))))
    wb = load_workbook(caminho)
    assert wb.sheetnames == ["Contratos_Area1_2026", "Resumo_Area1"]
    ws = wb["Contratos_Area1_2026"]
    assert ws["C5"].number_format == FMT_DATA and ws["C5"].value.year == 2026
    assert ws["G5"].number_format == FMT_MOEDA and ws["G5"].value == 1250000.5
    assert ws["J5"].hyperlink.target == "http://x/c.pdf"
    assert ws["K5"].value == "Não disponibilizado"
    assert wb["Resumo_Area1"]["A5"].value == "Simulado"


def test_coleta_fiorilli_export_json(portal):
    # Domínio contendo "transparencia." não pode confundir a raiz do SCPI.
    from config.provedores import raiz_fiorilli
    assert raiz_fiorilli("https://transparencia.ivinhema.ms.gov.br/transparencia/") == \
        "https://transparencia.ivinhema.ms.gov.br/transparencia/"

    mun = {"municipio": "Fiorilli Simulado", "url": portal + "/transparencia/", "provedor": FIORILLI,
           "url_contratos": ""}
    contratos, diags = coletar([mun], date(2026, 1, 1), date(2026, 11, 18))
    assert diags[0]["status"] == STATUS_ONLINE, diags[0]["mensagem"]
    assert diags[0]["registros_lidos"] == 2  # o contrato de 2025 fica fora do exercício
    assert [c["numero"] for c in contratos] == ["0049/26"]
    c = contratos[0]
    assert c["valor"] == pytest.approx(4254888.0)
    assert c["data_assinatura"] == date(2026, 6, 2)
    assert c["vigencia"] == "02/06/2026 a 02/09/2027"
    assert c["link_portal"] == portal + "/transparencia/"


def test_provedor_outro_detectado_pelo_html(portal):
    mun = {"municipio": "Fiorilli sem pista na URL", "url": portal + "/transparencia/", "provedor": OUTRO,
           "url_contratos": ""}
    contratos, diags = coletar([mun], date(2026, 1, 1), date(2026, 11, 18))
    assert diags[0]["provedor"] == FIORILLI and diags[0]["status"] == STATUS_ONLINE
    assert len(contratos) == 1
