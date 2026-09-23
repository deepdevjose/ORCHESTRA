# ORCHESTRA: simulacion hibrida en Fedora

Esta guia ejecuta el mismo stack hibrido que Windows: Robot 1 llega desde el ESP32 por MQTT y los robots 2-10 permanecen sinteticos en el gateway Next.js. El dashboard permite seleccionar cualquier robot en Model Observatory y enviar escenarios al Robot 1.

Los robots sinteticos mantienen memoria de salud y simulan una fabrica: trabajan shifts de 1.000 a 1.000.000 de piezas, acumulan degradacion segun carga y salud, y los robots que empiezan mal empeoran mas rapido. El dashboard ordena las maquinas por urgencia y muestra un limite de piezas, una frecuencia de reevaluacion y una accion propuesta. El mantenimiento aprobado reinicia la salud y aplica un periodo corto de recuperacion.

## Arranque diario despues de apagar la laptop

1. Conecta Fedora a `Jose's Network`.
2. Conecta el ESP32 por USB y comprueba que aparece como `/dev/ttyUSB0`.
3. Obtiene la IP actual de la laptop:

```bash
ip -4 -o addr show scope global
```

Usa la IPv4 de `wlp...` conectada a `Jose's Network`. Si cambio, actualiza `MQTT_BROKER_HOST` en `src/firmware/include/config.local.h` y vuelve a cargar el firmware. No uses `127.0.0.1` en el ESP32.

4. En una terminal inicia Mosquitto nativo:

```bash
cd simulation
mosquitto -c mosquitto/mosquitto.conf -v
```

5. En otra terminal observa los mensajes:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'orchestra/#' -v
```

6. En otra terminal inicia el dashboard:

```bash
cd src/ui
npm run dev:stack
```

7. Abre `http://localhost:3000`. Robot 1 debe aparecer como `MQTT` y los robots 2-10 como `SIM`.

No necesitas ejecutar `npm install` ni volver a cargar el ESP32 en cada arranque. Solo ejecuta `npm install` despues de clonar o cambiar dependencias, y `pio run --target upload` despues de cambiar firmware o la IP del broker.

## 1. Requisitos

Necesitas Fedora actualizado, Node.js LTS, Git, Docker, Docker Compose, VS Code con PlatformIO, un ESP32-WROOM-32 y una red Wi-Fi de laboratorio. El PC y el ESP32 deben estar en la misma red privada.

```bash
sudo dnf upgrade --refresh
sudo dnf install -y git curl python3 python3-pip docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Si el paquete Docker no existe en tu instalacion, agrega primero el repositorio oficial de Docker siguiendo la documentacion de Docker para Fedora. Como alternativa, usa Podman con `podman-compose` y adapta los comandos `docker compose` a `podman compose`.

Activa Docker y permite al usuario actual usarlo sin `sudo`:

```bash
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Cierra la sesion y vuelve a entrar para que el grupo tenga efecto. Comprueba:

```bash
docker --version
docker compose version
node --version
```

## 2. Obtener la IP del PC

```bash
ip -4 addr
```

Usa la IPv4 de la interfaz `wlp...` conectada a la misma red del ESP32, por ejemplo `10.80.65.66`. No uses `127.0.0.1` en el firmware.

## 3. Abrir el broker en firewalld

El broker de desarrollo escucha en TCP `1883` y solo debe exponerse en una red de laboratorio:

```bash
sudo firewall-cmd --permanent --add-port=1883/tcp
sudo firewall-cmd --reload
sudo firewall-cmd --list-ports
```

La configuracion de Mosquitto esta en `simulation/mosquitto/mosquitto.conf`. Usa autenticacion, ACL y TLS antes de usarlo fuera de una red aislada.

## 4. Iniciar Mosquitto

Desde la raiz del repositorio:

La forma recomendada para tu Fedora es Mosquitto nativo:

```bash
cd simulation
mosquitto -c mosquitto/mosquitto.conf -v
```

En otra terminal observa las tramas:

```bash
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'orchestra/#' -v
```

## 5. Configurar y ejecutar el dashboard

```bash
cd src/ui
cp .env.example .env.local
```

Ejecuta este `cp` solo la primera vez. Si `.env.local` ya existe, no lo reemplaces.

Verifica que `.env.local` contenga:

```env
MQTT_BROKER_URL=mqtt://127.0.0.1:1883
MQTT_TOPIC=orchestra/laser-welding/+/telemetry
MQTT_COMMAND_TOPIC=orchestra/laser-welding/{device_id}/command
ORCHESTRA_LIVE_DEVICE_ID=esp32-wroom32-laser-01
ORCHESTRA_STATION_ID=CN-SUZHOU-LW-01
ORCHESTRA_MODEL_URL=http://127.0.0.1:8787/score
```

Instala y arranca:

```bash
npm install
npm run dev:stack
```

Abre `http://localhost:3000`. Con MQTT configurado, Robot 1 queda reservado para el ESP32 y los robots 2-10 aparecen como `SIM`.

## 6. Configurar y cargar el ESP32

```bash
cp src/firmware/include/config.example.h src/firmware/include/config.local.h
```

Edita `src/firmware/include/config.local.h`:

```cpp
#define WIFI_SSID "NOMBRE_DE_TU_WIFI"
#define WIFI_PASSWORD "TU_PASSWORD"
#define MQTT_BROKER_HOST "IP_ACTUAL_DE_LA_LAPTOP"
#define MQTT_DEVICE_ID "esp32-wroom32-laser-01"
#define MQTT_STATION_ID "CN-SUZHOU-LW-01"
#define USE_SIMULATED_SENSORS true
```

Instala PlatformIO Core si no usas la extension de VS Code:

```bash
python3 -m pip install --user platformio
export PATH="$HOME/.local/bin:$PATH"
```

Compila, carga y abre el monitor serie:

```bash
cd src/firmware
pio run
pio run --target upload
pio device monitor
```

Si el ESP32 ya fue cargado y la IP no cambio, basta con abrir el monitor:

```bash
cd src/firmware
pio device monitor -p /dev/ttyUSB0 -b 115200
```

`USE_SIMULATED_SENSORS true` solo simula sensores dentro del ESP32 para probar el transporte. Robot 1 sigue siendo una fuente MQTT distinta de la simulacion local del dashboard.

## 7. Enviar escenarios

En Operations, selecciona `Cell 01`, elige un escenario en `ESP32 scenario command` y pulsa `Publish`. El ESP32 aplicara `normal`, `low_shielding_gas`, `lens_contamination`, `focal_offset`, `fixture_vibration` o `high_laser_power` en las siguientes tramas.

Prueba tambien desde la terminal:

```bash
docker exec orchestra-mosquitto mosquitto_pub -h 127.0.0.1 -p 1883 \
  -t 'orchestra/laser-welding/esp32-wroom32-laser-01/command' \
  -m '{"command":"set_scenario","scenario":"focal_offset"}'
```

En `http://localhost:3000/models`, el selector `Robot` filtra la grafica y los eventos del robot elegido.

## 8. Apagar y reiniciar

Antes de apagar Fedora:

1. Pulsa `Ctrl+C` en la terminal de `npm run dev:stack`.
2. Pulsa `Ctrl+C` en la terminal de Mosquitto.
3. Desconecta el ESP32 o deja el USB conectado para el siguiente arranque.

Despues de encender la laptop, vuelve a la seccion **Arranque diario despues de apagar la laptop**.

## 9. Solucion de problemas

### Error `.next/server/app/models/page.js` o `ENOENT`

Deten Next.js con `Ctrl+C`, limpia el bundle de desarrollo y vuelve a arrancar:

```bash
cd src/ui
rm -rf .next
npm run dev:stack
```

### Robot 1 aparece como `demo` en vez de `MQTT`

Comprueba que el dashboard fue iniciado desde `src/ui` y que existe `.env.local` con `MQTT_BROKER_URL=mqtt://127.0.0.1:1883`. Reinicia Next.js despues de crear o cambiar `.env.local`.

### El ESP32 conecta a Wi-Fi pero no publica

Comprueba que `MQTT_BROKER_HOST` coincide con la IPv4 actual de Fedora, que el puerto `1883` esta abierto en `firewalld` y que el monitor muestra `MQTT connected`.

## 10. Detener el stack

```bash
cd simulation
docker compose down
```

No guardes credenciales Wi-Fi en Git. Antes de conectar una red industrial real, configura autenticacion, ACL, TLS y segmentacion.
