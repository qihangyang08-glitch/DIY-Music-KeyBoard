/*
 * Optional Wi-Fi OTA (C4).
 *
 * The default build is USB-serial only and compiles the empty stubs below.
 * Define KEYBORAD_ENABLE_OTA together with KEYBORAD_WIFI_SSID and
 * KEYBORAD_WIFI_PASS to include ArduinoOTA; see pc/app/README.md.
 */

#pragma once

void otaSetup();
void otaLoop();
bool otaEnabled();
