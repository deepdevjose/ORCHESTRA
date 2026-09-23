# Explicacion profunda del notebook `01_simulation_validation_w1.ipynb`

Esta guia explica el notebook celda por celda. La idea central es que este notebook no intenta demostrar todavia que ORCHESTRA sea superior a otros metodos. Su objetivo de Semana 1 es mas basico y mas importante: demostrar que existe una base de simulacion reproducible, trazable y suficientemente coherente para que los experimentos posteriores tengan sentido.

En terminos simples: primero se construye un flujo sintetico de soldadura laser, luego se valida que ese flujo tenga variables esperadas, semillas, metadatos y casos fuera de distribucion; despues se transforma en un vector de caracteristicas para modelos, se revisan etiquetas de urgencia, se generan graficas diagnosticas y finalmente se prueba que el entorno de programacion de mantenimiento puede recibir estados, acciones y recompensas sin romperse.

## Lectura rapida del resultado global

El notebook produce 660 observaciones sinteticas:

| Grupo | Filas | Significado |
| --- | ---: | --- |
| In-distribution | 600 | Casos sinteticos generados por el simulador base: normal, focal offset, bajo gas, alta potencia, vibracion, contaminacion de lente, variacion de velocidad. |
| OOD | 60 | Casos explicitamente estresados de `ood_focus_drift`; estan fuera del rango normal esperado. |
| Train | 450 | Parte de las 600 filas in-distribution usada para entrenamiento futuro. |
| Test | 150 | Parte de las 600 filas in-distribution reservada para prueba futura. |
| OOD feature rows | 60 | Casos OOD conservados como conjunto separado, no mezclados en train/test. |

Todos los checks principales pasan: contrato cientifico, columnas, datos faltantes, reproducibilidad por semilla, separacion plausible de escenarios, vector de features, entorno, baselines, traza y evidencia.

## Que significa la semilla en este notebook

La semilla principal es `42`, tomada de `config/orchestra_config.json` como `random_seed`.

Una semilla fija hace que las decisiones aleatorias sean repetibles. Si vuelves a ejecutar el notebook con el mismo codigo, misma configuracion y misma version de librerias, deberias obtener el mismo `raw_stream.csv`, las mismas divisiones train/test y la misma traza inicial del entorno.

Donde se usa la semilla:

| Uso | Codigo conceptual | Que controla |
| --- | --- | --- |
| Simulador base | `generate_laser_welding_data(..., seed=42)` | Escenario de cada fila y valores de sensores sinteticos. |
| Metadatos | `provenance_seed = 42` | Guarda en cada fila que semilla produjo el dato. |
| OOD base | `seed + 999` | Genera una base distinta para los casos OOD antes de perturbarlos. |
| Perturbacion OOD | `seed + 2026` | Controla cuanto se estresan foco, gas, vibracion, contaminacion, etc. |
| Split train/test | `train_test_split(..., seed=42)` | Controla que filas in-distribution van a train o test. |
| Contexto de scheduling | `add_scheduling_context(..., seed=42)` | Genera carga de produccion, disponibilidad de recursos y contexto de costo. |
| Politica aleatoria | `np.random.default_rng(SEED)` | Controla las acciones aleatorias del baseline smoke test. |
| Entorno | `LaserMaintenanceSchedulingEnv(..., seed=42)` | Controla el indice inicial de cada episodio al hacer `reset()`. |

Importante: `provenance_seed` no es una variable fisica de soldadura. Es un campo de trazabilidad. Dice con que semilla se produjo la fila.

## Diccionario de datos: `raw_stream.csv`

`raw_stream.csv` representa la entrada del Machine/IoT Agent: una secuencia sintetica de observaciones de soldadura laser.

| Columna | Significado | Como leerla |
| --- | --- | --- |
| `record_id` | Identificador unico de la fila. | Ejemplo: `w1_raw_seed42_00000` significa fila base generada con semilla 42. |
| `cycle` | Indice sintetico de ciclo/tiempo. | Va de 0 a 659; OOD empieza en 600. |
| `timestamp` | Tiempo sintetico, un registro por minuto. | Inicia en `2026-09-03 00:00:00+08:00`. |
| `scenario` | Tipo de condicion simulada. | `normal`, `focal_offset`, `low_shielding_gas`, etc. |
| `laser_power_w` | Potencia del laser en watts. | Valores alrededor de 1800 W; sube en `high_laser_power`. |
| `welding_speed_mm_s` | Velocidad de soldadura en mm/s. | Alrededor de 35 mm/s; cambia fuerte en `speed_variation`. |
| `focal_position_error_mm` | Error de posicion focal en mm. | Mas alto implica foco mas desviado. |
| `shielding_gas_flow_l_min` | Flujo de gas protector en L/min. | Mas bajo puede aumentar porosidad/defectos. |
| `melt_pool_temp_c` | Temperatura del charco fundido en Celsius. | Sube con exceso de potencia. |
| `back_reflection_intensity` | Intensidad de reflexion optica normalizada. | Mayor puede sugerir problemas opticos/proceso inestable. |
| `plume_intensity` | Intensidad de pluma/plasma normalizada. | Mayor indica respuesta optica mas intensa. |
| `spatter_count` | Conteo de salpicaduras. | Mayor suele asociarse a inestabilidad. |
| `vibration_rms` | Vibracion RMS. | Mayor indica vibracion de fixture/robot. |
| `robot_path_error_mm` | Error de trayectoria del robot en mm. | Mayor indica desviacion geometrica. |
| `bead_width_mm` | Ancho del cordon. | Cambios fuertes indican defecto o variacion del proceso. |
| `bead_height_mm` | Altura del cordon. | Ayuda a describir geometria de la soldadura. |
| `porosity_risk` | Riesgo sintetico de porosidad, 0 a 1. | Mayor es peor. |
| `visual_defect_score` | Puntaje sintetico de defecto visual, 0 a 100. | Mayor es peor. |
| `lens_contamination_level` | Contaminacion de lente, 0 a 1. | Mayor es peor. |
| `cooling_system_alarm` | Alarma del sistema de enfriamiento. | 0 significa no alarma; 1 significa alarma. |
| `time_since_lens_cleaning_h` | Horas desde limpieza de lente. | Mayor puede elevar riesgo de mantenimiento. |
| `provenance_source` | Fuente del dato. | Indica si viene del generador base o del generador con estres OOD. |
| `provenance_seed` | Semilla usada. | En este notebook es 42. |
| `quality_flag` | Etiqueta de calidad del dato. | `synthetic_unvalidated` o `synthetic_ood_unvalidated`. |
| `synthetic_split` | Grupo sintetico original. | `in_distribution` u `ood`. |

## Escenarios simulados

| Escenario | Que representa | Variables que cambia el simulador |
| --- | --- | --- |
| `normal` | Operacion base sin degradacion explicita. | Valores cercanos a los centros del generador. |
| `focal_offset` | Error de enfoque. | Sube `focal_position_error_mm`, `bead_width_mm`, `visual_defect_score`. |
| `low_shielding_gas` | Flujo insuficiente de gas protector. | Baja `shielding_gas_flow_l_min`, sube `porosity_risk`, `visual_defect_score`. |
| `high_laser_power` | Exceso de potencia. | Sube `laser_power_w`, `melt_pool_temp_c`, `spatter_count`, `back_reflection_intensity`. |
| `speed_variation` | Variacion de velocidad del proceso. | Cambia `welding_speed_mm_s`, altera `bead_width_mm`, sube defectos visuales. |
| `fixture_vibration` | Vibracion mecanica. | Sube `vibration_rms`, `robot_path_error_mm`, `visual_defect_score`. |
| `lens_contamination_proxy` | Contaminacion optica. | Sube contaminacion, reflexion, pluma y tiempo desde limpieza. |
| `ood_focus_drift` | Estres fuera de distribucion. | Aumenta fuerte foco, reflexion, pluma, vibracion, error de robot, porosidad, defectos y contaminacion; baja gas. |

OOD significa "out-of-distribution": casos que no siguen la distribucion normal de entrenamiento. En el notebook, los OOD empiezan en el ciclo 600 y aparecen visualmente separados.

## Como se calcula la urgencia de mantenimiento

El notebook llama `add_maintenance_urgency(feature_vector)`. Esa funcion no lee fallas reales. Construye un target sintetico a partir de senales de riesgo.

Primero convierte varias variables a escala 0-1 con min-max:

```text
valor_normalizado = (valor - minimo) / (maximo - minimo)
```

Luego calcula componentes:

| Componente | Variables usadas |
| --- | --- |
| Riesgo termico | Desviacion de `melt_pool_temp_c` respecto a 1450 C. |
| Riesgo de potencia | Desviacion de `laser_power_w` respecto a 1800 W. |
| Riesgo de velocidad | Desviacion de `welding_speed_mm_s` respecto a 35 mm/s. |
| Riesgo focal | `focal_position_error_mm`. |
| Riesgo de gas | Inverso de `shielding_gas_flow_l_min`; menor gas equivale a mas riesgo. |
| Riesgo optico | `back_reflection_intensity` y `plume_intensity`. |
| Riesgo por salpicadura | `spatter_count`. |
| Riesgo de movimiento | `vibration_rms` y `robot_path_error_mm`. |
| Riesgo de calidad | `visual_defect_score`, `porosity_risk`, desviacion de `bead_width_mm`. |
| Riesgo de mantenimiento | `lens_contamination_level`, `time_since_lens_cleaning_h`, `cooling_system_alarm`. |

La formula ponderada es:

```text
raw =
  0.12 * thermal_risk
+ 0.08 * power_risk
+ 0.07 * speed_risk
+ 0.11 * focal_risk
+ 0.08 * gas_risk
+ 0.12 * optical_risk
+ 0.08 * spatter_risk
+ 0.10 * motion_risk
+ 0.14 * quality_risk
+ 0.10 * maintenance_risk
```

Despues:

```text
process_instability_score = 100 * raw
maintenance_urgency_score = minmax(process_instability_score) * 100
```

La diferencia entre ambos:

| Campo | Significado |
| --- | --- |
| `process_instability_score` | Riesgo agregado directo de la formula. |
| `maintenance_urgency_score` | Riesgo reescalado a 0-100 relativo al dataset completo. |

Esto es importante: como el min-max se calcula sobre todo el dataset, incluyendo OOD, los OOD empujan el maximo hacia arriba. Por eso los casos normales quedan con urgencias bajas y los OOD quedan mucho mas altos.

Las etiquetas se asignan asi:

| Urgencia | `maintenance_label` |
| ---: | --- |
| 0 a 40 | `low` |
| 40 a 70 | `medium` |
| 70 a 100 | `high` |

## Como leer las tablas de Pandas

En las tablas del notebook, la columna mas a la izquierda sin nombre suele ser el indice de Pandas, no una variable del experimento. Las columnas con nombre son los datos reales de la tabla.

En una tabla tipo `describe()`:

| Columna | Significado |
| --- | --- |
| `count` | Numero de filas. |
| `mean` | Promedio. |
| `std` | Desviacion estandar; indica dispersion. |
| `min` | Valor minimo. |
| `25%` | Primer cuartil. |
| `50%` | Mediana. |
| `75%` | Tercer cuartil. |
| `max` | Valor maximo. |

En una `crosstab`, las filas y columnas son categorias. Cada celda es un conteo.

## Explicacion celda por celda

### Celda 1 - Titulo y proposito

Es una celda Markdown. Declara que el notebook es la entrega de validacion de Semana 1 para ORCHESTRA en soldadura laser. Tambien deja claro que integra contrato cientifico, simulacion sintetica, features, checks, smoke tests, figuras y evidencia. No reemplaza el pipeline oficial, solo lo valida y documenta.

### Celda 2 - Executive Summary

Resume los entregables W1D1 a W1D7. La tabla muestra que cada dia de la semana tiene un artefacto asociado:

| Dia | Artefacto principal | Funcion |
| --- | --- | --- |
| W1D1 | `spec.md` | Contrato de claims permitidos y prohibidos. |
| W1D2 | `raw_stream.csv`, `ood_stream.csv` | Datos sinteticos base y OOD. |
| W1D3 | `feature_vector.csv` | Features listas para modelos con trazabilidad. |
| W1D4 | `week1_environment_sanity.csv` | Revision del entorno de scheduling. |
| W1D5 | `week1_baseline_smoke.csv` | Prueba rapida de politicas random y rule-based. |
| W1D6 | PNGs y traza CSV | Graficas diagnosticas y episodio reconstruible. |
| W1D7 | inventario y JSON | Indice de evidencia y resumen final. |

La frase clave es que todo es sintetico y debe reportarse como evidencia de simulacion.

### Celda 3 - Logica de aceptacion

Explica el criterio de aceptacion de Semana 1. La pregunta no es "el modelo predice bien?", sino "el simulador es plausible y trazable?". Por eso un buen resultado de XGBoost o PPO no bastaria si la simulacion estuviera mal construida.

### Celda 4 - Introduccion al setup reproducible

Indica que la siguiente celda localiza el proyecto, crea carpetas de evidencia y registra versiones. Es una preparacion para que alguien pueda reproducir el notebook.

### Celda 5 - Setup, paths y versiones

Esta es una celda de codigo larga. Hace varias cosas:

1. Importa librerias: `json`, `platform`, `sys`, `Path`, `matplotlib`, `numpy`, `pandas`.
2. Define `find_project_root()`, que busca la raiz del proyecto detectando `config/orchestra_config.json` y `src/orchestra_laser`.
3. Agrega `src` al `sys.path` para poder importar modulos locales.
4. Define rutas de evidencia por dia: `W1D1_DIR`, `W1D2_DIR`, ..., `W1D7_DIR`.
5. Define rutas concretas de archivos: `RAW_STREAM_PATH`, `FEATURE_VECTOR_PATH`, `ENV_SANITY_PATH`, etc.
6. Crea carpetas con `mkdir(parents=True, exist_ok=True)`.
7. Genera `version_info`.

Output importante:

```text
project_root = .../ORCHESTRA-Laser-Welding
workspace_root = .../Jose Manuel RDF
python = 3.14.7
numpy = 2.4.6
pandas = 2.3.3
matplotlib = 3.10.9
```

Ese output no es un resultado cientifico; es evidencia de ambiente. Sirve para reproducibilidad.

### Celda 6 - Importar modulos de produccion

Markdown. Explica que el notebook usa los mismos modulos bajo `src/orchestra_laser`, evitando duplicar logica dentro del notebook. Esto es bueno metodologicamente porque reduce discrepancias entre notebook y pipeline oficial.

### Celda 7 - Configuracion y acciones

Importa funciones del codigo del proyecto:

| Import | Para que sirve |
| --- | --- |
| `generate_laser_welding_data` | Generar datos sinteticos base. |
| `clean_laser_welding_data` | Asegurar columnas numericas y llenar faltantes. |
| `add_maintenance_urgency` | Crear score y etiqueta de urgencia. |
| `add_scheduling_context` | Agregar contexto operativo. |
| `LaserMaintenanceSchedulingEnv` | Entorno tipo Gym para scheduling. |
| `evaluate_policy`, `rule_based_policy` | Evaluar politicas simples. |
| `ACTION_NAMES` | Mapa de acciones 0-4. |

Lee `orchestra_config.json` y fija:

```text
SEED = 42
n_samples = 600
train_fraction = 0.75
episode_length = 120
n_eval_episodes = 30
feature_count = 17
```

Acciones:

| Accion | Nombre | Significado |
| ---: | --- | --- |
| 0 | `do_nothing` | Continuar produccion. |
| 1 | `inspect` | Inspeccionar. |
| 2 | `minor_maintenance` | Mantenimiento menor. |
| 3 | `major_maintenance` | Mantenimiento mayor. |
| 4 | `urgent_intervention` | Intervencion urgente. |

### Celda 8 - Guia del plan semanal

Markdown. Dice que la siguiente tabla mapea secciones del notebook contra tareas oficiales de Semana 1.

### Celda 9 - Tabla `plan_alignment`

Crea una tabla con columnas:

| Columna | Significado |
| --- | --- |
| `day` | Dia de Semana 1: W1D1, W1D2, etc. |
| `plan_task` | Tarea que correspondia a ese dia. |
| `notebook_section` | Secciones del notebook donde se evidencia. |
| `evidence` | Ruta del archivo generado o revisado. |

Como leerla: cada fila es un puente entre el plan y la evidencia. No valida datos todavia; organiza la auditoria.

### Celda 10 - Contrato cientifico

Markdown. Define que `spec.md` es el contrato cientifico: que puede afirmar el paper, que no puede afirmar y como se comunican los agentes.

Lista secciones requeridas: `Scope`, `Core Claims`, `Must Not Claim`, `Four-Agent Message Contract`, `Action Space`, `Data Contract`, `Reproducibility Contract`.

### Celda 11 - Check de `spec.md`

Verifica que `spec.md` exista y contenga las secciones minimas. Produce:

```text
spec.md lines: 100
```

La tabla `spec_checks` tiene 7 filas y todas salen `True`. Eso significa que el contrato minimo existe.

El excerpt de `spec.md` muestra claims:

| Claim | Significado |
| --- | --- |
| C1 | El simulador produce escenarios plausibles normal/degradacion/OOD. |
| C2 | La revision humana disparada por incertidumbre se evaluara despues. |
| C3 | La arquitectura completa se comparara contra baselines/ablaciones despues. |

Claims prohibidos:

- No afirmar validacion en hardware real.
- No afirmar estudio con operadores reales.
- No afirmar certificacion de seguridad.
- No afirmar despliegue industrial.
- No afirmar causalidad real fuera de simulacion.

### Celda 12 - Generacion del stream sintetico

Markdown. Introduce `raw_stream.csv` como la entrada del Machine/IoT Agent. Explica los dos grupos:

1. In-distribution: 600 casos del generador base.
2. OOD stress: 60 casos `ood_focus_drift`.

Esta celda marca el inicio de W1D2.

### Celda 13 - Crear `raw_stream.csv` y `ood_stream.csv`

Define dos funciones.

`attach_stream_metadata()` agrega:

| Campo | Funcion |
| --- | --- |
| `record_id` | ID unico con prefijo, semilla e indice. |
| `cycle` | Indice sintetico continuo. |
| `timestamp` | Tiempo sintetico a frecuencia de 1 minuto. |
| `provenance_source` | De donde viene la fila. |
| `provenance_seed` | Semilla usada. |
| `quality_flag` | Advertencia de que es sintetico/no validado. |

`generate_ood_focus_drift()` crea casos OOD. Primero llama al generador base con `seed + 999` y luego aplica perturbaciones con `seed + 2026`:

| Variable | Cambio OOD |
| --- | --- |
| `focal_position_error_mm` | Aumenta entre 0.55 y 0.95 mm. |
| `shielding_gas_flow_l_min` | Disminuye entre 6 y 10 L/min. |
| `lens_contamination_level` | Aumenta entre 0.35 y 0.65. |
| `back_reflection_intensity` | Aumenta entre 0.25 y 0.45. |
| `plume_intensity` | Aumenta entre 0.18 y 0.35. |
| `vibration_rms` | Aumenta entre 0.18 y 0.35. |
| `robot_path_error_mm` | Aumenta entre 0.12 y 0.28 mm. |
| `porosity_risk` | Aumenta entre 0.25 y 0.45. |
| `visual_defect_score` | Aumenta entre 25 y 45 puntos. |
| `time_since_lens_cleaning_h` | Aumenta entre 30 y 60 horas. |

Despues genera:

```text
base_stream = 600 filas
ood_stream = max(30, 10% de 600) = 60 filas
raw_stream = 660 filas
```

Output:

```text
Raw stream shape: (660, 25)
```

La tabla `raw_stream.head()` muestra las primeras 5 filas. Como leer una fila:

- `record_id = w1_raw_seed42_00000`: fila base, semilla 42, indice 0.
- `cycle = 0`: primer ciclo sintetico.
- `timestamp = 2026-09-03 00:00:00+08:00`: tiempo sintetico.
- `scenario = normal`: caso normal.
- Luego vienen 17 variables de proceso/sensor/calidad/mantenimiento.
- `provenance_source` y `quality_flag` recuerdan que es dato sintetico.

### Celda 14 - Validacion del stream crudo

Markdown. Introduce checks de ingenieria:

- columnas esperadas,
- datos faltantes,
- reproducibilidad con la misma semilla,
- metadatos,
- OOD presente.

Aclara que pasar estos checks no prueba realismo fisico; prueba usabilidad y trazabilidad inicial.

### Celda 15 - Checks de `raw_stream`

Recrea `base_stream_again` y `ood_stream_again` con la misma semilla, concatena y compara con `raw_stream`. Si son iguales, la semilla reproduce el stream.

Checks:

| Check | Resultado |
| --- | --- |
| Todas las features configuradas existen | True |
| Todos los metadatos existen | True |
| No hay faltantes en features | True |
| `record_id` es unico | True |
| Misma semilla reproduce stream | True |
| Hay OOD | True |
| Hay normales | True |
| Hay casos de focus drift/degradacion focal | True |

La tabla de conteos por escenario:

| Escenario | Filas |
| --- | ---: |
| `fixture_vibration` | 100 |
| `high_laser_power` | 98 |
| `normal` | 89 |
| `focal_offset` | 84 |
| `lens_contamination_proxy` | 80 |
| `low_shielding_gas` | 75 |
| `speed_variation` | 74 |
| `ood_focus_drift` | 60 |

La distribucion no es exactamente uniforme porque `rng.choice()` selecciona escenarios aleatoriamente.

### Celda 16 - Plausibilidad por escenario

Markdown. Introduce la idea de "direccion fisica esperada". No busca calibracion de laboratorio, sino verificar que los cambios simulados van en el sentido correcto.

### Celda 17 - Checks de plausibilidad y medias por escenario

Define `scenario_mean()` y compara promedios.

Checks principales:

| Expectativa | Comparacion observada | Resultado |
| --- | --- | --- |
| `focal_offset` tiene mas error focal que normal | 0.384 > 0.074 | True |
| OOD excede a `focal_offset` en error focal | 0.883 > 0.384 | True |
| `low_shielding_gas` tiene menos gas que normal | 11.903 < 18.137 | True |
| OOD tiene menos gas que normal | 8.662 < 18.137 | True |
| `fixture_vibration` tiene mas vibracion que normal | 0.279 > 0.077 | True |
| `lens_contamination_proxy` tiene mas contaminacion que normal | 0.527 > 0.115 | True |
| OOD tiene mas contaminacion que normal | 0.681 > 0.115 | True |
| OOD tiene mas defecto visual que normal | 51.959 > 8.269 | True |

La tabla `scenario_summary` muestra medias de variables clave por escenario. Ejemplos de lectura:

- `ood_focus_drift` tiene `focal_position_error_mm = 0.883`, mucho mayor que normal.
- `ood_focus_drift` tiene gas `8.662`, mucho menor que normal `18.137`.
- `fixture_vibration` tiene `vibration_rms = 0.279`, mayor que normal `0.077`.
- `lens_contamination_proxy` tiene contaminacion `0.527`, mayor que normal `0.115`.
- `low_shielding_gas` tiene porosidad `0.462`, mucho mayor que normal `0.116`.

Esto apoya C1/E1: los escenarios sinteticos se separan en la direccion esperada.

### Celda 18 - Construccion del feature vector

Markdown. Explica que el Machine/IoT Agent transforma el stream crudo en un vector listo para modelos. Incluye features, metadatos, split, target sintetico y contexto de scheduling.

### Celda 19 - Crear `feature_vector.csv`

Hace la transformacion principal:

1. `clean_laser_welding_data(raw_stream, FEATURE_COLUMNS)`: asegura que las 17 features sean numericas y sin faltantes.
2. `add_maintenance_urgency(feature_vector)`: agrega `process_instability_score`, `maintenance_urgency_score`, `maintenance_label`.
3. `add_scheduling_context(feature_vector, seed=SEED)`: agrega variables operativas.
4. Separa las 600 filas in-distribution.
5. Hace train/test con `train_fraction = 0.75`.
6. Marca todas las filas como `ood` inicialmente.
7. Cambia a `train` o `test` si el `record_id` esta en esos conjuntos.
8. Agrega version y transformacion de procedencia.
9. Copia `timestamp` a `available_at`.

Output:

```text
Feature vector shape: (660, 35)
```

Por que sube de 25 a 35 columnas:

| Nuevas columnas | Significado |
| --- | --- |
| `process_instability_score` | Score sintetico directo de inestabilidad. |
| `maintenance_urgency_score` | Urgencia normalizada 0-100. |
| `maintenance_label` | `low`, `medium`, `high`. |
| `production_load` | Carga de produccion 0.25-0.95. |
| `resource_availability` | Disponibilidad de recursos 0.35-1.0. |
| `maintenance_cost_context` | Contexto de costo 0.25-0.90. |
| `split` | `train`, `test`, `ood`. |
| `feature_vector_version` | Version del vector. |
| `provenance_transform` | Cadena de funciones aplicadas. |
| `available_at` | Momento en que el dato estaria disponible. |

### Celda 20 - Validacion del feature vector

Markdown. Introduce checks para saber si el vector sirve para el AI Predictive Agent y el scheduling environment.

### Celda 21 - Checks de `feature_vector`

Verifica:

| Check | Resultado |
| --- | --- |
| Todas las features configuradas existen | True |
| Metadatos existen | True |
| Targets existen | True |
| Contexto de scheduling existe | True |
| No hay faltantes en features | True |
| Urgencia esta entre 0 y 100 | True |
| Split train existe | True |
| Split test existe | True |
| Split OOD existe | True |

Conteo por split:

| Split | Filas |
| --- | ---: |
| train | 450 |
| test | 150 |
| ood | 60 |

Esto confirma que OOD no se mezclo con entrenamiento/prueba normal.

### Celda 22 - Distribucion de target y labels

Markdown. Explica una limitacion central: `maintenance_urgency_score` es sintetico, derivado de inestabilidad del proceso. En Week 2, un predictor podria aprender parcialmente la formula que genero el score, no una verdad de mantenimiento real.

Esto se debe reportar honestamente en el paper.

### Celda 23 - Tablas de distribucion de urgencia

Genera tres tablas.

Primera: `urgency_summary`, usando `describe()` por split.

| Split | Media | Lectura |
| --- | ---: | --- |
| `ood` | 73.534 | OOD es mucho mas urgente en promedio. |
| `test` | 21.877 | Test in-distribution es bajo en promedio. |
| `train` | 21.180 | Train in-distribution es similar a test. |

Detalles importantes:

- OOD tiene minimo 53.433 y maximo 100.000.
- Train tiene maximo 52.188.
- Test tiene maximo 49.808.

Eso indica separacion fuerte: OOD ocupa rangos de urgencia mas altos que train/test.

Segunda: `label_distribution`.

| Split | high | low | medium |
| --- | ---: | ---: | ---: |
| `ood` | 42 | 0 | 18 |
| `test` | 0 | 147 | 3 |
| `train` | 0 | 441 | 9 |

Lectura: casi todo train/test es `low`, algunos son `medium`, ninguno `high`; OOD tiene muchos `high`.

Tercera: `scenario_urgency`.

| Escenario | Media de urgencia |
| --- | ---: |
| `ood_focus_drift` | 73.534 |
| `high_laser_power` | 32.328 |
| `low_shielding_gas` | 23.440 |
| `lens_contamination_proxy` | 22.212 |
| `fixture_vibration` | 20.670 |
| `speed_variation` | 19.354 |
| `focal_offset` | 19.003 |
| `normal` | 11.392 |

Lectura: el mas grave es OOD; dentro de in-distribution, `high_laser_power` produce mayor urgencia media.

### Celda 24 - Figura 1: urgencia sobre tiempo sintetico

Markdown. Introduce la grafica de dispersion.

### Celda 25 - Grafica `week1_urgency_vs_time.png`

La figura muestra:

| Elemento | Significado |
| --- | --- |
| Eje X | `cycle`, ciclo sintetico de 0 a 659. |
| Eje Y | `maintenance_urgency_score`, urgencia 0-100. |
| Cada punto | Una fila/observacion. |
| Color | Escenario. |

Como leerla:

- Entre ciclos 0 y 599 estan los casos in-distribution mezclados.
- Entre ciclos 600 y 659 aparecen los OOD.
- Los OOD se ven agrupados arriba, aproximadamente entre 53 y 100.
- Los normales y degradaciones in-distribution quedan mayormente por debajo de 50.

Conclusion: visualmente hay separacion entre OOD y datos normales/degradados. Esto respalda la plausibilidad inicial del simulador.

### Celda 26 - Figura 2: distribuciones de features

Markdown. Introduce histogramas para comparar in-distribution contra OOD en variables clave.

### Celda 27 - Grafica `week1_feature_distributions.png`

Genera seis histogramas:

| Subgrafica | Que compara |
| --- | --- |
| `focal_position_error_mm` | Error focal in-distribution vs OOD. |
| `shielding_gas_flow_l_min` | Flujo de gas in-distribution vs OOD. |
| `back_reflection_intensity` | Reflexion optica in-distribution vs OOD. |
| `vibration_rms` | Vibracion in-distribution vs OOD. |
| `porosity_risk` | Riesgo de porosidad in-distribution vs OOD. |
| `lens_contamination_level` | Contaminacion de lente in-distribution vs OOD. |

Como leer cada histograma:

- Eje X: valor de la variable.
- Eje Y: numero de filas.
- Azul: in-distribution.
- Naranja: OOD.

Patrones esperados:

- En error focal, OOD se desplaza a la derecha: mas error.
- En gas, OOD se desplaza a la izquierda: menos gas protector.
- En reflexion, OOD se desplaza a la derecha: mas reflexion.
- En vibracion, OOD se desplaza a la derecha: mas vibracion.
- En porosidad, OOD se desplaza a la derecha: mas riesgo.
- En contaminacion, OOD se desplaza a la derecha: mas contaminacion.

Nota visual: en el PNG el titulo y la leyenda superior se enciman un poco. No cambia la interpretacion, pero convendria ajustarlo antes de publicar la figura.

### Celda 28 - Entorno de scheduling

Markdown. Explica el entorno `LaserMaintenanceSchedulingEnv`.

Vector de estado de 7 valores:

| Indice | Variable | Rango esperado |
| ---: | --- | --- |
| 0 | Urgencia u `orchestra_urgency` | 0-1 |
| 1 | Incertidumbre | 0-1 |
| 2 | Carga de produccion | 0-1 |
| 3 | Disponibilidad de recursos | 0-1 |
| 4 | Tiempo desde mantenimiento | 0-1 |
| 5 | Contexto de costo | 0-1 |
| 6 | Inestabilidad del proceso | 0-1 |

El entorno recibe una accion 0-4 y devuelve recompensa, siguiente estado, bandera `done` e informacion diagnostica.

### Celda 29 - Sanity check del entorno

Crea `env_data` excluyendo OOD. Esto es correcto para un smoke test del entorno base, porque no quiere que casos extremos dominen la prueba inicial.

Hace tres checks del estado inicial:

```text
state_shape_is_7 = True
state_values_are_finite = True
state_values_within_expected_range = True
```

Luego toma:

- `low_row`: fila con menor urgencia.
- `high_row`: fila in-distribution con mayor urgencia.

Evalua las 5 acciones en ambos casos.

Lectura de la tabla:

| Columna | Significado |
| --- | --- |
| `case` | Caso bajo o alto de urgencia. |
| `case_urgency` | Urgencia del caso. |
| `action` / `action_name` | Accion evaluada. |
| `reward` | Recompensa resultante. Mayor es mejor. |
| `downtime` | Penalizacion operativa por paro. |
| `cost` | Costo relativo de accion. |
| `failure` | Si queda riesgo de falla por subtratar. |
| `unnecessary` | Si fue mantenimiento innecesario. |
| `risk_after_action` | Riesgo residual despues de la accion. |
| `alignment_bonus` | Premio por elegir accion alineada con urgencia. |

Resultados clave:

- En `low_urgency_case`, `do_nothing` da la mejor recompensa: 2.488.
- En `low_urgency_case`, acciones fuertes son negativas porque son innecesarias.
- En `high_urgency_case` in-distribution, `minor_maintenance` da la mejor recompensa: 1.567.
- `urgent_intervention` es muy negativa en ambos porque para una urgencia de 52.188 es demasiado agresiva.

Esto muestra que la funcion de recompensa castiga tanto subtratar como sobretratar.

### Celda 30 - Baseline smoke test

Markdown. Aclara que no es una comparacion final. Solo verifica que politicas simples corren de inicio a fin con semilla fija y salidas finitas.

### Celda 31 - Random vs rule-based smoke

Define `random_policy`, que escoge una accion aleatoria entre 0 y 4.

Evalua dos politicas durante 5 episodios de 120 pasos:

| Politica | Mean reward | Mean downtime | Mean cost | Mean unnecessary |
| --- | ---: | ---: | ---: | ---: |
| `week1_random_smoke` | -273.265 | 41.620 | 38.000 | 71.000 |
| `week1_rule_based_smoke` | 225.830 | 0.292 | 0.220 | 0.000 |

Como interpretar:

- La politica aleatoria elige muchas acciones costosas sin necesidad. Por eso tiene recompensa muy negativa, mucho downtime, alto costo y 71 mantenimientos innecesarios promedio.
- La politica rule-based casi siempre evita intervenciones innecesarias y acumula recompensa positiva.
- Ambas tienen `mean_failures = 0`, lo cual en este smoke test indica que no se generaron fallas bajo esas trayectorias.

No se debe decir que la rule-based "gana cientificamente"; solo que el entorno distingue entre decisiones absurdas y decisiones razonables.

### Celda 32 - Traza de politica rule-based

Markdown. Introduce una traza completa de un episodio. Cada fila de la traza permite reconstruir que caso vio el agente, que accion eligio y que recompensa recibio.

### Celda 33 - Generar `week1_rule_based_trace.csv`

Crea un entorno nuevo con semilla 42, hace `reset()` y corre hasta `done`.

Como `episode_length = 120`, la traza tiene 120 pasos.

La politica usada es:

| Condicion | Accion |
| --- | --- |
| Urgencia >= 80 | `urgent_intervention` |
| Urgencia >= 65 | `major_maintenance` |
| Urgencia >= 45 o incertidumbre >= 0.45 | `minor_maintenance` |
| Incertidumbre >= 0.25 | `inspect` |
| Si no | `do_nothing` |

En Week 1 casi no hay incertidumbre, asi que domina la urgencia.

Checks:

```text
episode_length = 120
expected_episode_length = 120
all_rewards_are_finite = True
all_actions_are_valid = True
```

Primeras filas:

- Paso 0: ciclo 53, escenario `high_laser_power`, urgencia 31.97, accion `do_nothing`, recompensa 1.765.
- Paso 1: urgencia 30.17, accion `do_nothing`, recompensa 1.806.
- Paso 2: normal, urgencia 20.32, accion `do_nothing`, recompensa 2.003.

Resumen de la traza:

| Metrica | Valor |
| --- | ---: |
| Pasos | 120 |
| Recompensa media | 1.835 |
| Recompensa minima | -0.033 |
| Recompensa maxima | 2.469 |
| Acciones `do_nothing` | 118 |
| Acciones `minor_maintenance` | 2 |
| Fallas | 0 |

La traza empieza en ciclo 53 porque `env.reset()` selecciona un indice inicial pseudoaleatorio controlado por la semilla.

### Celda 34 - Figura 3: reward trace

Markdown. Introduce la grafica de recompensa paso a paso.

### Celda 35 - Grafica `week1_reward_trace.png`

La figura muestra:

| Elemento | Significado |
| --- | --- |
| Eje X | Paso del episodio, 0 a 119. |
| Eje Y | Recompensa en ese paso. |
| Linea azul | Recompensa de la politica rule-based. |
| Linea horizontal negra | Recompensa 0, referencia entre positivo y negativo. |

Como leerla:

- La mayoria de puntos estan entre 1.8 y 2.4: decisiones buenas o razonables.
- Hay caidas cerca de 0: casos donde `do_nothing` fue menos adecuado, usualmente por urgencia moderada-alta sin bonus de alineacion.
- Casi no hay valores negativos, y el minimo es -0.033.

Conclusion: el entorno produce recompensas finitas y coherentes, y la regla simple se mantiene estable en el episodio.

### Celda 36 - Inventario de evidencia

Markdown. Explica que la siguiente tabla es el indice de entrega de Semana 1.

### Celda 37 - Crear `week1_evidence_inventory.csv`

Construye una tabla con:

| Columna | Significado |
| --- | --- |
| `week_item` | Dia/entregable W1D1-W1D6. |
| `artifact` | Ruta del archivo. |
| `purpose` | Para que sirve la evidencia. |
| `exists` | Si el archivo existe en disco. |

Todos salen `exists = True`. Esto significa que el paquete de evidencia esta completo segun el notebook.

### Celda 38 - Resumen JSON

Markdown. Introduce el resumen machine-readable. Es util para reporte o paper porque concentra checks y rutas.

### Celda 39 - Crear `week1_deliverable_summary.json`

Crea un diccionario `week1_summary` y lo guarda como JSON.

Campos principales:

| Campo | Significado |
| --- | --- |
| `week` | Semana 1. |
| `dates` | 2026-09-03 a 2026-09-09. |
| `scope` | Solo validacion por simulacion. |
| `primary_evidence_target` | E1 simulation validity. |
| `seed` | 42. |
| `rows` | Conteos de raw, train, test, OOD. |
| `checks` | Resultado booleano de cada grupo de validacion. |
| `main_outputs` | Rutas de artefactos principales. |
| `valid_claim` | Claim permitido por esta evidencia. |
| `forbidden_claims` | Claims que todavia no se pueden hacer. |

El claim valido es limitado: existe una base de simulacion reproducible y trazable con OOD, features, entorno, baselines smoke, figuras y traza.

### Celda 40 - Interpretacion para reporte de Semana 1

Markdown. Resume como escribir el resultado:

Se puede afirmar que hay una base reproducible de simulacion con datos sinteticos trazables, OOD, features, checks de entorno, graficas diagnosticas y traza reconstruible.

No se puede afirmar:

- rendimiento final,
- despliegue industrial,
- operadores reales,
- certificacion de seguridad.

Tambien recomienda siguiente paso: unit tests formales y trabajo de Week 2 en prediccion/calibracion.

### Celda 41 - Preguntas de defensa

Markdown. Lista preguntas para verificar que entiendes el notebook:

1. Diferencia entre `raw_stream.csv` y `feature_vector.csv`.
2. Por que se necesitan OOD antes de entrenar.
3. Que variables distinguen `ood_focus_drift`.
4. Que significa provenance.
5. Por que la urgencia es target sintetico.
6. Cuales son las cinco acciones.
7. Por que random/rule baseline es smoke test.
8. Que claim valido soporta el notebook.
9. Que claims siguen prohibidos.
10. Que falta antes de cerrar Semana 1.

La respuesta buena a la 10 es: agregar unit tests, correr desde clean checkout, preservar logs/configuracion y revisar el simulador contra expectativas del dominio antes de usar metricas de Week 2 como evidencia fuerte.

## Como leer las tres graficas en conjunto

| Figura | Pregunta que responde | Respuesta visual |
| --- | --- | --- |
| Urgencia vs ciclo | Los OOD se separan en urgencia? | Si. OOD aparece despues del ciclo 600 y arriba en el eje Y. |
| Distribuciones de features | Los OOD se salen del rango normal en variables fisicas clave? | Si. Se desplazan en foco, gas, reflexion, vibracion, porosidad y contaminacion. |
| Reward trace | El entorno da recompensas finitas y razonables? | Si. La traza es estable, mayormente positiva, con pocas caidas. |

## Interpretacion cientifica correcta

Este notebook apoya una afirmacion fuerte pero limitada:

> La Semana 1 establece una base de simulacion reproducible, trazable y auditable para estudiar mantenimiento predictivo multi-agente en soldadura laser dentro de un entorno sintetico.

No apoya aun:

- que ORCHESTRA funcione en una celda real de soldadura,
- que el modelo generalice a datos industriales,
- que operadores humanos reales hayan validado el sistema,
- que PPO/XGBoost sean aportes algoritmicos novedosos,
- que el sistema sea seguro para despliegue.

## Puntos que conviene mejorar antes de publicar

1. Arreglar el solapamiento de titulo/leyenda en `week1_feature_distributions.png`.
2. Agregar tests unitarios para generador, OOD, split, urgencia y entorno.
3. Reportar explicitamente que `maintenance_urgency_score` es sintetico.
4. Evaluar con multiples semillas, no solo 42, para evidencia estadistica futura.
5. Mantener OOD separado de train/test para evitar leakage.
6. Documentar que los umbrales `low/medium/high` son de simulacion y no umbrales industriales calibrados.

