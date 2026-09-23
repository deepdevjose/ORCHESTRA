# ORCHESTRA 4-Week Validation Plan

Guia operativa para ejecutar el plan de validacion de ORCHESTRA. El plan
original esta disponible en:

- `ORCHESTRA_Student_4_Week_Validation_Plan.odt`: version narrativa.
- `ORCHESTRA_Student_4_Week_Validation_Plan.ods`: calendario, matriz y riesgos.
- `ORCHESTRA_Student_4_Week_Validation_Plan.docx` y `.xlsx`: versiones
  equivalentes conservadas.

## Contrato del trabajo

| Elemento | Definicion |
| --- | --- |
| Inicio | 03-09-2026, jueves |
| Fin planificado | 30-09-2026, miercoles |
| Zona horaria | Asia/Shanghai |
| Dedicacion | 40 h/semana, aproximadamente 160 h |
| Alcance | Validacion basada solo en simulacion |
| Entregable final | Borrador de conferencia de 8-10 paginas + paquete reproducible |
| Idioma | Ingles en codigo, comentarios y paper; cero texto chino |
| Evidencia minima | E1-E9, al menos 5 semillas y 95% CI |

No se debe afirmar validacion con hardware real ni estudio con operadores en
esta iteracion. Esas actividades quedan como trabajo futuro.

## Calendario general

| Semana | Fechas | Objetivo | Puerta de salida |
| --- | --- | --- | --- |
| Week 1 | 03-09 Sep | Fundaciones, simulador y entorno reproducible | Una traza completa con semilla fija + 3 graficas diagnosticas |
| Week 2 | 10-16 Sep | Predictor, incertidumbre y revision humana | CV de 5 folds + calibracion + barrido de umbral |
| Week 3 | 17-23 Sep | PPO, baselines, ablaciones y sensibilidad | Trazas auditables + significancia estadistica |
| Week 4 | 24-30 Sep | Paper, archivo y paquete reproducible | Pre-review del advisor + entrega v1.0 |

Cada semana usa D1-D7 en orden: jueves, viernes, sabado, domingo, lunes,
martes y miercoles.

## Semana 1: Foundations and freeze

**Fechas:** 03-09 Sep | **Carga:** 40 h

| Fecha | Horas | Actividad | Resultado esperado |
| --- | ---: | --- | --- |
| 03 Sep | 2 | Escribir `spec.md`: 3 claims, experimentos asociados, claims prohibidos y contrato entre 4 agentes | `spec.md` comprometido |
| 04 Sep | 6 | Generar escenarios normales y degradacion por focus drift con variables laser y semilla fija | `raw_stream.csv` |
| 05 Sep | 8 | Implementar Machine/IoT Agent, validacion, provenance y vector de features | `feature_vector.csv` + tags de provenance |
| 06 Sep | 8 | Implementar entorno tipo Gymnasium: estado, 5 acciones, recompensa, recursos y feedback | Sanity checks del entorno |
| 07 Sep | 8 | Configuracion, control de semillas, logging y baselines random/rule-based | Repo reproducible |
| 08 Sep | 6 | Tests unitarios y 3 graficas: urgencia-tiempo, distribuciones y recompensa | Graficas en `report/figures/` |
| 09 Sep | 2 | Clonar/ejecutar desde limpio y retrospectiva | Gate de Week 1 |

**Recursos:**

- Codigo base: `05_Publications/Journal_Paper/ORCHESTRA-Laser-Welding/src/orchestra_laser/`
- Generacion: `synthetic_data.py`, `preprocessing.py`, `urgency.py`
- Entorno: `scheduling_env.py`
- Entrada: `config/orchestra_config.json`
- Ejecucion: `scripts/run_pipeline.py`
- Tests/diagnostico: crear bajo `tests/` y `results/figures/` dentro del proyecto ORCHESTRA
- Contexto IAPM: `03_Framework_and_Methodology/IAPM_Framework/`

**Resumen:** primero hay que congelar el contrato científico y demostrar que la
simulacion produce estados plausibles, trazables y reproducibles. Si la traza
completa no corre con una semilla fija, no avanzar a modelos.

## Semana 2: Prediction and human review

**Fechas:** 10-16 Sep | **Carga:** 40 h

| Fecha | Horas | Actividad | Resultado esperado |
| --- | ---: | --- | --- |
| 10 Sep | 8 | Entrenar XGBoost, CV de 5 folds y tuning | MAE/RMSE/R2 registrados |
| 11 Sep | 6 | SHAP y contraste con expectativas físicas | Graficas SHAP + notas de plausibilidad |
| 12 Sep | 8 | Implementar proxy de incertidumbre y medir ECE/cobertura | Grafica de calibracion |
| 13 Sep | 8 | Routing de revisión por umbral, severidad, conflicto y recursos | Router implementado |
| 14 Sep | 6 | Barrido de umbrales | Tabla/grafica de review rate, overrides, fallos y carga |
| 15 Sep | 2 | Comparar no-review, random, uncertainty-triggered y all-review | Tabla E4 con presupuesto igual |
| 16 Sep | 2 | Archivar modelo/resultados y actualizar `spec.md` | Gate de Week 2 |

**Recursos:** `predictive_agent.py`, `uncertainty.py`, `human_agent.py`,
`experiments.py`, `config/orchestra_config.json`, `data/processed/`,
`models/predictive_agent_report.json` y `results/tables/`.

**Resumen:** el objetivo es demostrar que el predictor no solo acierta, sino
que conoce cuándo es incierto y deriva esos casos al agente humano. La
comparacion debe mantener el mismo presupuesto de revisiones.

## Semana 3: Scheduling and architecture

**Fechas:** 17-23 Sep | **Carga:** 40 h

| Fecha | Horas | Actividad | Resultado esperado |
| --- | ---: | --- | --- |
| 17 Sep | 8 | PPO y sensibilidad de hiperparametros sobre al menos 5 semillas | Curvas de aprendizaje |
| 18 Sep | 6 | Ablacion de recompensa: safety, downtime, cost, load y full | Tabla de reward ablation |
| 19 Sep | 8 | Ejecutar 5 baselines: corrective, periodic, XGBoost alert, rule y PPO-only | Tabla comparativa |
| 20 Sep | 8 | Ejecutar 5 ablaciones de componentes | Tabla de ablacion |
| 21 Sep | 6 | Sensibilidad a ruido, missing modality, drift, OOD, recursos y delay | Graficas de sensibilidad |
| 22 Sep | 2 | Completar trazas y 10 counterfactuals | Audit score + log |
| 23 Sep | 2 | Congelar figuras y numeros | Gate de Week 3 |

**Recursos:** `ppo_agent.py`, `scripts/train_ppo.py`, `scheduling_env.py`,
`baselines.py`, `experiments.py`, `uncertainty.py`, `results/`, `models/` y
`config/orchestra_config.json`.

**Resumen:** esta semana prueba si la arquitectura completa aporta valor
frente a politicas simples y versiones sin un componente. Cada decision debe
reconstruirse desde una traza, y los resultados deben reportar media y 95% CI.

**Nota de estado:** el ODS marca Week 3 como posible retraso. Si ocurre, se
protegen E2, E4, E5, E6, E9 y reproducibilidad; se recorta primero E7 o la
comparacion con algoritmos adicionales.

## Semana 4: Paper and archive

**Fechas:** 24-30 Sep | **Carga:** 40 h

| Fecha | Horas | Actividad | Resultado esperado |
| --- | ---: | --- | --- |
| 24 Sep | 8 | Introduccion, related work y contributions; revisar template | Secciones 1-2 |
| 25 Sep | 8 | Framework y methodology; reproducir tablas | Secciones 3-4 |
| 26 Sep | 8 | Experiments, results y validation discussion; reunir figuras | Secciones 5-6 |
| 27 Sep | 6 | Conclusion, limitaciones, future work y proofread | Draft de 8-10 paginas |
| 28 Sep | 6 | Paquete reproducible con generator, scripts, configs, logs y dependencias | Zip ejecutable desde checkout limpio |
| 29 Sep | 2 | Pre-review del advisor; resolver comentarios bloqueantes | Notas archivadas |
| 30 Sep | 2 | Revisión final, idioma, commit y tag | `v1.0-submission-ready` |

**Recursos:** `05_Publications/Conference_Paper/Conference_Paper_Workspace/`,
`05_Publications/Journal_Paper/ORCHESTRA-Laser-Welding/`,
`05_Publications/Journal_Paper/99_Archived_Previous_Structure/`.

**Resumen:** escribir únicamente claims respaldados por E1-E9, congelar las
tablas desde `results/` y entregar código/configuracion suficiente para que
otra persona ejecute el experimento desde cero.

## Matriz minima de evidencia

| ID | Experimento | Semana | Evidencia requerida |
| --- | --- | --- | --- |
| E1 | Validez de simulacion | W1 | Separacion normal/degradacion/OOD y plausibilidad fisica |
| E2 | Urgencia XGBoost | W2 | CV, MAE/RMSE/R2, SHAP y comparacion de modelos |
| E3 | Calibracion de incertidumbre | W2 | ECE, cobertura y relacion error-incertidumbre |
| E4 | Review routing | W2 | Seguridad y carga frente a presupuesto igual |
| E5 | Full vs baselines | W3 | Reward, downtime, coste, audit y review coverage |
| E6 | Ablaciones | W3 | Aporte medible de review, PPO, XGBoost, provenance y trigger |
| E7 | Sensibilidad | W3 | Degradacion ante ruido, missing data, drift, OOD, recursos y delay |
| E8 | Auditabilidad | W3 | 100% de trazas completas + 10 counterfactuals |
| E9 | Validez estadistica | W3 | >=5 semillas, media, 95% CI y paired bootstrap/Wilcoxon |

## Entregables `.ipynb`

Sí, los entregables de análisis pueden hacerse en notebooks, pero no conviene
convertir todo el sistema en un notebook. La división recomendada es:

| Notebook | Contenido | Semana |
| --- | --- | --- |
| `01_simulation_validation.ipynb` | Dataset, splits, plausibilidad y 3 graficas | W1 |
| `02_prediction_and_calibration.ipynb` | XGBoost, CV, SHAP, incertidumbre y review sweep | W2 |
| `03_scheduling_and_ablation.ipynb` | PPO, baselines, ablaciones y sensibilidad | W3 |
| `04_final_results.ipynb` | Carga de resultados congelados, tablas y figuras del paper | W4 |

Ubicacion sugerida:
`05_Publications/Journal_Paper/ORCHESTRA-Laser-Welding/notebooks/`.

Los notebooks deben llamar funciones de `src/orchestra_laser`, no duplicar la
logica. Para reproducibilidad, usar kernel/entorno definido por
`requirements.txt`, semilla explícita, rutas relativas al proyecto y una celda
inicial que imprima versiones/configuracion. Los entrenamientos largos, PPO,
tests y generacion oficial de resultados deben seguir siendo scripts ejecutables
por terminal; el notebook debe servir como evidencia exploratoria y narrativa.

## Checklist de cierre

- [ ] E1-E9 tienen estado, resultado y ruta de evidencia.
- [ ] Todas las cifras usan al menos 5 semillas y 95% CI cuando aplica.
- [ ] Cada decision tiene audit trace reconstruible.
- [ ] El mismo presupuesto se usa al comparar estrategias de review.
- [ ] El paper solo afirma validacion por simulacion.
- [ ] Codigo, comentarios y paper estan en ingles.
- [ ] Un checkout limpio puede instalar dependencias y ejecutar el pipeline.
- [ ] Configuracion, logs, tablas, figuras y notebooks estan incluidos.