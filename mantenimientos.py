import streamlit as st
from PIL import Image
import pandas as pd
from datetime import date
from fpdf import FPDF
import base64
import json
import psycopg2
# No necesitas importar sqlite3 si ya no lo usas

# Conexión global a PostgreSQL
try:
    # Forma usando indexación de diccionarios
    conn = psycopg2.connect(st.secrets["connections"]["postgresql"]["url"])
    c = conn.cursor()
    # st.success("Conexión a la base de datos PostgreSQL exitosa.")
except Exception as e:
    st.error(f"Error al conectar a la base de datos PostgreSQL: {e}")
    print(f"DEBUG: Error completo de conexión a PostgreSQL: {e}") # <-- ESTA LÍNEA DEBE ESTAR
    st.stop()


# Crear tabla si no existe con las columnas básicas
c.execute("""
CREATE TABLE IF NOT EXISTS ordenes (
    id BIGSERIAL PRIMARY KEY,
    usuario TEXT,
    area TEXT,
    seccion TEXT,
    responsable TEXT,
    tipo_de_mantenimiento TEXT,
    ejecutor TEXT,
    fecha_registro TEXT,
    hora_registro TEXT
)
""")
conn.commit()

# Verificar y agregar columnas adicionales si no existen
columnas_necesarias = {
    "tipo_de_trabajo": "TEXT",
    "prioridad": "TEXT",
    "descripcionp": "TEXT",
    "paro": "TEXT",
    "interrupcion": "TEXT",
    "fecha_mantenimiento": "TEXT",
    "hora_mantenimiento": "TEXT",
    "fecha_mantenimientof": "TEXT",
    "hora_mantenimientof": "TEXT",
    "servicio": "TEXT",
    "cantidad": "TEXT",
    "materiales": "TEXT",
    "observaciones": "TEXT",
    "estado": "TEXT DEFAULT 'Registrada'"
}

# VERIFICAR Y AGREGAR COLUMNAS ADICIONALES SI NO EXISTEN (VERSIÓN PARA POSTGRESQL)
for col, col_type in columnas_necesarias.items():
    try:
        # Verificar si la columna existe en PostgreSQL usando information_schema
        c.execute(f"""
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = 'public' -- 'public' es el esquema por defecto en PostgreSQL
                AND table_name = 'ordenes'
                AND column_name = '{col}'
            );
        """)
        column_exists = c.fetchone()[0]

        if not column_exists:
            # Añadir columna si no existe
            c.execute(f"ALTER TABLE ordenes ADD COLUMN {col} {col_type}")
            conn.commit()
            st.success(f"Columna '{col}' agregada a la tabla 'ordenes'.")
    except psycopg2.errors.DuplicateColumn:
        # Esto maneja el caso de que la columna ya exista (ej. por despliegues concurrentes)
        conn.rollback() # Revertir la transacción actual en caso de error
        st.info(f"Columna '{col}' ya existe en la tabla 'ordenes'.")
    except Exception as e:
        conn.rollback() # Revertir en caso de cualquier otro error inesperado
        st.error(f"Error al verificar/agregar columna '{col}': {e}")
        print(f"DEBUG: Error al verificar/agregar columna '{col}': {e}")

# Cuentas predefinidas (puedes editarlas manualmente)
CUENTAS = {
    "Elvira": {"password" : "ElvM01", "role" : "user"},
    "Gaudencio": {"password" : "GauM02", "role" : "user"},
    "Laboratorio": {"password" : "LabM03", "role" : "user"},
    "Atalia": {"password" : "AtaM04", "role" : "user"},
    "Ausencia": {"password" : "AusM05", "role" : "user"},
    "Shyma": {"password" : "ShyM06", "role" : "user"},
    "Almacen": {"password" : "AlmM07", "role" : "user"},
    "Oficinas": {"password" : "OfiM08", "role" : "user"},
    "Brenda": {"password" : "BreM09", "role" : "viewer"},
    "Carlos": {"password" : "CarM10", "role" : "editor"},
    "Enrique": {"password" : "EnrM11", "role" : "editor"},
    "Mantenimiento": {"password" : "ManM12", "role" : "Mantenimiento"},
    "Calderas": {"password" : "CalM13", "role" : "user"},
    "Cris": {"password" : "123", "role" : "admin"}
}

# Estilos personalizados
st.markdown("""
    <style>
    .header {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# Página de login
def pagina_login():
    st.title("Inicio de sesión")
    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        contraseña = st.text_input("Contraseña", type="password")
        enviar = st.form_submit_button("Iniciar sesión")

    if enviar:
        if usuario in CUENTAS and CUENTAS[usuario]["password"] == contraseña:
            st.session_state.usuario = usuario
            st.session_state.rol = CUENTAS[usuario]["role"]
            st.success("Inicio de sesión exitoso")
            cambiar_pagina("inicio")
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos")

# Inicializar estado
if "pagina" not in st.session_state:
    st.session_state.pagina = "login"
if "pagina" not in st.session_state:
    st.session_state.pagina = "inicio"
if "area" not in st.session_state:
    st.session_state.area = ""
if "seccion" not in st.session_state:
    st.session_state.seccion = ""
if "rol" not in st.session_state:
    st.session_state.rol = ""


# Función para cambiar de página
def cambiar_pagina(pagina, **kwargs):
    st.session_state.pagina = pagina
    for key, value in kwargs.items():
        st.session_state[key] = value

# Funcion para el usuario editor de ordenes
def pagina_ordenes():
    st.title("📋 Órdenes registradas")
    df = pd.read_sql_query("""
        SELECT id, usuario, area, seccion, responsable, tipo_de_mantenimiento,
               ejecutor, fecha_registro, hora_registro, tipo_de_trabajo, prioridad,
               descripcionp, paro, interrupcion, fecha_mantenimiento, hora_mantenimiento,
               fecha_mantenimientof, hora_mantenimientof, servicio, materiales, estado
        FROM ordenes
    """, conn)
    # -------------------
    st.dataframe(df)

    if st.session_state.rol in ["editor", "admin"]:
        st.subheader("✅ Finalizar orden")
        # Mostrar órdenes no finalizadas
        pendientes = df[df["estado"] != "Finalizada"]
        if not pendientes.empty:
            orden_id = st.selectbox("Selecciona una orden pendiente", pendientes["id"])
            if st.button("Marcar como finalizada"):
                c.execute("UPDATE ordenes SET estado = 'Finalizada' WHERE id = %s", (orden_id,))
                conn.commit()
                st.success(f"Orden {orden_id} marcada como finalizada.")
                st.rerun() # Recargar la página para ver los cambios
        else:
            st.info("No hay órdenes pendientes para finalizar.")
    elif st.session_state.rol == "viewer": # Mensaje para el viewer
        st.info("Solo puedes visualizar las órdenes.")
    if st.button("🔙 Volver al inicio", use_container_width=True):
        cambiar_pagina("inicio")


def pagina_mantenimiento():
    st.title("🛠️ Panel de Mantenimiento")

    df = pd.read_sql_query("SELECT * FROM ordenes WHERE estado != 'Finalizada'", conn)
    if df.empty:
        st.info("No mantenimiento.")
        return

    orden_id = st.selectbox("Selecciona la orden y completar", df["id"])
    orden = df[df["id"] == orden_id].iloc[0]

    st.subheader("📄 Detalles de la orden")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Usuario:** {orden['usuario']}")
        st.markdown(f"**Área:** {orden['area']}")
        st.markdown(f"**Sección:** {orden['seccion']}")
        st.markdown(f"**Responsable:** {orden['responsable']}")
        st.markdown(f"**Tipo de mantenimiento:** {orden['tipo_de_mantenimiento']}")
        st.markdown(f"**Ejecutor:** {orden['ejecutor']}")
    with col2:
        st.markdown(f"**Fecha:** {orden['fecha_registro']}")
        st.markdown(f"**Hora:** {orden['hora_registro']}")
        st.markdown(f"**Tipo de trabajo:** {orden['tipo_de_trabajo']}")
        st.markdown(f"**Prioridad:** {orden['prioridad']}")
        st.markdown(f"**Descripción del problema:** {orden['descripcionp']}")

    st.subheader("✏️ Completar información de mantenimiento")
    ejecutor = st.text_input("Ejecutor", value=orden.get("ejecutor", "") or "")
    paro = st.selectbox("Paro de equipo", ["si", "no"], index=["si", "no"].index(orden.get("paro", "no")) if orden.get("paro", "no") in ["si", "no"] else 0)
    interrupcion = st.selectbox("Interrupción de servicios", ["vapor", "agua", "electricidad", "otro (escribirlo)"], 
                                index=["vapor", "agua", "electricidad", "otro (escribirlo)"].index(orden.get("interrupcion", "vapor")) if orden.get("interrupcion", "vapor") in ["vapor", "agua", "electricidad", "otro (escribirlo)"] else 0)
    fecha_mantenimiento = st.date_input("Fecha de mantenimiento", value=(pd.to_datetime(orden.get("fecha_mantenimiento")) or pd.Timestamp.today()).date())
    hora_mantenimiento = st.time_input("Hora de mantenimiento", value=(pd.to_datetime(orden.get("hora_mantenimiento")) or pd.Timestamp("00:00")).time())
    fecha_mantenimientof = st.date_input("Fecha de mantenimiento final", value=(pd.to_datetime(orden.get("fecha_mantenimientof")) or pd.Timestamp.today()).date())
    hora_mantenimientof = st.time_input("Hora de mantenimiento final", value=(pd.to_datetime(orden.get("hora_mantenimientof")) or pd.Timestamp("00:00")).time())
    servicio = st.text_area("Descripción del servicio realizado", value=orden.get("servicio", "") or "")


    st.subheader("Materiales utilizados")

# Inicializa st.session_state.materiales_list si no existe
    if "materiales_list" not in st.session_state:
        st.session_state.materiales_list = []

# Carga los materiales existentes de la orden si están disponibles
# Esto es crucial para que al editar una orden, los materiales previamente guardados aparezcan.
# Se asume que en tu DB/CSV, 'materiales' ahora es una cadena JSON de una lista de diccionarios.
    if not st.session_state.materiales_list and orden.get("materiales"):
        try:
            # Intenta parsear la cadena JSON de materiales de la DB
            parsed_materials = json.loads(orden["materiales"])
            if isinstance(parsed_materials, list):
                st.session_state.materiales_list = parsed_materials
            else: # Si no es una lista después de parsear (ej. era solo un string)
                st.session_state.materiales_list = [{"material": str(orden["materiales"]), "cantidad": str(orden.get("cantidad", "")), "observacion": str(orden.get("observaciones", ""))}]
        except (json.JSONDecodeError, TypeError):
            # Si hay un error al decodificar JSON (ej. datos antiguos o mal formados),
            # intenta tratarlos como un solo material para compatibilidad.
            st.warning("⚠️ No se pudieron cargar los materiales existentes. Por favor, reintroduce si es necesario.")
            st.session_state.materiales_list = [{"material": str(orden.get("materiales", "")), "cantidad": str(orden.get("cantidad", "")), "observacion": str(orden.get("observaciones", ""))}]

# Muestra los materiales actuales y permite editarlos/eliminarlos
# (Este bucle crea una fila para cada material en la lista)
    for i, item in enumerate(st.session_state.materiales_list):
        col_qty, col_mat, col_obs, col_del = st.columns([1, 2, 2, 0.5])
        with col_qty:
            item["cantidad"] = st.text_input(f"Cantidad {i+1}", value=item.get("cantidad", ""), key=f"qty_{i}")
        with col_mat:
            # Asegúrate de que la clave sea 'material' si así la estás guardando en la lista de diccionarios
            item["material"] = st.text_input(f"Material {i+1}", value=item.get("material", ""), key=f"mat_{i}")
        with col_obs:
            # Asegúrate de que la clave sea 'observacion' si así la estás guardando en la lista de diccionarios
            item["observacion"] = st.text_input(f"Observación {i+1}", value=item.get("observacion", ""), key=f"obs_{i}")
        with col_del:
            if st.button("🗑️", key=f"delete_{i}"): # Botón para eliminar
                st.session_state.materiales_list.pop(i)
                st.rerun() # Volver a ejecutar para actualizar la interfaz

    # Botón para agregar una nueva fila de material
    # ¡Este botón debe ir FUERA del bucle for!
    if st.button("➕ Agregar Material"):
        # Asegúrate de que las claves aquí coincidan con las que usas para los text_input
        st.session_state.materiales_list.append({"material": "", "cantidad": "", "observacion": ""})
        st.rerun() # Volver a ejecutar para mostrar la nueva fila

# Elimina estas líneas si las tenías:
# nuevos_materiales = st.text_area("Materiales utilizados", value=orden.get("materiales", "") or "")
# cantidad = st.text_area("Cantidad", value=orden.get("cantidad", "") or "")
# nuevas_observaciones = st.text_area("Observaciones", value=orden.get("observaciones", "") or "")
    nuevo_estado = st.selectbox("Actualizar estado", ["En proceso"], index=0 if orden["estado"] == "Registrada" else 1)

    
    if st.button("Guardar actualización"):
    # Convierte la lista de diccionarios de materiales a una cadena JSON para guardar
        materiales_json = json.dumps(st.session_state.materiales_list)

        c.execute("""
            UPDATE ordenes
            SET ejecutor = %s, paro = %s, interrupcion = %s, fecha_mantenimiento = %s, hora_mantenimiento = %s,
            fecha_mantenimientof = %s, hora_mantenimientof = %s, servicio = %s,
            materiales = %s, estado = %s -- Elimina 'cantidad' y 'observaciones' de aquí si se incluyen en 'materiales' JSON
            WHERE id = %s
        """, (ejecutor, paro, interrupcion, fecha_mantenimiento.isoformat(), hora_mantenimiento.isoformat(),
            fecha_mantenimientof.isoformat(), hora_mantenimientof.isoformat(), servicio,
            materiales_json, nuevo_estado, orden_id)) # Pasa materiales_json aquí
        conn.commit()

        # Actualizar CSV: Esto también necesita almacenar la cadena JSON
        archivo_csv = f"{orden['area'].lower()}.csv"
        try:
            # Re-lee el CSV con el mapeo de tipos de datos, asegurando que 'Materiales' sea texto
            dtype_mapping = {
                "No. de orden": str,
                "Ejecutor": str,
                "Paro de equipo": str,
                "Interrupción de servicios": str,
                "Fecha de mantenimiento": str,
                "Hora de mantenimiento": str,
                "Fecha de mantenimiento final": str,
                "Hora de mantenimiento final": str,
                "servicio": str,
                "Materiales": str, # ¡Importante! Asegura que esta columna sea de tipo string para guardar JSON
                "Estado": str,
                # Considera si "Cantidad" y "Observaciones" siguen siendo columnas separadas en tu CSV
                # Si no las necesitas separadas, puedes eliminarlas de aquí y del DataFrame al leer/escribir.
            }
            df_csv = pd.read_csv(archivo_csv, dtype=dtype_mapping)
        except FileNotFoundError:
            # Si el archivo no existe, crea un DataFrame vacío con las columnas correctas
            df_csv = pd.DataFrame(columns=list(dtype_mapping.keys()))

        orden_id_str = str(orden_id).zfill(5)

        if orden_id_str not in df_csv["No. de orden"].values:
            # Crear una nueva fila si no existe la orden
            new_row = {
                "No. de orden": orden_id_str,
                "Ejecutor": ejecutor,
                "Paro de equipo": paro,
                "Interrupción de servicios": interrupcion,
                "Fecha de mantenimiento": fecha_mantenimiento.isoformat(),
                "Hora de mantenimiento": hora_mantenimiento.isoformat(),
                "Fecha de mantenimiento final": fecha_mantenimientof.isoformat(),
                "Hora de mantenimiento final": hora_mantenimientof.isoformat(),
                "servicio": servicio,
                "Materiales": materiales_json, # Guarda el JSON aquí
                "Estado": nuevo_estado
            }
            df_csv = pd.concat([df_csv, pd.DataFrame([new_row])], ignore_index=True)
        else:
            # Actualizar la fila existente
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Ejecutor"] = ejecutor
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Paro de equipo"] = paro
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Interrupción de servicios"] = interrupcion
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Fecha de mantenimiento"] = fecha_mantenimiento.isoformat()
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Hora de mantenimiento"] = hora_mantenimiento.isoformat()
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Fecha de mantenimiento final"] = fecha_mantenimientof.isoformat()
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Hora de mantenimiento final"] = hora_mantenimientof.isoformat()
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "servicio"] = servicio
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Materiales"] = materiales_json # Actualiza con el JSON
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Cantidad"] = "" # Vacía
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Observaciones"] = "" # Vacía
            df_csv.loc[df_csv["No. de orden"] == orden_id_str, "Estado"] = nuevo_estado

        df_csv.to_csv(archivo_csv, index=False)

        # Prepara los datos para el PDF: pasa la lista estructurada
        datos_pdf = {
            "No. de orden": str(orden_id).zfill(5),
            "Usuario": orden["usuario"],
            "Área": orden["area"],
            "Sección": orden["seccion"],
            "Responsable": orden["responsable"],
            "Tipo de mantenimiento": orden["tipo_de_mantenimiento"],
            "Fecha de registro": orden["fecha_registro"],
            "Hora de registro": orden["hora_registro"],
            "Ejecutor": ejecutor,
            "Tipo de trabajo": orden["tipo_de_trabajo"],
            "Prioridad": orden["prioridad"],
            "Descripción del problema": orden["descripcionp"],
            "Paro de equipo": paro,
            "Interrupción de servicios": interrupcion,
            "Fecha de mantenimiento": fecha_mantenimiento,
            "Hora de mantenimiento": hora_mantenimiento,
            "Fecha de mantenimiento final": fecha_mantenimientof,
            "Hora de mantenimiento final": hora_mantenimientof,
            "Descripción del servicio realizado": servicio,
            "Materiales_List": st.session_state.materiales_list, # ¡Pasa la lista estructurada aquí!
            "Estado": nuevo_estado
        }

        # Genera el PDF
        enlace_pdf = generar_pdf(datos_pdf)
        st.markdown(enlace_pdf, unsafe_allow_html=True)

def pagina_ordenes_completas():
    st.title("📋 Todas las Órdenes de Mantenimiento")
    df = pd.read_sql_query("""
        SELECT id, usuario, area, seccion, responsable, tipo_de_mantenimiento,
               ejecutor, fecha_registro, hora_registro, tipo_de_trabajo, prioridad,
               descripcionp, paro, interrupcion, fecha_mantenimiento, hora_mantenimiento,
               fecha_mantenimientof, hora_mantenimientof, servicio, materiales, estado
        FROM ordenes
    """, conn)
    # -------------------
    st.dataframe(df)

    if not df.empty:
        csv = df.to_csv(index=False).encode()
        st.download_button("📥 Descargar como CSV", data=csv, file_name="ordenes_completas.csv", mime="text/csv")

        # Generar PDF de todas las órdenes
        from fpdf import FPDF
        import base64

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        for i, row in df.iterrows():
            for col in df.columns:
                pdf.cell(200, 8, txt=f"{col}: {row[col]}", ln=True)
            pdf.ln(5)
        nombre_pdf = "ordenes_completas.pdf"
        pdf.output(nombre_pdf)
        with open(nombre_pdf, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        enlace_pdf = f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre_pdf}">🖨️ Imprimir PDF</a>'
        st.markdown(enlace_pdf, unsafe_allow_html=True)

# Página de inicio
def pagina_inicio():
    try:
        logo = Image.open("logo.png")
        st.image(logo, width=200)
    except:
        pass

    st.markdown("<div class='header'><h1>US Technologies S.A. de C.V.</h1><h3>Registro de Mantenimientos</h3></div>", unsafe_allow_html=True)
    st.title("Registro de Mantenimientos")
    st.subheader("Selecciona el Mantenimiento a elegir")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🛢️ Tanques", use_container_width=True):
            cambiar_pagina("subarea", area="Tanques")
        if st.button("🚻 Baños", use_container_width=True):
            cambiar_pagina("subarea", area="Baños")
        if st.button("🏘️ Techumbres y estructura civil", use_container_width=True):
            cambiar_pagina("subarea", area="estructura")
    with col2:
        if st.button("🛠️ Maquinaria", use_container_width=True):
            cambiar_pagina("subarea", area="Maquinaria")
        if st.button("🍽️ Comedor", use_container_width=True):
            cambiar_pagina("formulario", area="Comedor", seccion="General")
        if st.button("🚚 Logistica", use_container_width=True):
            cambiar_pagina("formulario", area="Logistica", seccion="General")
    with col3:
        if st.button("🔬 Laboratorio", use_container_width=True):
            cambiar_pagina("formulario", area="Laboratorio", seccion="General")
        if st.button("🏢 Oficinas", use_container_width=True):
            cambiar_pagina("formulario", area="Oficinas", seccion="General")
        if st.button("🔩 Calderas", use_container_width=True):
            cambiar_pagina("formulario", area="Calderas", seccion="General")
    if "rol" in st.session_state and st.session_state.rol in ["editor", "admin"]:
        st.markdown("---")
        if st.button("📋 Ver órdenes registradas", use_container_width=True):
            cambiar_pagina("ordenes")

# Página de selección de subáreas
def pagina_subareas():
    area = st.session_state.area
    st.markdown(f"### Formulario de mantenimiento - {area}")
    st.markdown("#### Selecciona el área específica:")

    opciones = {
        "Tanques": ["🛢️ Internos", "🧱 Externos", "⚙️ Grafito", "🧪 Shyma"],
        "Baños": ["🏢 Oficinas", "🚨 Vigilancia", "🏭 Planta", "🍽️ Comedor", "🔬 Laboratorio", "🏗️ Producción"],
        "Maquinaria": ["🏭 Planta", "🌳 Externos", "⚙️ Grafito", "📦 Otros"],
        "estructura": ["🛢️ Internos", "🧱 Externos", "⚙️ Grafito", "🏢 Oficinas", "🚨 Vigilancia", "🏭 Planta"]
    }

    opciones_area = opciones.get(area, [])
    num_columnas = 2 if len(opciones_area) == 4 else 3
    columnas = st.columns(num_columnas)

    for i, opcion in enumerate(opciones_area):
        texto = opcion.split(" ", 1)[1]
        with columnas[i % num_columnas]:
            if st.button(opcion, use_container_width=True):
                cambiar_pagina("formulario", seccion=texto)

    st.markdown("---")
    if st.button("🔙 Volver al inicio", use_container_width=True):
        cambiar_pagina("inicio")


def generar_pdf(datos):
    pdf = FPDF(format=(279.4, 215.9), unit='mm') # Tamaño carta (ancho, alto)
    pdf.add_page()
    
    try:
        # Asegúrate de que 'logo.png' exista en el mismo directorio o proporciona la ruta completa
        pdf.image("logo.png", x=10, y=8, w=30)
    except Exception as e:
        pass

    # Título en centro
    pdf.set_font("Arial", 'B', 14)
    pdf.set_xy(0, 10)
    pdf.cell(w=0, h=10, txt="ORDEN DE TRABAJO DE MANTENIMIENTO",
             border=0, ln=0, align='C')

    # Número de orden a la derecha
    pdf.set_font("Arial", 'B', 12)
    nro = datos.get("No. de orden", "N/A")
    pdf.set_xy(-60, 10) # Ajusta la posición X para que esté a la derecha
    pdf.cell(w=50, h=10, txt=f"No. de orden: {nro}",
             border=0, ln=1, align='R')

    pdf.ln(5) # Salto de línea después del encabezado

    # --- Primer bloque de datos: 3 columnas por fila ---
    pdf.set_font("Arial", '', 11)
    col_width = (pdf.w - pdf.l_margin - pdf.r_margin) / 3 # Ancho de cada columna
    row_height = 8 # Altura de cada fila

    # Fila 1 (Usuario, Área, Sección)
    fila1 = [("Usuario", "Usuario"), ("Área", "Área"), ("Sección", "Sección")]
    y_inicial = pdf.get_y()
    for i, (clave, _) in enumerate(fila1):
        pdf.set_xy(pdf.l_margin + i*col_width, y_inicial)
        valor = datos.get(clave, "N/A")
        pdf.cell(w=col_width, h=row_height,
                 txt=f"{clave}: {valor}", border=1, align='L')
    pdf.ln(row_height) # Salto de línea para la siguiente fila

    # Fila 2 (Responsable, Tipo de mantenimiento, Fecha de registro)
    fila2 = [("Responsable", "Responsable"),
             ("Tipo de mantenimiento", "Tipo de mantenimiento"),
             ("Fecha de registro", "Fecha"),]
    y_inicial = pdf.get_y()
    for i, (clave, _) in enumerate(fila2):
        pdf.set_xy(pdf.l_margin + i*col_width, y_inicial)
        valor = datos.get(clave, "N/A")
        if clave == "Fecha de registro":
            valor = f"{datos.get('Fecha de registro','N/A')} {datos.get('Hora de registro','')}"
        pdf.cell(w=col_width, h=row_height,
                 txt=f"{clave if clave!='Fecha de registro' else 'Fecha y hora'}: {valor}",
                 border=1, align='L')
    pdf.ln(row_height) # Salto de línea para la siguiente sección

    # --- Bloque de 'Tipo de trabajo', 'Paro', 'Prioridad', 'Interrupción' (izquierda)
    # y 'Descripción del problema' (derecha) ---
    y_inicial_bloque_problema = pdf.get_y() # Guarda la Y inicial para este bloque

    # Columna izquierda
    pdf.set_xy(pdf.l_margin, y_inicial_bloque_problema)
    pdf.cell(w=col_width, h=row_height, txt=f"Tipo de trabajo: {datos.get('Tipo de trabajo', 'N/A')}", border=1, align="L")
    pdf.ln(row_height)
    pdf.set_xy(pdf.l_margin, pdf.get_y())
    pdf.cell(w=col_width, h=row_height, txt=f"Paro de equipo: {datos.get('Paro de equipo', 'N/A')}", border=1, align="L")
    pdf.ln(row_height)
    pdf.set_xy(pdf.l_margin, pdf.get_y())
    pdf.cell(w=col_width, h=row_height, txt=f"Prioridad: {datos.get('Prioridad', 'N/A')}", border=1, align="L")
    pdf.ln(row_height)
    pdf.set_xy(pdf.l_margin, pdf.get_y())

    # Nuevo bloque de 'Interrupción' con altura fija de 2 líneas
    interrupcion = datos.get("Interrupción de servicios", "N/A")
    max_lines_interrupcion = 2
    
    lineas_interrupcion = []
    texto_restante_interrupcion = interrupcion
    while len(lineas_interrupcion) < max_lines_interrupcion and texto_restante_interrupcion:
        linea_actual = ""
        palabras = texto_restante_interrupcion.split(" ")
        for palabra in palabras:
            temp_linea = linea_actual + " " + palabra if linea_actual else palabra
            if pdf.get_string_width(temp_linea) <= col_width - 5:
                linea_actual = temp_linea
            else:
                break
        if linea_actual:
            lineas_interrupcion.append(linea_actual)
            texto_restante_interrupcion = " ".join(palabras[len(linea_actual.split(" ")):])
        else:
            if not linea_actual and palabras:
                lineas_interrupcion.append(palabras[0][:int((col_width-5)/pdf.font_size * 2)])
                texto_restante_interrupcion = " ".join(palabras[1:])
            else:
                break
    
    if len(lineas_interrupcion) == max_lines_interrupcion and texto_restante_interrupcion:
        if lineas_interrupcion:
            lineas_interrupcion[-1] = (lineas_interrupcion[-1][:int(pdf.get_string_width(lineas_interrupcion[-1]) * 0.8)] + "...")
        else:
            lineas_interrupcion.append("...")
    elif not lineas_interrupcion and interrupcion:
        lineas_interrupcion.append(interrupcion[:int((col_width-5)/pdf.font_size * 2)] + "...")

    texto_final_interrupcion = "Interrupción:\n" + "\n".join(lineas_interrupcion)
    pdf.multi_cell(w=col_width, h=row_height, txt=texto_final_interrupcion, border=1, align='L')


    # Bloque de 'Descripción del problema' con altura fija de 5 líneas
    descripcionp = datos.get("Descripción del problema", "N/A")
    max_lines_desc = 5
    fixed_box_height = max_lines_desc * row_height
    
    pdf.set_xy(pdf.l_margin + col_width, y_inicial_bloque_problema)
    pdf.rect(pdf.get_x(), pdf.get_y(), col_width * 2, fixed_box_height)
    
    lineas_problema = []
    texto_restante_problema = descripcionp
    while len(lineas_problema) < max_lines_desc and texto_restante_problema:
        linea_actual = ""
        palabras = texto_restante_problema.split(" ")
        for palabra in palabras:
            temp_linea = linea_actual + " " + palabra if linea_actual else palabra
            if pdf.get_string_width(temp_linea) <= (col_width * 2) - 5:
                linea_actual = temp_linea
            else:
                break
        if linea_actual:
            lineas_problema.append(linea_actual)
            texto_restante_problema = " ".join(palabras[len(linea_actual.split(" ")):])
        else:
            if not linea_actual and palabras:
                lineas_problema.append(palabras[0][:int(((col_width*2)-5)/pdf.font_size * 2)])
                texto_restante_problema = " ".join(palabras[1:])
            else:
                break
            
    if len(lineas_problema) == max_lines_desc and texto_restante_problema:
        if lineas_problema:
            lineas_problema[-1] = (lineas_problema[-1][:int(pdf.get_string_width(lineas_problema[-1]) * 0.8)] + "...")
        else:
            lineas_problema.append("...")
    elif not lineas_problema and descripcionp:
        lineas_problema.append(descripcionp[:int(((col_width*2)-5)/pdf.font_size * 2)] + "...")


    texto_final_desc = "Descripción del problema:\n" + "\n".join(lineas_problema)
    pdf.multi_cell(w=col_width * 2, h=row_height, txt=texto_final_desc, border=0, align="L")
    
    # Se ajusta la posición Y para la siguiente sección, tomando la más baja del bloque actual
    pdf.set_y(max(pdf.get_y(), y_inicial_bloque_problema + (5 * row_height)))


    # Fila 'Ejecutor'
    y_inicial = pdf.get_y()
    pdf.set_xy(pdf.l_margin, y_inicial)
    ejecutor = datos.get("Ejecutor", "N/A")
    pdf.cell(w=col_width * 3, h=row_height,
             txt=f"Ejecutor: {ejecutor}", border=1, align='L')
    pdf.ln(row_height)
    
    # Nuevas columnas para Fecha y Hora de mantenimiento
    y_inicial = pdf.get_y()
    pdf.set_xy(pdf.l_margin, y_inicial)
    pdf.cell(w=col_width * 1.5, h=row_height,
             txt=f"Fecha y hora de mantenimiento: {datos.get('Fecha de mantenimiento', 'N/A')} {datos.get('Hora de mantenimiento', '')}",
             border=1, align='L')
    pdf.set_xy(pdf.l_margin + col_width * 1.5, y_inicial)
    pdf.cell(w=col_width * 1.5, h=row_height,
             txt=f"Fecha y hora final: {datos.get('Fecha de mantenimiento final', 'N/A')} {datos.get('Hora de mantenimiento final', '')}",
             border=1, align='L')
    pdf.ln(row_height)

    # Bloque de 'Descripción del servicio realizado' con altura fija (4 líneas)
    servicio = datos.get("Descripción del servicio realizado", "N/A")
    max_lines_serv = 4
    fixed_box_height_serv = max_lines_serv * row_height
    
    y_inicial_serv = pdf.get_y()
    pdf.set_xy(pdf.l_margin, y_inicial_serv)
    pdf.rect(pdf.get_x(), pdf.get_y(), col_width * 3, fixed_box_height_serv)
    
    lineas_servicio = []
    texto_restante_servicio = servicio
    while len(lineas_servicio) < max_lines_serv and texto_restante_servicio:
        linea_actual = ""
        palabras = texto_restante_servicio.split(" ")
        for palabra in palabras:
            temp_linea = linea_actual + " " + palabra if linea_actual else palabra
            if pdf.get_string_width(temp_linea) <= (col_width * 3) - 5:
                linea_actual = temp_linea
            else:
                break
        if linea_actual:
            lineas_servicio.append(linea_actual)
            texto_restante_servicio = " ".join(palabras[len(linea_actual.split(" ")):])
        else:
            if not linea_actual and palabras:
                lineas_servicio.append(palabras[0][:int(((col_width*3)-5)/pdf.font_size * 2)])
                texto_restante_servicio = " ".join(palabras[1:])
            else:
                break
            
    if len(lineas_servicio) == max_lines_serv and texto_restante_servicio:
        if lineas_servicio:
            lineas_servicio[-1] = (lineas_servicio[-1][:int(pdf.get_string_width(lineas_servicio[-1]) * 0.8)] + "...")
        else:
            lineas_servicio.append("...")
    elif not lineas_servicio and servicio:
        lineas_servicio.append(servicio[:int(((col_width*3)-5)/pdf.font_size * 2)] + "...")


    texto_final_serv = "Descripción del servicio realizado:\n" + "\n".join(lineas_servicio)
    pdf.multi_cell(w=col_width * 3, h=row_height, txt=texto_final_serv, border=0, align='L')
    pdf.set_y(y_inicial_serv + fixed_box_height_serv)

    # Actualiza cómo recuperas 'materiales_data'. Ahora viene de "Materiales_List"
    materiales_data = datos.get("Materiales_List", [])

    # Si aún recibes una cadena JSON (ej. de datos antiguos que no se migraron en sesión), intentalo parsear
    if isinstance(materiales_data, str):
        try:
            materiales_data = json.loads(materiales_data)
        except json.JSONDecodeError:
            materiales_data = [] # Si falla la decodificación, trata como vacío

    # Asegúrate de que siempre sea una lista, incluso si está vacía
    if not isinstance(materiales_data, list):
        materiales_data = []

    # ... (resto de tu generación de PDF, antes de la sección de materiales) ...

    pdf.set_font("Arial", "B", 10) # Fuente para encabezados de tabla
    pdf.set_fill_color(200, 220, 255) # Color de fondo para encabezados

    # Encabezados de la tabla de materiales
    y_inicial_materiales = pdf.get_y()
    pdf.set_xy(pdf.l_margin, y_inicial_materiales)
    pdf.cell(w=col_width * 0.5, h=row_height, txt="Cantidad", border=1, align='L', fill=True)
    pdf.cell(w=col_width * 1.5, h=row_height, txt="Materiales", border=1, align='L', fill=True)
    pdf.cell(w=col_width, h=row_height, txt="Observaciones", border=1, align='L', fill=True)
    pdf.ln(row_height)

    pdf.set_font("Arial", "", 10) # Vuelve a la fuente normal para el contenido

    # Filas de materiales
    if not materiales_data:
        # Agrega una fila vacía o un mensaje si no hay materiales
        pdf.set_xy(pdf.l_margin, pdf.get_y())
        pdf.cell(w=col_width * 0.5, h=row_height, txt="", border=1, align='L')
        pdf.cell(w=col_width * 1.5, h=row_height, txt="No se utilizaron materiales", border=1, align='L')
        pdf.cell(w=col_width, h=row_height, txt="", border=1, align='L')
        pdf.ln(row_height)
    else:
        for item in materiales_data:
            cantidad = str(item.get('cantidad', 'N/A')) # Asegúrate de que sea string
            material = str(item.get('material', 'N/A')) # Asegúrate de que sea string
            observacion = str(item.get('observacion', 'N/A')) # Asegúrate de que sea string

            pdf.set_xy(pdf.l_margin, pdf.get_y())
            pdf.multi_cell(w=col_width * 0.5, h=row_height, txt=cantidad, border=1, align='L')
            pdf.set_xy(pdf.l_margin + col_width * 0.5, pdf.get_y() - row_height) # Vuelve a la Y de la fila actual para la siguiente celda
            pdf.multi_cell(w=col_width * 1.5, h=row_height, txt=material, border=1, align='L')
            pdf.set_xy(pdf.l_margin + col_width * 0.5 + col_width * 1.5, pdf.get_y() - row_height) # Vuelve a la Y de la fila actual para la siguiente celda
            pdf.multi_cell(w=col_width, h=row_height, txt=observacion, border=1, align='L')

    pdf.ln(row_height) # Espacio después de la tabla de materiales

    # --- Firmas ---
    pdf.set_font("Arial", '', 10)
    # Líneas para firmas
    pdf.cell(w=col_width, h=0, txt="_________________________", border=0, ln=0, align='C')
    pdf.cell(w=col_width, h=0, txt="_________________________", border=0, ln=0, align='C')
    pdf.cell(w=col_width, h=0, txt="_________________________", border=0, ln=1, align='C')
    pdf.ln(3)
    pdf.cell(w=col_width, h=0, txt="Técnico", border=0, ln=0, align='C')
    pdf.cell(w=col_width, h=0, txt="Supervisor", border=0, ln=0, align='C')
    pdf.cell(w=col_width, h=0, txt="Jefe de área", border=0, ln=1, align='C')

    # Guardar PDF y codificarlo en base64 para descarga
    nombre_archivo = "orden_mantenimiento.pdf"
    pdf.output(nombre_archivo)
    with open(nombre_archivo, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{nombre_archivo}">📄 Descargar orden en PDF</a>'

def crear_orden(datos):
    sql = """
    INSERT INTO ordenes (
        usuario, area, seccion,
        responsable, tipo_de_mantenimiento,
        tipo_de_trabajo, descripcionp, prioridad,
        ejecutor, fecha_registro, hora_registro
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    RETURNING id; -- <-- ¡CAMBIO AQUÍ! Añadir RETURNING id
    """
    c.execute(sql, (
        datos["Usuario"], datos["Área"], datos["Sección"],
        datos["Responsable"], datos["Tipo de mantenimiento"],
        datos["Tipo de trabajo"], datos["Descripción del problema"], datos["Prioridad"],
        datos["Ejecutor"], str(datos["Fecha de registro"]),
        str(datos["Hora de registro"])
    ))
    conn.commit()

    # Obtener el id generado para PostgreSQL
    # <-- ¡CAMBIO AQUÍ! Usar fetchone() después de RETURNING
    numero = c.fetchone()[0]
    return numero

# Página de formulario
def pagina_formulario():
    area = st.session_state.area
    seccion = st.session_state.get("seccion", "")
    st.markdown(f"### 📋 Formulario de mantenimiento - {area} - {seccion}")

    with st.form("form_mantenimiento"):
        responsable = st.selectbox("Responsable", [
            "Carlos Eduardo Villegas Delgado",
            "Enrique Ramirez Ruiz"
        ])
        tipo_de_mantenimiento = st.selectbox("Tipo de mantenimiento", [
            "Predictivo", "Correctivo", "Preventivo", "Sensorial"
        ])
        fecha = st.date_input("Fecha del registro", value=date.today())
        hora = st.time_input("Hora de registro")
        tipo_de_trabajo = st.selectbox("Tipo de trabajo", [
            "Mecanico", "Electrico", "Ambos"
        ])
        prioridad = st.selectbox("Prioridad", [
            "Alta", "Media", "Baja"
        ])
        descripcionp = st.text_input("Descripción del problema")
        ejecutor = st.text_input("Ejecutor")

        datos = {
            "Usuario": st.session_state.usuario,
            "No. de orden": "",
            "Área": area,
            "Sección": seccion,
            "Responsable": responsable,
            "Tipo de mantenimiento": tipo_de_mantenimiento,
            "Fecha de registro": fecha,
            "Hora de registro": hora,
            "Tipo de trabajo": tipo_de_trabajo,
            "Prioridad" : prioridad,
            "Descripción del problema" : descripcionp,
            "Ejecutor" : ejecutor,
        }

        campos_validos = ejecutor.strip() != ""
        enviar = st.form_submit_button("Guardar")

    if enviar:
        if campos_validos:
            # Guardar en PostgreSQL y obtener número de orden
            numero = crear_orden(datos)
            datos["No. de orden"] = str(numero).zfill(5) # Asigna el ID de la DB al diccionario de datos

            st.success("✅ ¡Datos guardados correctamente en la base de datos!") # Mensaje de éxito actualizado

            # Generar y mostrar PDF con el número ya actualizado
            enlace_pdf = generar_pdf(datos)
            st.markdown(enlace_pdf, unsafe_allow_html=True)
            st.markdown("---")
            if st.button("🔙 Volver al inicio", use_container_width=True, key="volver_inicio_exito"):
                cambiar_pagina("inicio")
                st.rerun()        
        else:
        # manejo de campos incompletos...

            st.warning("⚠️ Por favor, completa todos los campos obligatorios antes de guardar.")
            if st.button("🔙 Volver al inicio", use_container_width=True, key="volver_inicio_incompleto"):
                cambiar_pagina("inicio")
                st.rerun()
    else:
        if st.button("🔙 Volver al inicio", use_container_width=True, key="volver_inicio_default"):
            cambiar_pagina("inicio")

# Enrutador principal
def main():
    if st.session_state.pagina == "login":
        pagina_login()
    if st.session_state.pagina == "inicio" and st.session_state.rol in ["user", "viewer", "admin", "editor"]:
        pagina_inicio()
    elif st.session_state.pagina == "subarea":
        pagina_subareas()
    elif st.session_state.pagina == "formulario" and st.session_state.rol in ["user", "viewer", "admin"]:
        pagina_formulario()
    elif st.session_state.pagina == "ordenes" and st.session_state.rol in ["admin", "editor"]:
        pagina_ordenes()
    if st.session_state.rol in ["Mantenimiento", "admin"]:
        pagina_mantenimiento()
    elif st.session_state.rol in ["admin", "viewer"]:
        pagina_ordenes_completas()
main()