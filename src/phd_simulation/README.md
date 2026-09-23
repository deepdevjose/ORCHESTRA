# Guía de reproducción de la simulación PhD de ORCHESTRA

Esta carpeta contiene el paquete reproducible de simulación del plan de
validación de cuatro semanas. La simulación es independiente del pipeline
heredado de Week 1 para que la evidencia del artículo pueda ejecutarse sin
modificar el notebook existente.

## Requisitos

- Python 3.10 o posterior.
- Git, para descargar el repositorio.
- Conexión a Internet durante la instalación de las dependencias.
- Aproximadamente 2 GB de espacio libre para dependencias y resultados.

No se necesita GPU. La ejecución completa puede tardar bastante más que la
prueba rápida, especialmente durante el entrenamiento de PPO.

## 1. Descargar el repositorio

En los tres sistemas, abra una terminal y clone el repositorio:

```bash
git clone <URL_DEL_REPOSITORIO>
cd ORCHESTRA
```

Si ya tiene el repositorio, solo debe abrir una terminal en la carpeta raíz
`ORCHESTRA`. Los comandos de esta guía deben ejecutarse desde esa carpeta, no
desde `src/phd_simulation`.

## 2. Preparar Python

### Fedora

```bash
sudo dnf install python3 python3-pip python3-devel git
python3 --version
python3 -m venv .venv-phd
source .venv-phd/bin/activate
python -m pip install --upgrade pip
python -m pip install -r src/phd_simulation/requirements.txt
```

### Ubuntu

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv git
python3 --version
python3 -m venv .venv-phd
source .venv-phd/bin/activate
python -m pip install --upgrade pip
python -m pip install -r src/phd_simulation/requirements.txt
```

Si Ubuntu no ofrece Python 3.10 o posterior mediante sus paquetes actuales,
instale una versión compatible antes de crear el entorno virtual.

### Windows PowerShell

Instale Python desde <https://www.python.org/downloads/windows/> y active la
opción **Add Python to PATH** durante la instalación. Después, en PowerShell:

```powershell
py --version
py -3 -m venv .venv-phd
.\.venv-phd\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r src\phd_simulation\requirements.txt
```

Si PowerShell bloquea la activación del entorno, ejecute PowerShell como
usuario y configure la política para su cuenta:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

También puede usar `cmd.exe` en lugar de PowerShell:

```bat
py -3 -m venv .venv-phd
.venv-phd\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r src\phd_simulation\requirements.txt
```

## 3. Comprobar la instalación

Con el entorno virtual activo, ejecute las pruebas unitarias pequeñas:

```bash
python -m pytest src/phd_simulation/test_smoke.py
```

En Windows puede usar exactamente el mismo comando desde PowerShell o
`cmd.exe`. El resultado esperado es que las tres pruebas terminen con estado


## 4. Ejecutar una prueba rápida

La prueba rápida valida el flujo completo con menos datos y sin entrenar PPO.
No debe usarse como evidencia final del artículo.

Fedora y Ubuntu:

```bash
python src/phd_simulation/run.py --quick --skip-ppo --output-dir results/phd_simulation_smoke
```

Windows PowerShell o `cmd.exe`:

```powershell
python src\phd_simulation\run.py --quick --skip-ppo --output-dir results\phd_simulation_smoke
```

La ejecución termina mostrando un JSON con `status: completed`. Los archivos
se escriben en `results/phd_simulation_smoke/`.

## 5. Reproducir la simulación completa

Ejecute la configuración predeterminada:

Fedora y Ubuntu:

```bash
python src/phd_simulation/run.py
```

Windows PowerShell o `cmd.exe`:

```powershell
python src\phd_simulation\run.py
```

La configuración usa cinco semillas de evaluación, 180 casos y 40 pasos por
episodio. PPO está habilitado por defecto. Para reproducir todos los análisis
excepto el entrenamiento PPO:

```bash
python src/phd_simulation/run.py --skip-ppo
```

En Windows, use la misma opción con barras invertidas en la ruta si utiliza
una ruta de configuración explícita:

```powershell
python src\phd_simulation\run.py --config src\phd_simulation\default_config.json
```

## 6. Revisar los resultados

La salida predeterminada se guarda en:

```text
results/phd_simulation/
```

La carpeta contiene, entre otros elementos:

- `manifest.json`: modo de ejecución, configuración y límites de las
	afirmaciones reproducibles.
- `resolved_config.json`: configuración efectiva de la corrida.
- `data/`: datos simulados generados.
- `figures/`: figuras producidas por los análisis.
- `tables/`: tablas CSV para inspección o uso en el artículo.
- `logs/`: resúmenes, trazas y comprobaciones de auditoría.
- `models/`: modelos guardados cuando corresponde.

Para ejecutar en otra carpeta, use `--output-dir`:

```bash
python src/phd_simulation/run.py --output-dir results/phd_simulation_repeticion
```

## 7. Configuración y reproducibilidad

La configuración base está en
`src/phd_simulation/default_config.json`. Se pueden modificar, por ejemplo,
las semillas, el número de casos, el ruido de sensores y los pasos de PPO.
Para conservar una corrida reproducible, guarde una copia de la configuración
usada junto con sus resultados y no cambie las semillas.

El paquete implementa un simulador sembrado de soldadura láser con trayectorias
normales, degradadas y OOD; separación por casos para evitar fuga temporal;
validación de modelos; calibración de incertidumbre; revisión humana; políticas
de mantenimiento; análisis de sensibilidad y ablación; intervalos de confianza;
pruebas pareadas; comprobaciones contrafactuales; y trazas de auditoría con
hash encadenado.

## Limitaciones

Toda la evidencia generada es únicamente de simulación. El simulador, el
revisor experto y los objetivos del proceso son supuestos diseñados, no
mediciones de hardware real ni un estudio real con operadores. Los resultados
no constituyen validación industrial, certificación de seguridad ni prueba de
despliegue en producción.

## Desactivar el entorno virtual

Cuando termine:

```bash
deactivate
```

En la siguiente sesión, vuelva a la raíz del repositorio y active el entorno
con `source .venv-phd/bin/activate` en Fedora/Ubuntu o
`.\.venv-phd\Scripts\Activate.ps1` en PowerShell antes de ejecutar la
simulación.
