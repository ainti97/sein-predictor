import requests
import pandas as pd
from datetime import date, timedelta

BASE = 'https://appserver.coes.org.pe/waMediciones/api'

class COESError(Exception):
    pass

def fetch(endpoint, params):
    try:
        response = requests.get(f'{BASE}/{endpoint}', params=params, timeout=25,
                                headers={'Accept': 'application/json', 'User-Agent': 'SEIN-Predictor/0.1'})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise COESError(f'Respuesta inesperada de {endpoint}: {str(payload)[:200]}')
        return [row for row in payload if isinstance(row, dict) and '$ref' not in row]
    except (requests.RequestException, ValueError) as exc:
        raise COESError(f'No fue posible consultar COES: {exc}') from exc

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
    return df.dropna(subset=['fecha_hora','mw']).sort_values('fecha_hora')

def mediciones(code, start, end):
    if (end-start).days > 6:
        raise ValueError('La consulta debe abarcar hasta siete fechas.')
    rows = fetch('Mediciones', {'lectcodi': code, 'fechaIni': start.strftime('%d/%m/%Y'),
                                'fechaFin': end.strftime('%d/%m/%Y')})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    if 'Medifecha' not in df:
        raise COESError('Falta Medifecha en la respuesta.')
    long = df.melt(id_vars=[c for c in df.columns if not (c.startswith('H') and c[1:].isdigit())],
                   value_vars=[f'H{i}' for i in range(1,49) if f'H{i}' in df],
                   var_name='intervalo', value_name='mw')
    long['fecha'] = pd.to_datetime(long['Medifecha'], dayfirst=True, errors='coerce')
    long['mw'] = pd.to_numeric(long['mw'], errors='coerce')
    long['fecha_hora'] = long['fecha'] + pd.to_timedelta(long['intervalo'].str[1:].astype(int)*30, unit='min')
    return long.dropna(subset=['fecha_hora','mw'])

def series_keys(df):
    cols = ['Ptomedicodi', 'NombreEquipo', 'CodigoEquipo', 'Emprnomb', 'NombreUbicacion']
    return [c for c in cols if c in df.columns]
