# FiscalizaObras-MS | Área 1

Painel Streamlit da **Área 1 de Fiscalização de Obras e Serviços Técnicos (Crea-MS)** para pesquisa,
auditoria e extração de contratos públicos de **Engenharia, Agronomia e Geociências** direto dos
**Portais da Transparência das prefeituras** da Área 1 de Mato Grosso do Sul. **A API do PNCP não é usada.**

## Funcionalidades

- Leitura automática da planilha `.xlsx` da Área 1 (municípios + URLs dos portais) e identificação do
  provedor de cada portal (Fiorilli SCPI 9.0, Betha Cloud, Betha e-Gov, Quality Sistemas, Megasoft, CR2,
  IPM Atende.net, Elotech, Agili ou Genérico).
- Coleta paralela (`ThreadPoolExecutor`), com cache de 1 h por município e período (`@st.cache_data`) e
  progresso em tempo real.
- Filtro semântico do objeto do contrato por área técnica (Civil/Obras, Elétrica/Mecânica,
  Agronomia/Meio Ambiente, Geociências/Topografia, Projetos/Consultoria).
- Filtros: municípios, período (DD/MM/AAAA, exercício 2026), área técnica, texto livre, faixa de valor e
  “somente documentação completa”.
- KPIs, tabela com links (📄 Contrato, 📋 OS, 💰 Empenho, 🌐 Portal), ficha detalhada de fiscalização e
  diagnóstico de cada portal (`Online`, `Instável / Timeout`, `Acesso Manual`), com o link direto para a
  consulta.
- Exportação `.xlsx`, com a aba `Contratos_Area1_2026` (moeda R$, datas DD/MM/AAAA e hiperlinks) e a aba
  `Resumo_Area1` (consolidado por município).

## Estrutura

```
app.py                         # aplicação principal
config/
  area1_municipios.py          # municípios/URLs/provedores, GERADO a partir da planilha
  planilha.py                  # leitor tolerante da planilha .xlsx
  provedores.py                # identificação de provedores e links de consulta
scrapers/
  collector.py                 # coletor multiplataforma e diagnóstico
  parsers.py                   # parsers HTML/JSON, valores, datas, CNPJ e links
  keywords.py                  # vocabulário de Engenharia, Agronomia e Geociências
utils/
  styles.py                    # identidade visual (Área 1 + cores de MS)
  export_excel.py              # exportação .xlsx (openpyxl)
scripts/gerar_config_area1.py  # planilha -> config/area1_municipios.py
tests/test_pipeline.py         # testes com planilha e portal simulados
.streamlit/config.toml         # tema institucional
```

## Planilha da Área 1

Coloque o arquivo `.xlsx` na **raiz do projeto**. O leitor encontra sozinho:

- a linha de cabeçalho, mesmo com títulos acima dela;
- a coluna **Município**, também chamada Cidade ou Prefeitura;
- a coluna de **URL**, chamada URL, Link, Portal, Site ou Transparência, inclusive hiperlinks embutidos
  em células com texto como “Clique aqui”;
- as colunas opcionais **Provedor/Sistema** e **URL Contratos**;
- uma coluna **Área/Regional**: quando ela existe, somente as linhas da Área 1 são lidas.

Gere ou atualize o arquivo de configuração com:

```bash
python scripts/gerar_config_area1.py
```

O app sempre prefere a planilha presente na raiz. Se ela não estiver lá, usa `config/area1_municipios.py`.
Também é possível enviar a planilha pela barra lateral, em **Planilha da Área 1**.

> Se a identificação de um portal estiver errada, informe o provedor na coluna “Provedor” da planilha ou
> a página de contratos na coluna “URL Contratos”, e rode o gerador de novo.

## Execução local

```bash
python -m venv .venv
```

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

```bash
pip install -r requirements.txt
```

```bash
streamlit run app.py
```

Testes (opcional):

```bash
pip install pytest && python -m pytest -q
```

## Publicar no GitHub

```bash
git init
```

```bash
git add .
```

```bash
git commit -m "FiscalizaObras-MS | Área 1 - painel de fiscalização de contratos"
```

```bash
git branch -M main
```

```bash
git remote add origin https://github.com/SEU_USUARIO/fiscalizaobras-ms-area1.git
```

```bash
git push -u origin main
```

## Publicar no Streamlit Community Cloud

1. Acesse <https://share.streamlit.io> e entre com a conta do GitHub.
2. Clique em **Create app**, depois em **Deploy a public app from GitHub**.
3. Selecione o repositório, a branch `main` e o arquivo principal `app.py`.
4. Em **Advanced settings**, escolha Python 3.11 ou mais recente e clique em **Deploy**.

As dependências vêm do `requirements.txt` e o tema vem do `.streamlit/config.toml`.

## Observações técnicas

- **Portais dinâmicos** (Betha Cloud, Atende.net, Elotech e outros SPAs em JavaScript) não entregam os
  dados em HTML estático. O painel verifica se o portal está no ar e o marca como **Acesso Manual**, com o
  link direto.
- **Fiorilli SCPI**: o coletor tenta primeiro a listagem `VersaoJson/Contratos` e depois o HTML.
- **Demais provedores**: o coletor lê as tabelas de contratos da página e, se não houver nenhuma, segue o
  menu “Contratos”. Também visita até 20 páginas de detalhe por município para localizar a OS e o Empenho.
- **Certificados TLS** inválidos são comuns em portais municipais. A verificação fica ligada por padrão.
  Para desligá-la por sua conta e risco, defina `FISCALIZA_SSL_VERIFY=0`.
- O formato de moeda do Excel é gravado como `"R$" #,##0.00`, que o Excel em pt-BR exibe como
  `R$ 1.234,56` (equivale a `R$ #.##0,00`).
- Sempre confira o documento original no portal antes de lavrar autos.
