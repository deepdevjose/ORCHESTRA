#include <Arduino.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <time.h>

#include "config.h"

namespace {

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
unsigned long lastTelemetryAt = 0;
unsigned long sequenceNumber = 0;
bool commandSubscriptionReady = false;
String operationalState = "production";
String requestedScenario = "normal";

void connectToWifi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.printf("Connecting to Wi-Fi: %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setHostname(MQTT_DEVICE_ID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startedAt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startedAt < 20000UL) {
    delay(400);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWi-Fi connected. IP: %s\n", WiFi.localIP().toString().c_str());
    configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  } else {
    Serial.println("\nWi-Fi connection timed out; retrying from loop().");
  }
}

String isoTimestamp() {
  time_t now = time(nullptr);
  if (now < 100000) return String("1970-01-01T00:00:00.000Z");

  struct tm utcTime;
  gmtime_r(&now, &utcTime);
  char timestamp[25];
  strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%S.000Z", &utcTime);
  return String(timestamp);
}

float simulatedWave(float base, float amplitude, float frequency, float phase) {
  return base + sinf(phase * frequency) * amplitude;
}

float analogValue(uint8_t pin, float minimum, float maximum) {
  const int raw = analogRead(pin);
  return minimum + (static_cast<float>(raw) / 4095.0f) * (maximum - minimum);
}

void readTelemetry(float &laserPower, float &weldingSpeed, float &focalError,
                   float &shieldingGas, float &meltPoolTemp, float &backReflection,
                   float &plumeIntensity, float &spatterCount, float &vibration,
                   float &robotPathError, float &beadWidth, float &beadHeight,
                   float &porosityRisk, float &visualDefect, float &lensContamination,
                   float &coolingAlarm, float &hoursSinceCleaning) {
  const float phase = static_cast<float>(sequenceNumber) * 0.32f;

  if (USE_SIMULATED_SENSORS) {
    const float drift = fmodf(static_cast<float>(sequenceNumber), 24.0f) / 24.0f;
    const bool highLaserPower = requestedScenario == "high_laser_power";
    const bool lowGas = requestedScenario == "low_shielding_gas";
    const bool focalOffset = requestedScenario == "focal_offset";
    const bool vibrationScenario = requestedScenario == "fixture_vibration";
    const bool lensScenario = requestedScenario == "lens_contamination";
    laserPower = simulatedWave(1800.0f + 120.0f * drift + (highLaserPower ? 280.0f : 0.0f), 45.0f, 0.6f, phase);
    weldingSpeed = simulatedWave(35.0f, 1.7f, 0.45f, phase);
    focalError = 0.08f + fabsf(sinf(phase * 0.55f)) * 0.04f + (focalOffset ? 0.28f : 0.0f);
    shieldingGas = simulatedWave(18.0f - (lowGas ? 6.0f : 0.0f), 0.6f, 0.3f, phase);
    meltPoolTemp = simulatedWave(1450.0f + 90.0f * drift + (highLaserPower ? 150.0f : 0.0f), 48.0f, 0.35f, phase);
    backReflection = simulatedWave(0.34f + 0.08f * drift + (lensScenario ? 0.24f : 0.0f), 0.035f, 0.42f, phase);
    plumeIntensity = simulatedWave(0.45f + 0.04f * drift + (lensScenario ? 0.13f : 0.0f), 0.04f, 0.37f, phase);
    spatterCount = 3.0f + fmaxf(0.0f, roundf(sinf(phase * 0.7f) * 2.0f)) + (highLaserPower ? 5.0f : 0.0f);
    vibration = 0.08f + fabsf(sinf(phase * 0.52f)) * 0.018f + (vibrationScenario ? 0.19f : 0.0f);
    robotPathError = 0.05f + fabsf(sinf(phase * 0.41f)) * 0.015f + (vibrationScenario ? 0.13f : 0.0f);
    beadWidth = simulatedWave(2.0f + (focalOffset ? 0.18f : 0.0f), 0.06f, 0.5f, phase);
    beadHeight = simulatedWave(0.62f, 0.025f, 0.33f, phase);
    porosityRisk = 0.12f + fabsf(sinf(phase * 0.28f)) * 0.025f + (lowGas ? 0.35f : 0.0f);
    visualDefect = 8.0f + fmaxf(0.0f, sinf(phase * 0.27f) * 3.0f) + (focalOffset ? 18.0f : 0.0f);
    lensContamination = 0.12f + fabsf(sinf(phase * 0.24f)) * 0.025f + (lensScenario ? 0.42f : 0.0f);
    coolingAlarm = (sequenceNumber % 17UL == 0UL) ? 1.0f : 0.0f;
    hoursSinceCleaning = 24.0f + static_cast<float>(sequenceNumber % 12UL) * 1.7f;
    return;
  }

  // Generic ESP32-WROOM-32 calibration points for the first wired prototype.
  // Replace these pins/ranges with the actual sensor interface before deployment.
  laserPower = analogValue(34, 0.0f, 2500.0f);
  weldingSpeed = analogValue(35, 0.0f, 80.0f);
  focalError = analogValue(32, 0.0f, 1.0f);
  shieldingGas = analogValue(33, 0.0f, 30.0f);
  meltPoolTemp = analogValue(36, 0.0f, 2200.0f);
  backReflection = 0.34f;
  plumeIntensity = 0.45f;
  spatterCount = 0.0f;
  vibration = 0.08f;
  robotPathError = 0.05f;
  beadWidth = 2.0f;
  beadHeight = 0.62f;
  porosityRisk = 0.12f;
  visualDefect = 0.0f;
  lensContamination = 0.12f;
  coolingAlarm = digitalRead(27) == HIGH ? 1.0f : 0.0f;
  hoursSinceCleaning = 24.0f;
}

String telemetryJson() {
  float laserPower, weldingSpeed, focalError, shieldingGas, meltPoolTemp;
  float backReflection, plumeIntensity, spatterCount, vibration, robotPathError;
  float beadWidth, beadHeight, porosityRisk, visualDefect, lensContamination;
  float coolingAlarm, hoursSinceCleaning;
  readTelemetry(laserPower, weldingSpeed, focalError, shieldingGas, meltPoolTemp,
               backReflection, plumeIntensity, spatterCount, vibration, robotPathError,
               beadWidth, beadHeight, porosityRisk, visualDefect, lensContamination,
               coolingAlarm, hoursSinceCleaning);

  String payload;
  payload.reserve(900);
  payload += "{\"device_id\":\"" + String(MQTT_DEVICE_ID) + "\"";
  payload += ",\"station_id\":\"" + String(MQTT_STATION_ID) + "\"";
  payload += ",\"timestamp\":\"" + isoTimestamp() + "\"";
  payload += ",\"sequence\":" + String(sequenceNumber);
  payload += ",\"payload_version\":\"orchestra.telemetry.v1\"";
  payload += ",\"machine_name\":\"" + String(MACHINE_NAME) + "\"";
  payload += ",\"location\":\"" + String(MACHINE_LOCATION) + "\"";
  payload += ",\"line\":\"" + String(MACHINE_LINE) + "\"";
  payload += ",\"asset\":\"" + String(MACHINE_ASSET) + "\"";
  payload += ",\"source\":\"" + String(USE_SIMULATED_SENSORS ? "esp32_simulated" : "esp32_live_sensor") + "\"";
  payload += ",\"scenario\":\"" + (USE_SIMULATED_SENSORS ? requestedScenario : String("live_sensor")) + "\"";
  payload += ",\"operational_state\":\"" + operationalState + "\"";
  payload += ",\"wifi_rssi_dbm\":" + String(WiFi.RSSI());
  payload += ",\"signal_quality\":" + String(USE_SIMULATED_SENSORS ? 0.98f : 0.75f, 2);
  payload += ",\"laser_power_w\":" + String(laserPower, 2);
  payload += ",\"welding_speed_mm_s\":" + String(weldingSpeed, 3);
  payload += ",\"focal_position_error_mm\":" + String(focalError, 4);
  payload += ",\"shielding_gas_flow_l_min\":" + String(shieldingGas, 3);
  payload += ",\"melt_pool_temp_c\":" + String(meltPoolTemp, 2);
  payload += ",\"back_reflection_intensity\":" + String(backReflection, 4);
  payload += ",\"plume_intensity\":" + String(plumeIntensity, 4);
  payload += ",\"spatter_count\":" + String(spatterCount, 0);
  payload += ",\"vibration_rms\":" + String(vibration, 4);
  payload += ",\"robot_path_error_mm\":" + String(robotPathError, 4);
  payload += ",\"bead_width_mm\":" + String(beadWidth, 4);
  payload += ",\"bead_height_mm\":" + String(beadHeight, 4);
  payload += ",\"porosity_risk\":" + String(porosityRisk, 4);
  payload += ",\"visual_defect_score\":" + String(visualDefect, 2);
  payload += ",\"lens_contamination_level\":" + String(lensContamination, 4);
  payload += ",\"cooling_system_alarm\":" + String(coolingAlarm, 0);
  payload += ",\"time_since_lens_cleaning_h\":" + String(hoursSinceCleaning, 2);
  payload += "}";
  return payload;
}

String jsonStringField(const String &json, const char *field) {
  const String key = String("\"") + field + "\"";
  const int keyIndex = json.indexOf(key);
  if (keyIndex < 0) return String();
  const int colonIndex = json.indexOf(':', keyIndex + key.length());
  if (colonIndex < 0) return String();
  const int firstQuote = json.indexOf('"', colonIndex + 1);
  if (firstQuote < 0) return String();
  const int secondQuote = json.indexOf('"', firstQuote + 1);
  if (secondQuote < 0) return String();
  return json.substring(firstQuote + 1, secondQuote);
}

bool applyCommand(const String &action) {
  if (action == "inspect") operationalState = "inspection";
  else if (action == "hold_production" || action == "schedule_major_maintenance") operationalState = "maintenance_hold";
  else if (action == "schedule_minor_maintenance") operationalState = "maintenance_planned";
  else if (action == "urgent_intervention") operationalState = "stopped";
  else if (action == "resume_production") operationalState = "production";
  else if (action == "acknowledge") return true;
  else return false;
  return true;
}

void mqttMessageReceived(char *topic, byte *message, unsigned int length) {
  String command;
  command.reserve(length + 1);
  for (unsigned int index = 0; index < length; index++) command += static_cast<char>(message[index]);

  const String action = jsonStringField(command, "action");
  const String scenario = jsonStringField(command, "scenario");
  if (jsonStringField(command, "command") == "set_scenario" && scenario.length() > 0) {
    requestedScenario = scenario;
    Serial.printf("Scenario changed to %s\n", requestedScenario.c_str());
    String acknowledgement = "{\"device_id\":\"" + String(MQTT_DEVICE_ID) +
                             "\",\"status\":\"accepted\",\"scenario\":\"" + requestedScenario +
                             "\",\"payload_version\":\"orchestra.command_ack.v1\"}";
    mqttClient.publish(MQTT_STATUS_TOPIC, acknowledgement.c_str(), false);
    return;
  }
  const bool accepted = applyCommand(action);
  Serial.printf("MQTT command on %s: %s (%s)\n", topic, action.c_str(), accepted ? "accepted" : "rejected");
  String acknowledgement = "{\"device_id\":\"" + String(MQTT_DEVICE_ID) +
                           "\",\"status\":\"" + String(accepted ? "accepted" : "rejected") +
                           "\",\"action\":\"" + action +
                           "\",\"operational_state\":\"" + operationalState +
                           "\",\"payload_version\":\"orchestra.command_ack.v1\"}";
  mqttClient.publish(MQTT_STATUS_TOPIC, acknowledgement.c_str(), false);
}

void connectToMqtt() {
  if (WiFi.status() != WL_CONNECTED || mqttClient.connected()) return;

  String clientId = String(MQTT_DEVICE_ID) + "-" + String(static_cast<uint32_t>(ESP.getEfuseMac()), HEX);
  Serial.printf("Connecting to MQTT broker %s:%u ...\n", MQTT_BROKER_HOST, MQTT_BROKER_PORT);

  if (mqttClient.connect(clientId.c_str(), MQTT_STATUS_TOPIC, 0, true,
                         "{\"status\":\"offline\"}")) {
    Serial.println("MQTT connected.");
    commandSubscriptionReady = mqttClient.subscribe(MQTT_COMMAND_TOPIC, 1);
    Serial.printf("Subscribed to %s: %s\n", MQTT_COMMAND_TOPIC, commandSubscriptionReady ? "yes" : "no");
    String online = "{\"device_id\":\"" + String(MQTT_DEVICE_ID) +
                    "\",\"status\":\"online\",\"ip\":\"" + WiFi.localIP().toString() + "\"}";
    mqttClient.publish(MQTT_STATUS_TOPIC, online.c_str(), true);
  } else {
    Serial.printf("MQTT connection failed, state=%d\n", mqttClient.state());
  }
}

void publishTelemetry() {
  if (!mqttClient.connected()) return;
  sequenceNumber++;
  const String payload = telemetryJson();
  if (mqttClient.publish(MQTT_TELEMETRY_TOPIC, payload.c_str(), false)) {
    Serial.printf("Published telemetry #%lu (%u bytes)\n", sequenceNumber, payload.length());
  } else {
    Serial.println("Telemetry publish failed.");
  }
}

}  // namespace

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nORCHESTRA ESP32-WROOM-32 telemetry node");

  analogReadResolution(12);
  pinMode(27, INPUT_PULLDOWN);
  mqttClient.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  mqttClient.setCallback(mqttMessageReceived);
  connectToWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectToWifi();
  if (!mqttClient.connected()) connectToMqtt();
  mqttClient.loop();

  if (millis() - lastTelemetryAt >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryAt = millis();
    publishTelemetry();
  }
  delay(10);
}
