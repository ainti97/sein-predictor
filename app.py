from datetime import date, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
from coes import ranking, mediciones, series_keys, COESError

st.set_page_config(page_title='SEIN Predictor', page_icon='⚡', layout='wide')
st.title('⚡ SEIN Predictor | COES Perú')
st.caption('Versión 0.1 · Consultas en vivo · Datos sin simulación')
st.info('Los datos de programación y las mediciones por punto NO se consideran automáticamente demanda total del SEIN. Verifique el alcance de cada serie antes de tomar decisiones operativas.')

@st.cache_data(ttl=3600, show_spinner=False)
def load_ranking(y, m):
    return ranking(date(y,m,1))

@st.cache_data(ttl=1800, show_spinner=False)
def load_measure(code, start, end):
    return mediciones(code,start,end)

t1,t2,t3=st.tabs(['Histórico de máxima demanda','Programación semanal','Comparación y diagnóstico'])
with t1:
    c1,c2=st.columns(2)
    with c1: year=st.number_input('Año',min_value=2018,max_value=2035,value=date.today().year,step=1)
    with c2: month=st.selectbox('Mes',range(1,13),index=date.today().month-1)
    if st.button('Consultar histórico COES',type='primary'):
        try:
            df=load_ranking(year,month)
            if df.empty: st.warning('El COES no devolvió registros para el mes.')
            else:
                st.session_state['ranking']=df
                st.session_state['ranking_period']=(year,month)
        except (COESError,ValueError) as exc: st.error(str(exc))
    if 'ranking' in st.session_state:
        df=st.session_state['ranking']
        if not df.empty:
            top=df.loc[df['mw'].idxmax()]
            a,b,c=st.columns(3)
            a.metric('Mayor valor retornado',f"{top['mw']:,.2f} MW")
            b.metric('Fecha',top['fecha_hora'].strftime('%d/%m/%Y'))
            c.metric('Hora',top['fecha_hora'].strftime('%H:%M'))
            st.plotly_chart(px.line(df,x='fecha_hora',y='mw',title='Serie del ranking COES'),use_container_width=True)
            st.download_button('Descargar CSV histórico',df.to_csv(index=False).encode('utf-8-sig'),'ranking_coes.csv','text/csv')
            st.caption('Verificar el valor contra el reporte oficial de máxima demanda mensual. Puede haber rectificaciones.')
with t2:
    start=st.date_input('Inicio de semana',date.today()-timedelta(days=date.today().weekday()))
    end=start+timedelta(days=6)
    code=st.selectbox('Fuente',[3,4,6],format_func=lambda x:{3:'Programación semanal',4:'Programación diaria',6:'Ejecutado'}[x])
    st.caption(f'Consulta: {start:%d/%m/%Y} – {end:%d/%m/%Y}. La API devuelve series de medición, no necesariamente el total del SEIN.')
    if st.button('Consultar mediciones COES'):
        try:
            df=load_measure(code,start,end)
            if df.empty: st.warning('Sin registros en la respuesta.')
            else: st.session_state['measure']=df
        except (COESError,ValueError) as exc: st.error(str(exc))
    if 'measure' in st.session_state:
        df=st.session_state['measure']
        keys=series_keys(df)
        if keys:
            key=st.selectbox('Identificador de serie',keys)
            values=df[key].dropna().astype(str).unique().tolist()
            if values:
                chosen=st.selectbox('Serie específica (no sumar puntos sin validar)',values)
                view=df[df[key].astype(str)==chosen].copy()
            else: view=df.copy()
        else: view=df.copy()
        st.plotly_chart(px.line(view.sort_values('fecha_hora'),x='fecha_hora',y='mw',title='Mediciones de la serie seleccionada'),use_container_width=True)
        st.dataframe(view.head(100),use_container_width=True)
        st.download_button('Descargar CSV de mediciones',view.to_csv(index=False).encode('utf-8-sig'),'mediciones_coes.csv','text/csv')
with t3:
    st.subheader('Validación antes de habilitar predicción')
    st.markdown('''1. Confirmar que el ranking mensual coincide con el reporte oficial del COES.
2. Identificar una serie agregada representativa de la demanda total del SEIN, sin duplicar medidores ni sumar indebidamente puntos.
3. Obtener al menos 24 meses de histórico y guardar las versiones de los pronósticos semanales.
4. Entrenar un modelo con validación temporal: nunca usar datos futuros para pronosticar el pasado.
5. Publicar probabilidades por día solo después de medir aciertos, errores y calibración.''')
    st.warning('Estado: modelo predictivo aún NO entrenado. Esta versión conecta, inspecciona, grafica y exporta información oficial cuando la API responde.')
    st.markdown('[Documentación de API COES](https://appserver.coes.org.pe/waMediciones/Help) · [Reporte oficial de máxima demanda](https://www.coes.org.pe/Portal/medidores/MaximaDemanda/index)')
