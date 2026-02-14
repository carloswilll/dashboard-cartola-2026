import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Cartola Pro 2026 - Auto Update", layout="wide", page_icon="⚽")

# --- MÓDULO DE ATUALIZAÇÃO AUTOMÁTICA (O Segredo) ---
def gerenciar_banco_dados():
    nome_arquivo = "banco_de_dados_historico.csv"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Verifica qual a rodada ATUAL no campeonato
    try:
        status_mercado = requests.get("https://api.cartola.globo.com/mercado/status", headers=headers).json()
        rodada_atual_api = status_mercado['rodada_atual'] # Ex: Estamos na rodada 4
        # A rodada que acabou de fechar é a anterior (Ex: Rodada 3)
        ultima_rodada_finalizada = rodada_atual_api - 1 if status_mercado['status_mercado'] == 1 else rodada_atual_api
    except:
        st.error("Erro ao conectar com a API da Globo para verificar rodada.")
        return pd.DataFrame()

    # 2. Carrega o banco existente ou cria um vazio
    if os.path.exists(nome_arquivo):
        df_historico = pd.read_csv(nome_arquivo, sep=';')
        rodadas_no_banco = df_historico['rodada'].unique().tolist()
        ultima_no_banco = max(rodadas_no_banco) if rodadas_no_banco else 0
    else:
        df_historico = pd.DataFrame()
        ultima_no_banco = 0

    # 3. Verifica se precisa atualizar (Gap de Rodadas)
    if ultima_rodada_finalizada > ultima_no_banco:
        novas_rodadas = range(ultima_no_banco + 1, ultima_rodada_finalizada + 1)
        
        container_update = st.empty() # Placeholder visual
        lista_novos_dados = []
        
        # Baixa referências para cruzar nomes
        mercado = requests.get("https://api.cartola.globo.com/atletas/mercado", headers=headers).json()
        clubes = {int(k): v['nome'] for k, v in mercado['clubes'].items()}
        posicoes = {int(k): v['nome'] for k, v in mercado['posicoes'].items()}
        
        for r in novas_rodadas:
            container_update.info(f"🔄 Baixando dados da Rodada {r} pela primeira vez...")
            
            # Pega pontuados da rodada
            pontuados = requests.get(f"https://api.cartola.globo.com/atletas/pontuados/{r}", headers=headers).json()
            partidas = requests.get(f"https://api.cartola.globo.com/partidas/{r}", headers=headers).json()
            
            # Mapear confrontos dessa rodada específica
            mapa_confrontos = {}
            if partidas and 'partidas' in partidas:
                for p in partidas['partidas']:
                    casa = p['clube_casa_id']
                    visitante = p['clube_visitante_id']
                    mapa_confrontos[casa] = {'mando': 'CASA', 'adversario': clubes.get(visitante, 'Visitante')}
                    mapa_confrontos[visitante] = {'mando': 'FORA', 'adversario': clubes.get(casa, 'Mandante')}

            if pontuados and 'atletas' in pontuados:
                for id_atleta, dados in pontuados['atletas'].items():
                    clube_id = dados['clube_id']
                    confronto = mapa_confrontos.get(clube_id, {'mando': '-', 'adversario': '-'})
                    
                    linha = {
                        'rodada': r,
                        'atleta_id': int(id_atleta),
                        'apelido': dados.get('apelido', f"Jogador {id_atleta}"),
                        'pontos': dados.get('pontuacao', 0),
                        'preco': dados.get('preco', 0),
                        'media': dados.get('media', 0),
                        'clube_id': clube_id,
                        'posicao_id': dados['posicao_id'],
                        'mando': confronto['mando'],
                        'adversario': confronto['adversario']
                    }
                    if 'scout' in dados:
                        linha.update(dados['scout'])
                    
                    lista_novos_dados.append(linha)
        
        # 4. Salva o novo acumulado
        if lista_novos_dados:
            df_novo = pd.DataFrame(lista_novos_dados).fillna(0)
            df_final = pd.concat([df_historico, df_novo], ignore_index=True)
            df_final.to_csv(nome_arquivo, index=False, sep=';')
            container_update.success("✅ Banco de dados atualizado com sucesso!")
            return df_final
        else:
            return df_historico
    else:
        return df_historico

# --- CARGA DE DADOS (AGORA AUTOMÁTICA) ---
with st.spinner("Sincronizando banco de dados histórico..."):
    df_historico = gerenciar_banco_dados()

@st.cache_data(ttl=600)
def carregar_mercado_ao_vivo():
    """Mercado sempre fresco (API direta)"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = requests.get("https://api.cartola.globo.com/atletas/mercado", headers=headers).json()
        clubes = {int(k): v['nome'] for k, v in res['clubes'].items()}
        posicoes = {int(k): v['nome'] for k, v in res['posicoes'].items()}
        
        dados = []
        for a in res['atletas']:
            row = a.copy()
            row['clube'] = clubes[a['clube_id']]
            row['posicao'] = posicoes[a['posicao_id']]
            if 'scout' in a:
                row.update(a['scout'])
            dados.append(row)
        return pd.DataFrame(dados).fillna(0)
    except:
        return pd.DataFrame()

df_mercado = carregar_mercado_ao_vivo()

# --- CÁLCULO DE SCORE PERSONALIZADO ---
def calcular_score(df):
    if df.empty: return df
    pesos = {
        'DS': 1.5, 'G': 8.0, 'A': 5.0, 'SG': 5.0, 'FS': 0.5,
        'FF': 0.8, 'FD': 1.2, 'FT': 3.0, 'PS': 1.0, 'DE': 1.3, 'DP': 7.0,
        'GC': -3.0, 'CV': -3.0, 'CA': -1.0, 'GS': -1.0, 'PP': -4.0
    }
    df['Score Personalizado'] = 0
    for col, peso in pesos.items():
        if col in df.columns:
            df['Score Personalizado'] += df[col] * peso
    return df

df_mercado = calcular_score(df_mercado)

# --- DASHBOARD VISUAL (SIMPLIFICADO PARA FOCO NO UPDATE) ---

st.title("🤖 Dashboard Cartola 2026 - Auto-Gerenciado")
st.caption("O sistema detecta novas rodadas automaticamente e atualiza o histórico.")

tab1, tab2 = st.tabs(["🔥 Mercado Ao Vivo", "📊 Inteligência Tática"])

with tab1:
    st.subheader("Melhores Opções da Próxima Rodada (Score Personalizado)")
    if not df_mercado.empty:
        # Filtros rápidos
        pos_filter = st.multiselect("Filtrar Posição", df_mercado['posicao'].unique())
        df_view = df_mercado.copy()
        if pos_filter:
            df_view = df_view[df_view['posicao'].isin(pos_filter)]
            
        st.dataframe(
            df_view[['apelido', 'posicao', 'clube', 'preco', 'Score Personalizado', 'media']]
            .sort_values(by='Score Personalizado', ascending=False)
            .style.background_gradient(subset=['Score Personalizado'], cmap='Greens'),
            use_container_width=True
        )

with tab2:
    st.subheader("Análise Histórica (Baseada nas rodadas já ocorridas)")
    if not df_historico.empty:
        # Mapa de Calor de Adversários
        st.markdown("**Quem cede mais pontos?** (Baseado no histórico acumulado automaticamente)")
        
        # Cruzamento simples
        df_historico['posicao_nome'] = df_historico['posicao_id'].map({1:'Gol', 2:'Lat', 3:'Zag', 4:'Meia', 5:'Ata', 6:'Tec'})
        heat_data = df_historico.groupby(['adversario', 'posicao_nome'])['pontos'].mean().reset_index()
        
        fig = px.density_heatmap(
            heat_data, x='posicao_nome', y='adversario', z='pontos', 
            color_continuous_scale='RdYlGn_r', title="Média de Pontos Cedidos pelo Adversário"
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"Dados históricos processados até a rodada: {df_historico['rodada'].max()}")
    else:
        st.warning("Ainda não há histórico suficiente (Rodada 1 ainda não finalizou ou API vazia).")
