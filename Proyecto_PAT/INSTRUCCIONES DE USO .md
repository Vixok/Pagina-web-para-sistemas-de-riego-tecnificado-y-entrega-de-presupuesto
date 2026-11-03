# PAT Riego — Arquitectura V2 (Pasos 4 → 8)

Esta versión parte del `app(5).py` entregado y conserva los cálculos agronómicos, hidráulicos y la secuencia Tavily/Mercado Libre → SQL → Streamlit.

## Qué incorpora

0. **Navegación por etapas**: conserva las siete pestañas superiores y agrega al pie de cada sección botones anterior/siguiente con indicador de paso. El estado nativo de `st.tabs` permite cambiar la pestaña activa sin reiniciar `st.session_state`; requiere Streamlit 1.63.0 o superior.
1. **Blindaje SQL/IDs**: los catálogos dejan de usar `DELETE + INSERT`. `migrar_catalogos_sql.py` hace UPSERT y conserva `id_bomba`, `id_tuberia`, etc.
2. **Optimizador serie/paralelo**: evalúa explícitamente combinaciones `n_paralelo × n_serie` dentro de límites configurables.
3. **Curvas Q-H y punto de operación**: si existen puntos reales validados, calcula la curva equivalente, la curva del sistema y su intersección. Si faltan curvas, muestra `ESTIMACION_PRELIMINAR` y no presenta Qmax/Hmax como un punto real.
4. **Candidatos web + HITL**: si el catálogo no entrega una solución factible, busca equipos externos, los guarda en `CandidatosBombasWeb` y exige aprobación humana antes de incorporar a `Bombas`.
5. **Histórico de precios**: mediana, promedio, min, max, desviación, antigüedad, vigencia, variación y volatilidad.
6. **Agente OpenAI + HITL**: usa Responses API; el agente solo analiza resultados deterministas. No modifica cálculos ni catálogos.
7. **Monte Carlo**: presupuesto probabilístico con seed reproducible; bootstrap del precio de bombas si hay historial suficiente.
8. **Estimación referencial Williams**: si el catálogo no tiene una configuración factible y la búsqueda externa termina sin candidatos ni errores, estima un costo por caudal usando una bomba del catálogo con caudal y precio conocidos. El resultado se etiqueta como referencial —nunca como cotización— y no valida TDH ni disponibilidad.
9. **Emisores y metraje de red preliminar**: aspersión y microaspersión tienen perfiles de parámetros separados. Los valores heredados (radio 12 m, caudal 1.260 L/h, presión 25 m.c.a. y factor geométrico 1,414) se identifican como no verificados; deben contrastarse con la ficha del fabricante. La aplicación prioriza emisores que tengan todos los datos requeridos en `catalogo_fichas_emisores.csv`, fuente, fecha y `validada=1`. La marca de validación es una declaración del equipo técnico, no una comprobación automática. El terreno se aproxima por un cuadrado equivalente, los laterales se estiman por separación y la matriz por perímetro/2,5. No hay trazado real de tuberías: longitudes, caudal, presión y dimensionamiento resultante son preliminares, nunca un diseño definitivo.
10. **Presupuesto de obras civiles**: la pestaña **4. Presupuesto** presenta primero costos de matriz, laterales, emisores, equipos y total base, además de accesorios, obra civil e instalación. En la sección civil solo se muestran longitudes geométricas de matriz y laterales, su clasificación como pendiente, enterrada o superficial, la longitud de excavación confirmada y el costo porcentual referencial. Ningún tramo se considera enterrado por defecto. Como el proyecto no aporta dimensiones justificadas de zanja ni cubicaciones de relleno y hormigón, el cálculo detallado se identifica como pendiente y se conserva el porcentaje como referencia, no como cotización. El catálogo local `catalogo_precios_obra_civil.csv` mantiene unidad, precio, fuente, fecha, condiciones y alcance de mano de obra; se administra separadamente en **Bases de Datos → Precios de obras civiles**. Solo acepta para uso potencial filas completas marcadas como validadas, con unidad compatible y trazabilidad. ONDAC BA_08000 continúa pendiente hasta verificar suelo, dimensiones y modalidad de excavación. `DEI_02_Costes.pdf` (pp. 5–6) respalda la distinción entre estimación preliminar y detallada; no establece dimensiones de zanjas para este proyecto.

## Orden de instalación

El tema visual de la aplicación se fija en
`.streamlit/config.toml`: conserva el fondo oscuro y los acentos verdes, con
colores de texto y estados seleccionados de alto contraste para todas las
pestañas y widgets.

### 1. Respaldar SQL Server
Antes de ejecutar cambios, respalda `PAT_RIEGO`.

### 2. Ejecutar migración de arquitectura
En SQL Server Management Studio abre y ejecuta:

`sql/00_migracion_arquitectura_v2.sql`

El script es incremental e idempotente.

Para habilitar el guardado completo de proyectos desde la pestaña **4. Presupuesto**, ejecuta también:

`sql/02_guardado_proyectos.sql`

Esta migración agrega la columna nullable `datos_json` a `dbo.Proyectos`; conserva los proyectos existentes y puede ejecutarse más de una vez.

### 3. Instalar dependencias

```powershell
pip install -r requirements.txt
```

### 4. Configurar variables
Copia `.env.example` a `.env` y completa únicamente los servicios que quieras usar. `.env` contiene credenciales locales y está excluido de Git; nunca publiques sus valores ni los escribas directamente en el código.

- **OpenAI (opcional):** crea una clave en la plataforma de OpenAI y asígnala a `OPENAI_API_KEY`. `OPENAI_MODEL` y `OPENAI_JUDGE_MODEL` ya tienen valores predeterminados en la plantilla.
- **Tavily (opcional):** crea una clave en Tavily y asígnala a `TAVILY_API_KEY` para habilitar la búsqueda web de precios.
- **Mercado Libre (opcional):** registra una aplicación en Mercado Libre y configura `ML_CLIENT_ID`, `ML_CLIENT_SECRET` y `ML_REDIRECT_URI` con la URL de redirección registrada. Ejecuta `python autorizar_ml.py` y agrega a `.env` los valores completos de `ML_ACCESS_TOKEN` y `ML_REFRESH_TOKEN` que obtengas.

Las funciones que dependen de estas APIs no estarán disponibles hasta configurar sus credenciales. No compartas claves o tokens; si alguno ya fue publicado o expuesto, revócalo y genera uno nuevo.

### 5. Migrar catálogos preservando IDs

```powershell
python migrar_catalogos_sql.py
```

### 6. Cargar curvas Q-H reales
Completa `CurvasBombas_template.csv` con puntos provenientes de ficha técnica/fabricante. No inventes puntos. Para que el motor los use como validación hidráulica, marca `validada=1` solo tras revisión técnica.

```powershell
python importar_curvas_qh.py
```

### 7. Ejecutar pruebas

```powershell
python -m py_compile app.py database.py mercado_equipos.py optimizador_bombeo.py agente_riego.py simulacion_montecarlo.py
python -m unittest discover -s tests -v
```

Los tests cubren: 1 bomba, paralelo, serie, serie-paralelo y reproducibilidad Monte Carlo.

### 8. Ejecutar Streamlit

```powershell
streamlit run app.py
```

## Lógica hidráulica V2

Para bombas idénticas:

`H_config(Q) = n_serie * H_bomba(Q / n_paralelo)`

La curva del sistema se modela como:

`H_sistema(Q) = H_estatica + H_emisor + hf_ref*(Q/Qref)^1.852 + hacc_ref*(Q/Qref)^2`

La selección con curva válida se basa en el punto real de intersección. Sin curva se conserva solo una preselección de catálogo claramente etiquetada.

## Seguridad de datos

- Tavily/Mercado Libre nunca escriben directamente en `Bombas`.
- `CandidatosBombasWeb` requiere HITL.
- `migrar_catalogos_sql.py` no borra IDs maestros.
- Escrituras SQL usan `commit/rollback/finally` y `XACT_ABORT`.
- El agente OpenAI no puede cambiar variables hidráulicas deterministas.
- Los históricos de precios no se sobrescriben.

## OpenAI

El módulo `agente_riego.py` usa la Responses API. `OPENAI_API_KEY` se lee desde `.env`; no se necesita modificar `app.py` ni `agente_riego.py` para configurarla. La aplicación continúa funcionando si no hay clave o si la API está temporalmente no disponible.

---

## Ubicación automática del predio

La delimitación del terreno se cruza localmente con los polígonos simplificados
de comunas (ADM3) y regiones (ADM1) de Chile publicados por
[geoBoundaries](https://www.geoboundaries.org/), a partir de BCN Chile/OCHA
ROLAC. El proveedor identifica esos conjuntos con licencia CC BY 3.0 IGO y
solicita atribución visible; la aplicación muestra la fuente y licencia debajo
del mapa. Los archivos se descargan solo cuando se necesita ubicar un polígono
y quedan cacheados durante 30 días; los resultados por polígono se cachean
durante siete días, evitando consultas en cada actualización de Streamlit.

La cobertura comunal publicada es de 345 unidades con año representado 2020.
La ubicación se indica como no disponible si no hay una intersección reconocida
o falla la descarga. Si el polígono intersecta más de una comuna o región, la
interfaz advierte el cruce en lugar de asignar una única unidad.

## HOTFIX: error `cargar_curvas_bombas` / `DELETE FROM Bombas`

Si `app.py` informa `ImportError: cannot import name 'cargar_curvas_bombas' from 'database'`, el proyecto contiene una mezcla de archivos antiguos y V2. **No basta con reemplazar `app.py`**. Deben reemplazarse juntos, como mínimo:

- `app.py`
- `database.py`
- `migrar_catalogos_sql.py`
- `mercado_equipos.py`
- `optimizador_bombeo.py`
- `agente_riego.py`
- `simulacion_montecarlo.py`
- `proveedor_tavily.py`
- `proveedor_mercadolibre.py`

La versión V2 de `migrar_catalogos_sql.py` **no contiene `DELETE FROM Bombas`**: hace UPSERT por `codigo_bomba` para preservar `id_bomba` y las FK del histórico.

Orden recomendado después de copiar todos los archivos:

```powershell
python verificar_instalacion.py
python -m py_compile app.py database.py migrar_catalogos_sql.py mercado_equipos.py optimizador_bombeo.py agente_riego.py simulacion_montecarlo.py
python migrar_catalogos_sql.py
streamlit run app.py
```

El SQL `sql/00_migracion_arquitectura_v2.sql` fue dejado sin comentarios `/* ... */` para evitar errores de copia/pegado con `/` en SSMS. Es idempotente y puede volver a ejecutarse.
