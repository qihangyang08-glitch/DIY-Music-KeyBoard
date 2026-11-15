#include "ota.h"

#include <Arduino.h>

#ifdef KEYBORAD_ENABLE_OTA

#include <ArduinoOTA.h>
#include <WiFi.h>

#ifndef KEYBORAD_WIFI_SSID
#error "KEYBORAD_ENABLE_OTA needs KEYBORAD_WIFI_SSID and KEYBORAD_WIFI_PASS"
#endif
#ifndef KEYBORAD_WIFI_PASS
#define KEYBORAD_WIFI_PASS ""
#endif

static const uint32_t RECONNECT_MS = 10000;

static bool begun = false;
static uint32_t lastAttempt = 0;

void otaSetup() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(KEYBORAD_WIFI_SSID, KEYBORAD_WIFI_PASS);
  Serial.printf("OTA: joining Wi-Fi \"%s\"\n", KEYBORAD_WIFI_SSID);
}

void otaLoop() {
  const uint32_t now = millis();
  if (WiFi.status() != WL_CONNECTED) {
    if (now - lastAttempt >= RECONNECT_MS) {
      lastAttempt = now;
      WiFi.reconnect();
    }
    return;
  }
  if (!begun) {
    ArduinoOTA.setHostname("keyborad");
    ArduinoOTA.onStart([]() { Serial.println(F("OTA: update starting")); });
    ArduinoOTA.onEnd([]() { Serial.println(F("\nOTA: update finished")); });
    ArduinoOTA.onError([](ota_error_t error) {
      Serial.printf("OTA error %u\n", (unsigned)error);
    });
    ArduinoOTA.begin();
    begun = true;
    Serial.printf("OTA ready at %s\n", WiFi.localIP().toString().c_str());
  }
  ArduinoOTA.handle();
}

bool otaEnabled() { return true; }

#else

void otaSetup() {}
void otaLoop() {}
bool otaEnabled() { return false; }

#endif
