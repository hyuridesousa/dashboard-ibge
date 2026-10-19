# Painel Analítico Interativo de Desocupação no Brasil (PNAD Contínua / IBGE)

## 1. Visão Geral do Sistema
Este painel analítico interativo foi projetado para apoio à tomada de decisão gerencial no acompanhamento das taxas de desocupação do trabalho no Brasil, consumindo dados oficiais da PNAD Contínua (Tabela 4099/IBGE).

A solução utiliza **Python**, **Streamlit** e **Plotly**, incorporando visualizações coordenadas e interatividade em tempo real.

---

## 2. Aplicação do Mantra de Shneiderman
A arquitetura visual segue o paradigma *"Overview first, zoom and filter, details-on-demand"*:

1. **Overview First (Visão Geral Primeiro):**
   - O painel exibe a visão espacial completa do Brasil por meio de um Mapa Coroplético e a trajetória histórica nacional na Série Temporal.
2. **Zoom and Filter (Aproximar e Filtrar):**
   - Seleção regional na barra lateral para filtrar o escopo de análise.
   - Brushing no mapa ou no gráfico de barras para isolar estados de interesse.
   - Seleção de faixa temporal na série de linhas para redefinir a janela de análise.
3. **Details-on-Demand (Detalhes Sob Demanda):**
   - Tooltips enriquecidos com estatísticas detalhadas ao passar o cursor sobre os elementos.
   - Card de KPIs dinâmicos exibindo extremos da série histórica, médias e variações percentuais.
   - Tabela de dados detalhada e filtrada ao final da página com botão de exportação CSV.

---

## 3. Arquitetura de Visões Coordenadas (Multiple Coordinated Views)
O painel coordena simultaneamente **3 visões primárias**:
- **Visão Espacial:** Mapa Coroplético por UF.
- **Visão Categórica:** Ranking de Barras Horizontais das UFs.
- **Visão Temporal:** Série Histórica de Linhas.

### Mecanismo de Sincronização (Brushing & Linking)
A comunicação interativa entre os componentes ocorre de forma bidirecional via captura de eventos `on_select="rerun"` no Streamlit:
- **Destaque Espaço-Categórico:** Ao selecionar uma UF no mapa ou no ranking, a linha correspondente é destacada na série temporal e o detalhamento individual é atualizado no painel de estatísticas.
- **Seleção Focus + Context:** Os elementos não selecionados mantêm o contexto visual com opacidade reduzida e tons cinzas neutros (`#B8B8B8` e `#CFCFCF`).

---

## 4. Acessibilidade Visual e Data-Ink Ratio
- **Acessibilidade para Daltonismo:**
  - Uso da paleta de cores categórica **Okabe-Ito** (segura para protanopia, deuteranopia e tritanopia).
  - Escala contínua do mapa em **Cividis**, perceptualmente uniforme para daltônicos.
- **Maximização do Data-Ink Ratio (Tufte):**
  - Remoção de linhas de grade ruidosas e fundos escuros.
  - Omissão do eixo X do gráfico de barras em prol da rotulagem direta de dados nas extremidades das barras.