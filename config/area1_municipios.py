"""Municípios da Área 1 de Fiscalização (Crea-MS) e seus Portais da Transparência.

ARQUIVO GERADO AUTOMATICAMENTE por ``scripts/gerar_config_area1.py``.
Planilha de origem: regiao_1.xlsx
Gerado em: 18/11/2026 00:56

Para atualizar: substitua a planilha .xlsx na raiz do projeto e execute
    python scripts/gerar_config_area1.py
Campos por município:
    municipio      nome oficial do município
    url            URL oficial do Portal da Transparência (planilha)
    provedor       provedor identificado (roteia o coletor em scrapers/collector.py)
    url_contratos  link direto para a consulta de contratos no portal
"""

EXERCICIO = 2026
PLANILHA_ORIGEM = 'regiao_1.xlsx'

MUNICIPIOS_AREA1 = [{'municipio': 'Angélica',
  'url': 'https://transparencia.betha.cloud/#/3CsimkdlAFWc2SxNasIRBA==',
  'provedor': 'Betha Cloud',
  'url_contratos': 'https://transparencia.betha.cloud/#/3CsimkdlAFWc2SxNasIRBA=='},
 {'municipio': 'Deodápolis',
  'url': 'https://transparencia.betha.cloud/#/whlvWPlYqIFeODuQD0dKgA==',
  'provedor': 'Betha Cloud',
  'url_contratos': 'https://transparencia.betha.cloud/#/whlvWPlYqIFeODuQD0dKgA=='},
 {'municipio': 'Glória de Dourados',
  'url': 'http://177.73.106.211:5656/Transparencia/',
  'provedor': 'Fiorilli SCPI 9.0',
  'url_contratos': 'http://177.73.106.211:5656/Transparencia/'},
 {'municipio': 'Ivinhema',
  'url': 'https://transparencia.ivinhema.ms.gov.br/transparencia/',
  'provedor': 'Outro / Genérico',
  'url_contratos': 'https://transparencia.ivinhema.ms.gov.br/transparencia/'}]
