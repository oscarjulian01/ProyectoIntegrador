import streamlit as str_root
import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# Configuración de la página del Dashboard
st.set_page_config(
    page_title="Everwod IA - Panel de Control de FAQs",
    page_icon="📊",
    layout="wide"
)

# Definición de URLs locales de los Microservicios
INGEST_URL = "http://127.0.0.1:8001"
SUGGESTION_URL = "http://127.0.0.1:8003"
VALIDATION_URL = "http://127.0.0.1:8004"

st.title("📊 Panel de Administración y Validación Humana de FAQs")
st.caption("Filtra, edita, aprueba o rechaza las sugerencias generadas por los modelos de IA local.")

# ==========================================
# 🔍 FUNCIÓN: VERIFICAR SALUD DE SERVICIOS
# ==========================================
def check_health(url):
    try:
        response = requests.get(f"{url}/health", timeout=2)
        if response.status_code == 200:
            return "✅ Activo"
    except:
        pass
    return "❌ Caído"

# Barra lateral para el Estado del Sistema
with st.sidebar:
    st.header("⚙️ Estado de la Red")
    st.write(f"**Ingest Service (8001):** {check_health(INGEST_URL)}")
    st.write(f"**Suggestion Service (8003):** {check_health(SUGGESTION_URL)}")
    st.write(f"**Validation Service (8004):** {check_health(VALIDATION_URL)}")
    st.markdown("---")
    reviewer_name = st.text_input("✍️ Nombre del Revisor", value="Oscar Torres")


tab_pipeline, tab_validation, tab_history = st.tabs([
    "🚀 Ejecutar Canalización", 
    "📥 Bandeja de Validación Humana", 
    "📜 Historial de FAQs Aprobadas"
])


# CONTROL DE LA CANALIZACIÓN

with tab_pipeline:
    st.header("Orquestación del Pipeline de Datos")
    st.write("Si requieres actualizar las sugerencias con los datos más recientes de PostgreSQL, ejecuta la canalización completa manualmente desde aquí.")
    
    col1, col2 = st.columns(2)
    with col1:
        limit = st.slider("Cantidad máxima de mensajes a extraer:", 100, 20000, 5000, step=100)
    with col2:
        since_days = st.number_input("Ventana de tiempo (Días atrás):", min_value=1, max_value=365, value=90)
        
    if st.button("⚡ Disparar Análisis de Datos Manual", use_container_width=True):
        with st.spinner("Paso 1: Extrayendo conversaciones de PostgreSQL..."):
            try:
                ingest_res = requests.post(f"{INGEST_URL}/ingest", json={"limit": limit, "since_days": since_days})
                if ingest_res.status_code == 200:
                    st.success(f"✓ Ingesta completada con éxito. Registros importados: {ingest_res.json().get('imported_records')}")
                else:
                    st.error(f"Fallo en Ingesta: {ingest_res.text}")
            except Exception as e:
                st.error(f"Error al conectar con Ingest Service: {e}")
                
        with st.spinner("Paso 2: Generando Embeddings semánticos y aplicando DBSCAN + Qwen..."):
            try:
                suggest_res = requests.post(f"{SUGGESTION_URL}/suggest")
                if suggest_res.status_code == 200:
                    data = suggest_res.json()
                    st.success(f"✓ Análisis terminado. Se detectaron {data.get('cluster_count')} grupos lógicos en {data.get('company_count')} empresas.")
                    st.metric(label="Métrica de Separación (Silhouette Score)", value=data.get("silhouette_score") or "N/A")
                    st.rerun()
                else:
                    st.error(f"Fallo en el Modelo de Sugerencias: {suggest_res.text}")
            except Exception as e:
                st.error(f"Error al conectar con Suggestion Service: {e}")


# BANDEJA DE VALIDACIÓN HUMANA

with tab_validation:
    st.header("Sugerencias de Inteligencia Artificial Pendientes")
    
    # Intentar obtener las sugerencias desde el backend
    suggestions_data = None
    try:
        response = requests.get(f"{VALIDATION_URL}/suggestions")
        if response.status_code == 200:
            suggestions_data = response.json()
    except:
        st.info("💡 Ejecuta el pipeline en la pestaña 1 para generar el archivo de sugerencias inicial.")

    if suggestions_data:
        # Extraer nombres únicos de empresas para el filtro dinámico
        companies = sorted(list({item.get("company_name") or "Desconocida" for item in suggestions_data}))
        selected_company = st.selectbox("🏢 Filtrar sugerencias por Empresa/Workspace:", ["Todas"] + companies)
        
        # Filtrar la lista según la selección del UI
        filtered_suggestions = [
            s for s in suggestions_data 
            if selected_company == "Todas" or (s.get("company_name") or "Desconocida") == selected_company
        ]
        
        st.write(f"Mostrando **{len(filtered_suggestions)}** sugerencias pendientes.")
        
        # Renderizado interactivo de cada bloque de FAQ sugerido
        for idx, sug in enumerate(filtered_suggestions):
            sug_id = sug.get("id")
            comp_name = sug.get("company_name") or "Desconocido"
            
            with st.container(border=True):
                c_head1, c_head2 = st.columns([3, 1])
                with c_head1:
                    st.markdown(f"#### 🏢 Empresa: **{comp_name}**")
                with c_head2:
                    st.caption(f"🆔 ID: `{sug_id[:8]}...` | 📊 Score: {sug.get('cluster_score')}%")
                
                # Campos de texto editables por el administrador
                edited_question = st.text_input(f"Pregunta Propuesta ({idx})", value=sug.get("question"), key=f"q_{sug_id}")
                edited_answer = st.text_area(f"Respuesta Redactada por IA ({idx})", value=sug.get("answer"), key=f"a_{sug_id}")
                
                # Mostrar ejemplos reales del clúster de DBSCAN para que el humano tenga contexto
                with st.expander("🔍 Ver mensajes reales que originaron esta FAQ"):
                    for ex in sug.get("support_examples", []):
                        st.caption(f"• \"{ex}\"")
                
                # Notas u observaciones adicionales para la auditoría
                notes = st.text_input("📝 Notas o comentarios de la revisión (opcional)", key=f"n_{sug_id}", placeholder="Ej. Ajuste menor de ortografía...")
                
                # Botones de Acción alineados horizontalmente
                b_col1, b_col2, b_col3, _ = st.columns([1, 1, 1.2, 4])
                
                with b_col1:
                    if st.button("✅ Aprobar", key=f"btn_app_{sug_id}", use_container_width=True):
                        payload = {"suggestion_id": sug_id, "reviewer": reviewer_name, "status": "approved", "notes": notes}
                        res = requests.post(f"{VALIDATION_URL}/validate", json=payload)
                        if res.status_code == 200:
                            st.success("¡FAQ Aprobada con éxito!")
                            st.info("Cambio registrado. Por favor, refresca la página o cambia de pestaña para actualizar la lista.")
                            
                with b_col2:
                    if st.button("❌ Rechazar", key=f"btn_rej_{sug_id}", use_container_width=True):
                        payload = {"suggestion_id": sug_id, "reviewer": reviewer_name, "status": "rejected", "notes": notes}
                        res = requests.post(f"{VALIDATION_URL}/validate", json=payload)
                        if res.status_code == 200:
                            st.error("FAQ Marcada como Rechazada.")
                            st.info("Cambio registrado. Por favor, refresca la página o cambia de pestaña para actualizar la lista.")
                            
                with b_col3:
                    if st.button("⚠️ Pedir Cambios", key=f"btn_chg_{sug_id}", use_container_width=True):
                        payload = {"suggestion_id": sug_id, "reviewer": reviewer_name, "status": "needs_changes", "notes": notes}
                        res = requests.post(f"{VALIDATION_URL}/validate", json=payload)
                        if res.status_code == 200:
                            st.warning("Estado actualizado: Requiere Cambios.")
                            st.info("Cambio registrado. Por favor, refresca la página o cambia de pestaña para actualizar la lista.")
    else:
        st.warning("No hay registros cargados o no se pudo acceder al servicio de validación.")

# HISTORIAL DE FAQS APROBADAS

with tab_history:
    st.header("Historial de Decisiones del Comité de Calidad")
    st.write("Lista completa de auditoría de las acciones registradas en `faq_validations.json` mediante peticiones HTTP.")
    
    try:
        val_response = requests.get(f"{VALIDATION_URL}/validations")
        if val_response.status_code == 200 and val_response.json():
            df_history = pd.DataFrame(val_response.json())
            
            # Formatear el DataFrame para una visualización más agradable en el UI
            st.dataframe(df_history, use_container_width=True, hide_index=True)
            
            # Permitir descargar el reporte en formato CSV nativo de Windows
            csv_data = df_history.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Descargar Reporte Completo (CSV)",
                data=csv_data,
                file_name="reporte_validaciones_faqs.csv",
                mime="text/csv"   
            )
            # Botón para vaciar todo el historial
            st.markdown("---")
            st.subheader("⚠️ Zona de Peligro")
            if st.button("🗑️ Vaciar todo el historial de validaciones", type="primary", use_container_width=True):
                try:
                    import json
                    from faq_common import DATA_DIR
                    
                    # Construimos la ruta directamente usando DATA_DIR
                    ruta_validaciones = DATA_DIR / "faq_validations.json"
                    
                    # Escribimos un arreglo vacío para limpiar el historial
                    with open(ruta_validaciones, "w", encoding="utf-8") as f:
                        json.dump([], f)
                        
                    st.success("¡Historial vaciado por completo!")
                    st.info("Cambio registrado. Por favor, cambia de pestaña o refresca para limpiar la tabla.")
                except Exception as e:
                    st.error(f"No se pudo limpiar el archivo: {e}")
        else:
            st.info("Aún no se han guardado revisiones o el archivo histórico está vacío.")
    except Exception as e:
        st.error(f"Error al cargar el historial de auditoría: {e}")