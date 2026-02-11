import streamlit as st
import pandas as pd
import glob
import plotly.express as px
import plotly.graph_objects as go

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

# --- Funções Auxiliares ---
def formatar_foto(url):
    if pd.isna(url) or str(url) == 'nan':
        return "https://via.placeholder.com/220?text=Sem+Foto"
    return str(url).replace('FORMATO', '220x220')

# --- Funções de Carregamento ---
@st.cache_data
def load_data():
    # 1. Carregar Rodadas
    rodada_files = sorted(glob.glob("rodada-*.csv"))
    if not rodada_files:
        return pd.DataFrame(), pd.DataFrame()
    
    dfs = []
    for f in rodada_files:
        try:
            temp = pd.read_csv(f)
            dfs.append(temp)
        except Exception as e:
            st.warning(f"Erro ao ler {f}: {e}")
            
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    
    if not df_main.empty:
        df_main = df_main.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    # 2. Carregar Confrontos (Para saber o adversário futuro)
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos_list = []
    
    for f in confronto_files:
        try:
            temp_df = pd.read_csv(f)
            # Normaliza Mando
            temp_df['Mando_Padrao'] = temp_df['Mando'].apply(
                lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA'
            )
            df_jogos_list.append(temp_df)
        except Exception as e:
            pass
            
    df_jogos = pd.concat(df_jogos_list, ignore_index=True) if df_jogos_list else pd.DataFrame()
    
    # Remove duplicatas de jogos (mesmo time na mesma rodada)
    if not df_jogos.empty:
        df_jogos = df_jogos.drop_duplicates(subset=['rodada_id', 'clube_id'])
    
    return df_main, df_jogos

# Executa carregamento
df, df_jogos = load_data()

# --- Processamento ---
if df.empty:
    st.error("⚠️ Nenhum dado encontrado.")
else:
    # Tipagem
    df['atletas.rodada_id'] = pd.to_numeric(df['atletas.rodada_id'], errors='coerce').fillna(0).astype(int)
    df['atletas.clube_id'] = pd.to_numeric(df['atletas.clube_id'], errors='coerce').fillna(0).astype(int)
    
    # Cruzamento Inicial (Histórico - O que já aconteceu)
    if not df_jogos.empty:
        df_jogos['rodada_id'] = pd.to_numeric(df_jogos['rodada_id'], errors='coerce').fillna(0).astype(int)
        df_jogos['clube_id'] = pd.to_numeric(df_jogos['clube_id'], errors='coerce').fillna(0).astype(int)

        df = pd.merge(
            df, 
            df_jogos[['rodada_id', 'clube_id', 'Mando_Padrao', 'Adversario']], 
            left_on=['atletas.rodada_id', 'atletas.clube_id'], 
            right_on=['rodada_id', 'clube_id'], 
            how='left'
        )
        df['Mando_Padrao'] = df['Mando_Padrao'].fillna('N/A')
        df['Adversario'] = df['Adversario'].fillna('N/A')
    else:
        df['Mando_Padrao'] = 'N/A'
        df['Adversario'] = 'N/A'

    df = df.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    if 'atletas.entrou_em_campo' in df.columns:
        df['atletas.entrou_em_campo'] = df['atletas.entrou_em_campo'].astype(str).str.lower().isin(['true', '1', '1.0'])

    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    # Preenche Scouts
    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns: df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # --- CÁLCULO DA PONTUAÇÃO BÁSICA (Somente Positivos) ---
    # Ignora Gol, Assistência e todos os Negativos
    df['pontuacao_basica'] = (
        (df['DS'] * 1.2) + 
        (df['DE'] * 1.0) + 
        (df['SG'] * 5.0) + # SG é defensivo básico
        (df['FS'] * 0.5) + 
        (df['FD'] * 1.2) + 
        (df['FT'] * 3.0) + 
        (df['FF'] * 0.8) + 
        (df['PS'] * 1.0) + 
        (df['DP'] * 7.0)
    )
    
    df['tamanho_visual'] = df['pontuacao_basica'].apply(lambda x: max(1.0, x))
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR ---
    # ==========================================
    st.sidebar.header("🔍 Filtros & Pesquisa")
    
    # 1. Filtro de Nome (Global)
    busca_nome = st.sidebar.text_input("🕵️ Buscar Jogador (Nome)", placeholder="Ex: Hulk, Veiga...").strip().lower()

    st.sidebar.markdown("---")
    st.sidebar.subheader("Filtros de Dados")

    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    if min_rodada == max_rodada:
        sel_rodada_range = (min_rodada, max_rodada)
    else:
        sel_rodada_range = st.sidebar.slider("Intervalo de Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))

    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Faixa de Preço", min_preco, max_preco, (min_preco, max_preco))
    
    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    all_posicoes = sorted(df['posicao_nome'].dropna().unique())

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    sel_mando = st.sidebar.multiselect("Mando", ['CASA', 'FORA'], default=['CASA', 'FORA'])
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # ==========================================
    # --- APLICAÇÃO DOS FILTROS ---
    # ==========================================
    # Filtro base
    df_filtrado = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]

    # Filtros Categóricos
    if sel_clube: df_filtrado = df_filtrado[df_filtrado['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_filtrado = df_filtrado[df_filtrado['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_filtrado = df_filtrado[df_filtrado['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram: df_filtrado = df_filtrado[df_filtrado['atletas.entrou_em_campo'] == True]
    
    # Filtro de Preço
    df_filtrado = df_filtrado[
        (df_filtrado['atletas.preco_num'] >= sel_preco_range[0]) &
        (df_filtrado['atletas.preco_num'] <= sel_preco_range[1])
    ]

    # Filtro de Busca por Nome (Aplica em tudo que deriva de df_filtrado)
    if busca_nome:
        df_filtrado = df_filtrado[
            df_filtrado['atletas.apelido'].str.lower().str.contains(busca_nome) | 
            df_filtrado['atletas.clube.id.full.name'].str.lower().str.contains(busca_nome)
        ]

    # ==========================================
    # --- FUNÇÃO DE AGRUPAMENTO (SNAPSHOT) ---
    # ==========================================
    def agrupar_dados(dataframe_base):
        if dataframe_base.empty: return pd.DataFrame()
        
        # A) PONTUAÇÃO é SOMADA
        df_pontos = dataframe_base.groupby('atletas.atleta_id')['atletas.pontos_num'].sum().reset_index()
        df_pontos.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)
        
        # B) SCOUTS são SNAPSHOT (Última rodada disponível no filtro)
        df_snapshot = dataframe_base.sort_values('atletas.rodada_id', ascending=False).drop_duplicates('atletas.atleta_id')
        
        # Merge
        df_agrp = pd.merge(df_snapshot, df_pontos, on='atletas.atleta_id', how='left')
        
        # Recalcula Básica (Positivos) com os dados acumulados
        df_agrp['pontuacao_basica_atual'] = (
            (df_agrp['DS'] * 1.2) + (df_agrp['DE'] * 1.0) + (df_agrp['SG'] * 5.0) + 
            (df_agrp['FS'] * 0.5) + (df_agrp['FD'] * 1.2) + (df_agrp['FT'] * 3.0) + 
            (df_agrp['FF'] * 0.8) + (df_agrp['PS'] * 1.0) + (df_agrp['DP'] * 7.0)
        )
        return df_agrp

    df_agrupado = agrupar_dados(df_filtrado)
    
    # Dataset Base para Robô e Comparador (ignora filtros de preço da sidebar, mas respeita busca de nome)
    df_base_robo = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]
    if somente_jogaram: df_base_robo = df_base_robo[df_base_robo['atletas.entrou_em_campo'] == True]
    if busca_nome: df_base_robo = df_base_robo[df_base_robo['atletas.apelido'].str.lower().str.contains(busca_nome)]
    
    df_robo_consolidado = agrupar_dados(df_base_robo)

    # ==========================================
    # --- DASHBOARD ---
    # ==========================================
    if df_agrupado.empty:
        st.warning(f"⚠️ Nenhum jogador encontrado para '{busca_nome}' com os filtros atuais.")
    else:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador (Soma)", f"{df_agrupado['pontuacao_total_periodo'].max():.1f}")
        k2.metric("Média Geral (Por Jogo)", f"{df_filtrado['atletas.pontos_num'].mean():.2f}")
        k3.metric("Pontuação Básica (Acumulada)", f"{df_agrupado['pontuacao_basica_atual'].mean():.2f}")
        k4.metric("Jogadores Listados", f"{len(df_agrupado)}")

        st.markdown("---")

        tab_robo, tab_comparador, tab_capitao, tab_destaques, tab_adversario, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🤖 Robô Escalador",
            "⚔️ Comparador",
            "© Capitão de Segurança",
            "🏆 Destaques", 
            "🛡️ Raio-X Adversário",
            "📊 Times", 
            "🏠 Casa vs Fora", 
            "💎 Valorização", 
            "📋 Tabela"
        ])

        # --- ABA ROBÔ ---
        with tab_robo:
            st.header("🤖 Otimizador com Orçamento Exato")
            c1, c2, c3 = st.columns(3)
            orcamento = c1.number_input("💰 Orçamento (C$)", value=100.0)
            esquema = c2.selectbox("Formação", ["4-3-3", "3-4-3", "3-5-2", "4-4-2", "5-3-2"])
            criterio = c3.selectbox("Focar em:", ["Pontuação Básica", "Pontuação Total"])
            col_sort = 'pontuacao_basica_atual' if criterio == "Pontuação Básica" else 'pontuacao_total_periodo'

            if st.button("🚀 Escalar Time"):
                esquemas = {
                    "4-3-3": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 3, 'Atacante': 3, 'Técnico': 0},
                    "3-4-3": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 3, 'Técnico': 0},
                    "3-5-2": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 5, 'Atacante': 2, 'Técnico': 0},
                    "4-4-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 4, 'Atacante': 2, 'Técnico': 0},
                    "5-3-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 3, 'Atacante': 2, 'Técnico': 0},
                }
                
                # 1. Seleciona os melhores absolutos (Time dos Sonhos)
                pool = df_robo_consolidado.sort_values(col_sort, ascending=False)
                time_atual = []
                for pos, qtd in esquemas[esquema].items():
                    if qtd > 0:
                        melhores = pool[pool['posicao_nome'] == pos].head(qtd)
                        time_atual.append(melhores)
                
                df_time = pd.concat(time_atual)
                custo = df_time['atletas.preco_num'].sum()
                
                # 2. Otimização (Trocas para caber no orçamento)
                # Loop de troca: Sai o jogador com pior custo-benefício de troca
                loop_limit = 0
                while custo > orcamento and loop_limit < 100:
                    melhor_troca = None
                    melhor_ratio = float('inf') # Queremos minimizar Perda de Pontos / Economia
                    
                    for idx, sair in df_time.iterrows():
                        # Busca substitutos mais baratos na mesma posição e que não estão no time
                        candidatos = pool[
                            (pool['posicao_nome'] == sair['posicao_nome']) & 
                            (pool['atletas.preco_num'] < sair['atletas.preco_num']) & 
                            (~pool['atletas.atleta_id'].isin(df_time['atletas.atleta_id']))
                        ]
                        
                        if not candidatos.empty:
                            entrar = candidatos.iloc[0] # O melhor dos baratos
                            economia = sair['atletas.preco_num'] - entrar['atletas.preco_num']
                            perda = sair[col_sort] - entrar[col_sort]
                            
                            # Ratio: Quanto de ponto eu perco para cada $1 economizado?
                            # Quanto menor esse número, "menos dolorosa" é a troca
                            if economia > 0:
                                ratio = perda / economia
                                if ratio < melhor_ratio:
                                    melhor_ratio = ratio
                                    melhor_troca = (idx, entrar)
                    
                    if melhor_troca:
                        idx_sair, row_entrar = melhor_troca
                        df_time = df_time.drop(idx_sair)
                        df_time = pd.concat([df_time, row_entrar.to_frame().T])
                        custo = df_time['atletas.preco_num'].sum()
                    else:
                        break # Sem trocas possíveis
                    loop_limit += 1

                # Exibição
                st.success(f"✅ Time Escalado! Custo: C$ {custo:.2f} | Saldo: C$ {orcamento - custo:.2f}")
                
                ordem = {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 5}
                df_time['ordem'] = df_time['posicao_nome'].map(ordem)
                df_time = df_time.sort_values('ordem')
                
                cols = st.columns(5)
                i = 0
                for _, row in df_time.iterrows():
                    with cols[i % 5]:
                        st.image(formatar_foto(row.get('atletas.foto', '')), width=80)
                        st.markdown(f"**{row['posicao_nome']}**")
                        st.caption(row['atletas.apelido'])
                        st.write(f"C$ {row['atletas.preco_num']:.1f}")
                        st.metric("Pontos", f"{row[col_sort]:.1f}")
                        st.divider()
                    i += 1

        # --- ABA COMPARADOR ---
        with tab_comparador:
            st.header("⚔️ Comparador Mano a Mano")
            c1, c2 = st.columns(2)
            lista_nomes = sorted(df_robo_consolidado['atletas.apelido'].unique())
            p1 = c1.selectbox("Jogador 1", lista_nomes, index=0)
            p2 = c2.selectbox("Jogador 2", lista_nomes, index=min(1, len(lista_nomes)-1))
            
            if p1 and p2:
                d1 = df_robo_consolidado[df_robo_consolidado['atletas.apelido'] == p1].iloc[0]
                d2 = df_robo_consolidado[df_robo_consolidado['atletas.apelido'] == p2].iloc[0]
                
                cats = ['Pontos Totais', 'Pontuação Básica', 'Gols', 'Assist', 'Finalizações', 'Desarmes']
                v1 = [d1['pontuacao_total_periodo'], d1['pontuacao_basica_atual'], d1['G'], d1['A'], d1['finalizacoes_total'], d1['DS']]
                v2 = [d2['pontuacao_total_periodo'], d2['pontuacao_basica_atual'], d2['G'], d2['A'], d2['finalizacoes_total'], d2['DS']]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(r=v1, theta=cats, fill='toself', name=p1, line_color='#00CC96'))
                fig.add_trace(go.Scatterpolar(r=v2, theta=cats, fill='toself', name=p2, line_color='#EF553B'))
                fig.update_layout(polar=dict(radialaxis=dict(visible=True)), title="Comparativo Direto")
                st.plotly_chart(fig, use_container_width=True)

        # --- ABA CAPITÃO ---
        with tab_capitao:
            st.header("© Capitão de Segurança (Simulação)")
            
            # Seletor de Rodada Futura
            rodadas_disponiveis = sorted(df_jogos['rodada_id'].unique())
            if rodadas_disponiveis:
                rodada_simulacao = st.selectbox("Simular contra adversários de qual Rodada?", rodadas_disponiveis)
                
                # 1. Fragilidade (Quem cede pontos HOJE baseado no histórico carregado)
                # Ignora N/A para cálculo de média
                df_fragilidade = df[df['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                df_fragilidade.rename(columns={'atletas.pontos_num': 'media_cedida_adv'}, inplace=True)
                
                # 2. Pegar os jogadores atuais e ver contra quem jogam na rodada selecionada
                jogos_rodada = df_jogos[df_jogos['rodada_id'] == rodada_simulacao][['clube_id', 'Adversario', 'Mando_Padrao']]
                
                # Juntar info do jogo futuro no dataframe de jogadores (df_robo_consolidado tem os dados unificados)
                # Precisamos da coluna clube_id no df_robo. Ela está lá? Sim, 'atletas.clube.id.full.name' não serve, precisamos do ID.
                # Vamos pegar do df_snapshot usado no agrupamento.
                
                # Recria df base leve
                df_base_capitao = df_robo_consolidado.copy()
                # Precisamos re-mergear o clube_id numérico pois o agrupado perdeu. 
                # Simplificação: Vamos usar o nome do clube para cruzar se o ID falhar, ou pegar do snapshot.
                # Melhor: Vamos fazer merge com df_main para pegar o clube_id de volta pelo atleta_id
                df_ids = df[['atletas.atleta_id', 'atletas.clube_id']].drop_duplicates()
                df_base_capitao = pd.merge(df_base_capitao, df_ids, on='atletas.atleta_id', how='left')
                
                # Agora cruza com a tabela de jogos da rodada simulada
                df_simulacao = pd.merge(df_base_capitao, jogos_rodada, left_on='atletas.clube_id', right_on='clube_id', how='inner')
                
                # Agora cruza com a fragilidade do ADVERSÁRIO dessa rodada
                df_final_cap = pd.merge(
                    df_simulacao, 
                    df_fragilidade, 
                    left_on=['Adversario', 'posicao_nome'], 
                    right_on=['Adversario', 'posicao_nome'], 
                    how='left'
                )
                
                # Cálculo Score
                # Score = (Minha Média + O que o Adv Cede) / 2
                # Usamos pontuacao_basica_atual ou total? Vamos usar uma média simples por jogo estimada
                # Estimativa Pontos Por Jogo = pontuacao_total_periodo / jogos_num
                df_final_cap['media_ppj'] = df_final_cap['pontuacao_total_periodo'] / df_final_cap['atletas.jogos_num']
                
                df_final_cap['score_seguranca'] = (df_final_cap['media_ppj'] + df_final_cap['media_cedida_adv'].fillna(0)) / 2
                
                st.info(f"Mostrando confrontos da **Rodada {rodada_simulacao}**. O Score cruza a média do jogador com a média que o adversário ({rodada_simulacao}) costuma levar.")
                
                top_caps = df_final_cap.sort_values('score_seguranca', ascending=False).head(20)
                
                # Exibição
                st.dataframe(
                    top_caps[['atletas.apelido', 'posicao_nome', 'Adversario', 'Mando_Padrao', 'media_ppj', 'media_cedida_adv', 'score_seguranca']]
                    .rename(columns={'media_ppj': 'Média Jogador', 'media_cedida_adv': 'Fragilidade Adv', 'score_seguranca': 'Score Capitão'}),
                    use_container_width=True, hide_index=True
                )
            else:
                st.warning("Carregue arquivos de confrontos para usar esta aba.")

        # --- ABA DESTAQUES (Mantida) ---
        with tab_destaques:
            # ... (Código Mantido Igual) ...
            st.markdown(f"#### 🔥 Líderes (Acumulado)")
            def render_destaque(label, col_scout, container):
                if df_agrupado[col_scout].sum() == 0:
                    container.info(f"{label}: 0")
                    return
                idx = df_agrupado[col_scout].idxmax()
                row = df_agrupado.loc[idx]
                foto_url = formatar_foto(row.get('atletas.foto', ''))
                with container:
                    st.markdown(f"**{label}**")
                    c_img, c_info = st.columns([1, 2])
                    with c_img: st.image(foto_url, width=80)
                    with c_info:
                        st.caption(f"{row['atletas.apelido']}")
                        st.caption(f"{row['atletas.clube.id.full.name']}")
                        st.metric("Total", int(row[col_scout]))
                    st.divider()

            c1, c2, c3, c4 = st.columns(4)
            render_destaque("Artilheiro (G)", 'G', c1)
            render_destaque("Garçom (A)", 'A', c2)
            render_destaque("Fin. Trave (FT)", 'FT', c3)
            render_destaque("Fin. Defendida (FD)", 'FD', c4)
            c5, c6, c7, c8 = st.columns(4)
            render_destaque("Fin. Fora (FF)", 'FF', c5)
            render_destaque("Faltas Sofridas (FS)", 'FS', c6)
            render_destaque("Impedimentos (I)", 'I', c7)
            c8.empty() 
            d1, d2, d3, d4 = st.columns(4)
            render_destaque("Desarmes (DS)", 'DS', d1)
            render_destaque("Saldo de Gol (SG)", 'SG', d2)
            render_destaque("Defesas (DE)", 'DE', d3)
            render_destaque("Pênaltis Def (DP)", 'DP', d4)
            n1, n2, n3, n4 = st.columns(4)
            render_destaque("Gols Sofridos (GS)", 'GS', n1)
            render_destaque("Faltas Cometidas (FC)", 'FC', n2)
            render_destaque("Cartão Amarelo (CA)", 'CA', n3)
            render_destaque("Cartão Vermelho (CV)", 'CV', n4)

        # --- ABA RAIO-X (Mantida) ---
        with tab_adversario:
            st.subheader("🔥 Raio-X: Quem cede mais pontos?")
            if 'Adversario' in df_filtrado.columns and not df_filtrado['Adversario'].isin(['N/A']).all():
                df_heat = df_filtrado[df_filtrado['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                def criar_heatmap(posicoes, titulo, cor):
                    d = df_heat[df_heat['posicao_nome'].isin(posicoes)]
                    if d.empty: return
                    p = d.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                    p['Total'] = p.sum(axis=1)
                    p = p.sort_values('Total').drop(columns='Total')
                    st.plotly_chart(px.imshow(p, text_auto=".1f", aspect="auto", color_continuous_scale=cor, title=titulo), use_container_width=True)
                
                c1, c2, c3, c4 = st.columns(4)
                with c1: criar_heatmap(['Goleiro'], "Goleiros", "Blues")
                with c2: criar_heatmap(['Zagueiro', 'Lateral'], "Defesa", "Greens")
                with c3: criar_heatmap(['Meia'], "Meias", "Oranges")
                with c4: criar_heatmap(['Atacante'], "Ataque", "Reds")

        # --- ABA TIMES (Mantida) ---
        with tab_times:
            club_stats = df_filtrado.groupby('atletas.clube.id.full.name').agg({'atletas.pontos_num': 'mean', 'finalizacoes_total': 'mean'}).reset_index()
            c1, c2 = st.columns(2)
            with c1: st.plotly_chart(px.bar(club_stats.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h', title="Média Pontos"), use_container_width=True)
            with c2: st.plotly_chart(px.bar(club_stats.sort_values('finalizacoes_total'), x='finalizacoes_total', y='atletas.clube.id.full.name', orientation='h', title="Média Finalizações", color_discrete_sequence=['red']), use_container_width=True)

        # --- ABA CASA/FORA (Mantida) ---
        with tab_scouts:
            if not df_filtrado['Mando_Padrao'].isin(['N/A']).all():
                grp = df_filtrado.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                c1, c2 = st.columns(2)
                with c1: st.plotly_chart(px.bar(grp, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group', title="Ataque"), use_container_width=True)
                with c2: st.plotly_chart(px.bar(grp, x='atletas.clube.id.full.name', y='scouts_defensivos_total', color='Mando_Padrao', barmode='group', title="Defesa"), use_container_width=True)

        # --- ABA VALORIZAÇÃO (Mantida) ---
        with tab_valorizacao:
            st.plotly_chart(px.scatter(df_filtrado, x='atletas.preco_num', y='atletas.pontos_num', color='posicao_nome', size='tamanho_visual', hover_name='atletas.apelido', title="Preço x Pontuação"), use_container_width=True)

        # --- ABA TABELA ---
        with tab_tabela:
            st.subheader("Tabela Consolidada")
            cols = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.preco_num', 'pontuacao_total_periodo', 'pontuacao_basica_atual'] + todos_scouts
            df_show = df_agrupado[cols].sort_values('pontuacao_total_periodo', ascending=False)
            df_show.columns = ['Apelido', 'Clube', 'Posição', 'Preço', 'Pontos Totais', 'Pontuação Básica'] + todos_scouts
            st.dataframe(df_show, use_container_width=True, hide_index=True)
