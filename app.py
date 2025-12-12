
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="機構個案額度使用率分析", layout="wide")

# --- Constants & Config ---
REQUIRED_COLUMNS = [
    '月份', '機構', '主責人員', '個案', 
    '照管金額分配額度', '服務紀錄(不含自費)', 
    '服務項目', '政府服務項目單價', '服務紀錄組數', '服務紀錄使用額度',
    '服務使用狀態', # Added per request.
    '主單A單位',  # Added for A Unit Analysis
    '給付額度',   # Added for Gap Analysis
    'CMS',       # Added for Gap Analysis
    '區域'        # Added for Region Analysis
]

import io
import json
import urllib.request

# --- Helper Functions ---
def clean_currency_column(series):
    """Removes commas and converts to float."""
    return pd.to_numeric(series.astype(str).str.replace(',', ''), errors='coerce').fillna(0)

@st.cache_data
def convert_df_to_excel(df):
    """Converts DataFrame to Excel bytes."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

@st.cache_data
def load_data(file):
    """Loads and cleans the data from Excel."""
    try:
        df = pd.read_excel(file)
        
        # Soft check for '服務使用狀態'
        if '服務使用狀態' not in df.columns:
            df['服務使用狀態'] = '未知'

        # Soft check for '主單A單位'
        if '主單A單位' not in df.columns:
             df['主單A單位'] = '未知A單位'
             
        # Soft check for '給付額度' and 'CMS'
        if '給付額度' not in df.columns:
            df['給付額度'] = 0 
        if 'CMS' not in df.columns:
            df['CMS'] = '未知'
            
        # Soft check for '區域'
        if '區域' not in df.columns:
            df['區域'] = '未知區域'

        # Clean numeric columns
        df['照管金額分配額度'] = clean_currency_column(df['照管金額分配額度'])
        df['服務紀錄(不含自費)'] = clean_currency_column(df['服務紀錄(不含自費)'])
        df['政府服務項目單價'] = clean_currency_column(df['政府服務項目單價'])
        df['服務紀錄使用額度'] = clean_currency_column(df['服務紀錄使用額度']) 
        df['給付額度'] = clean_currency_column(df['給付額度'])
        
        return df
    except Exception as e:
        st.error(f"Error loading file: {e}")
        return None

def get_monthly_aggregated_data(df):
    """
    Aggregates data to the Case-Month level.
    """
    if '服務使用狀態' not in df.columns: df['服務使用狀態'] = '未知'
    if '區域' not in df.columns: df['區域'] = '未知'
    if 'CMS' not in df.columns: df['CMS'] = '未知'

    grouped = df.groupby(['月份', '機構', '主責人員', '個案', '主單A單位']).agg({
        '照管金額分配額度': 'max',
        '服務紀錄(不含自費)': 'max',
        '給付額度': 'max', 
        'CMS': 'first',   
        '服務使用狀態': 'first',
        '區域': 'first'
    }).reset_index()
    
    return grouped



# --- Main App ---
def main():
    st.title("🏡機構個案額度使用率分析 App")

    # --- Sidebar ---
    st.sidebar.header("設定")
    uploaded_file = st.sidebar.file_uploader("上傳 Excel 檔案", type=['xlsx', 'xls'])
    
    if uploaded_file is None:
        st.info("請先上傳資料檔案以開始分析。")
        return

    # Load Data
    raw_df = load_data(uploaded_file)
    if raw_df is None:
        return

    # Create Aggregated DF for High-level analysis
    agg_df = get_monthly_aggregated_data(raw_df)

    # Navigation
    # Re-enabled "區域與狀態分析"
    page = st.sidebar.radio(
        "選擇頁面",
        ["機構總覽", "區域與狀態分析", "服務狀態統計", "主單 A 單位關聯分析", "督導/人員績效", "服務項目分析", "異常個案警示", "個案詳細分析"]
    )
    
    st.sidebar.markdown("---")
    
    # Global Theme Selector
    theme_options = {
        "🌿 清新淡雅 (預設)": ("GnBu", "Blues"), 
        "☀️ 溫暖活力": ("OrRd", "YlOrRd"),
        "🤵 專業深色": ("viridis", "magma"),
        "🌊 海洋藍調": ("YlGnBu", "PuBu"),
        "🔮 神秘紫調": ("Purples", "RdPu")
    }
    
    if 'theme_primary' not in st.session_state:
        st.session_state.theme_primary = "GnBu"
    if 'theme_secondary' not in st.session_state:
        st.session_state.theme_secondary = "Blues"
        
    selected_theme_name = st.sidebar.selectbox("🎨 選擇圖表風格", list(theme_options.keys()), index=0)
    st.session_state.theme_primary, st.session_state.theme_secondary = theme_options[selected_theme_name]

    if page == "機構總覽":
        page_agency_overview(agg_df)
    elif page == "區域與狀態分析":
        page_region_analysis(agg_df)
    elif page == "服務狀態統計":
        page_status_stats(agg_df)
    elif page == "主單 A 單位關聯分析":
        page_a_unit_analysis(agg_df)
    elif page == "督導/人員績效":
        page_supervisor_performance(agg_df)
    elif page == "服務項目分析":
        page_service_analysis(raw_df)
    elif page == "異常個案警示":
        page_abnormal_alerts(agg_df)
    elif page == "個案詳細分析":
        page_case_detail(raw_df, agg_df)


# --- Pages ---

def page_status_stats(agg_df):
    st.header("📋 機構服務狀態統計")
    
    # Filter Agency (Optional)
    agencies = agg_df['機構'].unique()
    selected_agency = st.selectbox("選擇機構 (全選則不填)", ["全部"] + list(agencies), key='status_agency')
    
    df_to_use = agg_df.copy()
    if selected_agency != "全部":
        df_to_use = df_to_use[df_to_use['機構'] == selected_agency]

    # Simplify Status Logic
    def simplify_status(s):
        s = str(s)
        if s.startswith('服務中'):
            return '服務中'
        elif s.startswith('暫停'):
            return '暫停'
        elif s.startswith('結案'):
            return '結案'
        else:
            return s # Or '其他' if strict

    df_to_use['服務使用狀態'] = df_to_use['服務使用狀態'].apply(simplify_status)

    # Aggregate: Group by Month, Agency, Status -> Count Cases
    status_counts = df_to_use.groupby(['月份', '機構', '服務使用狀態']).agg({
        '個案': 'count'
    }).rename(columns={'個案': '人數'}).reset_index()
    
    # Aggregate for Chart: If "All", group by [Month, Status] only to get clean total bars
    if selected_agency == "全部":
        chart_data = df_to_use.groupby(['月份', '服務使用狀態']).agg({'個案': 'count'}).rename(columns={'個案': '人數'}).reset_index()
    else:
        chart_data = status_counts # Already grouped by [Month, Agency, Status]

    # Visualization: Stacked Bar Chart
    # X=Month, Y=Count, Color=Status
    title_str = f"{selected_agency} - 每月服務狀態人數統計" if selected_agency != "全部" else "全機構 - 每月服務狀態人數統計"
    
    fig = px.bar(
        chart_data, 
        x='月份', 
        y='人數', 
        color='服務使用狀態', 
        text='人數',
        title=title_str,
        barmode='stack' # Force stacked for cleaner look
    )
    fig.update_xaxes(type='category')
    fig.update_traces(textangle=0, textposition='inside', width=0.15) # Force horizontal text inside bars, make bars thinner
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', bargap=0.2) # Hide too small text
    st.plotly_chart(fig, use_container_width=True)
    
    # --- Growth Momentum (New) ---
    st.subheader("📈 機構成長動能分析 (淨成長)")
    # Calculate Active Count Trend
    # Filter only '服務中'
    active_df = df_to_use[df_to_use['服務使用狀態'] == '服務中']
    
    # Define months for reindexing to ensure continuity
    months = sorted(agg_df['月份'].unique())
    
    if not active_df.empty:
        active_trend = active_df.groupby(['月份']).agg({'個案': 'count'}).rename(columns={'個案': '服務中人數'}).reindex(months, fill_value=0).reset_index()
        # Calculate Delta
        active_trend['淨成長'] = active_trend['服務中人數'].diff().fillna(0)
        
        fig_growth = px.bar(
            active_trend, 
            x='月份', 
            y='淨成長', 
            text='淨成長',
            title=f"{selected_agency} - 每月個案淨成長數",
            color='淨成長',
            color_continuous_scale=['red', 'gray', 'green'] # Red for negative, Green for positive
        )
        fig_growth.update_xaxes(type='category')
        fig_growth.update_traces(width=0.2) # Make bars narrower
        st.plotly_chart(fig_growth, use_container_width=True)
    else:
        st.info("尚無服務中個案數據可計算成長動能。")

    # Pivot Table for clearer view
    pivot_table = status_counts.pivot_table(
        index=['月份', '機構'], 
        columns='服務使用狀態', 
        values='人數', 
        fill_value=0,
        aggfunc='sum' # Should be sum of counts
    ).astype(int)
    
    st.subheader("詳細數據表")
    st.dataframe(pivot_table)
    
    # Export
    excel_data = convert_df_to_excel(pivot_table.reset_index())
    st.download_button(
        label="📥 下載狀態統計表",
        data=excel_data,
        file_name='每月服務狀態統計.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

def page_service_analysis(raw_df):
    st.header("📊 服務項目分析")
    
    # Filter by Month (Optional, but good for drilling down)
    months = sorted(raw_df['月份'].unique())
    selected_month = st.selectbox("選擇月份 (全選則不填)", ["全年度"] + list(months))
    
    # Filter by Agency (New)
    agencies = sorted(raw_df['機構'].unique())
    selected_agency = st.selectbox("選擇機構 (全選則不填)", ["全部"] + list(agencies))
    
    df_to_use = raw_df.copy()
    if selected_month != "全年度":
        df_to_use = df_to_use[df_to_use['月份'] == selected_month]
        
    if selected_agency != "全部":
        df_to_use = df_to_use[df_to_use['機構'] == selected_agency]

    # Aggregate by Service Item
    # Metric 1: Total Cost (Sum of 服務紀錄使用額度)
    # Metric 2: Frequency (Count of rows) - assuming 1 row = 1 record. 
    # Or sum of '服務紀錄組數' if that represents units providing value. Let's use Count for frequency first (Usage Count).
    
    # Check if '服務紀錄使用額度' is numeric
    # It should be from load_data
    
    service_agg = df_to_use.groupby('服務項目').agg({
        '服務紀錄使用額度': 'sum',
        '個案': 'count' # Proxy for frequency key
    }).rename(columns={'個案': '使用次數', '服務紀錄使用額度': '總金額'}).reset_index()
    
    # Top 20 by Cost
    top_cost = service_agg.sort_values('總金額', ascending=False).head(20)
    
    st.subheader(f"💰 花費最高的前 20 項服務 ({selected_month})")
    fig_cost = px.bar(
        top_cost, 
        x='總金額', 
        y='服務項目', 
        orientation='h', 
        title='服務項目總金額排名', 
        text_auto='.2s',
        color='總金額',
        color_continuous_scale=st.session_state.theme_primary
    )
    fig_cost.update_layout(yaxis={'categoryorder':'total ascending'})
    fig_cost.update_traces(width=0.6) # Slightly thicker for horizontal bars to remain readable
    st.plotly_chart(fig_cost, use_container_width=True)
    
    # Top 20 by Frequency
    top_freq = service_agg.sort_values('使用次數', ascending=False).head(20)
    
    st.subheader(f"🔄 使用頻率最高的前 20 項服務 ({selected_month})")
    fig_freq = px.bar(
        top_freq, 
        x='使用次數', 
        y='服務項目', 
        orientation='h', 
        title='服務項目使用次數排名', 
        text_auto=True,
        color='使用次數',
        color_continuous_scale=st.session_state.theme_secondary
    )
    fig_freq.update_layout(yaxis={'categoryorder':'total ascending'})
    fig_freq.update_traces(width=0.6)
    st.plotly_chart(fig_freq, use_container_width=True)

    # --- Cost Structure Analysis (New) ---
    st.markdown("---")
    st.subheader(f"🥧 經費結構分析 ({selected_month})")
    
    def categorize_service(item_name):
        item_name = str(item_name) # Ensure string for inclusion check
        if any(x in item_name for x in ['沐浴', '身體', '洗頭', '肢體']): 
            return '身體照顧'
        elif any(x in item_name for x in ['家務', '陪同', '代購', '餐']): 
            return '日常生活照顧'
        elif any(x in item_name for x in ['復能', '護理', '營養']): 
            return '專業服務'
        elif any(x in item_name for x in ['喘息']): 
            return '喘息服務'
        else:
            return '其他'
            
    df_to_use['類別'] = df_to_use['服務項目'].apply(categorize_service)
    
    df_to_use['類別'] = df_to_use['服務項目'].apply(categorize_service)
    
    # Treemap Data Preparation
    treemap_data = df_to_use.groupby(['類別', '服務項目']).agg({'服務紀錄使用額度': 'sum'}).reset_index()
    # Filter out 0 or negative values
    treemap_data = treemap_data[treemap_data['服務紀錄使用額度'] > 0]
    
    if not treemap_data.empty:
        fig_tree = px.treemap(
            treemap_data, 
            path=['類別', '服務項目'], 
            values='服務紀錄使用額度',
            title=f'經費結構與服務細項分析 ({selected_month})',
            color='類別', # Color by Category to keep it structured
            color_discrete_map={ # Optional: Define nice colors if needed, or let Plotly decide
                '身體照顧': '#e74c3c', 
                '日常生活照顧': '#3498db', 
                '專業服務': '#f1c40f', 
                '喘息服務': '#2ecc71', 
                '其他': '#95a5a6'
            }
        )
        fig_tree.update_traces(textinfo='label+value+percent entry')
        st.plotly_chart(fig_tree, use_container_width=True)
    else:
        st.info("無有效數據可繪製經費結構圖。")

def page_abnormal_alerts(agg_df):
    st.header("🚨 異常個案警示")
    
    # Filters in Sidebar
    months = sorted(agg_df['月份'].unique())
    selected_month = st.sidebar.selectbox("異常警示-選擇月份", months, index=len(months)-1 if months else 0)
    
    agencies = agg_df['機構'].unique()
    selected_agency = st.sidebar.selectbox("異常警示-選擇機構", ["全部"] + list(agencies))
    
    # Filter Data
    current_data = agg_df[agg_df['月份'] == selected_month].copy()
    if selected_agency != "全部":
        current_data = current_data[current_data['機構'] == selected_agency]
        
    # Calculate Rate
    current_data['Rate'] = (current_data['服務紀錄(不含自費)'] / current_data['照管金額分配額度'].replace(0, 1) * 100).round(2)
    
    # Thresholds
    low_threshold = 53
    high_threshold = 95
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([f"📉 低使用率警示 (<{low_threshold}%)", "📈 高使用率警示 (>95%)", "🏆 貢獻度 80/20 法則 (VIP)", "🧨 驟跌預警 (MoM > 30%)", "📉 連續衰退警示 (連續3月下滑)"])
    
    with tab1:
        low_usage = current_data[current_data['Rate'] < low_threshold].sort_values('Rate')
        st.warning(f"共有 {len(low_usage)} 位個案使用率低於 {low_threshold}%")
        
        # Download Button for Low Usage
        if not low_usage.empty:
            excel_data = convert_df_to_excel(low_usage)
            st.download_button(
                label="📥 下載低使用率個案清單",
                data=excel_data,
                file_name=f'低使用率個案_{selected_month}月.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key='dl_low'
            )

        st.dataframe(
            low_usage[['機構', '主責人員', '個案', '服務使用狀態', '照管金額分配額度', '服務紀錄(不含自費)', 'Rate']],
            column_config={
                "Rate": st.column_config.ProgressColumn(
                    "使用率 (%)",
                    help="額度使用率",
                    format="%.2f%%",
                    min_value=0,
                    max_value=100,
                ),
                "照管金額分配額度": st.column_config.NumberColumn(format="$%d"),
                "服務紀錄(不含自費)": st.column_config.NumberColumn(format="$%d"),
            },
            hide_index=True,
            use_container_width=True
        )
        
    with tab2:
        high_usage = current_data[current_data['Rate'] > high_threshold].sort_values('Rate', ascending=False)
        st.error(f"共有 {len(high_usage)} 位個案使用率高於 {high_threshold}%")
        
        # Download Button for High Usage
        if not high_usage.empty:
            excel_data = convert_df_to_excel(high_usage)
            st.download_button(
                label="📥 下載高使用率個案清單",
                data=excel_data,
                file_name=f'高使用率個案_{selected_month}月.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key='dl_high'
            )

        st.dataframe(
            high_usage[['機構', '主責人員', '個案', '服務使用狀態', '照管金額分配額度', '服務紀錄(不含自費)', 'Rate']],
            column_config={
                "Rate": st.column_config.ProgressColumn(
                    "使用率 (%)",
                    help="額度使用率",
                    format="%.2f%%",
                    min_value=0,
                    max_value=100,
                ),
                "照管金額分配額度": st.column_config.NumberColumn(format="$%d"),
                "服務紀錄(不含自費)": st.column_config.NumberColumn(format="$%d"),
            },
            hide_index=True,
            use_container_width=True
        )

    with tab3:
        # Pareto Principle (80/20 Rule)
        # Sort by Revenue
        vip_data = current_data.sort_values('服務紀錄(不含自費)', ascending=False).copy()
        total_revenue = vip_data['服務紀錄(不含自費)'].sum()
        vip_data['累積營收'] = vip_data['服務紀錄(不含自費)'].cumsum()
        vip_data['累積佔比(%)'] = (vip_data['累積營收'] / total_revenue * 100)
        
        # Find the cut-off for 80% revenue
        vip_80 = vip_data[vip_data['累積佔比(%)'] <= 80]
        # If very few, take at least top 10
        if len(vip_80) == 0 and not vip_data.empty:
            vip_80 = vip_data.head(10) # Fallback
            
        count_vip = len(vip_80)
        count_total = len(vip_data)
        percent_vip = (count_vip / count_total * 100) if count_total > 0 else 0
        
        st.success(f"本月前 {count_vip} 位 (約 {percent_vip:.1f}%) 個案貢獻了 80% 的營收服務費。")
        
        # Download Button for VIP
        if not vip_80.empty:
            excel_data = convert_df_to_excel(vip_80)
            st.download_button(
                label="📥 下載 VIP 高貢獻名單",
                data=excel_data,
                file_name=f'VIP個案_{selected_month}月.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key='dl_vip'
            )

        st.dataframe(
            vip_80[['機構', '主責人員', '個案', '服務使用狀態', '照管金額分配額度', '服務紀錄(不含自費)', '累積佔比(%)']]
            .style.format({'累積佔比(%)': '{:.1f}%', '照管金額分配額度': '{:,.0f}', '服務紀錄(不含自費)': '{:,.0f}'})
        )

    with tab4:
        # Sudden Drop Analysis
        # We need to compare "selected_month" vs "selected_month - 1"
        # Since months are integers (e.g., 9, 10, 11), prev_month is simple subtraction
        prev_month = selected_month - 1
        
        if prev_month not in sorted(agg_df['月份'].unique()):
            st.info(f"無法計算驟跌預警，因為找不到上一期 ({prev_month}月) 的數據。")
        else:
            # Prepare Previous Month Data
            prev_data = agg_df[agg_df['月份'] == prev_month].copy()
            prev_data['Rate_Prev'] = (prev_data['服務紀錄(不含自費)'] / prev_data['照管金額分配額度'].replace(0, 1) * 100)
            
            # Prepare Current Data (already filtered as current_data)
            # We need to merge on [Agency, Staff, Case]
            merged_drop = current_data.merge(
                prev_data[['機構', '主責人員', '個案', 'Rate_Prev']], 
                on=['機構', '主責人員', '個案'], 
                how='inner',
                suffixes=('', '_Prev')
            )
            
            # Calculate Drop
            merged_drop['Drop'] = merged_drop['Rate_Prev'] - merged_drop['Rate']
            
            # Filter for sudden drop > 30%
            sudden_drop_cases = merged_drop[merged_drop['Drop'] > 30].sort_values('Drop', ascending=False)
            
            st.error(f"共有 {len(sudden_drop_cases)} 位個案使用率較上月驟跌超過 30%")
            
            if not sudden_drop_cases.empty:
                excel_drop = convert_df_to_excel(sudden_drop_cases)
                st.download_button(
                    label="📥 下載驟跌個案清單",
                    data=excel_drop,
                    file_name=f'驟跌個案_{selected_month}月.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    key='dl_drop'
                )

                st.dataframe(
                    sudden_drop_cases[['機構', '主責人員', '個案', '服務使用狀態', 'Rate_Prev', 'Rate', 'Drop']]
                    .rename(columns={'Rate_Prev': '上月(%)', 'Rate': '本月(%)', 'Drop': '跌幅(%)'})
                    .style.format({'上月(%)': '{:.1f}%', '本月(%)': '{:.1f}%', '跌幅(%)': '{:.1f}%'})
                )

    with tab5:
        # Churn Risk: Continuous Decline over 3 months
        # T (selected), T-1, T-2
        m1 = selected_month
        m2 = m1 - 1
        m3 = m1 - 2
        
        valid_months = sorted(agg_df['月份'].unique())
        
        if m2 not in valid_months or m3 not in valid_months:
             st.info(f"無法計算連續衰退預警，因為需要連續三個月的數據 (需包含 {m2}月, {m3}月)。")
        else:
            # Prepare Dataframes
            # We need Agency, Staff, Case, Rate for M1, M2, M3
            cols_needed = ['機構', '主責人員', '個案', '照管金額分配額度', '服務紀錄(不含自費)']
            
            df1 = agg_df[agg_df['月份'] == m1][cols_needed].copy()
            df2 = agg_df[agg_df['月份'] == m2][cols_needed].copy()
            df3 = agg_df[agg_df['月份'] == m3][cols_needed].copy()
            
            # Filter Agency if needed
            if selected_agency != "全部":
                df1 = df1[df1['機構'] == selected_agency]
                df2 = df2[df2['機構'] == selected_agency]
                df3 = df3[df3['機構'] == selected_agency]

            # Calc Rates
            def calc_rate_series(df):
                return (df['服務紀錄(不含自費)'] / df['照管金額分配額度'].replace(0, 1) * 100)

            df1['Rate_M1'] = calc_rate_series(df1)
            df2['Rate_M2'] = calc_rate_series(df2)
            df3['Rate_M3'] = calc_rate_series(df3)
            
            # Merge
            # Inner join because we need the case to exist in all 3 months to say "continuous" decline?
            # Or left join? If a case didn't exist in m3, it's not a "decline" from m3. So Inner is safer for specific "Churn Risk" definition.
            merge_base = df1[['機構', '主責人員', '個案', 'Rate_M1', '服務使用狀態'] if '服務使用狀態' in df1.columns else ['機構', '主責人員', '個案', 'Rate_M1']]
            if '服務使用狀態' not in merge_base.columns:
                 # Try adding status from df1
                 status_map = agg_df[agg_df['月份'] == m1][['機構', '主責人員', '個案', '服務使用狀態']].drop_duplicates()
                 merge_base = merge_base.merge(status_map, on=['機構', '主責人員', '個案'], how='left')

            m_churn = merge_base.merge(
                df2[['機構', '主責人員', '個案', 'Rate_M2']], on=['機構', '主責人員', '個案'], how='inner'
            ).merge(
                df3[['機構', '主責人員', '個案', 'Rate_M3']], on=['機構', '主責人員', '個案'], how='inner'
            )
            
            # Check Logic: Rate_M3 > Rate_M2 > Rate_M1
            # Filter: strict decline
            churn_risk = m_churn[
                (m_churn['Rate_M3'] > m_churn['Rate_M2']) & 
                (m_churn['Rate_M2'] > m_churn['Rate_M1'])
            ].copy()
            
            # Calculate Total Drop
            churn_risk['總跌幅'] = churn_risk['Rate_M3'] - churn_risk['Rate_M1']
            
            # Sort by Total Drop
            churn_risk = churn_risk.sort_values('總跌幅', ascending=False)
            
            st.error(f"⚠️ 共有 {len(churn_risk)} 位個案呈現連續三個月使用率下滑")
            
            if not churn_risk.empty:
                excel_churn = convert_df_to_excel(churn_risk)
                st.download_button(
                    label="📥 下載流失風險個案清單",
                    data=excel_churn,
                    file_name=f'流失風險個案_{selected_month}月.xlsx',
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    key='dl_churn'
                )

                st.dataframe(
                    churn_risk[['機構', '主責人員', '個案', '服務使用狀態', 'Rate_M3', 'Rate_M2', 'Rate_M1', '總跌幅']]
                    .rename(columns={
                        'Rate_M3': f'{m3}月(%)', 
                        'Rate_M2': f'{m2}月(%)', 
                        'Rate_M1': f'{m1}月(%)'
                    })
                    .style.format({
                        f'{m3}月(%)': '{:.1f}%', 
                        f'{m2}月(%)': '{:.1f}%', 
                        f'{m1}月(%)': '{:.1f}%',
                        '總跌幅': '{:.1f}%'
                    })
                    .background_gradient(subset=['總跌幅'], cmap='Reds')
                )

def page_agency_overview(agg_df):
    st.header("📊 機構額度使用率總覽")
    
    # Logic: Group by [Month, Agency], Sum(Used) / Sum(Quota)
    agency_monthly = agg_df.groupby(['月份', '機構']).agg({
        '照管金額分配額度': 'sum',
        '服務紀錄(不含自費)': 'sum'
    }).reset_index()
    
    agency_monthly['使用率(%)'] = (agency_monthly['服務紀錄(不含自費)'] / agency_monthly['照管金額分配額度'].replace(0, 1) * 100).round(2)
    
    # --- Executive Metric Cards (New) ---
    st.markdown("### 🏠 經營關鍵指標 (KPI)")
    total_revenue = agency_monthly['服務紀錄(不含自費)'].sum()
    total_quota = agency_monthly['照管金額分配額度'].sum()
    avg_rate_total = (total_revenue / total_quota * 100) if total_quota > 0 else 0
    total_cases = agg_df[agg_df['月份'].isin(agency_monthly['月份'])]['個案'].nunique() # Approx
    # Actually metrics should probably be based on the "Latest Month" or "Selected Period Avg"?
    # Agency Overview chart shows trend, but metrics usually need a specific context. 
    # Let's show "Average Monthly Performance" or "Total YTD".
    # Given the chart is monthly trend, let's show totals for the *visible data*.
    
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("總服務金額 (累計)", f"${total_revenue:,.0f}")
    kpi2.metric("平均額度使用率", f"{avg_rate_total:.1f}%")
    kpi3.metric("總服務人次 (累計)", f"{total_cases:,.0f}") # Sum of monthly counts

    # --- Automated Insights (New) ---
    # Calculate variables for insights
    avg_rate = avg_rate_total # Using the overall average rate
    gap = (total_quota * 0.85 - total_revenue) # Potential revenue if rate reaches 85%

    analysis_text = "**📝 月報摘要：**\n"

    # Calculate MoM Growth (Revenue & Cases) Breakdown by Agency
    months_sorted = sorted(agg_df['月份'].unique())
    if len(months_sorted) >= 2:
        curr_m = months_sorted[-1]
        prev_m = months_sorted[-2]
        
        analysis_text += f"\n    - {curr_m}月與上月機構動能比較 (營收 / 活躍個案)："
        
        agencies = sorted(agg_df['機構'].unique())
        for agency in agencies:
            curr_stats = agg_df[(agg_df['月份'] == curr_m) & (agg_df['機構'] == agency)]
            prev_stats = agg_df[(agg_df['月份'] == prev_m) & (agg_df['機構'] == agency)]
            
            # Revenue
            curr_rev = curr_stats['服務紀錄(不含自費)'].sum()
            prev_rev = prev_stats['服務紀錄(不含自費)'].sum()
            rev_diff = curr_rev - prev_rev
            
            # Active Cases
            curr_cases = curr_stats[curr_stats['服務紀錄(不含自費)'] > 0]['個案'].nunique()
            prev_cases = prev_stats[prev_stats['服務紀錄(不含自費)'] > 0]['個案'].nunique()
            case_diff = curr_cases - prev_cases
            
            # Formatting with Colors (Using HTML for compatibility)
            # Green: #2ecc71, Red: #e74c3c, Gray: #95a5a6
            rev_str = f"+${rev_diff:,.0f}" if rev_diff >= 0 else f"-${abs(rev_diff):,.0f}"
            if rev_diff > 0:
                rev_display = f"<span style='color:#2ecc71'>{rev_str}</span>"
            elif rev_diff < 0:
                rev_display = f"<span style='color:#e74c3c'>{rev_str}</span>"
            else:
                rev_display = f"<span style='color:#95a5a6'>{rev_str}</span>"

            case_str = f"+{case_diff}" if case_diff >= 0 else f"{case_diff}"
            if case_diff > 0:
                case_display = f"<span style='color:#2ecc71'>{case_str}人</span>"
            elif case_diff < 0:
                case_display = f"<span style='color:#e74c3c'>{case_str}人</span>"
            else:
                case_display = f"<span style='color:#95a5a6'>{case_str}人</span>"
            
            analysis_text += f"\n        - {agency}：營收 {rev_display}，個案 {case_display}"

    analysis_text += f"""
    - 本年度至今，機構整體平均使用率為 {avg_rate:.1f}% ，居家服務總營收達 ${total_revenue:,.0f} 。
    - 潛在營收機會：若能將整體使用率提升至 85% ，預期可額外增加 ${gap:,.0f} 的營收。
    """
    
    # Add Abnormal Case Ratio Insight (Breakdown by Agency)
    # Get data for the latest month to calculate abnormal cases
    latest_month = agg_df['月份'].max()
    latest_month_df = agg_df[agg_df['月份'] == latest_month].copy()
    latest_month_df['Rate'] = (latest_month_df['服務紀錄(不含自費)'] / latest_month_df['照管金額分配額度'].replace(0, 1) * 100)
    
    analysis_text += f"\n    - {latest_month}月份異常警示詳情 (使用率 < 30%)："

    agencies = sorted(latest_month_df['機構'].unique())
    for agency in agencies:
        agency_df = latest_month_df[latest_month_df['機構'] == agency]
        total_agency_cases = len(agency_df)
        if total_agency_cases > 0:
            low_cases = len(agency_df[agency_df['Rate'] < 30])
            ratio = (low_cases / total_agency_cases * 100)
            analysis_text += f"\n        - {agency}：{low_cases} 位 (佔該機構 {ratio:.1f}%)"
    
    # Use st.markdown with HTML instead of st.info
    st.markdown(
        f"""
        <div style="background-color: #262730; color: white; padding: 15px; border-radius: 5px; border: 1px solid #464b5d;">
        {analysis_text.replace(chr(10), '<br>')}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("---")
    
    # --- Agency Performance Radar (New) ---
    st.subheader("🎯 各機構綜合效能雷達圖")
    
    # Needs to be based on the LATEST month to be relevant current snapshot
    radar_month = agg_df['月份'].max()
    radar_df = agg_df[agg_df['月份'] == radar_month].copy()
    
    # Metrics
    # 1. 效能 Efficiency: Avg Usage Rate
    # 2. 產值 Value: Rev / Case
    # 3. 產能 Productivity: Rev / Staff
    # 4. 動能 Potential: % of cases > 80% usage
    # 5. 貢獻 Impact: Total Rev (Normalized)
    
    radar_metrics = []
    
    radar_agencies = sorted(radar_df['機構'].unique())
    
    for ag in radar_agencies:
        sub = radar_df[radar_df['機構'] == ag]
        if sub.empty: continue
        
        # 1. Efficiency
        sub['Rate'] = (sub['服務紀錄(不含自費)'] / sub['照管金額分配額度'].replace(0, 1) * 100)
        eff = sub['Rate'].mean()
        
        # 2. Value
        total_rev = sub['服務紀錄(不含自費)'].sum()
        count_case = sub['個案'].nunique()
        val = (total_rev / count_case) if count_case > 0 else 0
        
        # 3. Productivity
        count_staff = sub['主責人員'].nunique()
        prod = (total_rev / count_staff) if count_staff > 0 else 0
        
        # 4. Potential
        high_perf = len(sub[sub['Rate'] >= 80])
        pot = (high_perf / count_case * 100) if count_case > 0 else 0
        
        # 5. Impact 
        imp = total_rev
        
        radar_metrics.append({
            '機構': ag,
            '效能 (平均使用率)': eff,
            '產值 (人均營收)': val,
            '產能 (督導平均產出)': prod,
            '動能 (高績效個案佔比)': pot,
            '貢獻 (總營收)': imp
        })
        
    radar_data = pd.DataFrame(radar_metrics)
    
    # Normalization (Min-Max to 0-100)
    # Efficiency and Potential are already 0-100 (mostly)
    # Value, Productivity, Impact need scaling
    
    cols_to_norm = ['產值 (人均營收)', '產能 (督導平均產出)', '貢獻 (總營收)']
    
    # Initialize normalized df
    radar_norm = radar_data.copy()
    
    for col in cols_to_norm:
        min_v = radar_data[col].min()
        max_v = radar_data[col].max()
        if max_v > min_v:
            radar_norm[col] = (radar_data[col] - min_v) / (max_v - min_v) * 100
        else:
            radar_norm[col] = 100 # If all same or single agency
            
    # For chart, melt
    radar_melted = radar_norm.melt(
        id_vars=['機構'], 
        var_name='指標', 
        value_name='分數'
    )
    
    fig_radar = px.line_polar(
        radar_melted, 
        r='分數', 
        theta='指標', 
        color='機構', 
        line_close=True,
        title=f"各機構五力分析 ({radar_month}月份)",
        range_r=[0, 100]
    )
    fig_radar.update_traces(fill='toself', opacity=0.4)
    st.plotly_chart(fig_radar, use_container_width=True)
    
    with st.expander("查看原始數據"):
        st.dataframe(radar_data.style.format({
            '效能 (平均使用率)': '{:.1f}%',
            '產值 (人均營收)': '${:,.0f}',
            '產能 (督導平均產出)': '${:,.0f}',
            '動能 (高績效個案佔比)': '{:.1f}%',
            '貢獻 (總營收)': '${:,.0f}'
        }))
        
    with st.expander("💡 如何解讀五力分析雷達圖 (點擊展開說明)"):
        st.markdown("""
        1.  **效能 (平均使用率)**：代表預算執行效率。高分表示大部分個案額度用好用滿；低分表示有閒置額度。
        2.  **產值 (人均營收)**：每位個案帶來的營收貢獻。高分表示個案需求強度高；低分表示多為輕度使用者。
        3.  **產能 (督導平均產出)**：每位督導管理的營收規模。高分表示管理效率高，能扛起較大業績。
        4.  **動能 (高績效個案佔比)**：使用率 > 80% 的優質個案比例。高分表示主力客群穩定，體質健康。
        5.  **貢獻 (總營收)**：在整體組織中的營收市佔率。圖形越飽滿代表全方位表現優異。
        """)

    st.divider()

    # --- Trend Chart ---
    st.subheader("📈 機構月度使用率趨勢")
    fig = px.line(
        agency_monthly, 
        x='月份', 
        y='使用率(%)', 
        color='機構', 
        markers=True,
        title='各機構月度額度使用率趨勢'
    )
    fig.update_xaxes(type='category') # Use category to avoid 9.5, 10.5
    st.plotly_chart(fig, use_container_width=True)
    
    # --- Unused Quota Opportunity (New) ---
    # --- Unused Quota Opportunity (New) ---
    st.subheader("💰 潛在營收機會分析 (已用 vs. 剩餘)")
    
    # Filter for Opportunity Chart
    opp_agencies = ["全部"] + list(agency_monthly['機構'].unique())
    selected_opp_agency = st.selectbox("選擇機構查看 (潛在機會)", opp_agencies, key='opp_agency_select')

    chart_opp = agency_monthly.copy()
    
    if selected_opp_agency != "全部":
        chart_opp = chart_opp[chart_opp['機構'] == selected_opp_agency]

    # Stacked Bar: Used Amount vs (Quota - Used Amount)
    chart_opp['剩餘額度 (機會)'] = (chart_opp['照管金額分配額度'] - chart_opp['服務紀錄(不含自費)']).clip(lower=0)
    chart_opp = chart_opp.rename(columns={'服務紀錄(不含自費)': '已實現營收'})
    
    # We need to melt for stacked chart
    opp_melted = chart_opp.melt(
        id_vars=['月份', '機構'], 
        value_vars=['已實現營收', '剩餘額度 (機會)'],
        var_name='類型',
        value_name='金額'
    )
    
    # Dynamic Title
    opp_title = f'{selected_opp_agency} - 額度使用 vs. 剩餘空間' if selected_opp_agency != "全部" else '全機構 - 額度使用 vs. 剩餘空間'

    fig_opp = px.bar(
        opp_melted, 
        x='月份', 
        y='金額', 
        color='類型', 
        title=opp_title,
        color_discrete_map={'已實現營收': '#2ecc71', '剩餘額度 (機會)': '#95a5a6'}
    )
    fig_opp.update_xaxes(type='category')
    fig_opp.update_traces(width=0.2) # Thinner bars
    st.plotly_chart(fig_opp, use_container_width=True)
    
    # --- Usage Rate Histogram (New) ---
    st.subheader("📊 個案使用率分佈診斷")
    # We need row-level data for histogram, not aggregated agency level.
    # agg_df contains row per [Month, Agency, Staff, Case]. perfect.
    
    # Let users pick a month for histogram to see the 'shape' of that month
    hist_month = st.selectbox("選擇月份查看分佈", sorted(agg_df['月份'].unique()), index=len(agg_df['月份'].unique())-1, key='hist_month')
    hist_data = agg_df[agg_df['月份'] == hist_month].copy() # Use .copy() to avoid SettingWithCopyWarning
    
    hist_data['Rate'] = (hist_data['服務紀錄(不含自費)'] / hist_data['照管金額分配額度'].replace(0, 1) * 100)
    # Cap at 120% for cleaner view if there are outliers
    hist_data['Rate_Capped'] = hist_data['Rate'].apply(lambda x: min(x, 120))
    
    fig_hist = px.histogram(
        hist_data, 
        x='Rate_Capped', 
        nbins=20, 
        title=f"{hist_month} 月份 - 個案使用率分佈圖",
        labels={'Rate_Capped': '使用率 (%)'},
        color='機構', # Stack by Agency
        marginal='box' # Show box plot on top
    )
    fig_hist.add_vline(x=53, line_dash="dash", line_color="green", annotation_text="目標 53%")
    st.plotly_chart(fig_hist, use_container_width=True)
    
    with st.expander("💡 如何解讀個案使用率分佈 (點擊展開說明)"):
        st.markdown("""
        此圖表展示了該月份所有個案的「額度使用率」分佈情形，幫助您判斷整體營收結構是否健康。
        
        *   **X 軸 (使用率 %)**：數值越高代表個案額度用得越滿。
        *   **Y 軸 (Count)**：代表在該使用率區間的個案人數。
        *   **綠色虛線 (目標 53%)**：理想的經營目標線。
        
        **觀察重點：**
        1.  **右偏分佈 (理想)**：大部分色塊集中在右側 (53%~100%)，代表大多數個案都穩定使用額度。
        2.  **雙峰分佈 (警訊)**：若左側 (0~30%) 出現另一個高峰，代表有大量「低使用率/無效」個案，可能是幽靈人口或潛在流失戶。
        3.  **箱型圖 (上方)**：
            *   **箱子中間線**：中位數，代表最中間那位個案的使用率。
            *   **箱子寬度**：主要個案群的分佈範圍。箱子越窄越好，代表服務一致性高。
        """)
    
    # Data Table
    with st.expander("查看詳細數據"):
        st.dataframe(agency_monthly)
        excel_data = convert_df_to_excel(agency_monthly)
        st.download_button(
            label="📥 下載機構分析報表",
            data=excel_data,
            file_name='機構月度分析報表.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

def page_supervisor_performance(agg_df):
    st.header("🧑‍💼 督導/人員績效分析")
    
    # Filter Agency (Optional)
    agencies = agg_df['機構'].unique()
    selected_agency = st.selectbox("選擇機構 (全選則不填)", ["全部"] + list(agencies))
    
    df_to_use = agg_df.copy()
    if selected_agency != "全部":
        df_to_use = df_to_use[df_to_use['機構'] == selected_agency]
    
    # --- Tab 1: Trend Analysis ---
    # --- Tab 2: Workload Matrix (New) ---
    t1, t2, t3 = st.tabs(["📈 月度趨勢", "⚖️ 案量 vs. 績效矩陣", "🏆 業績排行"])
    
    with t1:
        # Aggregation for Trend
        staff_monthly = df_to_use.groupby(['月份', '主責人員']).agg({
            '照管金額分配額度': 'sum',
            '服務紀錄(不含自費)': 'sum'
        }).reset_index()
        
        staff_monthly['使用率(%)'] = (staff_monthly['服務紀錄(不含自費)'] / staff_monthly['照管金額分配額度'].replace(0, 1) * 100).round(2)
        
        fig_trend = px.line(
            staff_monthly, 
            x='月份', 
            y='使用率(%)', 
            color='主責人員', 
            markers=True,
            title=f'各督導/人員月度使用率趨勢'
        )
        fig_trend.update_xaxes(type='category')
        st.plotly_chart(fig_trend, use_container_width=True)

    with t2:
        st.markdown("### 督導案量矩陣")
        st.caption("X軸：負責個案數 (案量) | Y軸：平均額度使用率 (績效) | 點的大小：總分配額度規模")
        
        # 1. Month Selector
        months = sorted(df_to_use['月份'].unique())
        matrix_month = st.selectbox("選擇月份進行分析", months, index=len(months)-1 if months else 0, key='matrix_month')
        
        matrix_data = df_to_use[df_to_use['月份'] == matrix_month]
        
        # 2. Local Agency Filter (If global is 'All', allow specific drill down here)
        if selected_agency == "全部":
            matrix_agencies = matrix_data['機構'].unique()
            local_agency = st.selectbox("在矩陣中篩選機構", ["全部"] + list(matrix_agencies), key='matrix_agency_filter')
            if local_agency != "全部":
                matrix_data = matrix_data[matrix_data['機構'] == local_agency]

        # Aggregation by [Agency, Staff] to avoid name collisions
        staff_matrix = matrix_data.groupby(['機構', '主責人員']).agg({
            '個案': 'count',
            '照管金額分配額度': 'sum',
            '服務紀錄(不含自費)': 'sum'
        }).reset_index()
        
        staff_matrix['平均使用率(%)'] = (staff_matrix['服務紀錄(不含自費)'] / staff_matrix['照管金額分配額度'].replace(0, 1) * 100).round(2)
        staff_matrix = staff_matrix.rename(columns={'個案': '個案數'})
        
        # Quadrant Lines
        if not staff_matrix.empty:
            avg_load = staff_matrix['個案數'].mean()
            avg_rate = staff_matrix['平均使用率(%)'].mean()
        else:
            avg_load = 0
            avg_rate = 0
        
        # Color strategy: If filtering specific agency, color by Staff. If All, color by Agency? 
        # Or always color by Staff but show Agency in hover. 
        # If too many staff, color by Agency is better for "All".
        color_col = '主責人員'
        if selected_agency == "全部" and (pd.isna(local_agency) if 'local_agency' not in locals() else local_agency == "全部"):
             # If displaying ALL agencies, maybe color by Agency to distinguish clusters?
             # But user wants to identify Staff. Let's stick to Staff but add Agency to hover.
             pass

        fig_matrix = px.scatter(
            staff_matrix,
            x='個案數',
            y='平均使用率(%)',
            color='主責人員', # Color by Staff Name
            # symbol='主責人員', # Removed to use default dots (circles)
            size='照管金額分配額度', 
            hover_data=['機構', '主責人員', '個案數', '平均使用率(%)', '照管金額分配額度'],
            text='主責人員',
            title=f"{matrix_month} 月份 - 督導案量效能矩陣"
        )
        fig_matrix.update_traces(textposition='top center')
        
        # Add Reference Lines
        fig_matrix.add_hline(y=avg_rate, line_dash="dash", line_color="green", annotation_text=f"平均使用率: {avg_rate:.1f}%")
        fig_matrix.add_vline(x=avg_load, line_dash="dash", line_color="orange", annotation_text=f"平均案量: {avg_load:.1f}")
        
        st.plotly_chart(fig_matrix, use_container_width=True)

    with t3:
        st.markdown("### 🏆 督導業績排行")
        
        # Reuse existing selectors? 
        # Ideally, ranking is also monthly.
        # Let's use a fresh selector or sync? Sync is hard across tabs without session state shenanigans.
        # Let's just add a simple selector for this tab or reuse the one from Matrix if we move it up?
        # Moving selectors up to the main page level is cleaner.
        
        # But to avoid refactoring the whole function, let's just add a month selector here locally.
        rank_month = st.selectbox("選擇排序月份", months, index=len(months)-1 if months else 0, key='rank_month')
        
        rank_data = df_to_use[df_to_use['月份'] == rank_month]
        
        # Group by Staff
        staff_rank = rank_data.groupby(['主責人員', '機構']).agg({
            '服務紀錄(不含自費)': 'sum',
            '照管金額分配額度': 'sum',
            '個案': 'count'
        }).reset_index()
        
        staff_rank['使用率(%)'] = (staff_rank['服務紀錄(不含自費)'] / staff_rank['照管金額分配額度'].replace(0, 1) * 100).round(2)
        
        # Sort by Revenue (Performance)
        staff_rank = staff_rank.sort_values('服務紀錄(不含自費)', ascending=True) # Ascending for horizontal bar
        
        # Plot
        fig_rank = px.bar(
            staff_rank,
            x='服務紀錄(不含自費)',
            y='主責人員',
            orientation='h',
            title=f"{rank_month} 月份 - 督導業績排行 (依營收)",
            text_auto='.2s',
            color='服務紀錄(不含自費)', # Color by metric for gradient
            color_continuous_scale=st.session_state.theme_primary,
            hover_data=['使用率(%)', '個案', '機構']
        )
        fig_rank.update_traces(textposition='outside')
        fig_rank.update_layout(yaxis={'categoryorder':'total ascending'})
        
        st.plotly_chart(fig_rank, use_container_width=True)
        
        # Table View
        st.dataframe(
            staff_rank.sort_values('服務紀錄(不含自費)', ascending=False)
            .style.format({'服務紀錄(不含自費)': '{:,.0f}', '照管金額分配額度': '{:,.0f}', '使用率(%)': '{:.1f}%'})
            .background_gradient(subset=['服務紀錄(不含自費)'], cmap=st.session_state.theme_primary)
        )

def page_case_detail(raw_df, agg_df):
    st.header("🔍 個案詳細分析")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    months = sorted(agg_df['月份'].unique())
    with col1:
        current_month = st.selectbox("選擇月份", months, index=len(months)-1 if months else 0)
    
    agencies = agg_df[agg_df['月份'] == current_month]['機構'].unique()
    with col2:
        agency = st.selectbox("機構", agencies)
        
    staffs = agg_df[(agg_df['月份'] == current_month) & (agg_df['機構'] == agency)]['主責人員'].unique()
    with col3:
        staff = st.selectbox("主責人員", staffs)
        
    # Data Prep
    # Get Current Month Data
    current_data = agg_df[
        (agg_df['月份'] == current_month) & 
        (agg_df['機構'] == agency) & 
        (agg_df['主責人員'] == staff)
    ].copy()
    
    # Determine 'Previous Month' for Trend
    # Need to handle string months properly. Assuming they are sortable.
    # Ideally, we should convert to int if possible, but let's stick to list index.
    curr_idx = months.index(current_month)
    prev_month = months[curr_idx - 1] if curr_idx > 0 else None
    
    prev_data = None
    if prev_month:
        prev_data = agg_df[
            (agg_df['月份'] == prev_month) & 
            (agg_df['機構'] == agency) & 
            (agg_df['主責人員'] == staff)
        ].set_index('個案')['服務紀錄(不含自費)'] # Need ratio? Or just used amount?
        # Re-calculate usage rate for prev month lookup
        prev_data_full = agg_df[
             (agg_df['月份'] == prev_month) & 
             (agg_df['機構'] == agency) & 
             (agg_df['主責人員'] == staff)
        ].copy()
        prev_data_full['Rate'] = (prev_data_full['服務紀錄(不含自費)'] / prev_data_full['照管金額分配額度'].replace(0, 1) * 100)
        # Fix for potential duplicates if A Unit differs but it's same case
        prev_map = prev_data_full.groupby('個案')['Rate'].mean()

    # Display Cases
    # Avoid div by zero
    current_data['Rate'] = (current_data['服務紀錄(不含自費)'] / current_data['照管金額分配額度'].replace(0, 1) * 100).round(2)
    
    st.markdown("### 個案列表")
    
    for _, row in current_data.iterrows():
        case_name = row['個案']
        rate = row['Rate']
        
        # Trend Logic
        diff = 0
        has_prev = False
        trend_str = ""
        
        if prev_month and prev_data is not None and case_name in prev_map:
            prev_rate = prev_map[case_name]
            diff = rate - prev_rate
            has_prev = True
            
            if diff > 0:
                trend_str = f":green[↑ {diff:.1f}%]"
            elif diff < 0:
                trend_str = f":red[↓ {abs(diff):.1f}%]"
            else:
                trend_str = ":gray[➖ 0.0%]"
        
        # UI Card (Expander)
        status = row.get('服務使用狀態', '未知')
        # Title with Colored Markdown
        with st.expander(f"{case_name} ({status}) | 本月使用率: {rate}% | {trend_str}"):
            
            # Metrics Row (Replaces the old st.info line)
            m1, m2, m3 = st.columns(3)
            m1.metric("額度使用率", f"{rate}%", f"{diff:.1f}%" if has_prev else None)
            m2.metric("分配額度", f"{row['照管金額分配額度']:,.0f}")
            m3.metric("使用額度", f"{row['服務紀錄(不含自費)']:,.0f}")
            
            # Drill Down: Show detailed service items from RAW dataframe
            curr_details = raw_df[
                (raw_df['月份'] == current_month) & 
                (raw_df['機構'] == agency) & 
                (raw_df['主責人員'] == staff) & 
                (raw_df['個案'] == case_name)
            ]
            
            # Aggregate to handle potential duplicate entries per item and clean up view
            curr_agg = curr_details.groupby('服務項目').agg({
                '政府服務項目單價': 'max', # Assumption: price is constant
                '服務紀錄組數': 'sum',
                '服務紀錄使用額度': 'sum'
            }).reset_index()

            if prev_month:
                # Get Previous Month Details
                prev_details = raw_df[
                    (raw_df['月份'] == prev_month) & 
                    (raw_df['機構'] == agency) & 
                    (raw_df['主責人員'] == staff) & 
                    (raw_df['個案'] == case_name)
                ]
                
                prev_agg = prev_details.groupby('服務項目').agg({
                    '政府服務項目單價': 'max',
                    '服務紀錄組數': 'sum',
                    '服務紀錄使用額度': 'sum'
                }).reset_index().rename(columns={
                    '政府服務項目單價': '單價(上月)',
                    '服務紀錄組數': '組數(上月)', 
                    '服務紀錄使用額度': '金額(上月)'
                })
                
                # Merge
                merged_details = pd.merge(curr_agg, prev_agg, on='服務項目', how='outer').fillna(0)
                
                # Coalesce Unit Price: Use Current if > 0, else Prev
                merged_details['政府服務項目單價'] = merged_details.apply(
                    lambda x: x['政府服務項目單價'] if x['政府服務項目單價'] > 0 else x['單價(上月)'], axis=1
                )
                
                # Calculate Deltas
                merged_details['金額差異'] = merged_details['服務紀錄使用額度'] - merged_details['金額(上月)']
                merged_details['組數差異'] = merged_details['服務紀錄組數'] - merged_details['組數(上月)']
                
                # Sort by Absolute Amount Difference to show most impactful changes first
                merged_details['abs_diff'] = merged_details['金額差異'].abs()
                merged_details = merged_details.sort_values('abs_diff', ascending=False).drop(columns=['abs_diff'])
                
                # Add Quota Column (from case level)
                merged_details['照管金額分配額度'] = row['照管金額分配額度']
                
                # Formatting Columns
                display_cols = ['服務項目', '政府服務項目單價', '服務紀錄組數', '組數差異', '服務紀錄使用額度', '金額差異', '照管金額分配額度']
                
                st.dataframe(
                    merged_details[display_cols].style
                    .format({
                        '政府服務項目單價': '{:.0f}', 
                        '服務紀錄組數': '{:.0f}', 
                        '組數差異': '{:+.0f}',
                        '服務紀錄使用額度': '{:,.0f}',
                        '金額差異': '{:+,.0f}',
                        '照管金額分配額度': '{:,.0f}'
                    })
                    .background_gradient(subset=['金額差異'], cmap='RdBu', vmin=-5000, vmax=5000)
                    .applymap(lambda v: 'color: transparent' if v == 0 else '', subset=['組數差異', '金額差異']) # Visual cleanup
                )
            else:
                # Fallback if no prev month
                curr_agg['照管金額分配額度'] = row['照管金額分配額度']
                st.dataframe(curr_agg.style.format({
                    '政府服務項目單價': '{:.0f}', 
                    '服務紀錄組數': '{:.0f}',
                    '服務紀錄使用額度': '{:,.0f}',
                    '照管金額分配額度': '{:,.0f}'
                }))

def page_comparison(agg_df):
    st.header("⚖️ 雙月份超級比對")
    
    months = sorted(agg_df['月份'].unique())
    if len(months) < 2:
        st.warning("資料不足兩個月，無法進行比對。")
        return
        
    col1, col2 = st.columns(2)
    with col1:
        month_a = st.selectbox("基準月份 (A)", months, index=len(months)-2)
    with col2:
        month_b = st.selectbox("比較月份 (B)", months, index=len(months)-1)
        
    if month_a == month_b:
        st.info("請選擇不同的月份進行比對。")
        return
    
    # Global Agency Filter
    agencies = sorted(agg_df['機構'].unique())
    selected_agency = st.selectbox("選擇機構範圍", ["全部"] + list(agencies), key='comp_global_agency')
    
    # Get Data
    data_a = agg_df[agg_df['月份'] == month_a]
    data_b = agg_df[agg_df['月份'] == month_b]
    
    # Apply Filter
    if selected_agency != "全部":
        data_a = data_a[data_a['機構'] == selected_agency]
        data_b = data_b[data_b['機構'] == selected_agency]
    
    # Metrics Calculation
    def get_metrics(df):
        rev = df['服務紀錄(不含自費)'].sum()
        quota = df['照管金額分配額度'].sum()
        rate = (rev / quota * 100) if quota > 0 else 0
        cases = df['個案'].nunique()
        return rev, rate, cases
        
    rev_a, rate_a, cases_a = get_metrics(data_a)
    rev_b, rate_b, cases_b = get_metrics(data_b)
    
    # Display Side-by-Side Metrics
    st.markdown("### 關鍵指標差異")
    c1, c2, c3 = st.columns(3)
    
    rev_diff = rev_b - rev_a
    c1.metric("總營收 (B vs A)", f"${rev_b:,.0f}", f"{rev_diff:,.0f}")
    c2.metric("平均使用率 (B vs A)", f"{rate_b:.1f}%", f"{rate_b - rate_a:.1f}%")
    c3.metric("服務個案數 (B vs A)", f"{cases_b}", f"{cases_b - cases_a}")
    
    st.markdown("---")
    
    # Drill Down by Agency
    # If specific agency selected, this chart is less useful (1 bar), but still ok.
    if selected_agency == "全部":
        st.subheader("各機構差異明細")
    else:
        st.subheader(f"{selected_agency} - 營收差異")
    
    group_a = data_a.groupby('機構')['服務紀錄(不含自費)'].sum()
    group_b = data_b.groupby('機構')['服務紀錄(不含自費)'].sum()
    
    # Combine
    comp_df = pd.DataFrame({'基準月': group_a, '比較月': group_b}).fillna(0)
    comp_df['差異金額'] = comp_df['比較月'] - comp_df['基準月']
    comp_df['成長率(%)'] = (comp_df['差異金額'] / comp_df['基準月'].replace(0, 1) * 100).round(1)
    
    st.dataframe(comp_df.style.format("{:,.0f}", subset=['基準月', '比較月', '差異金額']).format("{:.1f}%", subset=['成長率(%)']))
    
    # Visual Delta
    fig = px.bar(
        comp_df.reset_index(), 
        x='機構', 
        y='差異金額', 
        title=f"各機構營收差異 ({month_b}月 - {month_a}月)",
        text='差異金額',
        color='差異金額',
        color_continuous_scale=['red', 'gray', 'green']
    )
    fig.update_traces(width=0.2) # Thinner bars
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # --- Case Level Comparison (New) ---
    st.subheader("🔍 個案層級變化分析 (Top 10)")
    
    # No extra filter needed here, using global data_a/data_b
    
    # Prepare Merge
    cases_a = data_a.copy()
    cases_b = data_b.copy()
    
    cases_a['Rate_A'] = (cases_a['服務紀錄(不含自費)'] / cases_a['照管金額分配額度'].replace(0, 1) * 100)
    cases_b['Rate_B'] = (cases_b['服務紀錄(不含自費)'] / cases_b['照管金額分配額度'].replace(0, 1) * 100)
    
    # Merge on Agency (needed if 'All'), Staff and Case
    # Grouping key should be unique. [Agency, Staff, Case]
    
    merged_cases = pd.merge(
        cases_a[['機構', '主責人員', '個案', 'Rate_A', '服務紀錄(不含自費)']],
        cases_b[['機構', '主責人員', '個案', 'Rate_B', '服務紀錄(不含自費)']],
        on=['機構', '主責人員', '個案'],
        how='outer',
        suffixes=('_A', '_B')
    )
    
    # Fill NA for calculation (0 means didn't exist or 0 usage)
    merged_cases['Rate_A_Fill'] = merged_cases['Rate_A'].fillna(0)
    merged_cases['Rate_B_Fill'] = merged_cases['Rate_B'].fillna(0)
    
    merged_cases['差異(%)'] = merged_cases['Rate_B_Fill'] - merged_cases['Rate_A_Fill']
    merged_cases['狀態'] = merged_cases.apply(
        lambda x: '🆕 新案' if pd.isna(x['Rate_A']) else ('❌ 結案/中斷' if pd.isna(x['Rate_B']) else '服務中'), 
        axis=1
    )
    
    # Scatter Plot: Rate A vs Rate B
    # Only for common cases to avoid clutter at 0 axes
    common_cases = merged_cases[merged_cases['狀態'] == '服務中']
    
    if not common_cases.empty:
        col_growth, col_decline = st.columns(2)
        
        with col_growth:
            st.markdown("#### 🏆 變化幅度排行 (Top 10 成長)")
            top_growth = common_cases.sort_values('差異(%)', ascending=False).head(10)
            st.dataframe(
                top_growth[['機構', '主責人員', '個案', 'Rate_A', 'Rate_B', '差異(%)']]
                .style.format({'Rate_A': '{:.1f}%', 'Rate_B': '{:.1f}%', '差異(%)': '{:+.1f}%'})
                .background_gradient(subset=['差異(%)'], cmap='Greens')
            )
            
        with col_decline:
            st.markdown("#### 📉 變化幅度排行 (Top 10 衰退)")
            top_decline = common_cases.sort_values('差異(%)', ascending=True).head(10)
            st.dataframe(
                top_decline[['機構', '主責人員', '個案', 'Rate_A', 'Rate_B', '差異(%)']]
                .style.format({'Rate_A': '{:.1f}%', 'Rate_B': '{:.1f}%', '差異(%)': '{:+.1f}%'})
                .background_gradient(subset=['差異(%)'], cmap='Reds_r')
            )
    else:
        st.info("在此範圍內，兩期間無共同服務個案。")


def page_a_unit_analysis(agg_df):
    st.header("🔗A 單位關聯分析")
    
    # Filters
    col1, col2 = st.columns(2)
    months = sorted(agg_df['月份'].unique())
    with col1:
        selected_month = st.selectbox("選擇月份", months, index=len(months)-1 if months else 0, key='a_unit_month')
    
    agencies = sorted(agg_df['機構'].unique())
    with col2:
        selected_agency = st.selectbox("選擇機構", ["全部"] + list(agencies), key='a_unit_agency')
        
    # Theme is now global in sidebar, accessed via st.session_state
    quota_color = st.session_state.theme_primary
    usage_color = st.session_state.theme_secondary
        
    # Filter Data
    df_used = agg_df[agg_df['月份'] == selected_month].copy()
    if selected_agency != "全部":
        df_used = df_used[df_used['機構'] == selected_agency]
        
    # Aggregation by A Unit
    # Check if '主單A單位' exists (it should based on load_data)
    if '主單A單位' not in df_used.columns:
         st.error("資料中缺少 '主單A單位' 欄位，無法進行分析。")
         return

    # Calculate individual case rates first for distribution analysis
    df_used['Rate'] = (df_used['服務紀錄(不含自費)'] / df_used['照管金額分配額度'].replace(0, 1) * 100)
    
    # Group by A Unit
    a_unit_stats = df_used.groupby('主單A單位').agg({
        '個案': 'nunique', # nunique for accurate case count
        '照管金額分配額度': 'mean',
        '給付額度': 'mean', # Add Benefit Amount
        'Rate': 'mean',
        '服務紀錄(不含自費)': 'mean' 
    }).reset_index().rename(columns={
        '個案': '個案數',
        '照管金額分配額度': '平均核定額度',
        '給付額度': '平均給付額度',
        'Rate': '平均使用率(%)',
    })
    
    # Calculate Gaps
    a_unit_stats['平均額度差距'] = (a_unit_stats['平均給付額度'] - a_unit_stats['平均核定額度'])
    a_unit_stats['平均分配率(%)'] = (a_unit_stats['平均核定額度'] / a_unit_stats['平均給付額度'].replace(0, 1) * 100)
    
    a_unit_stats['平均使用率(%)'] = a_unit_stats['平均使用率(%)'].round(1)
    a_unit_stats['平均核定額度'] = a_unit_stats['平均核定額度'].round(0)
    
    # Overview Metrics
    total_units = len(a_unit_stats)
    max_quota_unit = a_unit_stats.loc[a_unit_stats['平均核定額度'].idxmax()] if not a_unit_stats.empty else None
    max_rate_unit = a_unit_stats.loc[a_unit_stats['平均使用率(%)'].idxmax()] if not a_unit_stats.empty else None
    
    
    def shorten_name(name):
        # Common prefixes to strip for cleaner display
        prefixes = ["社團法人", "財團法人", "有限責任", "台南市", "臺南市", "私立"]
        short_name = name
        for p in prefixes:
            short_name = short_name.replace(p, "")
        # Truncate if still too long
        if len(short_name) > 10:
            return short_name[:10] + "..."
        return short_name

    st.markdown("### 📊 概況總覽")
    m1, m2, m3 = st.columns(3)
    m1.metric("合作 A 單位數量", total_units)
    if max_quota_unit is not None:
        full_name = max_quota_unit['主單A單位']
        clean_name = full_name
        for p in ["社團法人", "財團法人", "有限責任", "台南市", "臺南市", "私立"]:
            clean_name = clean_name.replace(p, "")
            
        m2.markdown(f"""
        <div style="padding: 0px 0px 10px 0px;">
            <p style="margin-bottom: 0px; font-size: 0.8rem; color: #666;">最高平均額度單位</p>
            <p style="margin: 0px; font-size: 1.1rem; font-weight: 600; line-height: 1.4; min-height: 3rem;">{clean_name}</p>
            <p style="margin: 0px; font-size: 1rem; color: #09ab3b;">
                ${max_quota_unit['平均核定額度']:,.0f} 
                <span style="font-size: 0.8rem; color: #666;">(平均額度)</span>
            </p>
        </div>
        """, unsafe_allow_html=True)

    if max_rate_unit is not None:
        full_name = max_rate_unit['主單A單位']
        clean_name = full_name
        for p in ["社團法人", "財團法人", "有限責任", "台南市", "臺南市", "私立"]:
            clean_name = clean_name.replace(p, "")
            
        m3.markdown(f"""
        <div style="padding: 0px 0px 10px 0px;">
            <p style="margin-bottom: 0px; font-size: 0.8rem; color: #666;">最高使用率單位</p>
            <p style="margin: 0px; font-size: 1.1rem; font-weight: 600; line-height: 1.4; min-height: 3rem;">{clean_name}</p>
            <p style="margin: 0px; font-size: 1rem; color: #09ab3b;">
                {max_rate_unit['平均使用率(%)']:.1f}%
                <span style="font-size: 0.8rem; color: #666;">(平均使用率(%))</span>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("---")
    
    # Charts
    # Chart 1: Average Quota
    st.subheader("💰 各 A 單位平均核定額度比較")
    # Sort by Quota
    top_quota = a_unit_stats.sort_values('平均核定額度', ascending=True) # Asc for horizontal bar
    fig_quota = px.bar(
        top_quota, 
        x='平均核定額度', 
        y='主單A單位', 
        orientation='h',
        text_auto='.2s',
        title='平均核定額度排名',
        color='平均使用率(%)', # Color by usage rate to see correlation
        color_continuous_scale=quota_color # Use selected theme
    )
    # Increase height for readability since we have more width now
    fig_quota.update_layout(height=max(400, len(top_quota) * 25))
    st.plotly_chart(fig_quota, use_container_width=True)
    
    st.markdown("---")

    # Chart 2: Average Usage Rate
    st.subheader("📈 各 A 單位平均使用率比較")
    # Sort by Rate
    top_rate = a_unit_stats.sort_values('平均使用率(%)', ascending=True)
    fig_rate = px.bar(
        top_rate, 
        x='平均使用率(%)', 
        y='主單A單位', 
        orientation='h',
        text_auto='.1f',
        title='平均使用率排名',
        color='平均核定額度',
        color_continuous_scale=usage_color # Use selected theme
    )
    fig_rate.add_vline(x=53, line_dash="dash", line_color="red", annotation_text="警示 53%")
    # Increase height for readability
    fig_rate.update_layout(height=max(400, len(top_rate) * 25))
    st.plotly_chart(fig_rate, use_container_width=True)
    
    st.markdown("---")
    
    # Chart 3: Benefit vs Allocation Gap (New)
    st.subheader("⚖️ 給付額度 vs. 分配額度 差異分析")
    with st.expander("💡 如何解讀這張圖表？ (點擊展開)"):
        st.markdown("""
        **這張圖表協助您判斷 A 單位在核定個案額度時，是傾向「給好給滿 (大方)」還是「有所保留 (保守)」。**
        
        #### **1. 看棒子的長度 (平均額度差距)**
        *   **代表意義**：政府給的上限 (CMS給付額度) 減去 實際核定的額度。也就是「沒用完而被保留下來的額度空間」。
        *   **棒子越長 (數值大)**：代表差距越大，保留空間多，**判定較為「保守」或「嚴格」**。
        *   **棒子越短 (數值小)**：代表差距越小，額度給得很滿，**判定較為「大方」或「寬鬆」**。

        #### **2. 看顏色深淺 (平均分配率 %)**
        *(註：顏色深淺依據您選擇的主題而定，通常深色代表數值高)*
        *   **顏色越深 (分配率高)**：代表給的額度很接近上限 (例 >80%) 👉 **大方**。
        *   **顏色越淺 (分配率低)**：代表給的額度離上限很遠 (例 <60%) 👉 **保守**。

        ---
        **⚡ 快速結論：**
        *   想找**最嚴格 (省錢)** 的單位 ➡ 找 **棒子最長** 且 **顏色最淺** 的。
        *   想找**最大方 (給滿)** 的單位 ➡ 找 **棒子最短** 且 **顏色最深** 的。
        
        **公式**：`平均分配率(%) = (平均核定額度 / 平均給付額度) * 100%`
        """)
    
    # Filter out units with 0 Benefit Amount (if data missing)
    gap_data = a_unit_stats[a_unit_stats['平均給付額度'] > 0].sort_values('平均額度差距', ascending=True)
    
    if not gap_data.empty:
        fig_gap = px.bar(
            gap_data,
            x='平均額度差距',
            y='主單A單位',
            orientation='h',
            text_auto='$,.0f',
            title='各 A 單位平均額度保留空間 (給付額度 - 核定額度)',
            color='平均分配率(%)', # Color by % allocated
            color_continuous_scale=st.session_state.theme_secondary # Use secondary theme
        )
        fig_gap.update_layout(height=max(400, len(gap_data) * 25))
        st.plotly_chart(fig_gap, use_container_width=True)
    else:
        st.info("無法顯示差異分析，請確認資料中是否包含有效的「給付額度 (CMS額度)」數據。")

    st.markdown("---")

    # Metrics Table (Enhanced)
    st.subheader("額度與使用率關聯分佈 (詳細數據)")
    
    styled_df = (
        a_unit_stats[['主單A單位', '個案數', '平均給付額度', '平均核定額度', '平均額度差距', '平均分配率(%)', '平均使用率(%)']]
        .sort_values('平均額度差距', ascending=False)
        .set_index('主單A單位')
        .style
        .format({
            '平均給付額度': '${:,.0f}',
            '平均核定額度': '${:,.0f}', 
            '平均額度差距': '${:,.0f}',
            '平均分配率(%)': '{:.1f}%',
            '平均使用率(%)': '{:.1f}%'
        })
        .background_gradient(subset=['平均核定額度'], cmap=quota_color) 
        .background_gradient(subset=['平均額度差距'], cmap='Reds') 
        .background_gradient(subset=['平均使用率(%)'], cmap=usage_color)
    )
    
    st.dataframe(styled_df, use_container_width=True, height=500)
    
    with st.expander("查看原始數據"):
        st.dataframe(a_unit_stats)

def page_region_analysis(agg_df):
    st.header("🗺️ 區域與狀態分析")
    
    # Filters
    col1, col2 = st.columns(2)
    months = sorted(agg_df['月份'].unique())
    with col1:
        selected_month = st.selectbox("選擇月份", months, index=len(months)-1 if months else 0, key='region_month')
    
    agencies = sorted(agg_df['機構'].unique())
    with col2:
        selected_agency = st.selectbox("選擇機構", ["全部"] + list(agencies), key='region_agency')
        
    # Theme
    theme_primary = st.session_state.theme_primary
    
    # Filter Data
    df_filtered = agg_df[agg_df['月份'] == selected_month].copy()
    if selected_agency != "全部":
        df_filtered = df_filtered[df_filtered['機構'] == selected_agency]
        
    if df_filtered.empty:
        st.warning("查無資料")
        return

    st.markdown("---")
    
    # Check for Region column
    if '區域' not in df_filtered.columns or df_filtered['區域'].isnull().all():
        st.error("資料中缺少 '區域' 欄位或內容為空，無法進行區域分析。")
    else:
        # 1. Region Analysis
        st.subheader("📍 各區域個案人數統計")
        
        region_stats = df_filtered.groupby('區域')['個案'].nunique().reset_index()
        region_stats.columns = ['區域', '個案人數']
        region_stats = region_stats.sort_values('個案人數', ascending=False)
        
        col_chart, col_table = st.columns([2, 1])
        
        with col_chart:
            fig_region = px.bar(
                region_stats,
                x='區域',
                y='個案人數',
                text='個案人數',
                title=f'{selected_month}月 各區域個案分佈',
                color='個案人數',
                color_continuous_scale=theme_primary
            )
            fig_region.update_traces(textposition='outside', width=0.5)
            st.plotly_chart(fig_region, use_container_width=True)
            
        with col_table:
            st.write("區域分佈詳情")
            region_stats['佔比(%)'] = (region_stats['個案人數'] / region_stats['個案人數'].sum() * 100).map('{:.1f}%'.format)
            st.dataframe(
                region_stats.set_index('區域').style.background_gradient(subset=['個案人數'], cmap=theme_primary),
                use_container_width=True
            )
            
    st.markdown("---")

    st.markdown("---")

    # 2. Service Status Analysis
    st.subheader("📊 服務使用狀態統計")
    
    # Analyze Status - Standardize to 3 categories
    def categorize_status(status):
        s = str(status)
        if s.startswith("暫停"):
            return "暫停"
        elif s.startswith("結案"):
            return "結案"
        elif s.startswith("服務中"):
            return "服務中"
        return s # Fallback for others (e.g. Unknown)

    df_filtered['狀態分類'] = df_filtered['服務使用狀態'].apply(categorize_status)
    
    status_stats = df_filtered.groupby('狀態分類')['個案'].nunique().reset_index()
    status_stats.columns = ['服務使用狀態', '個案人數']
    status_stats = status_stats.sort_values('個案人數', ascending=False)
    
    col_status_chart, col_status_table = st.columns([1, 1])
    
    with col_status_chart:
        fig_status = px.pie(
            status_stats,
            names='服務使用狀態',
            values='個案人數',
            title=f'{selected_month}月 服務狀態佔比',
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.RdBu 
        )
        st.plotly_chart(fig_status, use_container_width=True)
        
    with col_status_table:
        st.write("狀態分佈詳情")
        status_stats['佔比(%)'] = (status_stats['個案人數'] / status_stats['個案人數'].sum() * 100).map('{:.1f}%'.format)
        
        st.dataframe(
            status_stats.set_index('服務使用狀態'),
            use_container_width=True
        )


if __name__ == "__main__":
    main()
