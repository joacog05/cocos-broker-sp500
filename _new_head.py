"""
utils.py — Módulo de utilidades para el Dashboard de Cartera S&P 500.

Contiene:
    - Configuración de estilos CSS (Dark Mode Fintech)
    - Funciones de obtención de datos bursátiles (yfinance)
    - Funciones de cálculos financieros (DCA, rendimiento, etc.)
    - Funciones de formatting para métricas y KPIs
"""

# ---------------------------------------------------------------------------
# Constantes — ANTES de imports para que estén disponibles incluso si
# alguna librería (yfinance, plotly) falla al importar en Python 3.14
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
    "tv_bg": "#131722",
    "tv_bull": "#089981",
    "tv_bear": "#F23645",
    "tv_grid": "rgba(42, 46, 57, 0.5)",
    "tv_text": "#D1D4DC",
    "tv_crosshair": "#758696",
}


# ---------------------------------------------------------------------------
# Imports de librerías (yfinance, plotly, pandas, streamlit)
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
