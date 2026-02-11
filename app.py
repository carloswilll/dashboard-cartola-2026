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
    """Corrige a URL da foto do jogador para o tamanho correto."""
    if pd.isna(url) or str(url) == 'nan':
        return "https://via.placeholder.com/220?text=Sem+Foto"
    return str(url).replace('FORMATO', '220x220')

# --- Funções de Carregamento ---
@st.cache_data
def load_data():
    # 1. Carregar dados das Rodadas
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

    # 2. Carregar dados de Confrontos
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos_list = []
    
    for f in confronto_files:
        try:
            temp_df = pd.read_csv(f)
            temp_df['Mando_Padrao'] = temp_df['Mando'].apply(
                lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA'
            )
            df_jogos_list.append(temp_df)
        except Exception as e:
            pass
            
    df_jogos = pd.concat(df_jogos_list, ignore_index=True) if df_jogos_list else pd.DataFrame()
    if not df_jogos.empty:
        df_jogos = df_jogos.drop_duplicates(subset=['rodada_id', 'clube_id'])
    
    return df_main, df_jogos

# Executa o carregamento
df, df_jogos = load_data()

# --- Processamento ---
if df.empty:
    st.error("⚠️ Nenhum dado de rodada encontrado.")
else:
    # Tipagem Segura
    df['atletas.rodada_id'] = pd.to_numeric(df['atletas.rodada_id'], errors='coerce').fillna(0).astype(int)
    df['atletas.clube_id'] = pd.to_numeric(df['atletas.clube_id'], errors='coerce').fillna(0).astype(int)
    
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

    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['media_basica'] = (
        (df['FT'] * 3.0) + (df['FD'] * 1.2) + (df['FF'] * 0.8) + 
        (df['FS'] * 0.5) + (df['PS'] * 1.0) + (df['DP'] * 7.0) + 
        (df['DE'] * 1.0) + (df['DS'] * 1.2)
    )
    
    df['tamanho_visual'] = df['media_basica'].apply(lambda x: max(1.0, x) if pd.notnull(x) else 1.0)
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR: FILTROS ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Principais")

    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    if min_rodada == max_rodada:
        sel_rodada_range = (min_rodada, max_rodada)
    else:
        sel_rodada_range = st.sidebar.slider("Intervalo de Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))

    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Faixa de Preço", min_preco, max_preco, (min_preco, max_preco))
    
    st.sidebar.markdown("---")

    all_clubes = sorted(df['atletas.clube.id.full.name'].dropna().unique())
    all_posicoes = sorted(df['posicao_nome'].dropna().unique())

    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", all_posicoes, default=all_posicoes)
    
    opcoes_mando = ['CASA', 'FORA', 'N/A']
    sel_mando = st.sidebar.multiselect("Mando", opcoes_mando, default=['CASA', 'FORA'])
    somente_jogaram = st.sidebar.checkbox("Apenas quem entrou em campo?", value=True)

    # 1. Filtra as rodadas selecionadas
    df_periodo = df[
        (df['atletas.rodada_id'] >= sel_rodada_range[0]) &
        (df['atletas.rodada_id'] <= sel_rodada_range[1])
    ]

    # 2. Aplica demais filtros (exceto preço para análises gerais)
    if sel_clube: df_periodo = df_periodo[df_periodo['atletas.clube.id.full.name'].isin(sel_clube)]
    if sel_posicao: df_periodo = df_periodo[df_periodo['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_periodo = df_periodo[df_periodo['Mando_Padrao'].isin(sel_mando)]
    if somente_jogaram: df_periodo = df_periodo[df_periodo['atletas.entrou_em_campo'] == True]
    
    # Filtro para visualizações que dependem do preço
    df_analise_geral = df_periodo[
        (df_periodo['atletas.preco_num'] >= sel_preco_range[0]) &
        (df_periodo['atletas.preco_num'] <= sel_preco_range[1])
    ]

    # ==========================================
    # --- AGRUPAMENTO INTELIGENTE ---
    # ==========================================
    def agrupar_dados(dataframe_base):
        if dataframe_base.empty: return pd.DataFrame()
        
        # A) SOMA da Pontuação
        df_pontos = dataframe_base.groupby('atletas.atleta_id')['atletas.pontos_num'].sum().reset_index()
        df_pontos.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)
        
        # B) SNAPSHOT dos Scouts (Pega o acumulado da última rodada selecionada)
        df_snapshot = dataframe_base.sort_values('atletas.rodada_id', ascending=False).drop_duplicates('atletas.atleta_id')
        
        # Merge
        df_agrp = pd.merge(df_snapshot, df_pontos, on='atletas.atleta_id', how='left')
        
        # Recalcula Média Básica
        df_agrp['media_basica_atual'] = (
            (df_agrp['FT'] * 3.0) + (df_agrp['FD'] * 1.2) + (df_agrp['FF'] * 0.8) + 
            (df_agrp['FS'] * 0.5) + (df_agrp['PS'] * 1.0) + (df_agrp['DP'] * 7.0) + 
            (df_agrp['DE'] * 1.0) + (df_agrp['DS'] * 1.2)
        )
        return df_agrp

    df_agrupado = agrupar_dados(df_analise_geral)
    df_robo_base = agrupar_dados(df_periodo) # Base completa para o robô

    # ==========================================
    # --- INTERFACE ---
    # ==========================================
    if df_agrupado.empty:
        st.warning("⚠️ Nenhum jogador encontrado com os filtros atuais.")
    else:
        # KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Maior Pontuador (Soma)", f"{df_agrupado['pontuacao_total_periodo'].max():.1f}")
        k2.metric("Média Geral (Por Jogo)", f"{df_analise_geral['atletas.pontos_num'].mean():.2f}")
        k3.metric("Pontuação Básica (Acumulada)", f"{df_agrupado['media_basica_atual'].mean():.2f}")
        k4.metric("Jogadores", f"{len(df_agrupado)}")

        st.markdown("---")

        tab_robo, tab_comparador, tab_capitao, tab_destaques, tab_adversario, tab_times, tab_scouts, tab_valorizacao, tab_tabela = st.tabs([
            "🤖 Robô Escalador",
            "⚔️ Comparador",
            "© Capitão",
            "🏆 Destaques", 
            "🛡️ Raio-X Adversário",
            "📊 Times", 
            "🏠 Casa vs Fora", 
            "💎 Valorização", 
            "📋 Tabela"
        ])

        # --- ABA 0: ROBÔ ESCALADOR (ALGORITMO OTIMIZADO) ---
        with tab_robo:
            st.header("🤖 Otimizador de Escalação")
            
            c_input1, c_input2, c_input3 = st.columns(3)
            patrimonio = c_input1.number_input("💰 Orçamento Total (C$)", value=100.0, step=1.0)
            esquema_tatico = c_input2.selectbox("📋 Esquema Tático", ["4-3-3", "3-4-3", "3-5-2", "4-4-2", "5-3-2"])
            criterio_robo = c_input3.selectbox("🎯 Critério Principal", ["Média Básica (Segurança)", "Pontuação Total (Explosão)"])
            
            esquemas = {
                "4-3-3": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 3, 'Atacante': 3, 'Técnico': 0},
                "3-4-3": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 3, 'Técnico': 0},
                "3-5-2": {'Goleiro': 1, 'Lateral': 0, 'Zagueiro': 3, 'Meia': 5, 'Atacante': 2, 'Técnico': 0},
                "4-4-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 2, 'Meia': 4, 'Atacante': 2, 'Técnico': 0},
                "5-3-2": {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 3, 'Atacante': 2, 'Técnico': 0},
            }

            if st.button("🚀 Escalar Time Ideal"):
                col_sort = 'media_basica_atual' if criterio_robo == "Média Básica (Segurança)" else 'pontuacao_total_periodo'
                
                # 1. Seleção Inicial (Time dos Sonhos)
                candidatos = df_robo_base.sort_values(col_sort, ascending=False)
                time_atual = []
                
                # Preenche vagas
                requirements = esquemas[esquema_tatico]
                for pos, qtd in requirements.items():
                    if qtd > 0:
                        jogadores_pos = candidatos[candidatos['posicao_nome'] == pos].head(qtd)
                        time_atual.append(jogadores_pos)
                
                if time_atual:
                    df_time = pd.concat(time_atual)
                    custo_atual = df_time['atletas.preco_num'].sum()
                    
                    # 2. Otimização de Orçamento (Trocas Inteligentes)
                    # Enquanto estourar o orçamento, troca o jogador que tem o pior custo-benefício de troca
                    
                    iteracoes = 0
                    while custo_atual > patrimonio and iteracoes < 50:
                        # Identificar quem sair (o mais caro do time atual)
                        # Estratégia: Encontrar a troca que economiza $ mas perde menos Pontos
                        melhor_troca = None
                        menor_perda_ratio = float('inf')
                        
                        for idx, row_sair in df_time.iterrows():
                            pos = row_sair['posicao_nome']
                            preco_sair = row_sair['atletas.preco_num']
                            pontos_sair = row_sair[col_sort]
                            
                            # Candidatos a entrar (mesma posição, mais barato, não está no time)
                            opcoes = candidatos[
                                (candidatos['posicao_nome'] == pos) & 
                                (candidatos['atletas.preco_num'] < preco_sair) &
                                (~candidatos['atletas.atleta_id'].isin(df_time['atletas.atleta_id']))
                            ]
                            
                            if not opcoes.empty:
                                # Pega a melhor opção disponível (a maior pontuação abaixo do preço)
                                row_entrar = opcoes.iloc[0] 
                                preco_entrar = row_entrar['atletas.preco_num']
                                pontos_entrar = row_entrar[col_sort]
                                
                                economia = preco_sair - preco_entrar
                                perda_pontos = pontos_sair - pontos_entrar
                                
                                # Ratio: Pontos perdidos por C$ economizado (quanto menor, melhor)
                                if economia > 0:
                                    ratio = perda_pontos / economia
                                    if ratio < menor_perda_ratio:
                                        menor_perda_ratio = ratio
                                        melhor_troca = (idx, row_entrar)
                        
                        if melhor_troca:
                            idx_sair, row_entrar = melhor_troca
                            # Remove o antigo
                            df_time = df_time.drop(idx_sair)
                            # Adiciona o novo (como DataFrame de 1 linha)
                            df_time = pd.concat([df_time, row_entrar.to_frame().T])
                            custo_atual = df_time['atletas.preco_num'].sum()
                        else:
                            break # Não há mais trocas possíveis
                        iteracoes += 1
                        
                    # Exibição do Time Final
                    st.success(f"✅ Time Escalado! Custo Total: C$ {custo_atual:.2f}")
                    
                    # Ordenar por Posição para exibição bonita
                    ordem_pos = {'Goleiro': 1, 'Lateral': 2, 'Zagueiro': 3, 'Meia': 4, 'Atacante': 5, 'Técnico': 6}
                    df_time['ordem'] = df_time['posicao_nome'].map(ordem_pos)
                    df_time = df_time.sort_values('ordem')
                    
                    # Cards dos Jogadores
                    cols = st.columns(5)
                    idx_col = 0
                    for _, row in df_time.iterrows():
                        foto = formatar_foto(row.get('atletas.foto', ''))
                        with cols[idx_col % 5]:
                            st.image(foto, width=100)
                            st.markdown(f"**{row['posicao_nome']}**")
                            st.caption(f"{row['atletas.apelido']}")
                            st.write(f"C$ {row['atletas.preco_num']:.1f}")
                            st.metric(label=criterio_robo.split()[0], value=f"{row[col_sort]:.1f}")
                            st.divider()
                        idx_col += 1
                else:
                    st.warning("Não há jogadores suficientes para formar o time.")

        # --- ABA 1: COMPARADOR (NOVA) ---
        with tab_comparador:
            st.header("⚔️ Comparador Mano a Mano")
            
            c_sel1, c_sel2 = st.columns(2)
            nomes_jogadores = df_robo_base['atletas.apelido'].sort_values().unique()
            
            p1_nome = c_sel1.selectbox("Jogador 1", nomes_jogadores, index=0)
            p2_nome = c_sel2.selectbox("Jogador 2", nomes_jogadores, index=1)
            
            if p1_nome and p2_nome:
                p1 = df_robo_base[df_robo_base['atletas.apelido'] == p1_nome].iloc[0]
                p2 = df_robo_base[df_robo_base['atletas.apelido'] == p2_nome].iloc[0]
                
                # Dados para o Radar
                categorias = ['Pontos Totais', 'Média Básica', 'Gols', 'Assistências', 'Finalizações', 'Desarmes']
                valores_p1 = [p1['pontuacao_total_periodo'], p1['media_basica_atual'], p1['G'], p1['A'], p1['finalizacoes_total'], p1['DS']]
                valores_p2 = [p2['pontuacao_total_periodo'], p2['media_basica_atual'], p2['G'], p2['A'], p2['finalizacoes_total'], p2['DS']]
                
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(r=valores_p1, theta=categorias, fill='toself', name=p1_nome))
                fig.add_trace(go.Scatterpolar(r=valores_p2, theta=categorias, fill='toself', name=p2_nome))
                
                fig.update_layout(polar=dict(radialaxis=dict(visible=True)), showlegend=True, title="Comparativo de Atributos")
                st.plotly_chart(fig, use_container_width=True)

        # --- ABA 2: CAPITÃO (NOVA) ---
        with tab_capitao:
            st.header("© Capitão de Segurança")
            st.info("Score calculado cruzando: Desempenho do Jogador em Casa vs Fragilidade do Adversário na Posição.")
            
            if 'Adversario' in df_analise_geral.columns:
                # 1. Calcula Fragilidade dos Adversários (Pontos cedidos por posição)
                df_heat = df_analise_geral[df_analise_geral['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                df_heat.rename(columns={'atletas.pontos_num': 'fragilidade_adversario'}, inplace=True)
                
                # 2. Prepara base de jogadores
                # Considera apenas quem joga EM CASA nesta visualização (para 'Segurança')
                jogadores_casa = df_analise_geral[df_analise_geral['Mando_Padrao'] == 'CASA'].copy()
                
                if not jogadores_casa.empty:
                    # Merge para trazer a fragilidade do adversário
                    df_capitao = pd.merge(
                        jogadores_casa, 
                        df_heat, 
                        left_on=['Adversario', 'posicao_nome'], 
                        right_on=['Adversario', 'posicao_nome'], 
                        how='left'
                    )
                    
                    # Cálculo do Score
                    # Score = (Média do Jogador + Pontos que Adv Cede) / 2
                    df_capitao['score_capitao'] = (df_capitao['atletas.pontos_num'] + df_capitao['fragilidade_adversario'].fillna(0)) / 2
                    
                    top_capitaes = df_capitao[['atletas.apelido', 'posicao_nome', 'Adversario', 'atletas.pontos_num', 'fragilidade_adversario', 'score_capitao']]
                    top_capitaes = top_capitaes.sort_values('score_capitao', ascending=False).head(20)
                    
                    st.dataframe(
                        top_capitaes.rename(columns={
                            'atletas.pontos_num': 'Média Jogador',
                            'fragilidade_adversario': 'Média Cedida (Adv)',
                            'score_capitao': 'Score Final'
                        }), 
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.warning("Não há dados suficientes de jogos em casa para calcular o Capitão de Segurança.")
            else:
                st.warning("Dados de Adversário indisponíveis.")

        # --- ABA 3: DESTAQUES (Mantida) ---
        with tab_destaques:
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

        # --- ABA 4: RAIO-X ADVERSÁRIO (Mantida) ---
        with tab_adversario:
            st.subheader("🔥 Raio-X: Quem cede mais pontos por posição?")
            if 'Adversario' in df_analise_geral.columns and not df_analise_geral['Adversario'].isin(['N/A']).all():
                df_heat = df_analise_geral[df_analise_geral['Adversario'] != 'N/A'].groupby(['Adversario', 'posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                def criar_heatmap_posicao(posicoes_alvo, titulo, cor_escala):
                    df_pos = df_heat[df_heat['posicao_nome'].isin(posicoes_alvo)]
                    if df_pos.empty: return None
                    pivot = df_pos.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                    pivot['Total'] = pivot.sum(axis=1)
                    pivot = pivot.sort_values('Total', ascending=True).drop(columns='Total')
                    fig = px.imshow(pivot, text_auto=".1f", aspect="auto", color_continuous_scale=cor_escala, title=titulo)
                    fig.update_layout(height=600, xaxis_title=None, yaxis_title=None)
                    return fig

                c_goleiro, c_defesa, c_meia, c_ataque = st.columns(4)
                with c_goleiro: 
                    f = criar_heatmap_posicao(['Goleiro'], "🥅 Goleiros", "Blues")
                    if f: st.plotly_chart(f, use_container_width=True)
                with c_defesa: 
                    f = criar_heatmap_posicao(['Zagueiro', 'Lateral'], "🛡️ Defensores", "Greens")
                    if f: st.plotly_chart(f, use_container_width=True)
                with c_meia: 
                    f = criar_heatmap_posicao(['Meia'], "🧠 Meias", "Oranges")
                    if f: st.plotly_chart(f, use_container_width=True)
                with c_ataque: 
                    f = criar_heatmap_posicao(['Atacante'], "⚽ Atacantes", "Reds")
                    if f: st.plotly_chart(f, use_container_width=True)
            else:
                st.warning("Dados de Adversário indisponíveis.")

        # --- ABA 5: TIMES (Mantida) ---
        with tab_times:
            club_stats = df_analise_geral.groupby('atletas.clube.id.full.name').agg({
                'atletas.pontos_num': 'mean', 'finalizacoes_total': 'mean'
            }).reset_index()
            c_t1, c_t2 = st.columns(2)
            with c_t1:
                fig_pts = px.bar(club_stats.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y='atletas.clube.id.full.name', orientation='h', title="Média de Pontos")
                st.plotly_chart(fig_pts, use_container_width=True)
            with c_t2:
                fig_fin = px.bar(club_stats.sort_values('finalizacoes_total'), x='finalizacoes_total', y='atletas.clube.id.full.name', orientation='h', title="Média Finalizações", color_discrete_sequence=['red'])
                st.plotly_chart(fig_fin, use_container_width=True)

        # --- ABA 6: CASA VS FORA (Mantida) ---
        with tab_scouts:
            if not df_analise_geral['Mando_Padrao'].isin(['N/A']).all():
                grupo_mando = df_analise_geral.groupby(['atletas.clube.id.full.name', 'Mando_Padrao'])[['scouts_ofensivos_total', 'scouts_defensivos_total']].mean().reset_index()
                c1, c2 = st.columns(2)
                with c1:
                    fig_of = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group', title="Média Scouts Ofensivos")
                    st.plotly_chart(fig_of, use_container_width=True)
                with c2:
                    fig_def = px.bar(grupo_mando, x='atletas.clube.id.full.name', y='scouts_defensivos_total', color='Mando_Padrao', barmode='group', title="Média Scouts Defensivos")
                    st.plotly_chart(fig_def, use_container_width=True)
            else:
                st.info("Filtre por CASA ou FORA.")

        # --- ABA 7: VALORIZAÇÃO (Mantida) ---
        with tab_valorizacao:
            st.subheader("Relação Preço x Entrega")
            plot_df = df_analise_geral.copy()
            fig_val = px.scatter(
                plot_df, 
                x='atletas.preco_num', 
                y='atletas.pontos_num',
                color='posicao_nome',
                size='tamanho_visual',
                hover_name='atletas.apelido',
                hover_data=['media_basica', 'atletas.clube.id.full.name'],
                title="Preço x Pontuação (Bolha = Média Básica)"
            )
            st.plotly_chart(fig_val, use_container_width=True)

        # --- ABA 8: TABELA COMPLETA (Mantida) ---
        with tab_tabela:
            st.subheader("Tabela Consolidada")
            cols_info = ['atletas.apelido', 'atletas.clube.id.full.name', 'posicao_nome', 'atletas.preco_num']
            cols_kpis = ['pontuacao_total_periodo', 'media_basica_atual']
            cols_view = cols_info + cols_kpis + todos_scouts
            
            df_display = df_agrupado[cols_view].sort_values('pontuacao_total_periodo', ascending=False)
            
            renomear = {
                'atletas.apelido': 'Apelido',
                'atletas.clube.id.full.name': 'Clube',
                'posicao_nome': 'Posição',
                'atletas.preco_num': 'Preço Atual (C$)',
                'pontuacao_total_periodo': 'Pontos Totais (Soma)',
                'media_basica_atual': 'Pontuação Básica (Acumulada)'
            }
            
            df_display = df_display.rename(columns=renomear)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
