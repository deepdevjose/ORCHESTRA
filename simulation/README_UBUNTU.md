# ORCHESTRA: simulacion hibrida en Ubuntu

Esta guia ejecuta el stack hibrido de ORCHESTRA: Robot 1 llega desde el ESP32 por MQTT y los robots 2-10 permanecen sinteticos en el gateway Next.js. Model Observatory permite seleccionar cualquier robot y Operations permite enviar escenarios al Robot 1.

Los robots sinteticos mantienen memoria de salud y simulan una fabrica: trabajan shifts de 1.000 a 1.000.000 de piezas, acumulan degradacion segun carga y salud, y los robots que empiezan mal empeoran mas rapido. El dashboard ordena las maquinas por urgencia y muestra un limite de piezas, una frecuencia de reevaluacion y una accion propuesta. El mantenimiento aprobado reinicia la salud y aplica un periodo corto de recuperacion.

## 1. Requisitos

Necesitas Ubuntu actualizado, Node.js LTS, Git, Docker Engine, Docker Compose, VS Code con PlatformIO, un ESP32-WROOM-32 y una red Wi-Fi de laboratorio. El PC y el ESP32 deben estar en la misma red privada.

```bash
sudo apt update
sudo apt install -y git curl python3 python3-pip docker.io docker-compose-plugin
```

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

Instala Node.js LTS si `node --version` no existe. Puedes usar NodeSource, `nvm` o el gestor de paquetes aprobado por tu entorno.

## 2. Obtener la IP del PC

```bash
ip -4 addr
```

Usa la IPv4 de la interfaz conectada a la misma red del ESP32, por ejemplo `192.168.4.2`. No uses `127.0.0.1` en el firmware.

## 3. Abrir el broker en UFW

El broker de desarrollo escucha en TCP `1883` y solo debe exponerse en una red de laboratorio:

```bash
sudo ufw allow 1883/tcp
sudo ufw status
```

Si UFW esta inactivo y tu politica de laboratorio lo permite:

```bash
sudo ufw enable
```

La configuracion de Mosquitto esta en `simulation/mosquitto/mosquitto.conf`. Usa autenticacion, ACL y TLS antes de usarlo fuera de una red aislada.

## 4. Iniciar Mosquitto

Desde la raiz del repositorio:

```bash
cd simulation
docker compose up -d
docker compose ps
docker exec orchestra-mosquitto mosquitto_sub -h 127.0.0.1 -p 1883 -t 'orchestra/#' -v
```

Deja la suscripcion abierta para observar las tramas. La segunda orden puede ejecutarse en otra terminal.

## 5. Configurar y ejecutar el dashboard

```bash
cd src/ui
cp .env.example .env.local
```

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

Edita `src/firmware/include/config.h`:

```cpp
#define WIFI_SSID "NOMBRE_DE_TU_WIFI"
#define WIFI_PASSWORD "TU_PASSWORD"
#define MQTT_BROKER_HOST "192.168.4.2"
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

## 8. Detener el stack

```bash
cd simulation
docker compose down
```

No guardes credenciales Wi-Fi en Git. Antes de conectar una red industrial real, configura autenticacion, ACL, TLS y segmentacion.
