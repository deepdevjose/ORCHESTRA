# ORCHESTRA: simulacion hibrida en Windows

Este stack ejecuta un broker Mosquitto reproducible y conecta tres fuentes:

- **Robot 1**: el ESP32 publica `orchestra/laser-welding/esp32-wroom32-laser-01/telemetry`.
- **Robots 2-10**: el gateway Next.js genera datos sinteticos deterministas cuando MQTT esta configurado.
- **Model Observatory**: permite seleccionar cualquier robot. Robot 1 es el seleccionado por defecto y su fuente aparece como `MQTT`.

El escenario enviado desde el panel de Operations solo se habilita para Robot 1. El ESP32 lo aplica a sus siguientes tramas: `normal`, `low_shielding_gas`, `lens_contamination`, `focal_offset`, `fixture_vibration` o `high_laser_power`.

Los robots sinteticos mantienen memoria de salud y simulan una fabrica: trabajan shifts de 1.000 a 1.000.000 de piezas, acumulan degradacion segun carga y salud, y los robots que empiezan mal empeoran mas rapido. El dashboard ordena las maquinas por urgencia y muestra un limite de piezas, una frecuencia de reevaluacion y una accion propuesta. El mantenimiento aprobado reinicia la salud y aplica un periodo corto de recuperacion.

## Arranque completo despues de apagar la laptop

Usa este orden despues de encender Windows. Solo necesitas volver a cargar el firmware si cambiaste el codigo o la IP del broker.

1. Enciende la laptop y conectala a `Jose's Network`.
2. Conecta el ESP32 por USB y espera a que Windows lo reconozca.
3. Abre Docker Desktop y espera a que Docker Engine este ejecutandose.
4. Abre tres ventanas de PowerShell en la raiz del repositorio.
5. En la primera ventana ejecuta `ipconfig` y anota la IPv4 del adaptador conectado a `Jose's Network`.
6. Si la IP cambio, actualiza `src/firmware/include/config.local.h` y vuelve a cargar el firmware. El ESP32 debe apuntar a la IP del PC, no a `127.0.0.1`.
7. En la primera ventana inicia Mosquitto:

```powershell
cd simulation
docker compose up -d
docker compose ps
```

8. En la segunda ventana observa el broker:

```powershell
docker exec orchestra-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t "orchestra/#" -v
```

9. En la tercera ventana inicia el dashboard y el servicio de inferencia:

```powershell
cd src\ui
npm run dev:stack
```

10. Abre `http://localhost:3000` y espera a que Robot 1 aparezca como `MQTT`; los robots 2-10 apareceran como `SIM`.
11. Si cambiaste el firmware o la IP, carga y monitoriza el ESP32:

```powershell
cd src\firmware
pio run --target upload
pio device monitor
```

12. Confirma en la ventana del broker una conexion de `esp32-wroom32-laser-01` y mensajes en `.../telemetry`. En Model Observatory, Robot 1 debe mostrar `MQTT`.

El slider `Failure horizon` controla la velocidad de fallo de los robots sinteticos. No modifica el ritmo del ESP32.

## 1. Requisitos

Instala en Windows:

1. Docker Desktop con Docker Compose habilitado.
2. Node.js LTS.
3. VS Code y la extension PlatformIO.
4. PlatformIO Core o PlatformIO integrado en VS Code.
5. Un ESP32-WROOM-32 y un punto de acceso Wi-Fi aislado para el laboratorio.

El PC, el ESP32 y el navegador deben poder verse dentro de la misma red local. No expongas este broker a Internet.

## 2. Obtener la IP del PC

Abre PowerShell y ejecuta:

```powershell
ipconfig
```

Anota la direccion IPv4 del adaptador que comparte red con el ESP32. Por ejemplo, `192.168.4.2`. No uses `127.0.0.1` en el firmware: esa direccion significa el propio ESP32.

## 3. Iniciar Mosquitto

Desde la raiz del repositorio:

```powershell
cd simulation
docker compose up -d

docker compose ps
```

La configuracion esta en `simulation/mosquitto/mosquitto.conf`. El listener de desarrollo usa el puerto TCP `1883` y permite conexiones anonimas solo para una red de laboratorio aislada.

Si Windows Firewall pregunta, permite el puerto TCP 1883 en la red privada. Para abrirlo manualmente en PowerShell como administrador:

```powershell
New-NetFirewallRule -DisplayName "ORCHESTRA Mosquitto 1883" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow -Profile Private
```

Prueba el broker desde otro PowerShell:

```powershell
docker exec orchestra-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t "orchestra/#" -v
```

Deja esa ventana abierta para observar mensajes.

## 4. Configurar el dashboard

Copia el ejemplo y edita las variables solo la primera vez. Si `.env.local` ya existe, conservalo:

```powershell
cd src\ui
Copy-Item .env.example .env.local
```

`.env.local` debe contener al menos:

```env
MQTT_BROKER_URL=mqtt://127.0.0.1:1883
MQTT_TOPIC=orchestra/laser-welding/+/telemetry
MQTT_COMMAND_TOPIC=orchestra/laser-welding/{device_id}/command
ORCHESTRA_LIVE_DEVICE_ID=esp32-wroom32-laser-01
ORCHESTRA_STATION_ID=CN-SUZHOU-LW-01
ORCHESTRA_MODEL_URL=http://127.0.0.1:8787/score
```

Instala dependencias y arranca el gateway junto al servicio de inferencia:

```powershell
npm install
npm run dev:stack
```

Abre `http://localhost:3000`. Antes de conectar el ESP32, los robots 2-10 apareceran como `SIM`; Robot 1 quedara esperando su primera trama MQTT.

No ejecutes `Copy-Item` sobre un `.env.local` existente sin confirmar, porque reemplazaria tu configuracion local.

## 5. Configurar y cargar el ESP32

Copia `src/firmware/include/config.example.h` a `src/firmware/include/config.local.h` solo la primera vez y edita:

```cpp
#define WIFI_SSID "NOMBRE_DE_TU_WIFI"
#define WIFI_PASSWORD "TU_PASSWORD"
#define MQTT_BROKER_HOST "IP_ACTUAL_DE_LA_LAPTOP"
#define MQTT_DEVICE_ID "esp32-wroom32-laser-01"
#define MQTT_STATION_ID "CN-SUZHOU-LW-01"
#define USE_SIMULATED_SENSORS true
```

`USE_SIMULATED_SENSORS true` permite validar el transporte MQTT antes de conectar sensores reales. El ESP32 sigue siendo la fuente de Robot 1; no es la simulacion local del dashboard.

En la terminal de PlatformIO:

```powershell
cd src\firmware
pio run
pio run --target upload
pio device monitor
```

En el monitor serie debes ver la conexion Wi-Fi, la conexion MQTT y publicaciones cada 2.5 segundos. En la ventana `mosquitto_sub` apareceran las tramas de Robot 1.

El archivo `config.local.h` esta ignorado por Git. No lo reemplaces despues de cada reinicio: actualiza `MQTT_BROKER_HOST` solo cuando `ipconfig` muestre una IP diferente.

## 6. Probar comandos de escenario

En el dashboard:

1. Abre Operations.
2. Selecciona `Cell 01`.
3. En `ESP32 scenario command`, elige un escenario.
4. Pulsa `Publish`.
5. Observa el cambio de `scenario`, urgencia y sensores en la siguiente trama.

El firmware tambien acepta acciones de mantenimiento del panel y publica su confirmacion en el topic `.../status`. Estos comandos son demostrativos y no tienen autoridad de seguridad.

Para probar manualmente desde Docker:

```powershell
docker exec orchestra-mosquitto mosquitto_pub -h 127.0.0.1 -p 1883 `
  -t orchestra/laser-welding/esp32-wroom32-laser-01/command `
  -m '{"command":"set_scenario","scenario":"focal_offset"}'
```

## 7. Model Observatory

Abre `http://localhost:3000/models`. El selector `Robot` permite inspeccionar Robot 1 o cualquiera de los nueve robots sinteticos. La grafica y los eventos se filtran por el robot seleccionado; la matriz inferior conserva la comparacion de toda la flota.

## 8. Apagar y reiniciar

Antes de apagar la laptop, detiene el dashboard con `Ctrl+C` en la ventana de `npm run dev:stack` y detiene Mosquitto:

```powershell
cd simulation
docker compose down
```

Despues apaga Windows normalmente. Al siguiente encendido repite la seccion **Arranque completo despues de apagar la laptop**.

No es necesario borrar Docker ni ejecutar `npm install` en cada arranque. `npm install` solo se necesita despues de clonar el proyecto o cambiar las dependencias.

## 9. Solucion de problemas

### Robot 1 no aparece como MQTT

Comprueba que el broker este activo, que `MQTT_BROKER_HOST` coincida con la IPv4 actual y que Windows Firewall permita TCP `1883` en la red privada. El ESP32 debe estar conectado a la misma red Wi-Fi que la laptop.

### Error `ENOENT` o `Cannot find module` dentro de `.next`

Deten el proceso de Next.js con `Ctrl+C`, limpia el bundle temporal y vuelve a iniciar:

```powershell
cd src\ui
Remove-Item -Recurse -Force .next
npm run dev:stack
```

### El puerto 3000 esta ocupado

Deten la instancia anterior de Next.js o usa el puerto que indique la terminal. El navegador debe abrir la URL que imprime Next.js, por ejemplo `http://localhost:3001`.

### El ESP32 conecta a Wi-Fi pero no publica telemetria

Abre `pio device monitor`, confirma que el broker acepta la conexion y verifica que el firmware tenga `mqttClient.setBufferSize(1400)`. La trama completa de ORCHESTRA supera el buffer MQTT por defecto de PubSubClient.

## 10. Detener y limpiar

Para ver logs del broker:

```powershell
docker logs -f orchestra-mosquitto
```
