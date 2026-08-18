"""
db.py — Capa de acceso a datos con Supabase.

CRUD completo para la tabla `transacciones`:
    - Inicialización del cliente Supabase (secrets / env vars)
    - Lectura de transacciones por ticker
    - Escritura de nuevas compras
    - Eliminación de transacciones
    - Cálculo de Precio Promedio Ponderado de Compra (PPC)

Requisitos previos en Supabase:
    1. Crear la tabla `transacciones` con el schema indicado abajo.
    2. Habilitar RLS (Row Level Security) con una política permisiva
       para el rol `anon` durante desarrollo.
"""

import os
import streamlit as st
from datetime import date, datetime
from typing import Optional

from supabase import create_client, Client


# ---------------------------------------------------------------------------
# Schema SQL para crear en Supabase (Panel > SQL Editor)
# ---------------------------------------------------------------------------

SQL_CREATE_TABLE = """
-- Tabla de transacciones de compra de CEDEARs / acciones
CREATE TABLE IF NOT EXISTS transacciones (
    id                  BIGSERIAL PRIMARY KEY,
    ticker              TEXT           NOT NULL DEFAULT 'SPY',
    cantidad            NUMERIC(12,4) NOT NULL CHECK (cantidad > 0),
    precio_unitario_ars NUMERIC(14,2) NOT NULL CHECK (precio_unitario_ars > 0),
    fecha               DATE           NOT NULL DEFAULT CURRENT_DATE,
    notas               TEXT,
    monto_total_ars     DOUBLE PRECISION,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

-- Índice para búsquedas por ticker
CREATE INDEX IF NOT EXISTS idx_transacciones_ticker
    ON transacciones (ticker, fecha DESC);

-- Habilitar RLS (ajustar políticas según necesidad)
ALTER TABLE transacciones ENABLE ROW LEVEL SECURITY;

-- Política permisiva para desarrollo (anon + authenticated)
CREATE POLICY "Permitir todo en desarrollo"
    ON transacciones
    FOR ALL
    USING (true)
    WITH CHECK (true);
"""


# ---------------------------------------------------------------------------
# Inicialización del cliente Supabase
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_supabase_client() -> Optional[Client]:
    """
    Inicializa y cachea el cliente de Supabase.

    Prioridad de configuración:
        1. st.secrets (Streamlit secrets)
        2. Variables de entorno (SUPABASE_URL, SUPABASE_KEY)

    Returns:
        Cliente Client de supabase-py o None si falta configuración.
    """
    url = None
    key = None

    # -- Intento 1: Streamlit secrets --
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except (KeyError, FileNotFoundError):
        pass

    # -- Intento 2: Variables de entorno --
    if not url or not key:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        return None

    try:
        client = create_client(url, key)
        return client
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CRUD — Lectura
# ---------------------------------------------------------------------------

def fetch_transactions(
    ticker: str = "SPY",
    order_desc: bool = True,
) -> list[dict]:
    """
    Obtiene todas las transacciones de un ticker desde Supabase.

    Args:
        ticker:     Símbolo del activo (default: 'SPY').
        order_desc: Si True, ordena por fecha descendente.

    Returns:
        Lista de diccionarios con las transacciones.
    """
    client = get_supabase_client()
    if client is None:
        return []

    try:
        query = client.table("transacciones").select("*").eq("ticker", ticker)

        if order_desc:
            query = query.order("fecha", desc=True)
        else:
            query = query.order("fecha", desc=False)

        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error al consultar transacciones: {e}")
        return []


def fetch_all_transactions(order_desc: bool = True) -> list[dict]:
    """
    Obtiene TODAS las transacciones de TODOS los tickers desde Supabase.

    Args:
        order_desc: Si True, ordena por fecha descendente.

    Returns:
        Lista de diccionarios con todas las transacciones (SPY, QQQ, etc.).
    """
    client = get_supabase_client()
    if client is None:
        return []

    try:
        query = client.table("transacciones").select("*")

        if order_desc:
            query = query.order("fecha", desc=True)
        else:
            query = query.order("fecha", desc=False)

        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error al consultar transacciones: {e}")
        return []


# ---------------------------------------------------------------------------
# CRUD — Escritura
# ---------------------------------------------------------------------------

def insert_transaction(
    ticker: str,
    cantidad: float,
    precio_unitario_ars: float,
    fecha: date,
    notas: str = "",
    monto_total_ars: float = 0.0,
) -> Optional[dict]:
    """
    Inserta una nueva transacción de compra en Supabase.

    Args:
        ticker:             Símbolo del activo.
        cantidad:           Cantidad de unidades compradas.
        precio_unitario_ars: Precio por unidad en ARS.
        fecha:              Fecha de la operación.
        notas:              Notas opcionales.
        monto_total_ars:    Monto total de la operación en ARS.

    Returns:
        Diccionario con la transacción insertada o None si falla.
    """
    client = get_supabase_client()
    if client is None:
        st.error("No hay conexión a Supabase. Verificá la configuración.")
        return None

    payload = {
        "ticker": ticker.upper().strip(),
        "cantidad": int(cantidad),
        "precio_unitario_ars": round(float(precio_unitario_ars), 2),
        "monto_total_ars": round(float(monto_total_ars), 2),
        "fecha": fecha.isoformat(),
        "notas": notas.strip(),
    }

    try:
        result = client.table("transacciones").insert(payload).execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        st.error(f"Error al insertar transacción: {e}")
        return None


# ---------------------------------------------------------------------------
# CRUD — Eliminación
# ---------------------------------------------------------------------------

def delete_transaction(transaction_id: int) -> bool:
    """
    Elimina una transacción por su ID.

    Args:
        transaction_id: ID numérico de la transacción a eliminar.

    Returns:
        True si se eliminó correctamente, False si falló.
    """
    client = get_supabase_client()
    if client is None:
        return False

    try:
        result = (
            client.table("transacciones")
            .delete()
            .eq("id", transaction_id)
            .execute()
        )
        return True
    except Exception as e:
        st.error(f"Error al eliminar transacción: {e}")
        return False


# ---------------------------------------------------------------------------
# Cálculos financieros sobre datos de DB
# ---------------------------------------------------------------------------

def calculate_ppc(transactions: list[dict]) -> dict:
    """
    Calcula el Precio Promedio Ponderado de Compra (PPC) y
    las métricas acumuladas a partir de las transacciones.

    Fórmula PPC:
        PPC = Σ(cantidad_i × precio_i) / Σ(cantidad_i)

    Args:
        transactions: Lista de diccionarios con 'cantidad' y 'precio_unitario_ars'.

    Returns:
        Diccionario con:
            - total_shares:     Total de unidades acumuladas.
            - total_cost_ars:   Costo total invertido en ARS.
            - ppc_ars:          Precio Promedio Ponderado en ARS.
            - transaction_count: Cantidad de operaciones realizadas.
            - first_purchase:   Fecha de primera compra (str o None).
            - last_purchase:    Fecha de última compra (str o None).
    """
    if not transactions:
        return {
            "total_shares": 0.0,
            "total_cost_ars": 0.0,
            "ppc_ars": 0.0,
            "transaction_count": 0,
            "first_purchase": None,
            "last_purchase": None,
        }

    total_shares = 0.0
    total_cost_ars = 0.0

    for tx in transactions:
        cantidad = float(tx.get("cantidad", 0))
        precio = float(tx.get("precio_unitario_ars", 0))
        total_shares += cantidad
        total_cost_ars += cantidad * precio

    ppc_ars = total_cost_ars / total_shares if total_shares > 0 else 0.0

    # Fechas extremas (transacciones vienen ordenadas por fecha DESC)
    last_purchase = transactions[0].get("fecha") if transactions else None
    first_purchase = transactions[-1].get("fecha") if transactions else None

    return {
        "total_shares": round(total_shares, 4),
        "total_cost_ars": round(total_cost_ars, 2),
        "ppc_ars": round(ppc_ars, 2),
        "transaction_count": len(transactions),
        "first_purchase": first_purchase,
        "last_purchase": last_purchase,
    }


# ---------------------------------------------------------------------------
# Utilidades — SQL de referencia
# ---------------------------------------------------------------------------

def get_create_table_sql() -> str:
    """
    Retorna el SQL para crear la tabla `transacciones` en Supabase.
    Útil para copiar y pegar en el SQL Editor del panel.
    """
    return SQL_CREATE_TABLE.strip()
