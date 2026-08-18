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
    fetch_spy_data,
    fetch_current_price,
    fetch_exchange_rate,
    fetch_spy_usd_price,
    calculate_ccl,
    is_market_open,
    calculate_portfolio_metrics,
    calculate_daily_change,
    calculate_dca_projection,
    calculate_custom_projection,
    build_custom_projection_chart,
    fmt_usd,
    fmt_ars,
    fmt_pct,
    fmt_change,
    fmt_date,
    build_candlestick_chart,
    build_dca_chart,
)
from db import (
    get_supabase_client,
    fetch_transactions,
    insert_transaction,
    delete_transaction,
    calculate_ppc,
    get_create_table_sql,
)


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
        - Métricas calculadas automáticamente desde la DB
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

        # -- Consultar transacciones y calcular PPC --
        transactions = fetch_transactions(ticker=TICKER_SPY) if connected else []
        ppc_data = calculate_ppc(transactions)

        total_shares = ppc_data["total_shares"]
        ppc_ars = ppc_data["ppc_ars"]
        total_cost = ppc_data["total_cost_ars"]
        tx_count = ppc_data["transaction_count"]

        # -- Mostrar métricas calculadas --
        if tx_count > 0:
            st.markdown(f"### 📈 Posición Actual")
            st.markdown(
                f"""
                <div style="background-color:{COLORS['bg_main']}; border-radius:10px;
                            padding:16px; margin-bottom:12px; border:1px solid {COLORS['border']};">
                    <div style="color:{COLORS['text_secondary']}; font-size:0.75rem;
                                text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">
                        Unidades
                    </div>
                    <div style="color:{COLORS['text_primary']}; font-size:1.5rem;
                                font-weight:700;">
                        {total_shares:.2f}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
                <div style="background-color:{COLORS['bg_main']}; border-radius:10px;
                            padding:16px; margin-bottom:12px; border:1px solid {COLORS['border']};">
                    <div style="color:{COLORS['text_secondary']}; font-size:0.75rem;
                                text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">
                        PPC (Precio Prom. Ponderado)
                    </div>
                    <div style="color:{COLORS['accent']}; font-size:1.3rem;
                                font-weight:700;">
                        {fmt_ars(ppc_ars)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
                <div style="background-color:{COLORS['bg_main']}; border-radius:10px;
                            padding:16px; margin-bottom:12px; border:1px solid {COLORS['border']};">
                    <div style="color:{COLORS['text_secondary']}; font-size:0.75rem;
                                text-transform:uppercase; letter-spacing:0.05em; margin-bottom:8px;">
                        Costo Total Invertido
                    </div>
                    <div style="color:{COLORS['text_primary']}; font-size:1.1rem;
                                font-weight:600;">
                        {fmt_ars(total_cost)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<span style='color:{COLORS['text_secondary']}; font-size:0.8rem;'>"
                f"📋 {tx_count} transaccion{'es' if tx_count != 1 else ''} "
                f"registrada{'s' if tx_count != 1 else ''}"
                f"</span>",
                unsafe_allow_html=True,
            )
        else:
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
        "transactions": transactions,
        "total_shares": total_shares,
        "ppc_ars": ppc_ars,
        "total_cost_ars": total_cost,
        "transaction_count": tx_count,
        "manual_rate": manual_rate,
    }


# ===========================================================================
# Componentes de UI — KPI Cards
# ===========================================================================

def render_kpi_cards(metrics: dict, daily_change: dict, display: str, exchange_rate: float = 1.0) -> None:
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
                <div class="kpi-label">Precio Actual SPY</div>
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
        rate_display = f"ARS {ccl_val:,.1f}" if ccl_val else "N/D"
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

def render_purchase_form(current_price: float = 20000.0) -> None:
    """Renderiza el formulario para registrar una nueva compra.

    Args:
        current_price: Precio actual de mercado de SPY.BA en ARS.
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
        Completá los datos de la operación. Los campos con * son obligatorios.
        El PPC (Precio Promedio Ponderado) se recalculará automáticamente.
        </p>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)

    with col1:
        ticker = st.text_input(
            "Ticker *",
            value="SPY.BA",
            max_chars=10,
            help="Símbolo del activo (ej: SPY.BA, QQQ, AAPL)",
            key="input_ticker",
        )
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
        precio = st.number_input(
            "Precio unitario (ARS) *",
            value=float(current_price),
            min_value=0.0,
            step=10.0,
            format="%.2f",
            key="input_precio_unitario",
            help="Precio pagado por unidad en pesos argentinos.",
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
    total_ars_fmt = f"{total_operacion:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
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
                ARS {total_ars_fmt}
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
        if not ticker.strip():
            st.error("El ticker no puede estar vacío.")
        elif cantidad <= 0:
            st.error("La cantidad debe ser mayor a 0.")
        elif precio <= 0:
            st.error("El precio debe ser mayor a 0.")
        else:
            total_operacion = float(cantidad) * float(precio)
            result = insert_transaction(
                ticker=ticker.strip(),
                cantidad=int(cantidad),
                precio_unitario_ars=float(precio),
                fecha=fecha,
                notas=notas,
                monto_total_ars=total_operacion,
            )
            if result:
                st.success(
                    f"✅ ¡Compra de {cantidad} unidades registrada correctamente en Supabase!"
                )
                st.toast(
                    f"🎉 Portafolio actualizado: +{cantidad} unidades de {ticker.upper().strip()}",
                    icon="🥥",
                )
                st.balloons()
                # Limpiar campos del formulario
                for key in ["input_ticker", "input_cantidad", "input_precio_unitario", "input_notas"]:
                    if key in st.session_state:
                        del st.session_state[key]
                # Limpiar caché y recargar estado para actualizar métricas en toda la app
                st.cache_data.clear()
                time.sleep(1)
                st.rerun()


# ===========================================================================
# Componentes de UI — Historial de Transacciones
# ===========================================================================

def render_transaction_history(transactions: list[dict]) -> None:
    """
    Renderiza el historial completo de compras registradas.

    Args:
        transactions: Lista de transacciones desde Supabase.
    """
    st.markdown(
        '<div class="section-header">📜 Historial de Compras</div>',
        unsafe_allow_html=True,
    )

    if not transactions:
        st.info(
            "No hay transacciones registradas aún. "
            "Usá la pestaña **➕ Nueva Compra** para agregar la primera."
        )
        return

    # -- Resumen rápido --
    ppc_data = calculate_ppc(transactions)
    res_col1, res_col2, res_col3 = st.columns(3)
    with res_col1:
        st.metric(
            "Total Unidades",
            f"{ppc_data['total_shares']:.2f}",
        )
    with res_col2:
        st.metric(
            "PPC (ARS)",
            fmt_ars(ppc_data["ppc_ars"]),
        )
    with res_col3:
        st.metric(
            "Costo Total (ARS)",
            fmt_ars(ppc_data["total_cost_ars"]),
        )

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

def render_dca_section(metrics: dict, display_currency: str = "USD") -> None:
    """Renderiza la pestaña de calculadora DCA / Proyección.

    Args:
        metrics:          Diccionario con métricas de la cartera (para capital inicial).
        display_currency: Moneda de visualización ('USD' o 'ARS').
    """
    # ====================================================================
    # PARTE 1 — Calculadora DCA Estándar (sin capital previo)
    # ====================================================================
    st.markdown(
        '<div class="section-header">🧮 Calculadora DCA — Interés Compuesto</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <p style="color:{COLORS['text_secondary']}; font-size:0.9rem; margin-bottom:16px;">
        Simula el crecimiento de tu inversión con aportes periódicos.
        Ingresá el monto mensual, la tasa estimada y el horizonte de tiempo.
        </p>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        monthly = st.number_input(
            "Aporte mensual (USD)",
            min_value=0.0,
            value=100.0,
            step=10.0,
            key="dca_monthly",
        )
    with col2:
        annual_rate = st.number_input(
            "Tasa anual estimada (%)",
            min_value=0.0,
            max_value=100.0,
            value=10.0,
            step=0.5,
            key="dca_rate",
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

    df_dca = calculate_dca_projection(monthly, annual_rate, years)

    if df_dca is not None and not df_dca.empty:
        final = df_dca.iloc[-1]
        total_invested = final["Aporte Acumulado (USD)"]
        total_value = final["Capital Acumulado (USD)"]
        total_interest = final["Intereses (USD)"]
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
                    <div class="kpi-value" style="font-size:1.4rem;">{fmt_usd(total_invested)}</div>
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
                    <div class="kpi-value" style="font-size:1.4rem; color:{COLORS['gain']};">{fmt_usd(total_value)}</div>
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
                    <div class="kpi-value" style="font-size:1.4rem; color:{COLORS['accent']};">{fmt_usd(total_interest)}</div>
                    <div class="kpi-sub neutral">Compounding over {years} years</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("")

        fig_dca = build_dca_chart(df_dca)
        st.plotly_chart(fig_dca, use_container_width=True, config={"displayModeBar": False})

        with st.expander("📋 Ver detalle por año", expanded=False):
            df_yearly = (
                df_dca
                .groupby("Año")
                .last()
                .reset_index()
                [["Año", "Aporte Acumulado (USD)", "Capital Acumulado (USD)", "Intereses (USD)"]]
            )
            st.dataframe(
                df_yearly.style.format({
                    "Aporte Acumulado (USD)": "${:,.2f}",
                    "Capital Acumulado (USD)": "${:,.2f}",
                    "Intereses (USD)": "${:,.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

    st.markdown("---")

    # ====================================================================
    # PARTE 2 — Proyección Personalizada (Mi Capital + DCA Futuro)
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
        pv_input = st.number_input(
            f"Capital Inicial PV ({currency_label})",
            value=capital_default,
            min_value=0.0,
            step=50.0 if currency_label == "USD" else 5000.0,
            format="%.2f",
            key="custom_pv",
            help="Precargado automáticamente con el total invertido en tu portafolio actual.",
        )
        pmt_input = st.number_input(
            f"Aporte Mensual PMT ({currency_label})",
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
    """Función principal — orquesta la renderización del dashboard."""

    # -- Título + Badge de mercado --
    is_open, market_html = is_market_open()

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">
            <span style="font-size:2rem;">🥥</span>
            <div>
                <h1 style="margin:0; font-size:1.6rem; font-weight:700;">
                    Cocos Broker — S&P 500
                </h1>
                <p style="color:{COLORS['text_secondary']}; margin:0; font-size:0.85rem;">
                    Dashboard de Seguimiento de Cartera • SPY / CEDEARs • Supabase Cloud
                </p>
            </div>
            <div style="margin-left:auto;">
                {market_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -- Sidebar (calcula PPC desde la DB) --
    sidebar = render_sidebar()
    total_shares = sidebar["total_shares"]
    ppc_ars = sidebar["ppc_ars"]
    manual_rate = sidebar["manual_rate"]
    transactions = sidebar["transactions"]

    # -- Carga de datos de mercado --
    with st.spinner("Cargando datos de mercado..."):
        spy_data = fetch_spy_data(period="5y")
        current_price = fetch_current_price()
        spy_usd_price = fetch_spy_usd_price()
        market_rate = fetch_exchange_rate()

    if spy_data is None or current_price is None:
        st.error(
            "⚠️ No se pudieron obtener los datos de mercado. "
            "Verificá tu conexión a internet y volvé a intentar."
        )
        st.stop()

    # -- Calcular CCL --
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

    # -- CCL estimado de compra (aproximación) --
    buy_ccl = None
    if ppc_ars > 0 and spy_usd_price:
        buy_ccl = (ppc_ars * 20) / spy_usd_price  # estimación usando precio USD actual

    # -- Cálculos de cartera --
    metrics = calculate_portfolio_metrics(
        shares=total_shares,
        avg_price_ars=ppc_ars,
        current_price_usd=spy_usd_price or current_price,
        exchange_rate=exchange_rate,
        price_ars=current_price,
        ccl_rate=ccl_rate or exchange_rate,
        buy_ccl=buy_ccl or exchange_rate,
    )
    daily_change = calculate_daily_change(spy_data)

    # -- Selector de visualización --
    display_col1, display_col2 = st.columns([1, 5])
    with display_col1:
        display_currency = st.radio(
            "Mostrar en",
            ["USD", "ARS"],
            horizontal=True,
            key="display_currency",
        )

    st.markdown("")

    # -- KPI Cards --
    render_kpi_cards(metrics, daily_change, display_currency, exchange_rate)

    st.markdown("")

    # -- Tabs principales --
    tab_charts, tab_dca, tab_purchase, tab_history, tab_summary = st.tabs(
        [
            "📈 Gráficos Interactivos",
            "🧮 Calculadora DCA",
            "➕ Nueva Compra",
            "📜 Historial",
            "📊 Resumen",
        ]
    )

    with tab_charts:
        render_charts_section(spy_data)

    with tab_dca:
        render_dca_section(metrics, display_currency)

    with tab_purchase:
        render_purchase_form(current_price=current_price)

    with tab_history:
        render_transaction_history(transactions)

    with tab_summary:
        render_summary_table(metrics, daily_change)

    # -- Footer --
    st.markdown("---")
    st.markdown(
        f"""
        <div style="text-align:center; color:{COLORS['text_secondary']}; font-size:0.75rem; padding:8px 0;">
            Coco's Broker · Datos: yfinance · Persistencia: Supabase ·
            No constituye asesoramiento financiero ·
            Actualizado: {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')} ART
        </div>
        """,
        unsafe_allow_html=True,
    )


# -- Entry point --
if __name__ == "__main__":
    main()
