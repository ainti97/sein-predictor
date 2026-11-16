from datetime import date, timedelta
import calendar
import pandas as pd
import streamlit as st
import plotly.express as px
from coes import ranking, mediciones, series_keys, COESError

st.set_page_config(page_title='SEIN Predictor | Coincidencia HP',page_icon='⚡',layout='wide')
st.title('⚡ SEIN Predictor | Coincidencia HP')
st.caption('Versión 0.2 · COES en vivo · Histórico multimensual · Diagnóstico semanal')
st.warning('Los resultados filtrados por horario son CANDIDATOS a coincidencia HP, NO valores oficiales de potencia coincidente facturable. Validar horario, procedimiento, tipo de serie y contrato antes de decisiones de planta.')

@st.cache_data(ttl=3600,show_spinner=False)
def get_ranking(y,m): return ranking(date(y,m,1))
@st.cache_data(ttl=1800,show_spinner=False)
def get_measures(code,start,end): return mediciones(code,start,end)

with st.sidebar:
    st.header('Configuración HP')
    hp_start=st.time_input('Inicio de ventana HP',value=pd.Timestamp('18:00').time(),step=900)
    hp_end=st.time_input('Fin de ventana HP',value=pd.Timestamp('23:00').time(),step=900)
    days=st.multiselect('Días incluidos (0=lunes)',list(range(7)),default=list(range(6)),format_func=lambda x:['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'][x])
    st.caption('Configuración de análisis editable. No constituye verificación del procedimiento de coincidencia aplicable.')

def hp_filter(df):
    if df.empty:return df.copy()
    if hp_start>=hp_end: raise ValueError('La hora inicial debe ser menor que la final.')
    d=df.copy()
    d=d[d['fecha_hora'].dt.dayofweek.isin(days)]
    return d[(d['fecha_hora'].dt.time>=hp_start)&(d['fecha_hora'].dt.time<hp_end)].copy()

t1,t2,t3=st.tabs(['Histórico HP por mes','Programación semanal','Metodología y validación'])
with t1:
    st.subheader('Histórico mensual — candidatos HP')
    a,b,c=st.columns(3)
    y=a.number_input('Año',min_value=2018,max_value=2035,value=date.today().year,step=1)
    first=b.selectbox('Mes inicial',list(range(1,13)),index=0)
    last=c.selectbox('Mes final',list(range(1,13)),index=date.today().month-1)
    if st.button('Consultar meses COES',type='primary'):
        if first>last: st.error('Mes inicial debe ser menor o igual al final.')
        else:
            results=[]; failures=[]; samples=[]
            with st.spinner('Consultando meses...'):
                for m in range(first,last+1):
                    try:
                        raw=get_ranking(int(y),m)
                        if raw.empty: failures.append(f'{m:02d}: sin datos');continue
                        hp=hp_filter(raw)
                        if hp.empty: failures.append(f'{m:02d}: sin valores dentro de HP');continue
                        top=hp.loc[hp['mw'].idxmax()]
                        results.append({'Mes':f'{int(y)}-{m:02d}','Fecha':top['fecha_hora'].date(),'Día':top['fecha_hora'].strftime('%A'),'Hora':top['fecha_hora'].strftime('%H:%M'),'MW':float(top['mw']),'Registros HP':len(hp)})
                        hp['mes']=f'{int(y)}-{m:02d}';samples.append(hp)
                    except (COESError,ValueError,KeyError) as exc:failures.append(f'{m:02d}: {str(exc)[:130]}')
            st.session_state['hp_months']=pd.DataFrame(results)
            st.session_state['hp_samples']=pd.concat(samples,ignore_index=True) if samples else pd.DataFrame()
            st.session_state['hp_errors']=failures
    if 'hp_months' in st.session_state:
        summary=st.session_state['hp_months']
        if not summary.empty:
            st.dataframe(summary,use_container_width=True,hide_index=True)
            st.plotly_chart(px.bar(summary,x='Mes',y='MW',title='Máximo encontrado en ventana HP (no oficial)'),use_container_width=True)
            st.download_button('Descargar histórico CSV',summary.to_csv(index=False).encode('utf-8-sig'),'historico_candidatos_hp.csv','text/csv')
            st.info('Este máximo se obtiene filtrando el ranking devuelto por la API. No se ha comprobado que la API represente la serie oficial de demanda total coincidente del SEIN.')
        else:st.warning('No hay resultados válidos para la selección.')
        if st.session_state['hp_errors']:st.warning('Consultas incompletas: '+' | '.join(st.session_state['hp_errors']))
with t2:
    st.subheader('Programación semanal — inspección de series')
    start=st.date_input('Inicio de semana',date.today()-timedelta(days=date.today().weekday()))
    end=start+timedelta(days=6)
    code=st.selectbox('Tipo de lectura', [3,4,6],format_func=lambda x:{3:'Programación semanal',4:'Programación diaria',6:'Ejecutado'}[x])
    if st.button('Consultar programación COES'):
        try:st.session_state['weekly']=get_measures(code,start,end)
        except (COESError,ValueError) as exc:st.error(str(exc))
    if 'weekly' in st.session_state:
        df=st.session_state['weekly']
        if df.empty:st.warning('La API no devolvió registros.')
        else:
            keys=series_keys(df)
            if keys:
                key=st.selectbox('Columna identificadora',keys)
                options=df[key].dropna().astype(str).unique().tolist()
                selected=st.selectbox('Serie (sin agregación automática)',options) if options else None
                view=df[df[key].astype(str)==selected].copy() if selected else df.copy()
            else:view=df.copy()
            try:
                hp=hp_filter(view)
                if hp.empty:st.warning('No hay registros en la ventana HP configurada.')
                else:
                    hp['Día']=hp['fecha_hora'].dt.strftime('%Y-%m-%d')
                    peaks=hp.groupby('Día',as_index=False)['mw'].max().sort_values('mw',ascending=False)
                    st.markdown('**Máximos por día de la serie seleccionada — NO pronóstico de coincidencia SEIN**')
                    st.dataframe(peaks,use_container_width=True,hide_index=True)
                    st.plotly_chart(px.line(hp.sort_values('fecha_hora'),x='fecha_hora',y='mw',title='Curva de serie seleccionada dentro de HP'),use_container_width=True)
                    st.download_button('Descargar serie HP CSV',hp.to_csv(index=False).encode('utf-8-sig'),'serie_semanal_hp.csv','text/csv')
            except ValueError as exc:st.error(str(exc))
            st.warning('No sumar medidores ni llamar demanda total del SEIN a una serie no identificada. La predicción de coincidencia permanece deshabilitada hasta validar la serie agregada oficial.')
with t3:
    st.subheader('Estado de validación')
    st.markdown('''**Conectado:** consultas API COES, visualización histórica y mediciones por serie.\n\n**Por validar:** definición oficial de ventana HP y día hábil, correspondencia de `OrdenamientoMaximaDemanda` con la demanda total SEIN, zona horaria, resolución temporal y criterio contractual de facturación.\n\n**Pendiente:** identificar una fuente verificable de demanda total SEIN ejecutada y programada, guardar datos históricos, realizar backtesting temporal y calibrar probabilidades.\n\nNo se muestra una fecha predicha ni un porcentaje de probabilidad sin un modelo validado.''')
    st.markdown('[Documentación COES](https://appserver.coes.org.pe/waMediciones/Help) · [Portal máxima demanda](https://www.coes.org.pe/Portal/medidores/MaximaDemanda/index)')
