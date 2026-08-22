"""
app.py — Dashboard de Seguimiento de Cartera S&P 500 (SPY / CEDEARs).

Integración con Supabase para persistencia de transacciones de compra.

Ejecutar con:
    streamlit run app.py

Requisitos previos:
    1. Configurar .streamlit/secrets.toml (ver ejemplo en ese archivo).
    2. Crear la tabla `transacciones` en Supabase (ver db.py → SQL_CREATE_TABLE).
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import time

from utils import (
    COLORS,
    CUSTOM_CSS,
    TICKER_SPY,
    TICKER_QQQ,
    ASSET_CONFIG,
    CEDEAR_RATIO_SPY,
    fetch_spy_data,
    fetch_qqq_data,
    fetch_current_price,
    fetch_qqq_current_price,
    fetch_exchange_rate,
    fetch_spy_usd_price,
    fetch_qqq_usd_price,
    calculate_ccl,
    is_market_open,
    calculate_portfolio_metrics,
    calculate_consolidated_metrics,
    calculate_daily_change,
    calculate_dca_projection,
    calculate_custom_projection,
    build_custom_projection_chart,
    build_allocation_chart,
    fmt_usd,
    fmt_ars,
    fmt_pct,
    fmt_change,
    fmt_date,
    build_candlestick_chart,
    build_dca_chart,
    build_dca_comparison_chart,
    calculate_cagr,
    get_cagr_benchmarks,
)
from db import (
    get_supabase_client,
    fetch_transactions,
    fetch_all_transactions,
    insert_transaction,
    delete_transaction,
    calculate_ppc,
    get_create_table_sql,
)


def fmt_number_input(label, fmt_func, **kwargs):
    """Wrapper around st.number_input that adds a formatted caption below."""
    value = st.number_input(label, **kwargs)
    st.caption(fmt_func(value))
    return value


# ===========================================================================
# Configuración de la página
# ===========================================================================

st.set_page_config(
    page_title="Cocos Broker — S&P 500 Dashboard",
    page_icon="🥥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inyectar CSS personalizado
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ===========================================================================
# Sidebar — Estado de Supabase + Configuración
# ===========================================================================

def render_sidebar() -> dict:
    """
    Renderiza la barra lateral:
        - Estado de conexión a Supabase
        - Métricas de SPY y QQQ por separado
        - Override manual del tipo de cambio

    Returns:
        Diccionario con datos resueltos para la app principal.
    """
    # -- Verificar conexión a Supabase --
    client = get_supabase_client()
    connected = client is not None

    with st.sidebar:
        st.markdown("## 💼 Mi Cartera")
        st.markdown("---")

        # -- Estado de conexión --
        if connected:
            st.markdown(
                "<span class='status-pulse'></span> "
                f"<span style='color:{COLORS['gain']}; font-size:0.8rem;'>"
                "Conectado a Supabase"
                "</span>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<span style='color:{COLORS['loss']}; font-size:0.8rem;'>"
                "🔴 Sin conexión a Supabase"
                "</span>",
                unsafe_allow_html=True,
            )
            st.info(
                "Verificá `.streamlit/secrets.toml` o las variables de entorno "
                "`SUPABASE_URL` y `SUPABASE_KEY`."
            )

        st.markdown("---")

        # -- Consultar transacciones por activo --
        spy_transactions = fetch_transactions(ticker="SPY") if connected else []
        qqq_transactions = fetch_transactions(ticker="QQQ") if connected else []
        spy_ppc = calculate_ppc(spy_transactions)
        qqq_ppc = calculate_ppc(qqq_transactions)

        # -- Mostrar posiciones por activo --
        for ticker_label, ppc_data, color in [
            ("SPY (S&P 500)", spy_ppc, "#3D85C6"),
            ("QQQ (Nasdaq 100)", qqq_ppc, "#9B59B6"),
        ]:
            tx_count = ppc_data["transaction_count"]
            if tx_count > 0:
                st.markdown(
                    f"<span style='color:{color}; font-weight:600; font-size:0.95rem;'>"
                    f"{ticker_label}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"""
                    <div style="background-color:{COLORS['bg_main']}; border-radius:10px;
                                padding:12px; margin-bottom:8px; border:1px solid {COLORS['border']};">
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="color:{COLORS['text_secondary']}; font-size:0.75rem;">Unidades</span>
                            <span style="color:{COLORS['text_primary']}; font-weight:700;">{ppc_data['total_shares']:.2f}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                            <span style="color:{COLORS['text_secondary']}; font-size:0.75rem;">PPC</span>
                            <span style="color:{color}; font-weight:600; font-size:0.9rem;">{fmt_ars(ppc_data['ppc_ars'])}</span>
                        </div>
                        <div style="display:flex; justify-content:space-between;">
                            <span style="color:{COLORS['text_secondary']}; font-size:0.75rem;">Costo Total</span>
                            <span style="color:{COLORS['text_primary']}; font-weight:600;">{fmt_ars(ppc_data['total_cost_ars'])}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f"<span style='color:{COLORS['text_secondary']}; font-size:0.75rem;'>"
                    f"📋 {tx_count} transaccion{'es' if tx_count != 1 else ''}</span>",
                    unsafe_allow_html=True,
                )
                st.markdown("")

        # Si no hay transacciones de ningún activo
        if spy_ppc["transaction_count"] == 0 and qqq_ppc["transaction_count"] == 0:
            st.warning(
                "Sin transacciones registradas. "
                "Usá la pestaña **➕ Nueva Compra** para agregar la primera."
            )

        st.markdown("---")

        # -- Tipo de cambio manual --
        st.markdown("### 💱 Tipo de Cambio")
        manual_rate = st.number_input(
            "Tipo de cambio manual (USD/ARS)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            format="%.0f",
            help="Dejar en 0 para usar el tipo de cambio de mercado.",
        )

        st.markdown("---")
        st.markdown(
            f"<span style='color:{COLORS['text_secondary']}; font-size:0.75rem;'>"
            f"💡 Datos: **yfinance** · Persistencia: **Supabase**"
            f"</span>",
            unsafe_allow_html=True,
        )

    return {
        "connected": connected,
        "spy_transactions": spy_transactions,
        "qqq_transactions": qqq_transactions,
        "spy_ppc": spy_ppc,
        "qqq_ppc": qqq_ppc,
        "manual_rate": manual_rate,
    }


# ===========================================================================
# Componentes de UI — KPI Cards
# ===========================================================================

def render_kpi_cards(metrics: dict, daily_change: dict, display: str, exchange_rate: float = 1.0, asset_label: str = "SPY") -> None:
    """
    Renderiza las tarjetas de métricas clave (KPIs).

    Args:
        metrics:      Diccionario con métricas de la cartera.
        daily_change: Diccionario con variación diaria (en ARS).
        display:      Moneda de visualización ('USD' o 'ARS').
        exchange_rate: Tipo de cambio USD/ARS para convertir variación diaria.
    """
    if display == "USD":
        price_str = fmt_usd(metrics["current_price_usd"])
        value_str = fmt_usd(metrics["total_value_usd"])
        cost_str = fmt_usd(metrics["total_cost_usd"])
        pnl_str = fmt_usd(metrics["pnl_usd"])
        chg_abs_usd = daily_change["abs"] / exchange_rate if exchange_rate else 0
        chg_str = fmt_change(chg_abs_usd)
    else:
        price_str = fmt_ars(metrics["current_price_ars"])
        value_str = fmt_ars(metrics["total_value_ars"])
        cost_str = fmt_ars(metrics["total_cost_ars"])
        pnl_str = fmt_ars(metrics["pnl_ars"])
        chg_str = fmt_change(daily_change["abs"])

    pnl = metrics["pnl_pct"]
    pnl_class = "positive" if pnl >= 0 else "negative"
    daily_class = "positive" if daily_change["pct"] >= 0 else "negative"
    pnl_icon = "▲" if pnl >= 0 else "▼"
    daily_sign = "+" if daily_change["pct"] >= 0 else ""

    cols = st.columns(4)

    with cols[0]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Precio Actual {asset_label}</div>
                <div class="kpi-value">{price_str}</div>
                <div class="kpi-sub {daily_class}">
                    {daily_sign}{fmt_pct(daily_change['pct'])} · {chg_str} {display}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[1]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Valor Total Posición</div>
                <div class="kpi-value">{value_str}</div>
                <div class="kpi-sub neutral">
                    Costo: {cost_str}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[2]:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Ganancia / Pérdida</div>
                <div class="kpi-value {pnl_class}">{pnl_str}</div>
                <div class="kpi-sub {pnl_class}">
                    {pnl_icon} {fmt_pct(pnl)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[3]:
        # Mostrar CCL como tipo de referencia
        ccl_val = metrics.get("ccl_rate", 0)
        rate_display = fmt_ars(ccl_val) if ccl_val else "N/D"
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Dólar CCL</div>
                <div class="kpi-value" style="font-size:1.5rem;">{rate_display}</div>
                <div class="kpi-sub neutral">
                    PPC: {fmt_usd(metrics['avg_price_usd'])} / unidad
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ===========================================================================
# Componentes de UI — Formulario de Nueva Compra
# ===========================================================================

def render_purchase_form(spy_price: float = 20000.0, qqq_price: float = 20000.0) -> None:
    """Renderiza el formulario para registrar una nueva compra.

    Args:
        spy_price: Precio actual de mercado de SPY.BA en ARS.
        qqq_price: Precio actual de mercado de QQQ.BA en ARS.
    """
    st.markdown(
        '<div class="section-header">➕ Registrar Nueva Compra</div>',
        unsafe_allow_html=True,
    )

    client = get_supabase_client()
    if client is None:
        st.error(
            "No hay conexión a Supabase. No se pueden registrar compras."
        )
        st.code(get_create_table_sql(), language="sql")
        return

    st.markdown(
        f"""
        <p style="color:{COLORS['text_secondary']}; font-size:0.9rem; margin-bottom:20px;">
        Seleccioná el activo, completá los datos y registrá la operación.
        El precio se carga automáticamente desde el mercado.
        </p>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        activo_seleccionado = st.selectbox(
            "Activo *",
            options=["SPY (S&P 500)", "QQQ (Nasdaq 100)"],
            key="select_activo_compra",
        )

        if "QQQ" in activo_seleccionado:
            ticker_option = "QQQ"
            ticker_local = "QQQ.BA"
            precio_defecto = float(qqq_price)
        else:
            ticker_option = "SPY"
            ticker_local = "SPY.BA"
            precio_defecto = float(spy_price)

        ticker_byma = ticker_local

        cantidad = st.number_input(
            "Cantidad de unidades *",
            min_value=1,
            value=1,
            step=1,
            format="%d",
            help="Número de acciones o CEDEARs comprados.",
            key="input_cantidad",
        )
        fecha = st.date_input(
            "Fecha de compra *",
            value=date.today(),
            max_value=date.today(),
            help="Fecha en que se realizó la operación.",
            key="input_fecha",
        )

    with col2:
        precio = fmt_number_input(
            f"Precio unitario (ARS) — {ticker_local} *",
            fmt_ars,
            value=precio_defecto,
            min_value=0.0,
            step=10.0,
            format="%.2f",
            key=f"input_precio_{ticker_option}",
            help=f"Precio actual de mercado: {fmt_ars(precio_defecto)}. Editá si compraste a otro precio.",
        )
        notas = st.text_area(
            "Notas (opcional)",
            value="",
            height=108,
            max_chars=500,
            placeholder="Ej: Compra en Balanz, precio incluye comisión...",
            key="input_notas",
        )

    # -- Previsualización en tiempo real --
    total_operacion = float(cantidad) * float(precio)
    total_ars_fmt = fmt_ars(total_operacion)
    st.markdown(
        f"""
        <div style="background-color:{COLORS['bg_main']}; border-radius:8px;
                    padding:12px 16px; margin-top:4px;
                    border:1px solid {COLORS['border']};">
            <span style="color:{COLORS['text_secondary']}; font-size:0.8rem;">
                Total operación:
            </span>
            <span style="color:{COLORS['text_primary']}; font-size:1.1rem;
                        font-weight:700; margin-left:8px;">
                {total_ars_fmt}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")

    submitted = st.button(
        "💾 Registrar Compra",
        use_container_width=True,
        type="primary",
    )

    if submitted:
        # -- Validaciones --
        if cantidad <= 0:
            st.error("La cantidad debe ser mayor a 0.")
        elif precio <= 0:
            st.error("El precio debe ser mayor a 0.")
        else:
            total_operacion = float(cantidad) * float(precio)
            result = insert_transaction(
                ticker=ticker_option,
                cantidad=int(cantidad),
                precio_unitario_ars=float(precio),
                fecha=fecha,
                notas=notas,
                monto_total_ars=total_operacion,
            )
            if result:
                st.success(
                    f"✅ ¡Compra de {cantidad} unidades de {ticker_option} "
                    f"registrada correctamente en Supabase!"
                )
                st.toast(
                    f"🎉 Portafolio actualizado: +{cantidad} unidades de {ticker_byma}",
                    icon="🥥",
                )
                st.balloons()
                # Limpiar campos del formulario
                for key in ["input_ticker_select", "input_cantidad", "input_precio_unitario", "input_notas"]:
                    if key in st.session_state:
                        del st.session_state[key]
                # Limpiar caché y recargar estado para actualizar métricas en toda la app
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()


# ===========================================================================
# Componentes de UI — Historial de Transacciones
# ===========================================================================

def render_transaction_history(spy_transactions: list[dict], qqq_transactions: list[dict] = None) -> None:
    """
    Renderiza el historial completo de compras registradas (multi-asset).

    Args:
        spy_transactions: Lista de transacciones SPY desde Supabase.
        qqq_transactions: Lista de transacciones QQQ desde Supabase.
    """
    st.markdown(
        '<div class="section-header">📜 Historial de Compras</div>',
        unsafe_allow_html=True,
    )

    # Combinar transacciones de ambos activos
    transactions = list(spy_transactions or [])
    if qqq_transactions:
        transactions.extend(qqq_transactions)

    if not transactions:
        st.info(
            "No hay transacciones registradas aún. "
            "Usá la pestaña **➕ Nueva Compra** para agregar la primera."
        )
        return

    # -- Resumen rapido por activo --
    for label, txs, color in [
        ("SPY", spy_transactions or [], "#3D85C6"),
        ("QQQ", qqq_transactions or [], "#9B59B6"),
    ]:
        if not txs:
            continue
        ppc_data = calculate_ppc(txs)
        st.markdown(
            f"<span style='color:{color}; font-weight:600;'>{label}</span>",
            unsafe_allow_html=True,
        )
        res_col1, res_col2, res_col3 = st.columns(3)
        with res_col1:
            st.metric("Unidades", f"{ppc_data['total_shares']:.2f}")
        with res_col2:
            st.metric("PPC (ARS)", fmt_ars(ppc_data["ppc_ars"]))
        with res_col3:
            st.metric("Costo Total", fmt_ars(ppc_data["total_cost_ars"]))

    st.markdown("")

    # -- Construir DataFrame para mostrar --
    df_history = pd.DataFrame(transactions)

    # Seleccionar y renombrar columnas para presentación
    display_cols = {
        "fecha": "Fecha",
        "ticker": "Ticker",
        "cantidad": "Cantidad",
        "precio_unitario_ars": "Precio Unit. (ARS)",
        "notas": "Notas",
        "id": "ID",
    }

    # Filtrar solo columnas que existen
    cols_to_show = [c for c in display_cols if c in df_history.columns]
    df_display = df_history[cols_to_show].copy()

    # Formatear columnas numéricas y de fecha
    if "precio_unitario_ars" in df_display.columns:
        df_display["precio_unitario_ars"] = df_display["precio_unitario_ars"].apply(
            lambda x: f"${float(x):,.2f}"
        )
    if "cantidad" in df_display.columns:
        df_display["cantidad"] = df_display["cantidad"].apply(
            lambda x: f"{float(x):.4f}"
        )
    if "fecha" in df_display.columns:
        df_display["fecha"] = df_display["fecha"].apply(fmt_date)
    if "notas" in df_display.columns:
        df_display["notas"] = df_display["notas"].fillna("—").replace("", "—")

    # Agregar columna de sub-total
    if "cantidad" in df_history.columns and "precio_unitario_ars" in df_history.columns:
        df_display["Subtotal (ARS)"] = df_history.apply(
            lambda row: fmt_ars(float(row["cantidad"]) * float(row["precio_unitario_ars"])),
            axis=1,
        )

    # Renombrar columnas visibles
    rename_map = {k: v for k, v in display_cols.items() if k in df_display.columns}
    # Mantener ID oculto para la lógica de eliminación
    df_display = df_display.rename(columns=rename_map)

    # -- Tabla de datos --
    st.dataframe(
        df_display.drop(columns=["ID"], errors="ignore"),
        use_container_width=True,
        hide_index=True,
    )

    # -- Eliminar transacción --
    st.markdown("---")
    st.markdown(
        f"<span style='color:{COLORS['text_secondary']}; font-size:0.85rem; "
        f"font-weight:500;'>🗑️ Eliminar una transacción</span>",
        unsafe_allow_html=True,
    )

    # Selector de transacción a eliminar
    tx_options = []
    for tx in transactions:
        label = (
            f"{fmt_date(tx.get('fecha', ''))} · "
            f"{tx.get('ticker', '?')} · "
            f"{tx.get('cantidad', 0)} u × {fmt_ars(float(tx.get('precio_unitario_ars', 0)))}"
        )
        tx_options.append({"label": label, "id": tx["id"]})

    selected_tx = st.selectbox(
        "Seleccioná la transacción a eliminar",
        options=range(len(tx_options)),
        format_func=lambda i: tx_options[i]["label"],
        key="delete_selector",
    )

    confirm_delete = st.checkbox(
        "Confirmo que deseo eliminar esta transacción",
        key="confirm_delete",
    )

    if st.button("🗑️ Eliminar Transacción", type="secondary"):
        if not confirm_delete:
            st.warning("Marcá la casilla de confirmación primero.")
        else:
            tx_id = tx_options[selected_tx]["id"]
            success = delete_transaction(tx_id)
            if success:
                st.success("Transacción eliminada correctamente.")
                st.cache_data.clear()
                st.rerun()


# ===========================================================================
# Componentes de UI — Gráficos Interactivos
# ===========================================================================

def render_charts_section(df: pd.DataFrame) -> None:
    """Renderiza la sección de gráficos interactivos."""
    st.markdown(
        '<div class="section-header">📈 Análisis Técnico</div>',
        unsafe_allow_html=True,
    )

    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 2, 2])
    with ctrl_col1:
        period_options = {
            "1 Mes": "1mo",
            "6 Meses": "6mo",
            "1 Año": "1y",
            "5 Años": "5y",
        }
        period_label = st.selectbox(
            "Rango temporal",
            options=list(period_options.keys()),
            index=2,
            key="chart_period",
        )
    with ctrl_col2:
        show_sma50 = st.checkbox("SMA 50", value=True, key="sma50")
        show_sma200 = st.checkbox("SMA 200", value=True, key="sma200")
    with ctrl_col3:
        show_volume = st.checkbox("Volumen", value=True, key="vol")

    period_map = {"1 Mes": "1mo", "6 Meses": "6mo", "1 Año": "1y", "5 Años": "5y"}
    selected_period = period_map[period_label]
    df_filtered = _filter_df_by_period(df, selected_period)

    if df_filtered is not None and not df_filtered.empty:
        fig = build_candlestick_chart(
            df_filtered,
            show_sma50=show_sma50,
            show_sma200=show_sma200,
            show_volume=show_volume,
        )
        st.plotly_chart(fig, use_container_width=True, config={
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
        })
    else:
        st.warning("No hay datos disponibles para el período seleccionado.")


def _filter_df_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Filtra el DataFrame según el período seleccionado."""
    delta_map = {
        "1mo": timedelta(days=35),
        "6mo": timedelta(days=185),
        "1y": timedelta(days=370),
        "5y": timedelta(days=1830),
    }
    now = df.index.max()
    start = now - delta_map.get(period, timedelta(days=365))
    return df[df.index >= start]


# ===========================================================================
# Componentes de UI — Calculadora DCA
# ===========================================================================

def render_dca_section(
    metrics: dict,
    display_currency: str = "USD",
    spy_ppc: dict = None,
    qqq_ppc: dict = None,
    exchange_rate: float = 1.0,
    spy_usd_price: float = 0.0,
    qqq_usd_price: float = 0.0,
    spy_ars_price: float = 0.0,
    qqq_ars_price: float = 0.0,
) -> None:
    """Renderiza la pestaña de calculadora DCA / Proyección.

    Args:
        metrics:          Diccionario con métricas de la cartera.
        display_currency: Moneda de visualización ('USD' o 'ARS').
        spy_ppc:          Datos PPC de SPY desde la DB.
        qqq_ppc:          Datos PPC de QQQ desde la DB.
        exchange_rate:    Tipo de cambio USD/ARS.
        spy_usd_price:    Precio SPY en USD.
        qqq_usd_price:    Precio QQQ en USD.
        spy_ars_price:    Precio CEDEAR SPY en ARS (local).
        qqq_ars_price:    Precio CEDEAR QQQ en ARS (local).
    """
    # ====================================================================
    # PARTE 1 — Rebalanceo Automático por Flujo de Caja (70/30)
    # ====================================================================
    # Algoritmo inteligente: lee la tenencia real actual y optimiza la
    # distribución del presupuesto mensual para acercar la cartera al
    # objetivo 70% SPY / 30% QQQ (rebalanceo por flujo, sin venta).
    # ====================================================================
    st.markdown(
        '<div class="section-header">Compra Sugerida — Rebalanceo 70/30</div>',
        unsafe_allow_html=True,
    )

    # -- 0. Tenencia actual desde la DB --
    unidades_spy = float(spy_ppc.get("total_shares", 0)) if spy_ppc else 0.0
    unidades_qqq = float(qqq_ppc.get("total_shares", 0)) if qqq_ppc else 0.0

    valor_actual_spy_ars = unidades_spy * spy_ars_price
    valor_actual_qqq_ars = unidades_qqq * qqq_ars_price
    valor_portafolio_actual = valor_actual_spy_ars + valor_actual_qqq_ars

    pct_actual_spy = (valor_actual_spy_ars / valor_portafolio_actual * 100) if valor_portafolio_actual else 0
    pct_actual_qqq = (valor_actual_qqq_ars / valor_portafolio_actual * 100) if valor_portafolio_actual else 0

    # -- 1. Input del presupuesto mensual --
    st.markdown(
        f"""
        <p style="color:{COLORS['text_secondary']}; font-size:0.88rem; margin-bottom:16px;">
        Ingresá tu presupuesto mensual y el sistema calcula la compra óptima
        para equilibrar tu cartera hacia
        <span style="color:#3D85C6; font-weight:600;">SPY (70%)</span> /
        <span style="color:#9B59B6; font-weight:600;">QQQ (30%)</span>
        leyendo tu tenencia real.
        </p>
        """,
        unsafe_allow_html=True,
    )

    budget_col1, budget_col2 = st.columns([1, 2])
    with budget_col1:
        if display_currency == "USD":
            budget = fmt_number_input(
                "Presupuesto Mensual (USD)",
                fmt_usd,
                min_value=0.0,
                value=100.0,
                step=10.0,
                format="%.2f",
                key="dca_budget_usd",
            )
            budget_ars = budget * exchange_rate if exchange_rate else 0
        else:
            budget_ars = fmt_number_input(
                "Presupuesto Mensual (ARS)",
                fmt_ars,
                min_value=0.0,
                value=50000.0,
                step=5000.0,
                format="%.2f",
                key="dca_budget_ars",
            )
            budget = budget_ars / exchange_rate if exchange_rate else 0

    # -- 2. Algoritmo de rebalanceo dinámico --
    if display_currency == "USD":
        fmt_budget_share = fmt_usd
    else:
        fmt_budget_share = fmt_ars

    monto_spy_ars = 0.0
    monto_qqq_ars = 0.0
    cedears_spy = 0
    cedears_qqq = 0
    costo_real_spy = 0.0
    costo_real_qqq = 0.0
    remanente_total = 0.0
    es_rebalanceo = False

    if budget_ars > 0 and spy_ars_price > 0 and qqq_ars_price > 0:
        if valor_portafolio_actual > 0:
            es_rebalanceo = True
            nuevo_patrimonio_total = valor_portafolio_actual + budget_ars
            target_spy_ars = nuevo_patrimonio_total * 0.70
            target_qqq_ars = nuevo_patrimonio_total * 0.30

            deficit_spy = max(0.0, target_spy_ars - valor_actual_spy_ars)
            deficit_qqq = max(0.0, target_qqq_ars - valor_actual_qqq_ars)
            suma_deficits = deficit_spy + deficit_qqq

            if suma_deficits > 0:
                asignar_spy_ars = budget_ars * (deficit_spy / suma_deficits)
                asignar_qqq_ars = budget_ars * (deficit_qqq / suma_deficits)
            else:
                asignar_spy_ars = budget_ars * 0.70
                asignar_qqq_ars = budget_ars * 0.30
        else:
            asignar_spy_ars = budget_ars * 0.70
            asignar_qqq_ars = budget_ars * 0.30

        cedears_spy = int(asignar_spy_ars // spy_ars_price)
        costo_real_spy = cedears_spy * spy_ars_price

        cedears_qqq = int(asignar_qqq_ars // qqq_ars_price)
        costo_real_qqq = cedears_qqq * qqq_ars_price

        monto_spy_ars = asignar_spy_ars
        monto_qqq_ars = asignar_qqq_ars
        remanente_total = budget_ars - (costo_real_spy + costo_real_qqq)

    # -- 3. Tarjetas de Tenencia Actual vs. Objetivo --
    if valor_portafolio_actual > 0:
        st.markdown(
            f'<div style="color:{COLORS["text_secondary"]}; font-size:0.85rem; font-weight:500; margin-bottom:8px;">'
            'Posición Actual vs. Objetivo (70% SPY / 30% QQQ)</div>',
            unsafe_allow_html=True,
        )
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            st.markdown(
                f"""
                <div class="kpi-card" style="border-left:3px solid #3D85C6;">
                    <div class="kpi-label" style="color:#3D85C6;">SPY — Tenencia Actual</div>
                    <div class="kpi-value" style="font-size:1.1rem;">{unidades_spy:.0f} CEDEARs</div>
                    <div class="kpi-sub neutral">{fmt_ars(valor_actual_spy_ars)} ({pct_actual_spy:.1f}%)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with tc2:
            st.markdown(
                f"""
                <div class="kpi-card" style="border-left:3px solid #9B59B6;">
                    <div class="kpi-label" style="color:#9B59B6;">QQQ — Tenencia Actual</div>
                    <div class="kpi-value" style="font-size:1.1rem;">{unidades_qqq:.0f} CEDEARs</div>
                    <div class="kpi-sub neutral">{fmt_ars(valor_actual_qqq_ars)} ({pct_actual_qqq:.1f}%)</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with tc3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Valor Total de Cartera</div>
                    <div class="kpi-value" style="font-size:1.1rem;">{fmt_ars(valor_portafolio_actual)}</div>
                    <div class="kpi-sub neutral">SPY {pct_actual_spy:.1f}% · QQQ {pct_actual_qqq:.1f}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # -- 4. Sugerencia de compra del mes --
    if budget_ars > 0:
        st.markdown("")

        if es_rebalanceo and valor_portafolio_actual > 0:
            drift_spy = abs(pct_actual_spy - 70.0)
            drift_qqq = abs(pct_actual_qqq - 30.0)
            max_drift = max(drift_spy, drift_qqq)
            if pct_actual_spy > 70.0 + 5.0:
                st.info(
                    "Distribución desbalanceada: Asignando mayor proporción a QQQ "
                    "para converger al 30% objetivo."
                )
            elif pct_actual_qqq > 30.0 + 5.0:
                st.info(
                    "Distribución desbalanceada: Asignando mayor proporción a SPY "
                    "para converger al 70% objetivo."
                )
            else:
                st.success("Distribución equilibrada: Manteniendo ratio regular 70/30.")
        else:
            st.info("Primera compra registrada: Distribución base 70/30 aplicada.")

        st.markdown(
            f"""
            <div style="background:{COLORS['bg_card']}; border:1px solid rgba(255,255,255,0.06);
                        border-radius:8px; padding:10px 16px; margin-bottom:12px;
                        font-size:0.82rem; color:{COLORS['text_secondary']}; font-weight:500;">
                Orden de Compra Estimada
            </div>
            """,
            unsafe_allow_html=True,
        )

        dca_c1, dca_c2, dca_c3, dca_c4 = st.columns(4)

        with dca_c1:
            spy_sub = (
                f"≈ {cedears_spy} CEDEARs ({fmt_ars(costo_real_spy)})"
                if cedears_spy > 0
                else f"Faltan {fmt_ars(spy_ars_price - monto_spy_ars)} para 1 unidad"
            ) if monto_spy_ars > 0 and spy_ars_price > 0 else "Sin datos de mercado"
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label" style="color:#3D85C6;">SPY — Asignación Sugerida</div>
                    <div class="kpi-value" style="font-size:1.2rem;">{fmt_budget_share(monto_spy_ars if display_currency == 'ARS' else monto_spy_ars / exchange_rate if exchange_rate else 0)}</div>
                    <div class="kpi-sub neutral">{spy_sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with dca_c2:
            qqq_sub = (
                f"≈ {cedears_qqq} CEDEARs ({fmt_ars(costo_real_qqq)})"
                if cedears_qqq > 0
                else f"Faltan {fmt_ars(qqq_ars_price - monto_qqq_ars)} para 1 unidad"
            ) if monto_qqq_ars > 0 and qqq_ars_price > 0 else "Sin datos de mercado"
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label" style="color:#9B59B6;">QQQ — Asignación Sugerida</div>
                    <div class="kpi-value" style="font-size:1.2rem;">{fmt_budget_share(monto_qqq_ars if display_currency == 'ARS' else monto_qqq_ars / exchange_rate if exchange_rate else 0)}</div>
                    <div class="kpi-sub neutral">{qqq_sub}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with dca_c3:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Precio de Mercado — SPY (BYMA)</div>
                    <div class="kpi-value" style="font-size:1.2rem;">{fmt_ars(spy_ars_price)}</div>
                    <div class="kpi-sub neutral">BYMA</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with dca_c4:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Precio de Mercado — QQQ (BYMA)</div>
                    <div class="kpi-value" style="font-size:1.2rem;">{fmt_ars(qqq_ars_price)}</div>
                    <div class="kpi-sub neutral">BYMA</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # -- Remanente por indivisibilidad --
        if remanente_total > 0:
            remanente_fmt = fmt_ars(remanente_total)
            st.markdown(
                f"""
                <div style="background:{COLORS['bg_card']}; border:1px solid rgba(255,255,255,0.06);
                            border-radius:8px; padding:10px 16px; margin-top:8px;
                            font-size:0.82rem; color:{COLORS['text_secondary']};">
                    <span style="font-weight:500;">Remanente líquido no asignado:</span> {remanente_fmt}
                    <span style="opacity:0.7;">(saldo disponible en cuenta para el próximo período)</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # -- Proyección combinada 70/30 --
        st.markdown("")
        st.markdown(
            f'<div style="color:{COLORS["text_secondary"]}; font-size:0.85rem; font-weight:500;">'
            'Proyección Combinada (70% SPY + 30% QQQ a 10% anual)</div>',
            unsafe_allow_html=True,
        )

        spy_proj = calculate_custom_projection(0, monto_spy_ars, 0.10, 10)
        qqq_proj = calculate_custom_projection(0, monto_qqq_ars, 0.10, 10)

        if spy_proj["df"] is not None and qqq_proj["df"] is not None:
            combined_spy = spy_proj["df"]["Valor Total Proyectado"].values
            combined_qqq = qqq_proj["df"]["Valor Total Proyectado"].values
            combined_total = combined_spy + combined_qqq
            combined_aportado = spy_proj["df"]["Aportado (Bolsillo)"].values + qqq_proj["df"]["Aportado (Bolsillo)"].values

            final_total = combined_total[-1]
            final_aportado = combined_aportado[-1]
            final_intereses = final_total - final_aportado

            proj_c1, proj_c2, proj_c3 = st.columns(3)
            with proj_c1:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                        <div class="kpi-label">Total Aportado (10 años)</div>
                        <div class="kpi-value" style="font-size:1.2rem;">{fmt_ars(final_aportado)}</div>
                        <div class="kpi-sub neutral">120 cuotas</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with proj_c2:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                        <div class="kpi-label">Patrimonio Final Estimado</div>
                        <div class="kpi-value" style="font-size:1.2rem; color:{COLORS['gain']};">{fmt_ars(final_total)}</div>
                        <div class="kpi-sub positive">+{fmt_pct(((final_total - final_aportado) / final_aportado * 100) if final_aportado else 0)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with proj_c3:
                st.markdown(
                    f"""
                    <div class="kpi-card">
                        <div class="kpi-label">Intereses Ganados</div>
                        <div class="kpi-value" style="font-size:1.2rem; color:{COLORS['accent']};">{fmt_ars(final_intereses)}</div>
                        <div class="kpi-sub neutral">Poder del compuesto</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ====================================================================
    # PARTE 2 — Calculadora DCA Estándar (sin capital previo)
    # ====================================================================
    st.markdown(
        '<div class="section-header">🧮 Calculadora DCA — Interés Compuesto</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <p style="color:{COLORS['text_secondary']}; font-size:0.9rem; margin-bottom:16px;">
        Simula el crecimiento de tu inversión con aportes periódicos.
        Seleccioná moneda, un escenario o ingresá la tasa manualmente.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # -- Selector de moneda DCA --
    dca_currency = st.radio(
        "Moneda",
        ["ARS", "USD"],
        index=0,
        horizontal=True,
        key="dca_currency",
    )

    if dca_currency == "USD":
        fmt_dca = fmt_usd
        monthly_default = 100.0
        monthly_step = 10.0
    else:
        fmt_dca = fmt_ars
        monthly_default = 100000.0
        monthly_step = 10000.0

    # -- Descargar benchmarks CAGR --
    benchmarks = get_cagr_benchmarks()
    cagr_10y_mix = benchmarks.get("10y", {}).get("mix")
    cagr_5y_mix = benchmarks.get("5y", {}).get("mix")
    cagr_10y_spy = benchmarks.get("10y", {}).get("spy")
    cagr_10y_qqq = benchmarks.get("10y", {}).get("qqq")

    # -- Selector de escenario --
    st.markdown(
        f"""
        <div style="color:{COLORS['text_secondary']}; font-size:0.85rem;
                    font-weight:500; margin-bottom:8px;">
            📊 Escenario de tasa
        </div>
        """,
        unsafe_allow_html=True,
    )

    scenario_cols = st.columns(4)
    with scenario_cols[0]:
        if cagr_10y_mix is not None:
            btn_10y = st.button(
                f"CAGR Histórico 10A\n({cagr_10y_mix * 100:.1f}%)",
                key="btn_cagr_10y",
                use_container_width=True,
            )
        else:
            btn_10y = False
    with scenario_cols[1]:
        if cagr_5y_mix is not None:
            btn_5y = st.button(
                f"CAGR Histórico 5A\n({cagr_5y_mix * 100:.1f}%)",
                key="btn_cagr_5y",
                use_container_width=True,
            )
        else:
            btn_5y = False
    with scenario_cols[2]:
        btn_conserv = st.button(
            "Promedio Conservador\n(8.0%)",
            key="btn_cagr_conserv",
            use_container_width=True,
        )
    with scenario_cols[3]:
        btn_manual = st.button(
            "✏️ Manual / Personalizado",
            key="btn_cagr_manual",
            use_container_width=True,
        )

    # -- Actualizar session_state según botón presionado --
    if btn_10y and cagr_10y_mix is not None:
        st.session_state["dca_rate"] = round(cagr_10y_mix * 100, 1)
    elif btn_5y and cagr_5y_mix is not None:
        st.session_state["dca_rate"] = round(cagr_5y_mix * 100, 1)
    elif btn_conserv:
        st.session_state["dca_rate"] = 8.0
    elif btn_manual:
        st.session_state["dca_rate"] = 10.0

    # -- Inputs --
    col1, col2, col3 = st.columns(3)
    with col1:
        monthly = fmt_number_input(
            f"Aporte mensual ({dca_currency})",
            fmt_dca,
            min_value=0.0,
            value=monthly_default,
            step=monthly_step,
            format="%.2f",
            key="dca_monthly",
        )
    with col2:
        annual_rate = st.number_input(
            "Tasa anual estimada (%)",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=0.1,
            key="dca_rate",
            help="Elegí un escenario arriba o editá manualmente.",
        ) / 100.0
    with col3:
        years = st.number_input(
            "Horizonte (años)",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            key="dca_years",
        )

    # -- Badges informativos de benchmarks --
    if cagr_10y_mix is not None or cagr_5y_mix is not None:
        badges = []
        if cagr_10y_spy is not None:
            badges.append(f"SPY 10A: {cagr_10y_spy * 100:.1f}%")
        if cagr_10y_qqq is not None:
            badges.append(f"QQQ 10A: {cagr_10y_qqq * 100:.1f}%")
        if cagr_10y_mix is not None:
            badges.append(f"Mix 70/30 10A: {cagr_10y_mix * 100:.1f}%")
        if cagr_5y_mix is not None:
            badges.append(f"Mix 70/30 5A: {cagr_5y_mix * 100:.1f}%")
        badge_text = "  ·  ".join(badges)
        st.markdown(
            f"""
            <div style="background:rgba(61,133,198,0.1); border:1px solid rgba(61,133,198,0.3);
                        border-radius:8px; padding:8px 14px; margin-top:4px; margin-bottom:12px;
                        font-size:0.8rem; color:{COLORS['text_secondary']};">
                📈 <b>Rendimientos reales (USD):</b> {badge_text}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -- Proyectar --
    df_dca = calculate_dca_projection(monthly, annual_rate, years)

    if df_dca is not None and not df_dca.empty:
        final = df_dca.iloc[-1]
        total_invested = final["Aporte Acumulado"]
        total_value = final["Capital Acumulado"]
        total_interest = final["Intereses"]
        return_pct = (
            ((total_value - total_invested) / total_invested * 100)
            if total_invested else 0
        )

        kpi_cols = st.columns(3)
        with kpi_cols[0]:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Total Aportado</div>
                    <div class="kpi-value" style="font-size:1.4rem;">{fmt_dca(total_invested)}</div>
                    <div class="kpi-sub neutral">{years * 12} aportes mensuales</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with kpi_cols[1]:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Capital Final</div>
                    <div class="kpi-value" style="font-size:1.4rem; color:{COLORS['gain']};">{fmt_dca(total_value)}</div>
                    <div class="kpi-sub positive">+{fmt_pct(return_pct)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with kpi_cols[2]:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-label">Intereses Ganados</div>
                    <div class="kpi-value" style="font-size:1.4rem; color:{COLORS['accent']};">{fmt_dca(total_interest)}</div>
                    <div class="kpi-sub neutral">Compounding over {years} years</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("")

        # -- Gráfico con o sin comparación --
        show_comparison = (
            cagr_10y_mix is not None
            and abs(annual_rate - cagr_10y_mix) > 0.005
        )

        if show_comparison:
            df_hist = calculate_dca_projection(monthly, cagr_10y_mix, years)
            fig_dca = build_dca_comparison_chart(
                df_dca, df_hist, annual_rate, cagr_10y_mix, years * 12, dca_currency,
            )
        else:
            fig_dca = build_dca_chart(df_dca, currency=dca_currency)

        st.plotly_chart(fig_dca, use_container_width=True, config={"displayModeBar": False})

        with st.expander("📋 Ver detalle por año", expanded=False):
            df_yearly = (
                df_dca
                .groupby("Año")
                .last()
                .reset_index()
                [["Año", "Aporte Acumulado", "Capital Acumulado", "Intereses"]]
            )
            st.dataframe(
                df_yearly.style.format({
                    "Aporte Acumulado": "$ {:,.2f}",
                    "Capital Acumulado": "$ {:,.2f}",
                    "Intereses": "$ {:,.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("---")

    # ====================================================================
    # PARTE 3 — Proyección Personalizada (Mi Capital + DCA Futuro)
    # ====================================================================
    st.markdown(
        '<div class="section-header">🚀 Proyección Personalizada (Mi Capital + DCA Futuro)</div>',
        unsafe_allow_html=True,
    )

    # -- Capital inicial desde el portafolio actual (Costo Total Invertido) --
    if display_currency == "USD":
        capital_default = float(metrics.get("total_cost_usd", 0))
        currency_label = "USD"
        fmt_fn = fmt_usd
    else:
        capital_default = float(metrics.get("total_cost_ars", 0))
        currency_label = "ARS"
        fmt_fn = fmt_ars

    has_position = capital_default > 0

    # Sincronizar el default del number_input cuando cambian los datos
    if st.session_state.get("custom_pv") != capital_default:
        st.session_state["custom_pv"] = capital_default

    if not has_position:
        st.info(
            "ℹ️ No tenés posiciones registradas. "
            "Ingresá un capital inicial manualmente o agregá compras en la pestaña **➕ Nueva Compra**."
        )

    st.markdown(
        f"""
        <p style="color:{COLORS['text_secondary']}; font-size:0.88rem; margin-bottom:16px;">
        Combiná tu capital actual con aportes mensuales futuros para ver
        el poder del interés compuesto sobre tu portafolio real.
        </p>
        """,
        unsafe_allow_html=True,
    )

    # -- Inputs --
    pc1, pc2 = st.columns(2)
    with pc1:
        pv_input = fmt_number_input(
            f"Capital Inicial PV ({currency_label})",
            fmt_fn,
            value=capital_default,
            min_value=0.0,
            step=50.0 if currency_label == "USD" else 5000.0,
            format="%.2f",
            key="custom_pv",
            help="Precargado automáticamente con el total invertido en tu portafolio actual.",
        )
        pmt_input = fmt_number_input(
            f"Aporte Mensual PMT ({currency_label})",
            fmt_fn,
            min_value=0.0,
            value=100.0 if currency_label == "USD" else 50000.0,
            step=10.0 if currency_label == "USD" else 10000.0,
            format="%.2f",
            key="custom_pmt",
            help="Monto que vas a aportar cada mes.",
        )
    with pc2:
        rate_input = st.number_input(
            "Tasa Anual Estimada (%)",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=0.5,
            key="custom_rate",
        )
        horizon_input = st.number_input(
            "Horizonte (Años)",
            min_value=1,
            max_value=30,
            value=10,
            step=1,
            key="custom_horizon",
        )

    # -- Calcular --
    result = calculate_custom_projection(
        capital_inicial=pv_input,
        aporte_mensual=pmt_input,
        tasa_anual=rate_input / 100.0,
        anios=horizon_input,
    )

    df_proj = result["df"]

    # -- KPIs de resultados --
    st.markdown("")

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Capital Inicial Base</div>
                <div class="kpi-value" style="font-size:1.3rem;">{fmt_fn(result['capital_inicial'])}</div>
                <div class="kpi-sub neutral">Trabajando desde hoy</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with k2:
        nuevos_aportes = pmt_input * result["meses"]
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Total Nuevos Aportes</div>
                <div class="kpi-value" style="font-size:1.3rem;">{fmt_fn(nuevos_aportes)}</div>
                <div class="kpi-sub neutral">{result['meses']} aportes mensuales</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with k3:
        int_class = "positive" if result["intereses_totales"] >= 0 else "negative"
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Intereses Ganados</div>
                <div class="kpi-value {int_class}" style="font-size:1.3rem;">{fmt_fn(result['intereses_totales'])}</div>
                <div class="kpi-sub {int_class}">Poder del compuesto</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with k4:
        st.markdown(
            f"""
            <div class="kpi-card">
                <div class="kpi-label">Patrimonio Total Estimado</div>
                <div class="kpi-value" style="font-size:1.3rem; color:{COLORS['gain']};">{fmt_fn(result['capital_final'])}</div>
                <div class="kpi-sub positive">
                    +{fmt_pct(((result['capital_final'] - result['total_aportado']) / result['total_aportado'] * 100) if result['total_aportado'] else 0)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # -- Gráfico de evolución temporal --
    st.markdown("")

    fig_custom = build_custom_projection_chart(df_proj, currency=currency_label)
    st.plotly_chart(fig_custom, use_container_width=True, config={"displayModeBar": False})

    # -- Leyenda visual del gráfico --
    st.markdown(
        f"""
        <div style="display:flex; gap:24px; justify-content:center; margin-top:-8px; margin-bottom:8px;">
            <span style="font-size:0.78rem; color:#3D85C6;">
                ● Línea Azul — Total aportado de tu bolsillo
            </span>
            <span style="font-size:0.78rem; color:#2ECC71;">
                ● Línea Verde — Valor total proyectado
            </span>
            <span style="font-size:0.78rem; color:rgba(46,204,113,0.5);">
                ■ Área — Ganancia por intereses
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -- Detalle por año --
    with st.expander("📋 Ver detalle por año", expanded=False):
        df_yearly_custom = (
            df_proj[df_proj["Mes"] > 0]
            .groupby("Año")
            .last()
            .reset_index()
            [["Año", "Aportado (Bolsillo)", "Valor Total Proyectado", "Intereses Ganados"]]
        )
        st.dataframe(
            df_yearly_custom.style.format({
                "Aportado (Bolsillo)": "${:,.2f}",
                "Valor Total Proyectado": "${:,.2f}",
                "Intereses Ganados": "${:,.2f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")



# ===========================================================================
# Componentes de UI — Tabla de Resumen
# ===========================================================================

def render_summary_table(metrics: dict, daily_change: dict) -> None:
    """Renderiza una tabla resumen con todos los datos de la posición."""
    st.markdown(
        '<div class="section-header">📋 Resumen de Posición</div>',
        unsafe_allow_html=True,
    )

    summary_data = {
        "Métrica": [
            "Precio Actual (USD)",
            "Precio Actual (ARS)",
            "PPC Compra (USD)",
            "PPC Compra (ARS)",
            "Cantidad",
            "Valor Total (USD)",
            "Valor Total (ARS)",
            "Costo Total (USD)",
            "Costo Total (ARS)",
            "Ganancia/Pérdida (USD)",
            "Ganancia/Pérdida (ARS)",
            "Rendimiento (%)",
            "Variación Diaria (%)",
            "Dólar CCL Actual",
            "CCL en Compra",
        ],
        "Valor": [
            fmt_usd(metrics["current_price_usd"]),
            fmt_ars(metrics["current_price_ars"]),
            fmt_usd(metrics["avg_price_usd"]),
            fmt_ars(metrics["avg_price_ars"]),
            f"{metrics['total_value_usd'] / metrics['current_price_usd']:.2f}"
            if metrics["current_price_usd"] else "0",
            fmt_usd(metrics["total_value_usd"]),
            fmt_ars(metrics["total_value_ars"]),
            fmt_usd(metrics["total_cost_usd"]),
            fmt_ars(metrics["total_cost_ars"]),
            fmt_usd(metrics["pnl_usd"]),
            fmt_ars(metrics["pnl_ars"]),
            fmt_pct(metrics["pnl_pct"]),
            fmt_pct(daily_change["pct"]),
            f"ARS {metrics.get('ccl_rate', 0):,.1f}" if metrics.get("ccl_rate") else "N/D",
            f"ARS {metrics.get('buy_ccl', 0):,.1f}" if metrics.get("buy_ccl") else "N/D",
        ],
    }

    df_summary = pd.DataFrame(summary_data)
    st.dataframe(df_summary, use_container_width=True, hide_index=True, height=520)

    # -- Desglose de Ganancia --
    ccl_rate = metrics.get("ccl_rate", 0)
    buy_ccl = metrics.get("buy_ccl", 0)

    if ccl_rate and buy_ccl:
        st.markdown("")
        st.markdown(
            '<div class="section-header">🔍 Desglose de Ganancia</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            f"""
            <p style="color:{COLORS['text_secondary']}; font-size:0.85rem; margin-bottom:16px;">
            Separación entre la ganancia por la variación del subyacente (SPY en USD)
            y la ganancia por la variación del tipo de cambio CCL.
            </p>
            """,
            unsafe_allow_html=True,
        )

        b_cols = st.columns(2)

        # -- Subyacente USD --
        underlying = metrics.get("underlying_pnl_usd", 0)
        underlying_pct = metrics.get("underlying_pnl_pct", 0)
        underlying_ars = metrics.get("underlying_pnl_ars", 0)
        u_class = "positive" if underlying >= 0 else "negative"
        u_icon = "▲" if underlying >= 0 else "▼"

        with b_cols[0]:
            st.markdown(
                f"""
                <div class="breakdown-card">
                    <div class="breakdown-label">📈 Rendimiento Subyacente (USD)</div>
                    <div class="breakdown-value">{fmt_usd(underlying)}</div>
                    <div class="breakdown-sub {u_class}">
                        {u_icon} {fmt_pct(underlying_pct)} sobre la inversión en USD
                    </div>
                    <div class="breakdown-sub neutral" style="margin-top:4px;">
                        En ARS: {fmt_ars(underlying_ars)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # -- Cambiario CCL --
        fx_pnl = metrics.get("fx_pnl_ars", 0)
        fx_pct = metrics.get("fx_pnl_pct", 0)
        f_class = "positive" if fx_pnl >= 0 else "negative"
        f_icon = "▲" if fx_pnl >= 0 else "▼"

        with b_cols[1]:
            st.markdown(
                f"""
                <div class="breakdown-card">
                    <div class="breakdown-label">💱 Rendimiento Cambiario (CCL)</div>
                    <div class="breakdown-value">{fmt_ars(fx_pnl)}</div>
                    <div class="breakdown-sub {f_class}">
                        {f_icon} {fmt_pct(fx_pct)} variación del CCL
                    </div>
                    <div class="breakdown-sub neutral" style="margin-top:4px;">
                        Compra: ARS {buy_ccl:,.1f} → Actual: ARS {ccl_rate:,.1f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # -- Verificación --
        total_from_breakdown = underlying_ars + fx_pnl
        total_actual = metrics["pnl_ars"]
        st.markdown(
            f"""
            <div style="background-color:{COLORS['bg_main']}; border-radius:8px;
                        padding:10px 14px; margin-top:12px;
                        border:1px solid {COLORS['border']};">
                <span style="color:{COLORS['text_secondary']}; font-size:0.78rem;">
                    ✓ Verificación: {fmt_ars(underlying_ars)} (subyacente) + {fmt_ars(fx_pnl)} (CCL)
                    = {fmt_ars(total_from_breakdown)} ≈ {fmt_ars(total_actual)} (total)
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ===========================================================================
# App Principal
# ===========================================================================

def main():
    """Funcion principal — orquesta la renderizacion del dashboard multi-asset."""

    # -- Titulo + Badge de mercado --
    is_open, market_html = is_market_open()

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
            <span style="font-size:2rem;">🥥</span>
            <div>
                <h1 style="margin:0; font-size:1.6rem; font-weight:700;">
                    Cocos Broker — Multi-Asset
                </h1>
                <p style="color:{COLORS['text_secondary']}; margin:0; font-size:0.85rem;">
                    Dashboard de Cartera • SPY (S&P 500) + QQQ (Nasdaq 100) • CEDEARs • Supabase
                </p>
            </div>
            <div style="margin-left:auto;">
                {market_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -- Sidebar (calcula PPC desde la DB para ambos activos) --
    sidebar = render_sidebar()
    spy_ppc = sidebar["spy_ppc"]
    qqq_ppc = sidebar["qqq_ppc"]
    manual_rate = sidebar["manual_rate"]
    spy_transactions = sidebar["spy_transactions"]
    qqq_transactions = sidebar["qqq_transactions"]

    # -- Carga de datos de mercado para ambos activos --
    with st.spinner("Cargando datos de mercado..."):
        spy_data = fetch_spy_data(period="5y")
        qqq_data = fetch_qqq_data(period="5y")
        current_price = fetch_current_price()
        qqq_current_price = fetch_qqq_current_price()
        spy_usd_price = fetch_spy_usd_price()
        qqq_usd_price = fetch_qqq_usd_price()
        market_rate = fetch_exchange_rate()

    if spy_data is None or current_price is None:
        st.error(
            "⚠️ No se pudieron obtener los datos de mercado de SPY. "
            "Verificá tu conexión a internet y volvé a intentar."
        )
        st.stop()

    # -- Calcular CCL (usando SPY como referencia) --
    ccl_rate = calculate_ccl(current_price, spy_usd_price) if spy_usd_price else None

    # Resolver tipo de cambio: prioridad CCL > manual > mercado > fallback
    if ccl_rate:
        exchange_rate = ccl_rate
        rate_source = "CCL"
    elif manual_rate > 0:
        exchange_rate = manual_rate
        rate_source = "manual"
    elif market_rate:
        exchange_rate = market_rate
        rate_source = "mercado"
    else:
        exchange_rate = 1050.0
        rate_source = "fallback"

    if rate_source != "CCL":
        st.toast(
            f"💱 Tipo de cambio: ARS {exchange_rate:,.1f} (fuente: {rate_source})",
            icon="💱",
        )

    # -- CCL estimado de compra --
    buy_ccl_spy = None
    if spy_ppc["ppc_ars"] > 0 and spy_usd_price:
        buy_ccl_spy = (spy_ppc["ppc_ars"] * CEDEAR_RATIO_SPY) / spy_usd_price

    # -- Metricas por activo --
    spy_metrics = calculate_portfolio_metrics(
        shares=spy_ppc["total_shares"],
        avg_price_ars=spy_ppc["ppc_ars"],
        current_price_usd=spy_usd_price or current_price,
        exchange_rate=exchange_rate,
        price_ars=current_price,
        ccl_rate=ccl_rate or exchange_rate,
        buy_ccl=buy_ccl_spy or exchange_rate,
    )
    qqq_usd_est = qqq_usd_price
    if not qqq_usd_est and qqq_current_price and exchange_rate:
        qqq_usd_est = qqq_current_price / exchange_rate
    qqq_metrics = calculate_portfolio_metrics(
        shares=qqq_ppc["total_shares"],
        avg_price_ars=qqq_ppc["ppc_ars"],
        current_price_usd=qqq_usd_est or 0,
        exchange_rate=exchange_rate,
        price_ars=qqq_current_price or 0,
        ccl_rate=ccl_rate or exchange_rate,
        buy_ccl=exchange_rate,
    )

    spy_daily = calculate_daily_change(spy_data)
    qqq_daily = calculate_daily_change(qqq_data) if qqq_data is not None else {"pct": 0, "abs": 0, "prev_close": 0}

    # -- Selector de moneda + vista activa --
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 3, 1])
    with ctrl_col1:
        display_currency = st.radio(
            "Mostrar en",
            ["ARS", "USD"],
            index=0,
            horizontal=True,
            key="display_currency",
        )
    with ctrl_col3:
        asset_view = st.selectbox(
            "Vista",
            options=["Portafolio Consolidado", "SPY (S&P 500)", "QQQ (Nasdaq 100)"],
            key="asset_view_selector",
        )

    st.markdown("")

    # -- Seleccionar que metricas mostrar --
    if asset_view == "SPY (S&P 500)":
        active_metrics = spy_metrics
        active_daily = spy_daily
        active_chart_data = spy_data
    elif asset_view == "QQQ (Nasdaq 100)":
        active_metrics = qqq_metrics
        active_daily = qqq_daily
        active_chart_data = qqq_data if qqq_data is not None else spy_data
    else:
        active_metrics = calculate_consolidated_metrics(spy_metrics, qqq_metrics, display_currency)
        active_daily = spy_daily
        active_chart_data = spy_data

    # -- Determinar label del activo para KPIs --
    if asset_view == "QQQ (Nasdaq 100)":
        asset_label = "QQQ"
    elif asset_view == "SPY (S&P 500)":
        asset_label = "SPY"
    else:
        asset_label = "Portafolio"

    # -- KPI Cards --
    render_kpi_cards(active_metrics, active_daily, display_currency, exchange_rate, asset_label)

    st.markdown("")

    # -- Tabs principales --
    tab_charts, tab_dca, tab_purchase, tab_history, tab_summary = st.tabs(
        [
            "Gráficos Interactivos",
            "Calculadora DCA",
            "➕ Nueva Compra",
            "📜 Historial",
            "📊 Resumen",
        ]
    )

    with tab_charts:
        render_charts_section(active_chart_data)

    with tab_dca:
        render_dca_section(active_metrics, display_currency, spy_ppc, qqq_ppc, exchange_rate, spy_usd_price, qqq_usd_price, current_price, qqq_current_price or 0)

    with tab_purchase:
        render_purchase_form(
            spy_price=current_price,
            qqq_price=qqq_current_price or current_price,
        )

    with tab_history:
        render_transaction_history(spy_transactions, qqq_transactions)

    with tab_summary:
        render_summary_table(active_metrics, active_daily)
        # -- Asset Allocation (solo en vista consolidada) --
        total_ars = (spy_metrics.get("total_value_ars", 0) or 0) + (qqq_metrics.get("total_value_ars", 0) or 0)
        if asset_view == "Portafolio Consolidado" and total_ars > 0:
            st.markdown("")
            st.markdown(
                '<div class="section-header">🎯 Asset Allocation — Distribución del Portafolio</div>',
                unsafe_allow_html=True,
            )
            fig_alloc = build_allocation_chart(active_metrics, display_currency)
            st.plotly_chart(fig_alloc, use_container_width=True, config={"displayModeBar": False})
            # -- Indicador de rebalanceo --
            key_prefix = "spy_value_" + ("ars" if display_currency == "ARS" else "usd")
            spy_val = active_metrics.get(key_prefix, 0) or 0
            qqq_key = "qqq_value_" + ("ars" if display_currency == "ARS" else "usd")
            qqq_val = active_metrics.get(qqq_key, 0) or 0
            total_val = spy_val + qqq_val
            if total_val > 0:
                spy_pct = spy_val / total_val * 100
                diff = spy_pct - 70
                if abs(diff) > 5:
                    direction = "más" if diff > 0 else "menos"
                    st.warning(
                        f"⚠️ Tu ponderación de SPY es {spy_pct:.1f}% (objetivo: 70%). "
                        f"Convendría rebalancear — {abs(diff):.1f}% {direction} de lo ideal."
                    )
                else:
                    st.success(
                        f"✅ Tu distribución ({spy_pct:.1f}% SPY / {100-spy_pct:.1f}% QQQ) "
                        f"está cerca del objetivo 70/30. No necesita rebalanceo."
                    )

    # -- Footer --
    st.markdown("---")
    st.markdown(
        f"""
        <div style="text-align:center; color:{COLORS['text_secondary']}; font-size:0.75rem; padding:8px 0;">
            Coco's Broker · Multi-Asset · SPY + QQQ · CEDEARs ·
            Datos: yfinance · Persistencia: Supabase ·
            No constituye asesoramiento financiero ·
            Actualizado: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')} ART
        </div>
        """,
        unsafe_allow_html=True,
    )



# -- Entry point --
if __name__ == "__main__":
    main()
