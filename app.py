import streamlit as st
import pandas as pd
import glob
import plotly.express as px
import plotly.graph_objects as go

# --- Configurações Iniciais ---
st.set_page_config(page_title="Dashboard Cartola 2026", layout="wide", initial_sidebar_state="expanded")
st.title("⚽ Dashboard Analítico - Cartola FC 2026")

# --- Estilos CSS ---
st.markdown("""
<style>
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem; font-weight: 600;
    }
    .big-font { font-size: 1.5rem !important; font-weight: bold; color: #4CAF50; }
</style>
""", unsafe_allow_html=True)

# --- Funções Auxiliares ---
def formatar_foto(url):
    if pd.isna(url) or str(url) == 'nan':
        return "https://via.placeholder.com/220?text=Sem+Foto"
    return str(url).replace('FORMATO', '220x220')

# --- Funções de Carregamento ---
@st.cache_data
def load_data():
    # 1. Rodadas
    rodada_files = sorted(glob.glob("rodada-*.csv"))
    if not rodada_files: return pd.DataFrame(), pd.DataFrame()
    dfs = []
    for f in rodada_files:
        try:
            temp = pd.read_csv(f)
            temp.columns = temp.columns.str.strip()
            dfs.append(temp)
        except: pass
    df_main = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    if not df_main.empty: df_main = df_main.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])

    # 2. Confrontos
    confronto_files = glob.glob("confrontos_*.csv")
    df_jogos_list = []
    for f in confronto_files:
        try:
            temp_df = pd.read_csv(f)
            temp_df.columns = temp_df.columns.str.strip()
            if 'Mando' in temp_df.columns:
                temp_df['Mando_Padrao'] = temp_df['Mando'].apply(lambda x: 'CASA' if 'Casa' in str(x) and 'Fora' not in str(x) else 'FORA')
            else: temp_df['Mando_Padrao'] = 'N/A'
            df_jogos_list.append(temp_df)
        except: pass
    df_jogos = pd.concat(df_jogos_list, ignore_index=True) if df_jogos_list else pd.DataFrame()
    if not df_jogos.empty: df_jogos = df_jogos.drop_duplicates(subset=['rodada_id', 'clube_id'])
    
    return df_main, df_jogos

df, df_jogos = load_data()

# --- Processamento ---
if df.empty:
    st.error("⚠️ Nenhum dado encontrado.")
else:
    # Identificação Dinâmica da Coluna de Clube (Correção do KeyError)
    possiveis_nomes_clube = ['atletas.clube.id.full.name', 'Clube', 'clube_nome', 'atletas.clube_id_full_name', 'club_name']
    col_clube = next((c for c in possiveis_nomes_clube if c in df.columns), None)
    
    if not col_clube:
        # Se não achar, cria uma genérica baseada no ID
        df['Nome_Clube_Gen'] = "Clube " + df['atletas.clube_id'].astype(str)
        col_clube = 'Nome_Clube_Gen'

    # Tipagem
    df['atletas.rodada_id'] = pd.to_numeric(df['atletas.rodada_id'], errors='coerce').fillna(0).astype(int)
    df['atletas.clube_id'] = pd.to_numeric(df['atletas.clube_id'], errors='coerce').fillna(0).astype(int)
    
    if not df_jogos.empty:
        df_jogos['rodada_id'] = pd.to_numeric(df_jogos['rodada_id'], errors='coerce').fillna(0).astype(int)
        df_jogos['clube_id'] = pd.to_numeric(df_jogos['clube_id'], errors='coerce').fillna(0).astype(int)
        cols_jogo = ['rodada_id', 'clube_id']
        for c in ['Mando_Padrao', 'Adversario', 'Estadio', 'Data', 'Hora']:
            if c in df_jogos.columns: cols_jogo.append(c)
        df = pd.merge(df, df_jogos[cols_jogo], left_on=['atletas.rodada_id', 'atletas.clube_id'], right_on=['rodada_id', 'clube_id'], how='left')
    
    for c in ['Mando_Padrao', 'Adversario']:
        if c not in df.columns: df[c] = 'N/A'
        df[c] = df[c].fillna('N/A')

    df = df.drop_duplicates(subset=['atletas.atleta_id', 'atletas.rodada_id'])
    pos_map = {1: 'Goleiro', 2: 'Lateral', 3: 'Zagueiro', 4: 'Meia', 5: 'Atacante', 6: 'Técnico'}
    df['posicao_nome'] = df['atletas.posicao_id'].map(pos_map)

    todos_scouts = ['G', 'A', 'FT', 'FD', 'FF', 'FS', 'PS', 'I', 'PP', 'DS', 'SG', 'DE', 'DP', 'GS', 'FC', 'PC', 'CA', 'CV', 'GC']
    for col in todos_scouts:
        if col not in df.columns: df[col] = 0
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Auxiliares
    df['tamanho_visual'] = df['atletas.pontos_num'].apply(lambda x: max(1.0, x))
    df['scouts_ofensivos_total'] = df['G'] + df['A'] + df['FD'] + df['FF'] + df['FT'] + df['FS']
    df['scouts_defensivos_total'] = df['DS'] + df['DE'] + df['SG']
    df['finalizacoes_total'] = df['FD'] + df['FF'] + df['FT']

    # ==========================================
    # --- SIDEBAR ---
    # ==========================================
    st.sidebar.header("🔍 Filtros Globais")
    min_rodada, max_rodada = int(df['atletas.rodada_id'].min()), int(df['atletas.rodada_id'].max())
    sel_rodada_range = st.sidebar.slider("Rodadas", min_rodada, max_rodada, (min_rodada, max_rodada))
    
    min_preco, max_preco = float(df['atletas.preco_num'].min()), float(df['atletas.preco_num'].max())
    sel_preco_range = st.sidebar.slider("Preço (C$)", min_preco, max_preco, (min_preco, max_preco))
    st.sidebar.markdown("---")
    
    all_clubes = sorted(df[col_clube].dropna().unique())
    sel_clube = st.sidebar.multiselect("Clube", all_clubes, default=all_clubes)
    sel_posicao = st.sidebar.multiselect("Posição", sorted(df['posicao_nome'].dropna().unique()), default=sorted(df['posicao_nome'].dropna().unique()))
    sel_mando = st.sidebar.multiselect("Mando", ['CASA', 'FORA'], default=['CASA', 'FORA'])
    
    # --- FILTRAGEM ---
    df_filtrado_base = df[(df['atletas.rodada_id'] >= sel_rodada_range[0]) & (df['atletas.rodada_id'] <= sel_rodada_range[1])]
    if sel_clube: df_filtrado_base = df_filtrado_base[df_filtrado_base[col_clube].isin(sel_clube)]
    if sel_posicao: df_filtrado_base = df_filtrado_base[df_filtrado_base['posicao_nome'].isin(sel_posicao)]
    if sel_mando: df_filtrado_base = df_filtrado_base[df_filtrado_base['Mando_Padrao'].isin(sel_mando)]
    
    df_filtrado_completo = df_filtrado_base[(df_filtrado_base['atletas.preco_num'] >= sel_preco_range[0]) & (df_filtrado_base['atletas.preco_num'] <= sel_preco_range[1])]

    # --- AGRUPAMENTO ---
    def agrupar_dados(dataframe_input):
        if dataframe_input.empty: return pd.DataFrame()
        df_sorted = dataframe_input.sort_values('atletas.rodada_id', ascending=True)
        agg_dict = {
            'atletas.pontos_num': 'sum',
            'atletas.preco_num': 'last', 'atletas.apelido': 'last',
            col_clube: 'last', 'atletas.clube_id': 'last',
            'posicao_nome': 'last', 'atletas.foto': 'last',
            'finalizacoes_total': 'last', 'atletas.jogos_num': 'last'
        }
        for s in todos_scouts: agg_dict[s] = 'last'
        df_grouped = df_sorted.groupby('atletas.atleta_id').agg(agg_dict).reset_index()
        df_grouped.rename(columns={'atletas.pontos_num': 'pontuacao_total_periodo'}, inplace=True)
        
        # CÁLCULO PONTUAÇÃO BÁSICA (RESTAURADO)
        df_grouped['pontuacao_basica_atual'] = (
            (df_grouped['DS'] * 1.2) + (df_grouped['DE'] * 1.0) + (df_grouped['SG'] * 5.0) + 
            (df_grouped['FS'] * 0.5) + (df_grouped['FD'] * 1.2) + (df_grouped['FT'] * 3.0) + 
            (df_grouped['FF'] * 0.8) + (df_grouped['PS'] * 1.0) + (df_grouped['DP'] * 7.0)
        )
        return df_grouped

    df_agrupado_geral = agrupar_dados(df_filtrado_completo)
    df_pool_total = agrupar_dados(df_filtrado_base)

    # ==========================================
    # --- DASHBOARD ---
    # ==========================================
    if df_agrupado_geral.empty and df_pool_total.empty:
        st.warning("⚠️ Nenhum jogador encontrado.")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["📅 Central de Jogos", "🤖 Inteligência", "📊 Tática", "📈 Mercado"])

        # ---------------------------------------------------------
        # ABA 1: CENTRAL DE JOGOS
        # ---------------------------------------------------------
        with tab1:
            if not df_jogos.empty:
                col_sel, col_kpi = st.columns([1, 3])
                with col_sel:
                    rodadas_disp = sorted(df_jogos['rodada_id'].unique())
                    rodada_selecionada = st.selectbox("Selecione a Rodada:", rodadas_disp)
                
                jogos_r = df_jogos[df_jogos['rodada_id'] == rodada_selecionada]
                stats_clubes = df.groupby([col_clube, 'Mando_Padrao'])['atletas.pontos_num'].mean().reset_index()
                
                jogos_unicos = jogos_r[jogos_r['Mando_Padrao'] == 'CASA'].copy()
                
                if not jogos_unicos.empty:
                    tabela = []
                    # Mapeamento ID -> Nome seguro
                    mapa_nomes = df[['atletas.clube_id', col_clube]].drop_duplicates().set_index('atletas.clube_id')[col_clube].to_dict()

                    for _, jogo in jogos_unicos.iterrows():
                        mandante = mapa_nomes.get(jogo['clube_id'], f"ID {jogo['clube_id']}")
                        visitante = jogo['Adversario']
                        
                        m_stat = stats_clubes[(stats_clubes[col_clube] == mandante) & (stats_clubes['Mando_Padrao'] == 'CASA')]['atletas.pontos_num'].mean()
                        v_stat = stats_clubes[(stats_clubes[col_clube].astype(str).str.contains(visitante, case=False, na=False)) & (stats_clubes['Mando_Padrao'] == 'FORA')]['atletas.pontos_num'].mean()
                        
                        m_val = m_stat if pd.notna(m_stat) else 0
                        v_val = v_stat if pd.notna(v_stat) else 0
                        
                        delta = m_val - v_val
                        fav_bar = "⚪ Equilibrado"
                        if delta > 10: fav_bar = "🟢 Mandante Forte"
                        elif delta < -10: fav_bar = "🔴 Visitante Forte"
                        elif delta > 0: fav_bar = "🟢 Leve Mandante"
                        elif delta < 0: fav_bar = "🔴 Leve Visitante"

                        tabela.append({
                            "Data/Hora": f"{jogo.get('Data','')} {jogo.get('Hora','')}",
                            "Mandante": mandante,
                            "Força Casa": m_val,
                            "Visitante": visitante,
                            "Força Fora": v_val,
                            "Favoritismo": fav_bar,
                            "Local": jogo.get('Estadio', '')
                        })
                    
                    df_view_jogos = pd.DataFrame(tabela)
                    
                    # KPIs
                    if not df_view_jogos.empty:
                        best_home = df_view_jogos.loc[df_view_jogos['Força Casa'].idxmax()]
                        worst_away = df_view_jogos.loc[df_view_jogos['Força Fora'].idxmin()]
                        
                        k1, k2, k3 = st.columns(3)
                        k1.metric("🏰 Melhor Mandante", best_home['Mandante'], f"{best_home['Força Casa']:.1f} pts")
                        k2.metric("🚌 Visitante + Fraco", worst_away['Visitante'], f"{worst_away['Força Fora']:.1f} pts")
                        k3.metric("🔥 Jogo + Promissor", f"{best_home['Mandante']} x {best_home['Visitante']}")
                    
                    st.dataframe(
                        df_view_jogos,
                        column_config={
                            "Força Casa": st.column_config.ProgressColumn("Média Casa", format="%.1f", min_value=0, max_value=80),
                            "Força Fora": st.column_config.ProgressColumn("Média Fora", format="%.1f", min_value=0, max_value=80),
                        },
                        use_container_width=True, hide_index=True
                    )
            else: st.warning("Confrontos não carregados.")

        # ---------------------------------------------------------
        # ABA 2: INTELIGÊNCIA
        # ---------------------------------------------------------
        with tab2:
            st1, st2, st3 = st.tabs(["🤖 Robô", "⚔️ Comparador", "© Capitão"])
            
            with st1:
                c1, c2 = st.columns(2)
                orc = c1.number_input("Orçamento", value=100.0)
                esq = c2.selectbox("Esquema", ["4-3-3","3-4-3","3-5-2","4-4-2","5-3-2"])
                if st.button("Escalar"):
                    esqs = {"4-3-3": {'Goleiro':1,'Lateral':2,'Zagueiro':2,'Meia':3,'Atacante':3,'Técnico':0}, "3-4-3": {'Goleiro':1,'Lateral':0,'Zagueiro':3,'Meia':4,'Atacante':3,'Técnico':0}, "3-5-2": {'Goleiro':1,'Lateral':0,'Zagueiro':3,'Meia':5,'Atacante':2,'Técnico':0}, "4-4-2": {'Goleiro':1,'Lateral':2,'Zagueiro':2,'Meia':4,'Atacante':2,'Técnico':0}, "5-3-2": {'Goleiro':1,'Lateral':2,'Zagueiro':3,'Meia':3,'Atacante':2,'Técnico':0}}
                    pool = df_pool_total.sort_values('pontuacao_total_periodo', ascending=False)
                    time, custo = [], 0
                    for p, q in esqs[esq].items(): 
                        if q>0: time.append(pool[pool['posicao_nome']==p].head(q))
                    if time:
                        df_t = pd.concat(time)
                        custo = df_t['atletas.preco_num'].sum()
                        loop = 0
                        while custo > orc and loop < 100:
                            mt, mr = None, float('inf')
                            for i, s in df_t.iterrows():
                                cs = pool[(pool['posicao_nome']==s['posicao_nome'])&(pool['atletas.preco_num']<s['atletas.preco_num'])&(~pool['atletas.atleta_id'].isin(df_t['atletas.atleta_id']))]
                                if not cs.empty:
                                    e = cs.iloc[0]
                                    eco = s['atletas.preco_num'] - e['atletas.preco_num']
                                    if eco > 0:
                                        r = (s['pontuacao_total_periodo'] - e['pontuacao_total_periodo']) / eco
                                        if r < mr: mr, mt = r, (i, e)
                            if mt:
                                df_t = df_t.drop(mt[0])
                                df_t = pd.concat([df_t, mt[1].to_frame().T])
                                custo = df_t['atletas.preco_num'].sum()
                            else: break
                            loop += 1
                        st.success(f"Time Escalado! C$: {custo:.2f}")
                        st.dataframe(df_t[['posicao_nome','atletas.apelido','atletas.preco_num','pontuacao_total_periodo']].sort_values('posicao_nome'), use_container_width=True)
            
            with st2:
                c1, c2 = st.columns(2)
                b1, b2 = c1.text_input("Busca Jogador 1", "").strip().lower(), c2.text_input("Busca Jogador 2", "").strip().lower()
                ns = sorted(df_pool_total['atletas.apelido'].unique())
                l1, l2 = [n for n in ns if b1 in n.lower()] if b1 else ns, [n for n in ns if b2 in n.lower()] if b2 else ns
                p1, p2 = c1.selectbox("J1", l1, key='s1'), c2.selectbox("J2", l2, key='s2')
                if p1 and p2:
                    d1, d2 = df_pool_total[df_pool_total['atletas.apelido']==p1].iloc[0], df_pool_total[df_pool_total['atletas.apelido']==p2].iloc[0]
                    fig = go.Figure()
                    cats = ['Pontos','Gols','Assist','Fin','Desarmes']
                    v1 = [d1['pontuacao_total_periodo'],d1['G'],d1['A'],d1['finalizacoes_total'],d1['DS']]
                    v2 = [d2['pontuacao_total_periodo'],d2['G'],d2['A'],d2['finalizacoes_total'],d2['DS']]
                    fig.add_trace(go.Scatterpolar(r=v1, theta=cats, fill='toself', name=p1)); fig.add_trace(go.Scatterpolar(r=v2, theta=cats, fill='toself', name=p2))
                    st.plotly_chart(fig, use_container_width=True)

            with st3:
                if not df_jogos.empty:
                    rod = st.selectbox("Rodada Capitão:", sorted(df_jogos['rodada_id'].unique()))
                    jogos = df_jogos[df_jogos['rodada_id']==rod][['clube_id','Adversario']]
                    if not df_pool_total.empty:
                        base = pd.merge(df_pool_total, jogos, left_on='atletas.clube_id', right_on='clube_id', how='inner')
                        if not base.empty:
                            heat = df_filtrado_completo[df_filtrado_completo['Adversario']!='N/A'].groupby(['Adversario','posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                            final = pd.merge(base, heat, on=['Adversario','posicao_nome'], how='left')
                            final['Fragilidade'] = final['atletas.pontos_num'].fillna(0)
                            final['Score'] = final['pontuacao_total_periodo'] + (final['Fragilidade']*2)
                            st.dataframe(final[['atletas.apelido','posicao_nome','Adversario','pontuacao_total_periodo','Fragilidade','Score']].sort_values('Score', ascending=False), use_container_width=True)

        # ---------------------------------------------------------
        # ABA 3: TÁTICA
        # ---------------------------------------------------------
        with tab3:
            st1, st2, st3 = st.tabs(["🔥 Raio-X", "🛡️ Times", "🏠 Casa/Fora"])
            with st1:
                if 'Adversario' in df_filtrado_completo.columns:
                    h = df_filtrado_completo[df_filtrado_completo['Adversario']!='N/A'].groupby(['Adversario','posicao_nome'])['atletas.pontos_num'].mean().reset_index()
                    if not h.empty:
                        p = h.pivot(index='Adversario', columns='posicao_nome', values='atletas.pontos_num').fillna(0)
                        p['T'] = p.sum(axis=1); p = p.sort_values('T').drop(columns='T')
                        st.plotly_chart(px.imshow(p, text_auto=".1f", color_continuous_scale="Reds"), use_container_width=True)
            with st2:
                g = df_filtrado_completo.groupby(col_clube)[['atletas.pontos_num','finalizacoes_total']].mean().reset_index()
                st.plotly_chart(px.bar(g.sort_values('atletas.pontos_num'), x='atletas.pontos_num', y=col_clube, orientation='h', title="Média Pts"), use_container_width=True)
            with st3:
                if 'Mando_Padrao' in df_filtrado_completo.columns:
                    g = df_filtrado_completo.groupby([col_clube,'Mando_Padrao'])['scouts_ofensivos_total'].mean().reset_index()
                    st.plotly_chart(px.bar(g, x=col_clube, y='scouts_ofensivos_total', color='Mando_Padrao', barmode='group'), use_container_width=True)

        # ---------------------------------------------------------
        # ABA 4: MERCADO & DADOS
        # ---------------------------------------------------------
        with tab4:
            st1, st2, st3 = st.tabs(["📋 Tabela", "💎 Valorização", "🏆 Destaques"])
            with st1:
                b = st.text_input("Buscar Tabela", "").strip().lower()
                show = df_agrupado_geral
                if b: show = show[show['atletas.apelido'].str.lower().str.contains(b)]
                # COLUNAS INCLUINDO PONTUAÇÃO BÁSICA
                cols = ['atletas.apelido', col_clube, 'posicao_nome', 'atletas.preco_num', 'pontuacao_total_periodo', 'pontuacao_basica_atual'] + todos_scouts
                st.dataframe(show[cols].sort_values('pontuacao_total_periodo', ascending=False), use_container_width=True, hide_index=True)
            with st2:
                st.plotly_chart(px.scatter(df_filtrado_completo, x='atletas.preco_num', y='atletas.pontos_num', color='posicao_nome', hover_name='atletas.apelido'), use_container_width=True)
            with st3:
                def rd(l, c, ct):
                    if df_agrupado_geral.empty or c not in df_agrupado_geral or df_agrupado_geral[c].sum()==0: return
                    r = df_agrupado_geral.loc[df_agrupado_geral[c].idxmax()]
                    with ct:
                        st.markdown(f"**{l}**")
                        c1,c2 = st.columns([1,2])
                        c1.image(formatar_foto(r.get('atletas.foto','')), width=60)
                        c2.caption(r['atletas.apelido'])
                        st.metric("Total", int(r[c]))
                        st.divider()
                c1,c2,c3,c4 = st.columns(4)
                rd("Gols",'G',c1); rd("Assist",'A',c2); rd("Desarmes",'DS',c3); rd("SG",'SG',c4)
