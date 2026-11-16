"""Conector COES: diagnóstico HTTP y validación de series.
No certifica que las mediciones sean demanda agregada del SEIN.
"""
import requests
import pandas as pd
from datetime import datetime

BASE = 'https://appserver.coes.org.pe/waMediciones/api'

class COESError(Exception):
    pass

def fetch(endpoint, params):
    try:
        response = requests.get(
            f'{BASE}/{endpoint}', params=params, timeout=30,
            headers={'Accept': 'application/json', 'User-Agent': 'SEIN-Predictor/0.3'}
        )
    except requests.RequestException as exc:
        raise COESError(f'No se pudo conectar al COES: {exc}') from exc
    if not response.ok:
        detail = response.text[:700].replace('\n', ' ')
        raise COESError(
            f'COES respondió HTTP {response.status_code}. '
            f'Ruta: {endpoint}. Parámetros: {params}. '
            f'Detalle del servidor: {detail or "(sin detalle)"}'
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise COESError(f'COES no devolvió JSON en {endpoint}: {response.text[:300]}') from exc
    if not isinstance(payload, list):
        raise COESError(f'Respuesta inesperada de {endpoint}: {str(payload)[:300]}')
    return [row for row in payload if isinstance(row, dict) and '$ref' not in row]

def ranking(month):
    params = {'fecha': month.strftime('%m %Y'), 'empresas': '', 'tiposGeneracion': '0', 'central': 1}
    rows = fetch('OrdenamientoMaximaDemanda', params)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if not {'FechaHora', 'MaximaDemanda'}.issubset(df.columns):
        raise COESError('El COES modificó el formato del ranking de máxima demanda.')
    df['fecha_hora'] = pd.to_datetime(df['FechaHora'], dayfirst=True, errors='coerce')
    df['mw'] = pd.to_numeric(df['MaximaDemanda'], errors='coerce')
    return df.dropna(subset=['fecha_hora', 'mw']).sort_values('fecha_hora')

def mediciones(code, start, end):
    if end < start or (end - start).days > 6:
        raise ValueError('La consulta debe abarcar entre una y siete fechas inclusivas.')
    params = {'lectcodi': int(code), 'fechaIni': start.strftime('%d/%m/%Y'),
              'fechaFin': end.strftime('%d/%m/%Y')}
    rows = fetch('Mediciones', params)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if 'Medifecha' not in df.columns:
        raise COESError('Falta Medifecha en la respuesta.')
    hours = [f'H{i}' for i in range(1, 49) if f'H{i}' in df.columns]
    if not hours:
        raise COESError('La respuesta no incluye intervalos H1 a H48.')
    long = df.melt(id_vars=[c for c in df.columns if c not in hours],
                   value_vars=hours, var_name='intervalo', value_name='mw')
    long['fecha'] = pd.to_datetime(long['Medifecha'], dayfirst=True, errors='coerce')
    long['mw'] = pd.to_numeric(long['mw'], errors='coerce')
    # Convención H1 pendiente de contrastar con documentación/datos oficiales.
    # Se conserva el cálculo anterior hasta validar el sello horario.
    long['fecha_hora'] = long['fecha'] + pd.to_timedelta(
        long['intervalo'].str[1:].astype(int) * 30, unit='min'
    )
    return long.dropna(subset=['fecha_hora', 'mw'])

def series_keys(df):
    cols = ['Ptomedicodi', 'NombreEquipo', 'CodigoEquipo', 'Emprnomb', 'NombreUbicacion']
    return [c for c in cols if c in df.columns]
