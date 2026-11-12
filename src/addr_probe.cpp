/*
 * MPR121 address-strap probe.
 *
 * One job: answer "with ADD shorted to <pin>, does the module come up at the
 * expected address, and does it still sense?". It streams one line per tick so
 * the serial monitor shows the answer live, with no menu and no keys.
 *
 * Deliberately standalone — it talks to the chip over Wire directly instead of
 * including mpr121.*, so this can be flashed and thrown away.
 *
 * It sits next to main.cpp because PlatformIO has no per-env source directory;
 * the two firmwares are kept apart with build_src_filter instead (see
 * platformio.ini). The 'addr-probe' env builds this file and nothing else.
 *
 * The address is latched by the chip ONCE, at power-on. Changing the ADD
 * wiring while the board is running proves nothing: power-cycle every time.
 */

#include <Arduino.h>
#include <Wire.h>

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

static const int PIN_SDA = 8;
static const int PIN_SCL = 9;

// The address this firmware is built to watch. Change it when testing a
// different strap; the boot report lists all four either way.
static const uint8_t TARGET = 0x5D;

// The four addresses the ADD pin can select, with the wiring each implies.
static const uint8_t kAddr[] = {0x5A, 0x5B, 0x5C, 0x5D};
static const char *kStrap[] = {"ADD->GND", "ADD->3V3", "ADD->SDA", "ADD->SCL"};
static const uint8_t kAddrCount = 4;

// Touch/release thresholds and charge current. 0x3F is the maximum charge
// current, which is what makes a bare copper-foil pad readable.
static const uint8_t TOUCH_TH = 12;
static const uint8_t RELEASE_TH = 6;
static const uint8_t AFE_CFG = 0x3F;   // 0x5C: FFI[7:6] + CDC[5:0] = 63 uA
static const uint8_t FILTER_CFG = 0x20;  // 0x5D: ESI[7:6] + SFI[5:3] + CDT[2:0]

static const uint32_t TICK_MS = 250;      // streaming cadence
static const uint32_t QUIET_MS = 1000;    // "no answer" line cadence
static const uint32_t RECHECK_MS = 2000;  // re-init / re-probe cadence

// ---------------------------------------------------------------------------
// Register access
// ---------------------------------------------------------------------------

static bool wr(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

static int rd(uint8_t addr, uint8_t reg) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) {  // repeated start
    return -1;
  }
  if (Wire.requestFrom((int)addr, 1) != 1) {
    return -1;
  }
  return Wire.read();
}

// Plain "does this address ACK" check.
static bool present(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static int filtered(uint8_t addr, uint8_t e) {
  const int lo = rd(addr, 0x04 + e * 2);
  const int hi = rd(addr, 0x04 + e * 2 + 1);
  if (lo < 0 || hi < 0) {
    return -1;
  }
  return (int)((unsigned)(lo | (hi << 8)) >> 2);  // 10-bit value
}

static int baseline(uint8_t addr, uint8_t e) { return rd(addr, 0x1E + e); }

static int touchedBits(uint8_t addr) {
  const int lo = rd(addr, 0x00);
  const int hi = rd(addr, 0x01);
  if (lo < 0 || hi < 0) {
    return -1;
  }
  return lo | (hi << 8);
}

// ---------------------------------------------------------------------------
// Bring-up
// ---------------------------------------------------------------------------

// NXP's documented configuration sequence, minimum viable version: soft reset,
// calibrate, set thresholds, then enable the electrodes. Returns false if the
// chip never comes out of reset, which is the "it ACKs but is not really an
// MPR121 / not really running" case.
static bool initChip(uint8_t addr) {
  if (!wr(addr, 0x80, 0x63)) {  // soft reset
    return false;
  }
  delay(2);

  // REG_FILTER_CFG reads 0x24 once the part is out of reset.
  bool outOfReset = false;
  for (uint8_t i = 0; i < 5 && !outOfReset; i++) {
    outOfReset = (rd(addr, 0x5D) == 0x24);
    if (!outOfReset) {
      delay(2);
    }
  }
  if (!outOfReset) {
    return false;
  }

  wr(addr, 0x2B, 0x01);  // MHD rising
  wr(addr, 0x2C, 0x01);  // NHD rising
  wr(addr, 0x2D, 0x00);  // NCL rising
  wr(addr, 0x2E, 0x00);  // FDL rising
  wr(addr, 0x2F, 0x01);  // MHD falling
  wr(addr, 0x30, 0x01);  // NHD falling
  wr(addr, 0x31, 0xFF);  // NCL falling
  wr(addr, 0x32, 0x02);  // FDL falling

  wr(addr, 0x5C, AFE_CFG);
  wr(addr, 0x5D, FILTER_CFG);

  for (uint8_t e = 0; e < 12; e++) {
    wr(addr, 0x41 + e * 2, TOUCH_TH);
    wr(addr, 0x42 + e * 2, RELEASE_TH);
  }

  // Electrode config LAST: CL=0 (no proximity), ELE_EN=12 -> run mode.
  return wr(addr, 0x5E, 0x0C);
}

// ---------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------

// Everything we can learn with the chip merely ACKing. The boot report runs
// this on all four addresses, because a module showing up somewhere unexpected
// is exactly what a strap that did not take looks like.
static void bootReport() {
  Serial.println();
  Serial.println(F("=========== MPR121 ADDRESS-STRAP PROBE ==========="));
  Serial.printf(" bus       : SDA=GPIO%d  SCL=GPIO%d  @ 100 kHz\n", PIN_SDA, PIN_SCL);
  Serial.printf(" watching  : 0x%02X\n", TARGET);
  Serial.println(F(" probing the four ADD straps:"));

  bool targetFound = false;
  for (uint8_t i = 0; i < kAddrCount; i++) {
    if (!present(kAddr[i])) {
      Serial.printf("   0x%02X (%s) : no answer\n", kAddr[i], kStrap[i]);
      continue;
    }
    const int fcfg = rd(kAddr[i], 0x5D);
    Serial.printf("   0x%02X (%s) : ANSWERS   reg 0x5D = 0x%02X", kAddr[i], kStrap[i],
                  fcfg < 0 ? 0 : fcfg);
    if (fcfg == 0x24) {
      Serial.print(F("  (out of reset - really an MPR121)"));
    }
    if (kAddr[i] == TARGET) {
      targetFound = true;
      Serial.print(F("   <== target"));
    }
    Serial.println();
  }

  if (!targetFound) {
    Serial.println(F("\n target is NOT answering."));
    Serial.println(F("   - if ADD is strapped to SDA/SCL and the ADD jumper is still"));
    Serial.println(F("     closed, that line is shorted to GND and NOTHING will answer."));
    Serial.println(F("   - the address is latched at power-on: power-cycle after every"));
    Serial.println(F("     wiring change."));
    return;
  }

  Serial.println(F("\n initialising the target..."));
  if (!initChip(TARGET)) {
    Serial.println(F(" init FAILED (it ACKs but will not come out of reset)"));
    return;
  }
  const int ecr = rd(TARGET, 0x5E);
  Serial.printf(" init OK   ECR(0x5E) = 0x%02X  -> %s\n", ecr < 0 ? 0 : ecr,
                (ecr >= 0 && (ecr & 0x0F) == 12) ? "12 electrodes, running"
                                                 : "NOT running");
  Serial.println(F("\n streaming. Tap the E0 foil. Columns: filtered/baseline/delta."));
  Serial.println(F("=================================================="));
}

// One status line. `f`/`b` are -1 on an I2C failure.
static void tickLine(uint8_t addr, int f, int b, int touch) {
  Serial.printf("[%7lu ms] 0x%02X present  touch=0x%04X  E0 f=%4d b=%4d d=%4d",
                (unsigned long)millis(), addr, touch < 0 ? 0 : touch, f, b,
                (f < 0 || b < 0) ? 0 : f - b);
  if (touch < 0 || f < 0 || b < 0) {
    Serial.println(F("   <-- read error"));
    return;
  }
  if (touch & 0x0001) {
    Serial.println(F("   <<< TOUCH"));
  } else {
    Serial.println();
  }
}

// ---------------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(400);  // let the USB CDC enumerate before the first print

  Wire.begin(PIN_SDA, PIN_SCL, 100000);
  Wire.setTimeOut(20);

  bootReport();
}

void loop() {
  static uint32_t lastTick = 0;
  static uint32_t lastQuiet = 0;
  static uint32_t downSince = 0;
  static bool ready = false;
  const uint32_t now = millis();

  if (!present(TARGET)) {
    if (ready) {
      // It was working and stopped: say so once, with the uptime it survived.
      Serial.printf("\n!! 0x%02X stopped answering after %lu ms\n", TARGET,
                    (unsigned long)(now - downSince));
      ready = false;
    } else if (now - lastQuiet >= QUIET_MS) {
      lastQuiet = now;
      Serial.printf("[%7lu ms] 0x%02X NOT ANSWERING - check the ADD strap, then "
                    "power-cycle\n",
                    (unsigned long)now, TARGET);
    }
    // Keep trying quietly: a module that is plugged back in should recover
    // without a reflash.
    if (now - lastTick >= RECHECK_MS) {
      lastTick = now;
      if (initChip(TARGET)) {
        Serial.printf("\n-- 0x%02X is back, re-initialised\n", TARGET);
        ready = true;
        downSince = now;
      }
    }
    return;
  }

  // It answers. A chip that lost power comes back with ECR == 0 (Stop Mode):
  // it ACKs but senses nothing, so re-init rather than print a wall of zeros.
  const int ecr = rd(TARGET, 0x5E);
  if (ecr < 0) {
    return;  // a transient read failure; the next tick will sort it out
  }
  if ((ecr & 0x0F) == 0) {
    Serial.printf("\n-- 0x%02X lost its config (ECR=0x%02X, Stop Mode), re-initialising\n",
                  TARGET, ecr);
    ready = initChip(TARGET);
    downSince = now;
    return;
  }
  if (!ready) {
    ready = true;
    downSince = now;
    Serial.printf("-- 0x%02X initialised, ECR=0x%02X\n", TARGET, ecr);
  }

  if (now - lastTick < TICK_MS) {
    return;
  }
  lastTick = now;
  tickLine(TARGET, filtered(TARGET, 0), baseline(TARGET, 0), touchedBits(TARGET));
}
