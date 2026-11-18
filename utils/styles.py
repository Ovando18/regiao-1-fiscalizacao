"""Identidade visual institucional — Área 1 de Fiscalização (Crea-MS) + cores oficiais de MS."""
from __future__ import annotations

from html import escape

AZUL_MS = "#004B87"
AZUL_MS_ESCURO = "#00335C"
VERDE_MS = "#007A33"
AMARELO_MS = "#F2A900"
FUNDO = "#F4F6F9"
CARD = "#FFFFFF"
BORDA = "#DCE3EC"
TEXTO = "#1B2A3A"
TEXTO_SUAVE = "#5B6B7F"
VERMELHO = "#B42318"

CORES_STATUS = {
    "Online": VERDE_MS,
    "Instável / Timeout": AMARELO_MS,
    "Acesso Manual": AZUL_MS,
}


def emblema_svg(tamanho: int = 64) -> str:
    """Selo vetorial da Área 1: escudo azul, faixa verde e estrela amarela (MS)."""
    return f"""
<svg width="{tamanho}" height="{tamanho}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"
     role="img" aria-label="Selo Área 1 — Fiscalização Crea-MS">
  <path d="M32 3 L57 11 V30 C57 45 46 56 32 61 C18 56 7 45 7 30 V11 Z" fill="{AZUL_MS}"/>
  <path d="M32 3 L57 11 V30 C57 45 46 56 32 61 C18 56 7 45 7 30 V11 Z" fill="none"
        stroke="#FFFFFF" stroke-opacity=".35" stroke-width="1.5"/>
  <path d="M7 34 L57 22 V30 C57 31.5 56.9 33 56.7 34.4 L8.2 46 C7.4 42.9 7 39.7 7 36.5 Z" fill="{VERDE_MS}"/>
  <polygon points="44,12 45.6,16.4 50.2,16.5 46.5,19.3 47.9,23.7 44,21.1 40.1,23.7 41.5,19.3 37.8,16.5 42.4,16.4"
           fill="{AMARELO_MS}"/>
  <text x="25" y="33" text-anchor="middle" font-family="Inter,Segoe UI,Arial" font-weight="800"
        font-size="20" fill="#FFFFFF">1</text>
  <text x="32" y="55" text-anchor="middle" font-family="Inter,Segoe UI,Arial" font-weight="700"
        font-size="6.5" letter-spacing=".8" fill="#FFFFFF">ÁREA 1</text>
</svg>"""


CSS = f"""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"], .stApp {{ font-family: 'Inter', 'Segoe UI', Arial, sans-serif; }}
  .stApp {{ background: {FUNDO}; color: {TEXTO}; }}
  .block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1500px; }}
  header[data-testid="stHeader"] {{ background: transparent; }}

  /* Sidebar */
  section[data-testid="stSidebar"] {{ background: {CARD}; border-right: 1px solid {BORDA}; }}
  section[data-testid="stSidebar"] .stButton > button {{ width: 100%; }}

  /* Botões */
  .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {{
      background: {AZUL_MS}; border: 1px solid {AZUL_MS}; color: #fff; font-weight: 600; }}
  .stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover {{
      background: {AZUL_MS_ESCURO}; border-color: {AZUL_MS_ESCURO}; }}
  .stButton > button[kind="secondary"] {{ border: 1px solid {BORDA}; color: {AZUL_MS}; font-weight: 600; }}
  .stLinkButton > a {{ font-weight: 600; }}

  /* Cabeçalho institucional */
  .fo-header {{ background: linear-gradient(135deg, {AZUL_MS} 0%, {AZUL_MS_ESCURO} 100%);
      border-radius: 14px; padding: 22px 26px 18px; color: #fff; position: relative;
      box-shadow: 0 4px 14px rgba(0,51,92,.18); margin-bottom: 18px; overflow: hidden; }}
  .fo-header::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 5px;
      background: linear-gradient(90deg, {VERDE_MS} 0 62%, {AMARELO_MS} 62% 100%); }}
  .fo-header-row {{ display: flex; gap: 18px; align-items: center; }}
  .fo-kicker {{ display: inline-flex; align-items: center; gap: 8px; background: {VERDE_MS};
      border-radius: 999px; padding: 4px 12px; font-size: .72rem; font-weight: 700; letter-spacing: .06em; }}
  .fo-kicker .dot {{ width: 7px; height: 7px; border-radius: 50%; background: {AMARELO_MS}; }}
  .fo-title {{ font-size: 1.75rem; font-weight: 800; margin: 8px 0 2px; letter-spacing: -.01em; }}
  .fo-title span {{ color: {AMARELO_MS}; }}
  .fo-sub {{ font-size: .92rem; opacity: .9; }}
  .fo-munis {{ margin-top: 12px; font-size: .78rem; line-height: 1.55; opacity: .85;
      border-top: 1px solid rgba(255,255,255,.18); padding-top: 9px; }}
  .fo-munis b {{ color: #fff; font-weight: 600; letter-spacing: .04em; }}

  /* Selo compacto da sidebar */
  .fo-side {{ display: flex; gap: 10px; align-items: center; padding: 6px 2px 14px;
      border-bottom: 3px solid {AMARELO_MS}; margin-bottom: 10px; }}
  .fo-side .t1 {{ font-weight: 800; color: {AZUL_MS}; font-size: 1.02rem; line-height: 1.1; }}
  .fo-side .t2 {{ font-size: .7rem; color: {VERDE_MS}; font-weight: 700; letter-spacing: .05em; }}

  /* KPIs */
  .fo-kpi {{ background: {CARD}; border: 1px solid {BORDA}; border-radius: 12px; padding: 14px 16px;
      box-shadow: 0 1px 3px rgba(16,24,40,.05); border-left: 4px solid {AZUL_MS}; height: 100%; }}
  .fo-kpi.verde {{ border-left-color: {VERDE_MS}; }}
  .fo-kpi.amarelo {{ border-left-color: {AMARELO_MS}; }}
  .fo-kpi .rot {{ font-size: .74rem; color: {TEXTO_SUAVE}; font-weight: 600; text-transform: uppercase;
      letter-spacing: .05em; }}
  .fo-kpi .val {{ font-size: 1.55rem; font-weight: 800; color: {TEXTO}; margin-top: 4px; white-space: nowrap;
      overflow: hidden; text-overflow: ellipsis; }}
  .fo-kpi .det {{ font-size: .76rem; color: {TEXTO_SUAVE}; margin-top: 2px; }}

  /* Cards / seções */
  .fo-sec {{ font-size: 1.05rem; font-weight: 700; color: {AZUL_MS}; margin: 22px 0 8px;
      display: flex; align-items: center; gap: 8px; }}
  .fo-sec::before {{ content: ""; width: 4px; height: 18px; background: {VERDE_MS}; border-radius: 2px; }}
  .fo-card {{ background: {CARD}; border: 1px solid {BORDA}; border-radius: 12px; padding: 18px 20px;
      box-shadow: 0 1px 3px rgba(16,24,40,.05); }}
  .fo-ficha-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px 22px; }}
  .fo-ficha-grid .rot {{ font-size: .72rem; color: {TEXTO_SUAVE}; text-transform: uppercase; font-weight: 600;
      letter-spacing: .05em; }}
  .fo-ficha-grid .val {{ font-size: .98rem; font-weight: 600; color: {TEXTO}; }}
  .fo-objeto {{ background: {FUNDO}; border: 1px solid {BORDA}; border-radius: 8px; padding: 12px 14px;
      margin: 14px 0 4px; font-size: .93rem; line-height: 1.5; }}
  .fo-tag {{ display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: .72rem; font-weight: 600;
      background: rgba(0,122,51,.1); color: {VERDE_MS}; margin: 0 6px 4px 0; }}
  .fo-status {{ display: inline-flex; align-items: center; gap: 6px; font-size: .8rem; font-weight: 600; }}
  .fo-status i {{ width: 9px; height: 9px; border-radius: 50%; display: inline-block; }}
  .fo-aviso {{ background: #FFF8E6; border: 1px solid #F5D27A; border-left: 4px solid {AMARELO_MS};
      border-radius: 10px; padding: 12px 16px; font-size: .9rem; color: #5C4300; }}
  .fo-vazio {{ text-align: center; padding: 40px 20px; color: {TEXTO_SUAVE}; }}
  .fo-vazio b {{ color: {AZUL_MS}; }}
  .fo-rodape {{ margin-top: 36px; font-size: .74rem; color: {TEXTO_SUAVE}; text-align: center;
      border-top: 1px solid {BORDA}; padding-top: 12px; }}
  div[data-testid="stExpander"] {{ background: {CARD}; border: 1px solid {BORDA}; border-radius: 12px; }}
</style>
"""


def cabecalho_html(municipios: list[str], exercicio: int) -> str:
    lista = " · ".join(escape(m) for m in municipios) if municipios else "nenhum município carregado"
    return f"""
<div class="fo-header">
  <div class="fo-header-row">
    <div>{emblema_svg(76)}</div>
    <div style="flex:1;min-width:0">
      <div class="fo-kicker"><span class="dot"></span>ÁREA 1 • FISCALIZAÇÃO DE OBRAS E SERVIÇOS TÉCNICOS — MS</div>
      <div class="fo-title">FiscalizaObras-MS <span>|</span> Área 1</div>
      <div class="fo-sub">Pesquisa, auditoria e extração de contratos de Engenharia, Agronomia e Geociências
        diretamente dos Portais da Transparência municipais · Exercício {exercicio}</div>
    </div>
  </div>
  <div class="fo-munis"><b>MUNICÍPIOS ABRANGIDOS ({len(municipios)}):</b> {lista}</div>
</div>"""


def selo_sidebar_html() -> str:
    return f"""
<div class="fo-side">{emblema_svg(44)}
  <div><div class="t1">FiscalizaObras-MS</div><div class="t2">ÁREA 1 • CREA-MS</div></div>
</div>"""


def kpi_html(rotulo: str, valor: str, detalhe: str = "", variante: str = "") -> str:
    return (f'<div class="fo-kpi {variante}"><div class="rot">{escape(rotulo)}</div>'
            f'<div class="val" title="{escape(valor)}">{escape(valor)}</div>'
            f'<div class="det">{escape(detalhe)}</div></div>')


def secao_html(titulo: str) -> str:
    return f'<div class="fo-sec">{escape(titulo)}</div>'


def moeda_br(v: float | None) -> str:
    if v is None:
        return "—"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
