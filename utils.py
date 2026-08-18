"""
utils.py — Módulo de utilidades para el Dashboard de Cartera S&P 500.

Contiene:
    - Configuración de estilos CSS (Dark Mode Fintech)
    - Funciones de obtención de datos bursátiles (yfinance)
    - Funciones de cálculos financieros (DCA, rendimiento, etc.)
    - Funciones de formatting para métricas y KPIs
"""

# ---------------------------------------------------------------------------
# Constantes PRIMERO — disponibles aunque yfinance/plotly fallen en import
# ---------------------------------------------------------------------------

TICKER_SPY = "SPY.BA"       # BYMA — precio real en ARS
TICKER_SPY_USD = "SPY"      # NYSE — precio en USD
TICKER_QQQ = "QQQ.BA"       # BYMA — precio real en ARS
TICKER_QQQ_USD = "QQQ"      # NASDAQ — precio en USD
TICKER_USD_ARS = "USDARS=X"

CEDEAR_RATIO_SPY = 20
CEDEAR_RATIO_QQQ = 20

ASSET_CONFIG = {
    "SPY": {
        "ticker_byma": TICKER_SPY,
        "ticker_usd": TICKER_SPY_USD,
        "cear_ratio": CEDEAR_RATIO_SPY,
        "name": "S&P 500",
        "flag": "🇺🇸",
        "color": "#3D85C6",
    },
    "QQQ": {
        "ticker_byma": TICKER_QQQ,
        "ticker_usd": TICKER_QQQ_USD,
        "cear_ratio": CEDEAR_RATIO_QQQ,
        "name": "Nasdaq 100",
        "flag": "💻",
        "color": "#9B59B6",
    },
}

COLORS = {
    "bg_main": "#1E1E1E",
    "bg_card": "#2D2D2D",
    "bg_sidebar": "#252525",
    "text_primary": "#FFFFFF",
    "text_secondary": "#A0A0A0",
    "accent": "#3D85C6",
    "gain": "#2ECC71",
    "loss": "#E74C3C",
    "border": "#3A3A3A",
    # TradingView chart palette
    "tv_bg": "#131722",
    "tv_bull": "#089981",
    "tv_bear": "#F23645",
    "tv_grid": "rgba(42, 46, 57, 0.5)",
    "tv_text": "#D1D4DC",
    "tv_crosshair": "#758696",
}


# ---------------------------------------------------------------------------
# Imports de librerías
# ---------------------------------------------------------------------------

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta, time as dtime
from typing import Optional
import time as _time


# ---------------------------------------------------------------------------
# CSS personalizado inyectado en Streamlit
# ---------------------------------------------------------------------------

CUSTOM_CSS = f"""
<style>
/* Importar fuente Inter desde Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ============================================================
   RESET Y FUENTE GLOBAL
   ============================================================ */
.stApp {{
    font-family: 'Inter', sans-serif;
    background-color: {COLORS['bg_main']};
}}

/* ============================================================
   SIDEBAR
   ============================================================ */
section[data-testid="stSidebar"] {{
    background-color: {COLORS['bg_sidebar']};
    border-right: 1px solid {COLORS['border']};
}}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown li,
section[data-testid="stSidebar"] label {{
    color: {COLORS['text_secondary']} !important;
    font-size: 0.9rem;
}}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h2,
section[data-testid="stSidebar"] .stMarkdown h3 {{
    color: {COLORS['text_primary']} !important;
}}
section[data-testid="stSidebar"] .stNumberInput > div > div > input,
section[data-testid="stSidebar"] .stSelectbox > div > div {{
    background-color: {COLORS['bg_main']} !important;
    color: {COLORS['text_primary']} !important;
    border: 1px solid {COLORS['border']} !important;
    border-radius: 8px !important;
}}

/* ============================================================
   TARJETAS KPI — GRADIENT + HOVER ELEVATION
   ============================================================ */
div[data-testid="stMetric"],
div[data-testid="metric-container"],
.stMetric,
.kpi-card {{
    background: linear-gradient(140deg, #262934 0%, #1a1c24 100%) !important;
    padding: 1rem !important;
    border-radius: 14px !important;
    border: 1px solid rgba(255, 255, 255, 0.07) !important;
    backdrop-filter: blur(8px);
    transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1),
                box-shadow 0.25s ease,
                border-color 0.25s ease !important;
    min-height: 110px;
}}
div[data-testid="stMetric"]:hover,
div[data-testid="metric-container"]:hover,
.stMetric:hover,
.kpi-card:hover {{
    transform: translateY(-4px) !important;
    box-shadow: 0 12px 24px -6px rgba(0, 0, 0, 0.6),
                0 0 14px rgba(61, 133, 198, 0.3) !important;
    border-color: #3D85C6 !important;
}}
.kpi-label {{
    font-size: 0.8rem;
    font-weight: 500;
    color: {COLORS['text_secondary']};
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}}
.kpi-value {{
    font-size: 1.7rem;
    font-weight: 700;
    color: {COLORS['text_primary']};
    margin: 0;
    line-height: 1.2;
}}
.kpi-sub {{
    font-size: 0.85rem;
    font-weight: 500;
    margin-top: 4px;
}}
.kpi-sub.positive {{ color: {COLORS['gain']}; }}
.kpi-sub.negative {{ color: {COLORS['loss']}; }}
.kpi-sub.neutral  {{ color: {COLORS['text_secondary']}; }}

/* ============================================================
   BOTONES — HOVER LIFT
   ============================================================ */
div.stButton > button,
button[kind="primary"],
button[kind="secondary"] {{
    border-radius: 10px !important;
    transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1),
                box-shadow 0.2s ease,
                background-color 0.2s ease !important;
}}
div.stButton > button:hover,
button[kind="primary"]:hover,
button[kind="secondary"]:hover {{
    transform: translateY(-3px) !important;
    box-shadow: 0 8px 18px rgba(61, 133, 198, 0.35) !important;
}}

/* ============================================================
   PESTAÑAS (TABS) — SEGMENTED CONTROL / FLOATING PILLS
   ============================================================ */

/* --- CONTENEDOR DE PESTAÑAS (TABS BAR) --- */
div[data-baseweb="tab-list"],
div[data-testid="stTabs"] > div:first-child {{
    background-color: #1a1c23 !important;
    padding: 6px !important;
    border-radius: 12px !important;
    border: 1px solid #2d313d !important;
    display: inline-flex !important;
    gap: 8px !important;
    margin-bottom: 1.5rem !important;
}}

/* Ocultar la barra inferior por defecto de Streamlit */
div[data-baseweb="tab-highlight"],
div[data-baseweb="tab-border"] {{
    display: none !important;
}}

/* --- ESTILO BASE DE CADA CUADRO / PESTAÑA --- */
button[data-baseweb="tab"] {{
    background-color: #262934 !important;
    color: #a0a6b5 !important;
    font-weight: 500 !important;
    font-size: 0.90rem !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    border: 1px solid #363a49 !important;
    transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1) !important;
    cursor: pointer !important;
}}

/* --- ANIMACIÓN AL PASAR EL CURSOR (HOVER ELEVATION) --- */
button[data-baseweb="tab"]:hover {{
    transform: translateY(-3px) !important;
    background-color: #2f3442 !important;
    color: #ffffff !important;
    border-color: #3D85C6 !important;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4), 0 0 8px rgba(61, 133, 198, 0.3) !important;
}}

/* --- PESTAÑA SELECCIONADA / ACTIVA --- */
button[data-baseweb="tab"][aria-selected="true"] {{
    background-color: #3D85C6 !important;
    color: #ffffff !important;
    font-weight: 600 !important;
    border-color: #5ea4e4 !important;
    box-shadow: 0 4px 12px rgba(61, 133, 198, 0.35) !important;
    transform: translateY(-1px) !important;
}}

/* ============================================================
   INPUTS Y FORMULARIOS — FOCUS GLOW
   ============================================================ */
div[data-baseweb="input"],
div[data-baseweb="select"] > div {{
    border-radius: 10px !important;
    transition: border-color 0.2s ease,
                box-shadow 0.2s ease !important;
}}
div[data-baseweb="input"]:focus-within {{
    border-color: #3D85C6 !important;
    box-shadow: 0 0 0 2px rgba(61, 133, 198, 0.25) !important;
}}

/* ============================================================
   INDICADOR PULSANTE — CONEXIÓN SUPABASE
   ============================================================ */
@keyframes pulseGlow {{
    0%   {{ box-shadow: 0 0 0 0 rgba(46, 204, 113, 0.7); }}
    70%  {{ box-shadow: 0 0 0 8px rgba(46, 204, 113, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(46, 204, 113, 0); }}
}}
.status-pulse {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #2ecc71;
    animation: pulseGlow 2s infinite;
    margin-right: 8px;
    vertical-align: middle;
}}

/* ============================================================
   SECCIONES
   ============================================================ */
.section-header {{
    font-size: 1.1rem;
    font-weight: 600;
    color: {COLORS['text_primary']};
    padding-bottom: 8px;
    margin-top: 16px;
    margin-bottom: 8px;
    border-bottom: 2px solid {COLORS['accent']};
    display: inline-block;
}}

/* ============================================================
   TABLA DE DATOS
   ============================================================ */
.stDataFrame {{
    border-radius: 12px;
    overflow: hidden;
}}

/* ============================================================
   CONTENEDOR PLOTLY
   ============================================================ */
.stPlotlyChart {{
    background-color: {COLORS['bg_card']};
    border-radius: 12px;
    border: 1px solid {COLORS['border']};
    padding: 8px;
}}

/* ============================================================
   DIVIDER
   ============================================================ */
hr {{
    border: none;
    border-top: 1px solid {COLORS['border']};
    margin: 16px 0;
}}

/* ============================================================
   SCROLLBAR
   ============================================================ */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: {COLORS['bg_main']}; }}
::-webkit-scrollbar-thumb {{ background: {COLORS['border']}; border-radius: 3px; }}

/* ============================================================
   MARKET STATUS BADGE
   ============================================================ */
.market-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    vertical-align: middle;
}}
.market-badge.open {{
    background: rgba(46, 204, 113, 0.15);
    color: #2ecc71;
    border: 1px solid rgba(46, 204, 113, 0.3);
}}
.market-badge.closed {{
    background: rgba(160, 160, 160, 0.12);
    color: #a0a0a0;
    border: 1px solid rgba(160, 160, 160, 0.2);
}}

/* ============================================================
   BREAKDOWN CARD (Desglose Ganancia)
   ============================================================ */
.breakdown-card {{
    background: linear-gradient(140deg, #262934 0%, #1a1c24 100%) !important;
    border: 1px solid rgba(255, 255, 255, 0.07) !important;
    border-radius: 14px !important;
    padding: 1rem 1.2rem !important;
    backdrop-filter: blur(8px);
}}
.breakdown-label {{
    font-size: 0.75rem;
    font-weight: 500;
    color: {COLORS['text_secondary']};
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}}
.breakdown-value {{
    font-size: 1.15rem;
    font-weight: 700;
    color: {COLORS['text_primary']};
    margin: 0;
}}
.breakdown-sub {{
    font-size: 0.82rem;
    font-weight: 500;
    margin-top: 2px;
}}
.breakdown-sub.positive {{ color: {COLORS['gain']}; }}
.breakdown-sub.negative {{ color: {COLORS['loss']}; }}

/* ============================================================
   TÍTULOS
   ============================================================ */
h1, h2, h3, h4 {{
    color: {COLORS['text_primary']} !important;
    font-family: 'Inter', sans-serif;
}}
</style>
"""


# ---------------------------------------------------------------------------
# Funciones de obtención de datos
# ---------------------------------------------------------------------------


def _retry_yfinance(func, max_retries: int = 3, base_delay: float = 2.0):
    """Ejecuta una función de yfinance con retry y backoff exponencial.

    yfinance rate-limits desde IPs compartidas (nubes, VPNs).
    Backoff: 2s → 4s → 8s antes de rendirse.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                _time.sleep(delay)
            else:
                raise e


@st.cache_data(ttl=600, show_spinner=False)
def fetch_spy_data(period: str = "1y") -> Optional[pd.DataFrame]:
    """
    Descarga datos históricos de SPY desde yfinance.

    Args:
        period: Período de datos ('1mo', '6mo', '1y', '5y', 'max').

    Returns:
        DataFrame con OHLCV o None si falla la descarga.
    """
    try:
        def _fetch():
            ticker = yf.Ticker(TICKER_SPY)
            df = ticker.history(period=period, auto_adjust=True)
            if df.empty:
                return None
            return df
        df = _retry_yfinance(_fetch)
        if df is not None:
            df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception as e:
        st.error(f"Error al obtener datos de SPY: {e}")
        return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_current_price() -> Optional[float]:
    """
    Obtiene el precio de cierre más reciente de SPY.BA (BYMA).

    Retorna el precio en ARS porque SPY.BA ya cotiza en pesos.

    Returns:
        Precio actual en ARS (float) o None si falla.
    """
    try:
        def _fetch():
            ticker = yf.Ticker(TICKER_SPY)
            info = ticker.fast_info
            return float(info.last_price)
        return _retry_yfinance(_fetch)
    except Exception:
        pass
    try:
        def _fetch_hist():
            ticker = yf.Ticker(TICKER_SPY)
            data = ticker.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])
            return None
        result = _retry_yfinance(_fetch_hist)
        if result is not None:
            return result
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_exchange_rate() -> Optional[float]:
    """
    Obtiene el tipo de cambio USD/ARS actual.

    Returns:
        Tipo de cambio (float) o None si falla.
    """
    try:
        def _fetch():
            ticker = yf.Ticker(TICKER_USD_ARS)
            data = ticker.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])
            return None
        result = _retry_yfinance(_fetch)
        if result is not None:
            return result
    except Exception:
        pass

    # Fallback: API pública del Banco Nación
    try:
        import requests
        resp = requests.get(
            "https://api.bluelytics.com.ar/v2/latest",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return float(data["blue"]["value_avg"])
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Funciones de obtención de datos — SPY USD y CCL
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_spy_usd_price() -> Optional[float]:
    """
    Obtiene el precio actual de SPY en USD (NYSE).

    Returns:
        Precio en USD (float) o None si falla.
    """
    try:
        def _fetch():
            ticker = yf.Ticker(TICKER_SPY_USD)
            info = ticker.fast_info
            return float(info.last_price)
        return _retry_yfinance(_fetch)
    except Exception:
        pass
    try:
        def _fetch_hist():
            ticker = yf.Ticker(TICKER_SPY_USD)
            data = ticker.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])
            return None
        result = _retry_yfinance(_fetch_hist)
        if result is not None:
            return result
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Funciones de obtención de datos — QQQ
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600, show_spinner=False)
def fetch_qqq_data(period: str = "1y") -> Optional[pd.DataFrame]:
    """Descarga datos históricos de QQQ.BA desde yfinance."""
    try:
        def _fetch():
            ticker = yf.Ticker(TICKER_QQQ)
            df = ticker.history(period=period, auto_adjust=True)
            if df.empty:
                return None
            return df
        df = _retry_yfinance(_fetch)
        if df is not None:
            df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception:
        return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_qqq_current_price() -> Optional[float]:
    """Obtiene el precio actual de QQQ.BA en ARS."""
    try:
        def _fetch():
            ticker = yf.Ticker(TICKER_QQQ)
            info = ticker.fast_info
            return float(info.last_price)
        return _retry_yfinance(_fetch)
    except Exception:
        pass
    try:
        def _fetch_hist():
            ticker = yf.Ticker(TICKER_QQQ)
            data = ticker.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])
            return None
        result = _retry_yfinance(_fetch_hist)
        if result is not None:
            return result
    except Exception:
        pass
    return None


@st.cache_data(ttl=600, show_spinner=False)
def fetch_qqq_usd_price() -> Optional[float]:
    """Obtiene el precio actual de QQQ en USD (NASDAQ)."""
    try:
        def _fetch():
            ticker = yf.Ticker(TICKER_QQQ_USD)
            info = ticker.fast_info
            return float(info.last_price)
        return _retry_yfinance(_fetch)
    except Exception:
        pass
    try:
        def _fetch_hist():
            ticker = yf.Ticker(TICKER_QQQ_USD)
            data = ticker.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])
            return None
        result = _retry_yfinance(_fetch_hist)
        if result is not None:
            return result
    except Exception:
        pass
    return None


def calculate_ccl(spy_ars: float, spy_usd: float) -> Optional[float]:
    """
    Calcula el Dólar Contado con Liquidación (CCL) implícito.

    Fórmula: CCL = (SPY.BA_ARS * CEDEAR_RATIO) / SPY_USD

    Args:
        spy_ars: Precio de SPY.BA en ARS (BYMA).
        spy_usd: Precio de SPY en USD (NYSE).

    Returns:
        Tipo de cambio CCL (float) o None si faltan datos.
    """
    if not spy_ars or not spy_usd or spy_usd <= 0:
        return None
    return (spy_ars * CEDEAR_RATIO_SPY) / spy_usd


# ---------------------------------------------------------------------------
# Estado de mercado — BYMA
# ---------------------------------------------------------------------------

def is_market_open() -> tuple[bool, str]:
    """
    Verifica si el mercado de BYMA está abierto.

    Horario BYMA: 10:30 a 17:00 hs (Argentina), días hábiles (lun-vie).

    Returns:
        Tupla (is_open, status_html) con el estado del mercado.
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=lun, 6=dom
    current_time = now.time()

    market_open = dtime(10, 30)
    market_close = dtime(17, 0)

    is_trading_day = weekday < 5  # lun-vie
    is_trading_hours = market_open <= current_time <= market_close

    if is_trading_day and is_trading_hours:
        status_html = (
            "<span class='market-badge open'>"
            "<span style='font-size:0.65rem;'>🟢</span>"
            "Mercado Abierto (BYMA)"
            "</span>"
        )
        return True, status_html
    else:
        if not is_trading_day:
            reason = "Fin de semana"
        elif current_time < market_open:
            reason = f"Abre a las {market_open.strftime('%H:%M')}"
        else:
            reason = f"Cerró a las {market_close.strftime('%H:%M')}"

        status_html = (
            "<span class='market-badge closed'>"
            "<span style='font-size:0.65rem;'>⚪</span>"
            f"Mercado Cerrado — {reason}"
            "</span>"
        )
        return False, status_html


# ---------------------------------------------------------------------------
# Funciones de cálculos financieros
# ---------------------------------------------------------------------------

def calculate_portfolio_metrics(
    shares: float,
    avg_price_ars: float,
    current_price_usd: float,
    exchange_rate: float,
    price_ars: float = 0.0,
    ccl_rate: float = 0.0,
    buy_ccl: float = 0.0,
) -> dict:
    """
    Calcula todas las métricas de la cartera en ARS y USD.

    Incluye desglose de ganancia:
        - Rendimiento del subyacente en USD (variación del precio SPY).
        - Rendimiento cambiario por variación del CCL.

    Args:
        shares:            Cantidad de CEDEARs / acciones en posesión.
        avg_price_ars:     Precio promedio de compra por unidad en ARS.
        current_price_usd: Precio actual de mercado en USD (fallback).
        exchange_rate:     Tipo de cambio USD/ARS.
        price_ars:         Precio actual en ARS directo (SPY.BA).
        ccl_rate:          CCL actual calculado.
        buy_ccl:           CCL promedio al momento de la compra.

    Returns:
        Diccionario con todas las métricas calculadas.
    """
    # -- Resolver precio actual en ARS --
    if price_ars > 0:
        current_price_ars = price_ars
    else:
        current_price_ars = current_price_usd * exchange_rate

    avg_price_usd = avg_price_ars / exchange_rate if exchange_rate else 0

    total_value_ars = shares * current_price_ars
    total_cost_ars = shares * avg_price_ars
    pnl_ars = total_value_ars - total_cost_ars
    pnl_pct = (pnl_ars / total_cost_ars * 100) if total_cost_ars else 0

    total_value_usd = total_value_ars / exchange_rate if exchange_rate else 0
    total_cost_usd = shares * avg_price_usd
    pnl_usd = total_value_usd - total_cost_usd

    # -- Desglose: Subyacente vs Cambiario --
    # Rendimiento subyacente: variación del precio SPY en USD
    if buy_ccl > 0 and ccl_rate > 0:
        # Precio de compra en USD usando CCL de compra
        avg_price_usd_ccl = avg_price_ars / buy_ccl
        # Precio actual en USD usando CCL actual
        current_price_usd_ccl = current_price_ars / ccl_rate

        # Subyacente: ganancia por variación del activo en USD
        underlying_pnl_usd = (current_price_usd_ccl - avg_price_usd_ccl) * shares
        underlying_pnl_pct = (
            ((current_price_usd_ccl - avg_price_usd_ccl) / avg_price_usd_ccl * 100)
            if avg_price_usd_ccl else 0
        )

        # Cambiario: ganancia por variación del CCL
        # Si el CCL sube, el CEDEAR en ARS vale más aunque el subyacente no cambie
        fx_pnl_ars = shares * avg_price_usd_ccl * (ccl_rate - buy_ccl)
        fx_pnl_pct = (
            ((ccl_rate - buy_ccl) / buy_ccl * 100)
            if buy_ccl else 0
        )

        # Conversión a ARS del subyacente
        underlying_pnl_ars = underlying_pnl_usd * ccl_rate
    else:
        underlying_pnl_usd = 0.0
        underlying_pnl_pct = 0.0
        underlying_pnl_ars = 0.0
        fx_pnl_ars = 0.0
        fx_pnl_pct = 0.0

    return {
        "current_price_ars": current_price_ars,
        "current_price_usd": current_price_ars / exchange_rate if exchange_rate else 0,
        "avg_price_ars": avg_price_ars,
        "avg_price_usd": avg_price_usd,
        "total_value_ars": total_value_ars,
        "total_value_usd": total_value_usd,
        "total_cost_ars": total_cost_ars,
        "total_cost_usd": total_cost_usd,
        "pnl_ars": pnl_ars,
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_pct,
        # Desglose
        "underlying_pnl_usd": underlying_pnl_usd,
        "underlying_pnl_pct": underlying_pnl_pct,
        "underlying_pnl_ars": underlying_pnl_ars,
        "fx_pnl_ars": fx_pnl_ars,
        "fx_pnl_pct": fx_pnl_pct,
        "ccl_rate": ccl_rate,
        "buy_ccl": buy_ccl,
    }


def calculate_daily_change(df: pd.DataFrame) -> dict:
    """
    Calcula la variación diaria del precio de SPY.

    Args:
        df: DataFrame histórico con columna 'Close'.

    Returns:
        Diccionario con variación porcentual y monetaria.
    """
    if df is None or len(df) < 2:
        return {"pct": 0.0, "abs": 0.0, "prev_close": 0.0}

    current = float(df["Close"].iloc[-1])
    previous = float(df["Close"].iloc[-2])
    change_pct = ((current - previous) / previous) * 100 if previous else 0
    change_abs = current - previous

    return {
        "pct": change_pct,
        "abs": change_abs,
        "prev_close": previous,
    }


def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    """
    Calcula la Media Móvil Simple (SMA).

    Args:
        series: Serie de precios.
        window: Ventana de la media móvil.

    Returns:
        Serie con los valores SMA (NaN donde no hay suficientes datos).
    """
    return series.rolling(window=window, min_periods=window).mean()


# ---------------------------------------------------------------------------
# Métricas multi-asset — Consolidado SPY + QQQ
# ---------------------------------------------------------------------------

def calculate_consolidated_metrics(
    spy_metrics: dict,
    qqq_metrics: dict,
    display_currency: str = "ARS",
) -> dict:
    """
    Consolida métricas de SPY y QQQ en un único diccionario.

    Args:
        spy_metrics:       Resultado de calculate_portfolio_metrics() para SPY.
        qqq_metrics:       Resultado de calculate_portfolio_metrics() para QQQ.
        display_currency:  'USD' o 'ARS' para elegir qué campos consolidar.

    Returns:
        Diccionario con métricas consolidadas compatibles con render_kpi_cards.
    """
    if display_currency == "USD":
        total_value = (spy_metrics.get("total_value_usd", 0) or 0) + (qqq_metrics.get("total_value_usd", 0) or 0)
        total_cost = (spy_metrics.get("total_cost_usd", 0) or 0) + (qqq_metrics.get("total_cost_usd", 0) or 0)
        pnl = total_value - total_cost
        pnl_pct = (pnl / total_cost * 100) if total_cost else 0
        current_price = None  # No aplica para consolidado
        avg_price = total_cost / (spy_metrics.get("total_value_usd", 0) / spy_metrics.get("current_price_usd", 1) if spy_metrics.get("current_price_usd") else 0) if total_cost else 0
    else:
        total_value = (spy_metrics.get("total_value_ars", 0) or 0) + (qqq_metrics.get("total_value_ars", 0) or 0)
        total_cost = (spy_metrics.get("total_cost_ars", 0) or 0) + (qqq_metrics.get("total_cost_ars", 0) or 0)
        pnl = total_value - total_cost
        pnl_pct = (pnl / total_cost * 100) if total_cost else 0
        current_price = None
        avg_price = 0

    return {
        "current_price_usd": current_price,
        "current_price_ars": None,
        "avg_price_usd": avg_price if display_currency == "USD" else 0,
        "avg_price_ars": avg_price if display_currency == "ARS" else 0,
        "total_value_usd": total_value if display_currency == "USD" else 0,
        "total_value_ars": total_value if display_currency == "ARS" else 0,
        "total_cost_usd": total_cost if display_currency == "USD" else 0,
        "total_cost_ars": total_cost if display_currency == "ARS" else 0,
        "pnl_usd": pnl if display_currency == "USD" else 0,
        "pnl_ars": pnl if display_currency == "ARS" else 0,
        "pnl_pct": pnl_pct,
        "ccl_rate": spy_metrics.get("ccl_rate"),
        "buy_ccl": spy_metrics.get("buy_ccl"),
        # Campos extra para allocation
        "spy_value_ars": spy_metrics.get("total_value_ars", 0) or 0,
        "qqq_value_ars": qqq_metrics.get("total_value_ars", 0) or 0,
        "spy_value_usd": spy_metrics.get("total_value_usd", 0) or 0,
        "qqq_value_usd": qqq_metrics.get("total_value_usd", 0) or 0,
        "spy_cost_ars": spy_metrics.get("total_cost_ars", 0) or 0,
        "qqq_cost_ars": qqq_metrics.get("total_cost_ars", 0) or 0,
        "spy_pnl_pct": spy_metrics.get("pnl_pct", 0),
        "qqq_pnl_pct": qqq_metrics.get("pnl_pct", 0),
    }


def build_allocation_chart(metrics: dict, display_currency: str = "ARS") -> go.Figure:
    """
    Construye un gráfico de dona con la distribución actual del portafolio
    y la comparación contra la meta 70/30.

    Args:
        metrics:          Métricas consolidadas con spy_value y qqq_value.
        display_currency: Moneda para los labels.

    Returns:
        Objeto Plotly Figure con dona dual (actual vs objetivo).
    """
    if display_currency == "USD":
        spy_val = metrics.get("spy_value_usd", 0) or 0
        qqq_val = metrics.get("qqq_value_usd", 0) or 0
        curr_label = "USD"
    else:
        spy_val = metrics.get("spy_value_ars", 0) or 0
        qqq_val = metrics.get("qqq_value_ars", 0) or 0
        curr_label = "ARS"

    total = spy_val + qqq_val
    spy_pct = (spy_val / total * 100) if total else 0
    qqq_pct = (qqq_val / total * 100) if total else 0

    fig = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "pie"}, {"type": "pie"}]],
        subplot_titles=("Distribución Actual", "Objetivo 70/30"),
    )

    # -- Dona 1: Distribución actual --
    fig.add_trace(
        go.Pie(
            labels=["SPY (S&P 500)", "QQQ (Nasdaq 100)"],
            values=[spy_val, qqq_val],
            hole=0.55,
            marker=dict(colors=["#3D85C6", "#9B59B6"]),
            textinfo="label+percent",
            textfont=dict(size=12, color="white"),
            hovertemplate="%{label}<br>%{value:,.0f} " + curr_label + "<br>%{percent}<extra></extra>",
        ),
        row=1, col=1,
    )

    # -- Dona 2: Objetivo 70/30 --
    fig.add_trace(
        go.Pie(
            labels=["SPY (S&P 500)", "QQQ (Nasdaq 100)"],
            values=[70, 30],
            hole=0.55,
            marker=dict(colors=["#3D85C6", "#9B59B6"]),
            textinfo="label+percent",
            textfont=dict(size=12, color="white"),
            hovertemplate="%{label}<br>%{percent}<extra></extra>",
        ),
        row=1, col=2,
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=COLORS["text_primary"]),
        showlegend=False,
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        annotations=[
            dict(text=f"<b>{spy_pct:.1f}%</b><br>SPY", x=0.18, y=0.5, font_size=14, showarrow=False, font_color="#3D85C6"),
            dict(text=f"<b>{qqq_pct:.1f}%</b><br>QQQ", x=0.82, y=0.5, font_size=14, showarrow=False, font_color="#9B59B6"),
        ],
    )

    return fig


def calculate_dca_projection(
    monthly_amount: float,
    annual_rate: float,
    years: int,
) -> pd.DataFrame:
    """
    Proyecta el crecimiento de capital con aportes periódicos
    e interés compuesto (Dollar Cost Averaging).

    Args:
        monthly_amount: Monto del aporte mensual en USD.
        annual_rate:    Tasa de retorno anual estimada (ej: 0.10 para 10%).
        years:          Horizonte de inversión en años.

    Returns:
        DataFrame con columnas: mes, aporte_acumulado, capital_acumulado, intereses.
    """
    monthly_rate = annual_rate / 12
    total_months = years * 12

    records = []
    capital = 0.0
    total_contributed = 0.0

    for month in range(1, total_months + 1):
        capital = capital * (1 + monthly_rate) + monthly_amount
        total_contributed += monthly_amount
        interest_earned = capital - total_contributed

        records.append({
            "Mes": month,
            "Año": round(month / 12, 1),
            "Aporte Acumulado (USD)": round(total_contributed, 2),
            "Capital Acumulado (USD)": round(capital, 2),
            "Intereses (USD)": round(interest_earned, 2),
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Proyección personalizada — Capital Inicial + DCA Futuro
# ---------------------------------------------------------------------------

def calculate_custom_projection(
    capital_inicial: float,
    aporte_mensual: float,
    tasa_anual: float,
    anios: int,
) -> dict:
    """
    Proyecta el crecimiento de un capital existente + aportes futuros.

    Fórmulas:
        FV_capital = PV × (1 + r)^n
        FV_aportes = PMT × (((1 + r)^n - 1) / r)   si r > 0
        FV_aportes = PMT × n                         si r = 0

    Args:
        capital_inicial: Valor actual del portafolio (PV).
        aporte_mensual:  Monto recurrente mensual (PMT).
        tasa_anual:      Tasa anual estimada como decimal (ej: 0.10 = 10%).
        anios:           Horizonte en años.

    Returns:
        Diccionario con resultados + DataFrame mensual.
    """
    meses = anios * 12
    r_mensual = tasa_anual / 12

    # -- Curva mes a mes --
    records = []
    capital_acumulado = capital_inicial
    total_aportado_bolsillo = capital_inicial

    for mes in range(0, meses + 1):
        if mes == 0:
            fv_capital = capital_inicial
            fv_aportes = 0.0
        else:
            fv_capital = capital_inicial * ((1 + r_mensual) ** mes)
            if r_mensual > 0:
                fv_aportes = aporte_mensual * (((1 + r_mensual) ** mes - 1) / r_mensual)
            else:
                fv_aportes = aporte_mensual * mes

        total_aportado = capital_inicial + (aporte_mensual * mes)
        valor_total = fv_capital + fv_aportes
        intereses = valor_total - total_aportado

        records.append({
            "Mes": mes,
            "Año": round(mes / 12, 1),
            "Aportado (Bolsillo)": round(total_aportado, 2),
            "Valor Total Proyectado": round(valor_total, 2),
            "Intereses Ganados": round(intereses, 2),
        })

    df = pd.DataFrame(records)

    # -- Resultados finales --
    fv_capital_final = capital_inicial * ((1 + r_mensual) ** meses) if meses > 0 else capital_inicial
    if r_mensual > 0:
        fv_aportes_final = aporte_mensual * (((1 + r_mensual) ** meses - 1) / r_mensual)
    else:
        fv_aportes_final = aporte_mensual * meses

    total_aportado_final = capital_inicial + (aporte_mensual * meses)
    capital_final_total = fv_capital_final + fv_aportes_final
    intereses_totales = capital_final_total - total_aportado_final

    return {
        "df": df,
        "capital_inicial": capital_inicial,
        "fv_capital": fv_capital_final,
        "fv_aportes": fv_aportes_final,
        "total_aportado": total_aportado_final,
        "capital_final": capital_final_total,
        "intereses_totales": intereses_totales,
        "meses": meses,
        "r_mensual": r_mensual,
    }


def build_custom_projection_chart(df: pd.DataFrame, currency: str = "USD") -> go.Figure:
    """
    Construye el gráfico de proyección personalizada con 3 capas.

    Capas:
        1. Línea azul:  Total aportado de bolsillo (Capital Inicial + Aportes).
        2. Línea verde: Valor total proyectado (con interés compuesto).
        3. Área sombreada: Brecha de ganancia pura (intereses).

    Args:
        df:        DataFrame de calculate_custom_projection.
        currency:  'USD' o 'ARS' para el label del eje Y.

    Returns:
        Objeto Plotly Figure.
    """
    fig = go.Figure()

    # -- Capa 1: Total aportado (azul) --
    fig.add_trace(go.Scatter(
        x=df["Mes"],
        y=df["Aportado (Bolsillo)"],
        name="Total Aportado",
        line=dict(color="#3D85C6", width=2.5),
        mode="lines",
    ))

    # -- Capa 2: Valor total proyectado (verde) --
    fig.add_trace(go.Scatter(
        x=df["Mes"],
        y=df["Valor Total Proyectado"],
        name="Valor Total",
        line=dict(color="#2ECC71", width=2.5),
        mode="lines",
    ))

    # -- Capa 3: Área de intereses (sombreado) --
    fig.add_trace(go.Scatter(
        x=df["Mes"],
        y=df["Valor Total Proyectado"],
        name="Intereses Ganados",
        fill="tonexty",
        fillcolor="rgba(46, 204, 113, 0.12)",
        line=dict(color="rgba(46, 204, 113, 0.4)", width=1, dash="dot"),
        mode="lines",
    ))

    # -- Layout --
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=COLORS["text_primary"]),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Mes",
        yaxis_title=currency,
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.04)",
            showgrid=False,
            tickfont=dict(size=10, color=COLORS.get("tv_crosshair", "#758696")),
        ),
        yaxis=dict(
            gridcolor="rgba(255,255,255,0.04)",
            showgrid=False,
            tickfont=dict(size=10, color=COLORS.get("tv_crosshair", "#758696")),
        ),
        height=420,
        hovermode="x unified",
    )

    return fig


# ---------------------------------------------------------------------------
# Funciones de formato (presentation layer)
# ---------------------------------------------------------------------------

def fmt_usd(value: float) -> str:
    """Formatea un valor como moneda USD."""
    return f"USD {value:,.2f}"


def fmt_ars(value: float) -> str:
    """Formatea un valor como moneda ARS (formato argentino: 40.800)."""
    abs_val = abs(value)
    formatted = f"{abs_val:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if value < 0 else ''}ARS {formatted}"


def fmt_pct(value: float) -> str:
    """Formatea un valor como porcentaje con signo."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def fmt_change(value: float) -> str:
    """Formatea variación absoluta con signo."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:,.2f}"


def fmt_date(date_str: str) -> str:
    """
    Formatea una cadena ISO de fecha (YYYY-MM-DD) a formato local.

    Args:
        date_str: Cadena de fecha en formato ISO.

    Returns:
        Fecha formateada como DD/MM/YYYY o el original si falla.
    """
    if not date_str:
        return "—"
    try:
        dt = datetime.fromisoformat(str(date_str))
        return dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(date_str)


# ---------------------------------------------------------------------------
# Funciones de construcción de gráficos Plotly
# ---------------------------------------------------------------------------

def build_candlestick_chart(
    df: pd.DataFrame,
    show_sma50: bool = True,
    show_sma200: bool = True,
    show_volume: bool = True,
) -> go.Figure:
    """
    Construye un gráfico de velas estilo TradingView.

    Elementos visuales:
        - Cabecera OHLC fija (esquina superior izquierda)
        - Línea horizontal punteada en el precio actual con badge
        - Colores de velas TradingView (verde #089981 / rojo #F23645)
        - Fondo #131722, grilla sutil, sin rangeslider

    Args:
        df:             DataFrame histórico con OHLCV.
        show_sma50:     Mostrar SMA de 50 períodos.
        show_sma200:    Mostrar SMA de 200 períodos.
        show_volume:    Mostrar sub-gráfico de volumen.

    Returns:
        Objeto Plotly Figure listo para renderizar.
    """
    has_volume = show_volume and "Volume" in df.columns

    # -- Último registro para OHLC header --
    last = df.iloc[-1]
    o_last, h_last, l_last, c_last = (
        float(last["Open"]),
        float(last["High"]),
        float(last["Low"]),
        float(last["Close"]),
    )
    var_abs = c_last - o_last
    var_pct = (var_abs / o_last * 100) if o_last else 0
    is_bull = c_last >= o_last
    ohlc_color = COLORS["tv_bull"] if is_bull else COLORS["tv_bear"]

    # -- Subplot: velas (+ SMAs) arriba, volumen abajo --
    if has_volume:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.025,
            row_heights=[0.80, 0.20],
        )
    else:
        fig = make_subplots(rows=1, cols=1)

    # ================================================================
    # Velas japonesas — colores TradingView
    # ================================================================
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="SPY.BA",
            increasing_line_color=COLORS["tv_bull"],
            decreasing_line_color=COLORS["tv_bear"],
            increasing_fillcolor=COLORS["tv_bull"],
            decreasing_fillcolor=COLORS["tv_bear"],
        ),
        row=1, col=1,
    )

    # ================================================================
    # SMA 50
    # ================================================================
    if show_sma50:
        sma50 = calculate_sma(df["Close"], 50)
        fig.add_trace(
            go.Scatter(
                x=df.index, y=sma50,
                name="SMA 50",
                line=dict(color="#F7931A", width=1.0),
                opacity=0.85,
            ),
            row=1, col=1,
        )

    # ================================================================
    # SMA 200
    # ================================================================
    if show_sma200 and len(df) >= 200:
        sma200 = calculate_sma(df["Close"], 200)
        fig.add_trace(
            go.Scatter(
                x=df.index, y=sma200,
                name="SMA 200",
                line=dict(color="#9C27B0", width=1.0),
                opacity=0.85,
            ),
            row=1, col=1,
        )

    # ================================================================
    # Volumen
    # ================================================================
    if has_volume:
        colors_vol = [
            COLORS["tv_bull"] if c >= o else COLORS["tv_bear"]
            for c, o in zip(df["Close"], df["Open"])
        ]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="Volumen",
                marker_color=colors_vol,
                opacity=0.35,
            ),
            row=2, col=1,
        )

    # ================================================================
    # Línea horizontal punteada en el precio actual + badge derecho
    # ================================================================
    badge_bg = COLORS["tv_bull"] if is_bull else COLORS["tv_bear"]
    badge_text = f"{c_last:,.0f}"

    fig.add_hline(
        y=c_last,
        row=1, col=1,
        line=dict(color=ohlc_color, width=1, dash="dot"),
        annotation=dict(
            text=f"  {badge_text}  ",
            font=dict(size=11, color="#FFFFFF", family="Inter, sans-serif"),
            bgcolor=badge_bg,
            bordercolor=badge_bg,
            borderwidth=1,
            borderpad=3,
            xref="paper", x=1.0,
            xanchor="left",
        ),
    )

    # ================================================================
    # Cabecera OHLC — anotación fija esquina superior izquierda
    # ================================================================
    ohlc_text = (
        f"O: {o_last:,.0f}  "
        f"H: {h_last:,.0f}  "
        f"L: {l_last:,.0f}  "
        f"C: {c_last:,.0f}  "
        f"Var: {var_abs:+,.0f} ({var_pct:+.2f}%)"
    )

    fig.add_annotation(
        text=ohlc_text,
        xref="paper", yref="paper",
        x=0.01, y=0.98,
        xanchor="left", yanchor="top",
        showarrow=False,
        font=dict(size=12, color=ohlc_color, family="Courier New, monospace"),
        bgcolor="rgba(19, 23, 34, 0.85)",
        bordercolor=ohlc_color,
        borderwidth=1,
        borderpad=6,
    )

    # ================================================================
    # Layout general — estilo TradingView
    # ================================================================
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=COLORS["tv_bg"],
        plot_bgcolor=COLORS["tv_bg"],
        font=dict(family="Inter, sans-serif", color=COLORS["tv_text"]),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=10, color=COLORS["tv_crosshair"]),
            bgcolor="rgba(19, 23, 34, 0.7)",
        ),
        margin=dict(l=0, r=60, t=10, b=0),
        xaxis_rangeslider_visible=False,
        height=650 if has_volume else 460,
        dragmode="pan",
        hovermode="x unified",
    )

    # ================================================================
    # Ejes — grilla limpia estilo TradingView
    # ================================================================
    fig.update_xaxes(
        gridcolor=COLORS["tv_grid"],
        gridwidth=1,
        showgrid=False,
        zeroline=False,
        linecolor=COLORS["tv_grid"],
        tickfont=dict(size=10, color=COLORS["tv_crosshair"]),
        rangebreaks=[dict(bounds=["sat", "mon"])],
    )
    fig.update_yaxes(
        gridcolor=COLORS["tv_grid"],
        gridwidth=1,
        showgrid=True,
        zeroline=False,
        side="right",
        tickfont=dict(size=10, color=COLORS["tv_crosshair"]),
    )

    # Título del eje Y principal
    fig.update_yaxes(title_text="", row=1, col=1)

    if has_volume:
        fig.update_xaxes(
            gridcolor=COLORS["tv_grid"],
            showgrid=True,
            row=2, col=1,
        )
        fig.update_yaxes(
            showgrid=False,
            tickfont=dict(size=9, color=COLORS["tv_crosshair"]),
            row=2, col=1,
        )

    return fig


def build_dca_chart(df: pd.DataFrame) -> go.Figure:
    """
    Construye el gráfico de proyección DCA con áreas apiladas.

    Args:
        df: DataFrame resultante de calculate_dca_projection.

    Returns:
        Objeto Plotly Figure.
    """
    fig = go.Figure()

    # -- Aportes acumulados --
    fig.add_trace(go.Scatter(
        x=df["Mes"],
        y=df["Aporte Acumulado (USD)"],
        name="Aportes",
        fill="tozeroy",
        fillcolor="rgba(61, 133, 198, 0.2)",
        line=dict(color=COLORS["accent"], width=2),
    ))

    # -- Capital total --
    fig.add_trace(go.Scatter(
        x=df["Mes"],
        y=df["Capital Acumulado (USD)"],
        name="Capital Total",
        fill="tonexty",
        fillcolor="rgba(46, 204, 113, 0.15)",
        line=dict(color=COLORS["gain"], width=2),
    ))

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=COLORS["text_primary"]),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
        margin=dict(l=0, r=0, t=10, b=0),
        xaxis_title="Mes",
        yaxis_title="USD",
        xaxis=dict(gridcolor="rgba(255,255,255,0.04)", showgrid=False),
        yaxis=dict(gridcolor="rgba(255,255,255,0.04)", showgrid=False),
        height=380,
    )

    return fig
