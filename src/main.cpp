/*
 * KeyBorad — 36-channel wiring-stability test
 *
 * Three MPR121 modules share one I2C bus, 12 electrodes each. Channels are
 * numbered 1..36 in module order:
 *
 *   module 1 @ 0x5A (ADD->GND)  -> channels  1..12
 *   module 2 @ 0x5C (ADD->SDA)  -> channels 13..24
 *   module 3 @ 0x5D (ADD->SCL)  -> channels 25..36
 *
 * The point of this firmware is checking wiring, not tuning. So it does NOT
 * stream raw signal values. It prints a line only when the set of channels
 * over threshold changes, listing every active channel side by side, plus a
 * heartbeat every two seconds showing which modules are still answering.
 *
 * Commands:
 *   s  probe the addresses   m  re-initialise all modules
 *   d  one-shot channel dump t  cycle touch/release threshold preset
 *   g  cycle analog gain     h  help
 *   r  record 32 keys in layout order, x  abort
 *   c  toggle the 25 Hz CAL signal stream
 *   T <ch> <touch> <release> ...  write per-channel thresholds
 *   Q  print the current threshold table
 *
 * Calibration signal convention: CAL reports clamp(baseline - filtered, 0,
 * 255). A finger pulls the filtered reading down, so a touch is positive.
 */

#include <Arduino.h>
#include <Wire.h>
#include <ctype.h>
#include <stdlib.h>

#include "mpr121.h"

// ---------------------------------------------------------------------------
// Hardware configuration
// ---------------------------------------------------------------------------

static const int PIN_I2C_SDA = 8;
static const int PIN_I2C_SCL = 9;
static const uint32_t I2C_CLOCK_HZ = 100000;

// The three modules, in channel order.
static const uint8_t MODULE_COUNT = 3;
static const uint8_t MODULE_ADDR[MODULE_COUNT] = {
    mpr121::ADDR_GND,  // 0x5A — ADD tied to GND
    mpr121::ADDR_SDA,  // 0x5C — ADD tied to SDA
    mpr121::ADDR_SCL,  // 0x5D — ADD tied to SCL
};
static const char *MODULE_STRAP[MODULE_COUNT] = {"ADD->GND", "ADD->SDA",
                                                 "ADD->SCL"};

static const uint8_t ELECTRODES_PER_MODULE = mpr121::NUM_ELECTRODES;  // 12
static const uint8_t TOTAL_CHANNELS = MODULE_COUNT * ELECTRODES_PER_MODULE;  // 36

// ---------------------------------------------------------------------------
// Timing
// ---------------------------------------------------------------------------

static const uint32_t POLL_MS = 20;       // touch-status poll period
static const uint32_t HEARTBEAT_MS = 2000;
static const uint32_t HEALTH_MS = 2000;

// ---------------------------------------------------------------------------
// Threshold and gain presets
// ---------------------------------------------------------------------------

static const uint8_t kTouchPresets[] = {12, 8, 5, 3, 20};
static const uint8_t kReleasePresets[] = {6, 4, 2, 1, 10};
static const uint8_t kPresetCount = sizeof(kTouchPresets) / sizeof(kTouchPresets[0]);

// Charge current is the sensitivity knob: the reading, and therefore the size
// of a touch, scales with it. Once an electrode's untouched baseline approaches
// 255 the 8-bit baseline register saturates and tracking breaks, which on this
// pad geometry caps useful gain near 4x (CDC = 63 uA).
struct GainPreset {
  uint8_t afe;      // 0x5C: FFI[7:6] + CDC[5:0] in uA
  uint8_t filter;   // 0x5D: ESI[7:6] + SFI[5:3] + CDT[2:0]
  const char *name;
};
static const GainPreset kGainPresets[] = {
    {0x10, 0x20, "1.0x CDC=16uA"},
    {0x18, 0x20, "1.5x CDC=24uA"},
    {0x20, 0x20, "2.0x CDC=32uA"},
    {0x30, 0x20, "3.0x CDC=48uA"},
    {0x3F, 0x20, "4.0x CDC=63uA (max)"},
};
static const uint8_t kGainCount = sizeof(kGainPresets) / sizeof(kGainPresets[0]);
static const uint8_t kDefaultGain = 4;

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

static bool moduleReady[MODULE_COUNT] = {false, false, false};
static uint8_t presetIndex = 0;
static uint8_t gainIndex = kDefaultGain;

// Bit n set = channel n+1 is over its touch threshold.
static uint64_t channelMask = 0;
static uint64_t oorMask = 0;

static uint32_t lastPoll = 0;
static uint32_t lastHeartbeat = 0;
static uint32_t lastHealthCheck = 0;

// Calibration stream and per-channel thresholds.
static const uint8_t CAL_CHANNELS = 32;
static const uint32_t CAL_STREAM_MS = 40;  // 25 Hz
static const uint16_t MAX_COMMAND_LINE = 512;

static bool calStream = false;
static uint32_t lastCalStream = 0;

// The firmware's view of what it last wrote, channel 1..36 at index 0..35.
// A module re-init resets thresholds to the preset, so initModule() re-applies
// these values; Q reports them. NVS persistence is a later slice.
static uint8_t channelTouch[TOTAL_CHANNELS];
static uint8_t channelRelease[TOTAL_CHANNELS];

static char commandLine[MAX_COMMAND_LINE];
static size_t commandLineLen = 0;
static bool readingCommandLine = false;
static bool discardingLine = false;

static void applyPresetToMirror() {
  for (uint8_t ch = 0; ch < TOTAL_CHANNELS; ch++) {
    channelTouch[ch] = kTouchPresets[presetIndex];
    channelRelease[ch] = kReleasePresets[presetIndex];
  }
}

// Key-recording mode: press 'r', then touch the keys in the layout's order.
// Each press is stored as the channel it produced, so the physical key order
// can later be turned into a note -> channel table for the PC side.
static const uint8_t RECORD_TARGET = 32;
static bool recording = false;
static uint8_t recCount = 0;
static uint8_t recChannel[RECORD_TARGET];
static bool recArmed = true;         // ready to accept the next key
static uint32_t recReleasedAt = 0;   // when everything was last seen released

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// 0-based electrode index -> 1-based channel number.
static uint8_t channelNumber(uint8_t module, uint8_t electrode) {
  return (uint8_t)(module * ELECTRODES_PER_MODULE + electrode + 1);
}

// "channels 13-24"
static void printChannelRange(uint8_t module) {
  Serial.printf("channels %u-%u", (unsigned)channelNumber(module, 0),
                (unsigned)channelNumber(module, ELECTRODES_PER_MODULE - 1));
}

static bool i2cPresent(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

static bool initModule(uint8_t module) {
  const uint8_t addr = MODULE_ADDR[module];
  if (!mpr121::begin(Wire, addr, kTouchPresets[presetIndex],
                     kReleasePresets[presetIndex])) {
    return false;
  }
  // begin() writes 16 uA; re-apply the selected gain preset.
  const GainPreset &g = kGainPresets[gainIndex];
  if (!mpr121::setAnalogConfig(Wire, addr, g.afe, g.filter)) {
    return false;
  }
  // begin() also reset every threshold to the preset. Re-apply the PC's
  // per-channel values so a health-check recovery or 'm' does not silently
  // undo a calibration. At boot the mirror holds the preset values.
  for (uint8_t ele = 0; ele < ELECTRODES_PER_MODULE; ele++) {
    const uint8_t ch = module * ELECTRODES_PER_MODULE + ele;
    if (!mpr121::setElectrodeThreshold(Wire, addr, ele, channelTouch[ch],
                                       channelRelease[ch])) {
      return false;
    }
  }
  return true;
}

// ---------------------------------------------------------------------------
// Address probe
// ---------------------------------------------------------------------------

// The four addresses the ADD pin can select, and the wiring each implies.
// A mis-strapped module cannot appear anywhere else.
static const uint8_t kStrapAddr[] = {mpr121::ADDR_GND, mpr121::ADDR_VDD,
                                     mpr121::ADDR_SDA, mpr121::ADDR_SCL};
static const char *kStrapName[] = {"ADD->GND", "ADD->3V3", "ADD->SDA",
                                   "ADD->SCL"};
static const uint8_t kStrapCount = 4;

// -1 when `addr` is not one of the modules this firmware drives.
static int moduleForAddress(uint8_t addr) {
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    if (MODULE_ADDR[m] == addr) {
      return m;
    }
  }
  return -1;
}

// Probes only the four addresses an MPR121 can sit at. Deliberately NOT a
// 1..126 sweep: on a bus with no pull-ups each absent address burns about a
// second in the ESP32 I2C driver, so a full sweep takes two minutes and looks
// exactly like a board that never booted. Four targeted transactions answer
// the only question that matters, immediately.
static void probeAddresses() {
  Serial.println();
  Serial.println(F("probing the four MPR121 addresses:"));
  uint8_t found = 0;

  for (uint8_t i = 0; i < kStrapCount; i++) {
    const uint8_t addr = kStrapAddr[i];
    if (!i2cPresent(addr)) {
      Serial.printf("   0x%02X (%s) : no answer\n", addr, kStrapName[i]);
      continue;
    }
    found++;
    Serial.printf("   0x%02X (%s) : ANSWERS", addr, kStrapName[i]);
    const int m = moduleForAddress(addr);
    if (m >= 0) {
      Serial.printf("   -> module %u, ", m + 1);
      printChannelRange(m);
    } else {
      Serial.print(F("   (not used by this firmware)"));
    }
    Serial.println();
  }

  if (found == 0) {
    Serial.println(F("   nothing answered: check 3V3/GND, SDA/SCL, and the ADD straps"));
    Serial.println(F("   (a module strapped to SDA/SCL with its ADD jumper still closed"));
    Serial.println(F("    shorts that line to GND and takes the whole bus down)"));
  }
}

// ---------------------------------------------------------------------------
// Channel polling
// ---------------------------------------------------------------------------

// Reads the touch-status registers of every ready module and folds them into
// the global 36-bit mask. A module that stops answering is marked not-ready;
// the health check tries to bring it back.
static void pollTouch() {
  uint64_t mask = 0;
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    if (!moduleReady[m]) {
      continue;
    }
    const int lo = mpr121::readReg(Wire, MODULE_ADDR[m], mpr121::REG_TOUCH_STATUS_L);
    const int hi = mpr121::readReg(Wire, MODULE_ADDR[m], mpr121::REG_TOUCH_STATUS_H);
    if (lo < 0 || hi < 0) {
      moduleReady[m] = false;
      continue;
    }
    const uint16_t bits = (uint16_t)((hi << 8) | lo);
    for (uint8_t e = 0; e < ELECTRODES_PER_MODULE; e++) {
      if (bits & (1u << e)) {
        mask |= (1ULL << (m * ELECTRODES_PER_MODULE + e));
      }
    }
  }
  channelMask = mask;
}

// Out-of-range bits are the chip's own "this electrode is not behaving" flag:
// an unconnected or shorted electrode tends to trip them. Reported only when
// the set changes.
static void pollOutOfRange() {
  uint64_t mask = 0;
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    if (!moduleReady[m]) {
      continue;
    }
    const int lo = mpr121::readReg(Wire, MODULE_ADDR[m], mpr121::REG_OOR_L);
    const int hi = mpr121::readReg(Wire, MODULE_ADDR[m], mpr121::REG_OOR_H);
    if (lo < 0 || hi < 0) {
      continue;
    }
    const uint16_t bits = (uint16_t)((hi << 8) | lo);
    for (uint8_t e = 0; e < ELECTRODES_PER_MODULE; e++) {
      if (bits & (1u << e)) {
        mask |= (1ULL << (m * ELECTRODES_PER_MODULE + e));
      }
    }
  }

  if (mask == oorMask) {
    return;
  }
  oorMask = mask;
  Serial.print(F("!! out-of-range:"));
  if (mask == 0) {
    Serial.println(F(" none"));
    return;
  }
  for (uint8_t ch = 0; ch < TOTAL_CHANNELS; ch++) {
    if (mask & (1ULL << ch)) {
      Serial.printf(" %u", (unsigned)(ch + 1));
    }
  }
  Serial.println(F("   (check that electrode's wiring)"));
}

// ---------------------------------------------------------------------------
// Key recording
// ---------------------------------------------------------------------------

static void printRecording() {
  Serial.println();
  Serial.println(F("===== RECORDING COMPLETE ====="));
  Serial.println(F("key,channel,module_addr,electrode"));
  for (uint8_t i = 0; i < recCount; i++) {
    const uint8_t ch = recChannel[i];
    const uint8_t m = (uint8_t)((ch - 1) / ELECTRODES_PER_MODULE);
    const uint8_t e = (uint8_t)((ch - 1) % ELECTRODES_PER_MODULE);
    Serial.printf("%u,%u,0x%02X,%u\n", (unsigned)(i + 1), (unsigned)ch,
                  MODULE_ADDR[m], (unsigned)e);
  }

  // A missed or doubled press is easy to overlook in a 32-line list, so spell
  // both out explicitly.
  Serial.print(F("duplicate channels:"));
  bool anyDup = false;
  for (uint8_t i = 0; i < recCount; i++) {
    for (uint8_t j = (uint8_t)(i + 1); j < recCount; j++) {
      if (recChannel[i] == recChannel[j]) {
        Serial.printf(" key %u & %u -> ch %u;", (unsigned)(i + 1),
                      (unsigned)(j + 1), (unsigned)recChannel[i]);
        anyDup = true;
      }
    }
  }
  if (!anyDup) {
    Serial.print(F(" none"));
  }
  Serial.println();

  Serial.print(F("unused channels:"));
  bool anyUnused = false;
  for (uint8_t ch = 1; ch <= TOTAL_CHANNELS; ch++) {
    bool used = false;
    for (uint8_t i = 0; i < recCount; i++) {
      if (recChannel[i] == ch) {
        used = true;
        break;
      }
    }
    if (!used) {
      Serial.printf(" %u", (unsigned)ch);
      anyUnused = true;
    }
  }
  if (!anyUnused) {
    Serial.print(F(" none"));
  }
  Serial.println();
  Serial.println(F("=============================="));
}

static void recordChannel(uint8_t channel) {
  if (recCount >= RECORD_TARGET) {
    return;
  }
  recChannel[recCount++] = channel;

  const uint8_t m = (uint8_t)((channel - 1) / ELECTRODES_PER_MODULE);
  const uint8_t e = (uint8_t)((channel - 1) % ELECTRODES_PER_MODULE);
  Serial.printf("REC %2u/%u   key %2u -> channel %2u   (0x%02X E%u)\n",
                (unsigned)recCount, (unsigned)RECORD_TARGET, (unsigned)recCount,
                (unsigned)channel, MODULE_ADDR[m], (unsigned)e);

  if (recCount == RECORD_TARGET) {
    recording = false;
    printRecording();
  }
}

// Called every poll while recording. A key is taken on its rising edge, and the
// next one is only armed after everything has been released for a moment, so
// contact bounce and a slow release cannot record the same key twice.
static void recordTick() {
  const uint32_t now = millis();

  if (channelMask == 0) {
    if (!recArmed) {
      if (recReleasedAt == 0) {
        recReleasedAt = now;
      } else if (now - recReleasedAt >= 80) {
        recArmed = true;
        recReleasedAt = 0;
      }
    }
    return;
  }

  recReleasedAt = 0;
  if (!recArmed) {
    return;
  }

  for (uint8_t i = 0; i < TOTAL_CHANNELS; i++) {
    if (channelMask & (1ULL << i)) {
      recordChannel((uint8_t)(i + 1));
      break;
    }
  }
  recArmed = false;
}

static void startRecording() {
  recording = true;
  recCount = 0;
  recArmed = true;
  recReleasedAt = 0;
  Serial.println();
  Serial.println(F("===== RECORDING STARTED ====="));
  Serial.printf("press the %u keys in the layout's order (1..%u).\n",
                (unsigned)RECORD_TARGET, (unsigned)RECORD_TARGET);
  Serial.println(F("release each key fully before touching the next."));
  Serial.println(F("'x' aborts, 'r' restarts from key 1."));
  Serial.println(F("============================="));
}

// ---------------------------------------------------------------------------
// Reporting
// ---------------------------------------------------------------------------

static void printStatus() {
  Serial.printf("[%6lu ms]", (unsigned long)millis());
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    Serial.printf("  0x%02X %s", MODULE_ADDR[m], moduleReady[m] ? "OK" : "--");
  }
  Serial.print(F("   keys:"));
  if (channelMask == 0) {
    Serial.print(F(" none"));
  } else {
    for (uint8_t ch = 0; ch < TOTAL_CHANNELS; ch++) {
      if (channelMask & (1ULL << ch)) {
        Serial.printf(" %u", (unsigned)(ch + 1));
      }
    }
  }
  Serial.println();
}

// On-demand one-shot dump of every channel's raw numbers. Not streamed — this
// is for chasing a single flaky channel, so it prints once per 'd'.
static void dumpChannels() {
  Serial.println();
  Serial.println(F(" ch  module/ele    filtered  baseline   delta"));
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    for (uint8_t e = 0; e < ELECTRODES_PER_MODULE; e++) {
      const unsigned ch = channelNumber(m, e);
      if (!moduleReady[m]) {
        Serial.printf(" %2u  0x%02X/E%-2u   <module not ready>\n", ch, MODULE_ADDR[m],
                      (unsigned)e);
        continue;
      }
      const int f = mpr121::filtered(Wire, MODULE_ADDR[m], e);
      const int b = mpr121::baseline(Wire, MODULE_ADDR[m], e);
      if (f < 0 || b < 0) {
        Serial.printf(" %2u  0x%02X/E%-2u   <i2c error>\n", ch, MODULE_ADDR[m],
                      (unsigned)e);
        continue;
      }
      Serial.printf(" %2u  0x%02X/E%-2u   %8d  %8d  %5d\n", ch, MODULE_ADDR[m],
                    (unsigned)e, f, b, b - f);
    }
  }
}

// ---------------------------------------------------------------------------
// Calibration stream
// ---------------------------------------------------------------------------

// One CAL line: 32 values in module order. Modules 1 and 2 contribute 12
// electrodes each; module 3 contributes its first 8 (keys 25..32). An offline
// module prints -1 for every channel it owns, so the PC can draw a grey gap
// instead of a fake zero.
static void streamCalibration() {
  Serial.printf("CAL %lu", (unsigned long)millis());
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    const uint8_t electrodes =
        (m == MODULE_COUNT - 1) ? 8 : ELECTRODES_PER_MODULE;
    int16_t deltas[ELECTRODES_PER_MODULE];
    const bool ok =
        moduleReady[m] && mpr121::readDeltas(Wire, MODULE_ADDR[m], deltas);
    if (moduleReady[m] && !ok) {
      // Let the health check re-initialise it; do not report stale values.
      moduleReady[m] = false;
    }
    for (uint8_t e = 0; e < electrodes; e++) {
      int value = -1;
      if (ok) {
        value = deltas[e];
        if (value < 0) {
          value = 0;
        } else if (value > 255) {
          value = 255;
        }
      }
      Serial.printf(" %d", value);
    }
  }
  Serial.println();
}

static void toggleCalibrationStream() {
  calStream = !calStream;
  lastCalStream = millis();
  if (calStream) {
    Serial.println(F("CAL ON"));
  } else {
    Serial.println(F("CAL OFF"));
  }
}

// ---------------------------------------------------------------------------
// Per-channel threshold writes
// ---------------------------------------------------------------------------

// `T` and `Q` are line commands; everything else stays a single character.
// The PC sends one T line with up to 32 channel/touch/release triples.
static bool readLong(char *&cursor, long &value) {
  while (*cursor == ' ' || *cursor == '\t') {
    cursor++;
  }
  if (*cursor == '\0') {
    return false;
  }
  char *end = nullptr;
  const long parsed = strtol(cursor, &end, 10);
  if (end == cursor) {
    return false;
  }
  value = parsed;
  cursor = end;
  return true;
}

// Q replies with the 32 keys the PC calibrates. Channels 33..36 are function
// keys and stay on the preset.
static void printThresholdTable() {
  Serial.print(F("T"));
  for (uint8_t channel = 1; channel <= CAL_CHANNELS; channel++) {
    Serial.printf(" %u %u %u", (unsigned)channel,
                  (unsigned)channelTouch[channel - 1],
                  (unsigned)channelRelease[channel - 1]);
  }
  Serial.println();
}

static void writeThresholdTable(char *line) {
  struct Entry {
    uint8_t channel;
    uint8_t touch;
    uint8_t release;
  };
  Entry entries[TOTAL_CHANNELS];
  uint8_t count = 0;
  char *cursor = line + 1;

  while (true) {
    while (*cursor == ' ' || *cursor == '\t') {
      cursor++;
    }
    if (*cursor == '\0') {
      break;
    }
    long channel = 0;
    long touch = 0;
    long release = 0;
    if (!readLong(cursor, channel) || !readLong(cursor, touch) ||
        !readLong(cursor, release)) {
      Serial.println(F("ERR T 0"));
      return;
    }
    if (channel < 1 || channel > TOTAL_CHANNELS || touch < 1 || touch > 255 ||
        release < 0 || release >= touch) {
      Serial.printf("ERR T %ld\n", channel);
      return;
    }
    if (count >= TOTAL_CHANNELS) {
      Serial.println(F("ERR T 0"));
      return;
    }
    for (uint8_t i = 0; i < count; i++) {
      if (entries[i].channel == (uint8_t)channel) {
        Serial.printf("ERR T %ld\n", channel);
        return;
      }
    }
    entries[count].channel = (uint8_t)channel;
    entries[count].touch = (uint8_t)touch;
    entries[count].release = (uint8_t)release;
    count++;
  }

  if (count == 0) {
    Serial.println(F("ERR T 0"));
    return;
  }

  // Check every module before writing any register, so a request that names
  // an offline module does not leave half the keys updated.
  for (uint8_t i = 0; i < count; i++) {
    const uint8_t module =
        (uint8_t)((entries[i].channel - 1) / ELECTRODES_PER_MODULE);
    if (!moduleReady[module]) {
      Serial.printf("ERR T %u\n", (unsigned)entries[i].channel);
      return;
    }
  }

  for (uint8_t i = 0; i < count; i++) {
    const uint8_t channel = entries[i].channel;
    const uint8_t module =
        (uint8_t)((channel - 1) / ELECTRODES_PER_MODULE);
    const uint8_t electrode =
        (uint8_t)((channel - 1) % ELECTRODES_PER_MODULE);
    if (!mpr121::setElectrodeThreshold(Wire, MODULE_ADDR[module], electrode,
                                       entries[i].touch, entries[i].release)) {
      Serial.printf("ERR T %u\n", (unsigned)channel);
      return;
    }
    channelTouch[channel - 1] = entries[i].touch;
    channelRelease[channel - 1] = entries[i].release;
  }
  Serial.println(F("OK T"));
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

// Keeps the three modules alive. An MPR121 that loses power comes back with
// every register at 0x00 — it still ACKs but senses nothing (ECR low nibble
// zero = Stop Mode), so it is re-initialised rather than silently reporting
// zeroes. Modules that were absent are picked up if they appear.
static void healthCheck() {
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    const uint8_t addr = MODULE_ADDR[m];

    if (!moduleReady[m]) {
      if (!i2cPresent(addr)) {
        continue;
      }
      moduleReady[m] = initModule(m);
      Serial.printf("%s module %u @ 0x%02X (%s): %s\n",
                    moduleReady[m] ? "++" : "!!", m + 1, addr, MODULE_STRAP[m],
                    moduleReady[m] ? "appeared and initialised" : "present but init FAILED");
      continue;
    }

    const int ecr = mpr121::readReg(Wire, addr, mpr121::REG_ECR);
    if (ecr < 0) {
      moduleReady[m] = false;
      Serial.printf("!! module %u @ 0x%02X (%s) stopped answering\n", m + 1, addr,
                    MODULE_STRAP[m]);
      continue;
    }
    if ((ecr & 0x0F) == 0) {
      moduleReady[m] = initModule(m);
      Serial.printf("!! module %u @ 0x%02X (%s) lost its config (ECR=0x%02X), %s\n",
                    m + 1, addr, MODULE_STRAP[m], ecr,
                    moduleReady[m] ? "re-initialised" : "re-init FAILED");
    }
  }
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

static void cyclePreset() {
  presetIndex = (presetIndex + 1) % kPresetCount;
  applyPresetToMirror();
  Serial.printf("\nthreshold preset -> touch=%u release=%u\n",
                kTouchPresets[presetIndex], kReleasePresets[presetIndex]);
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    if (moduleReady[m]) {
      mpr121::setThresholds(Wire, MODULE_ADDR[m], kTouchPresets[presetIndex],
                            kReleasePresets[presetIndex]);
    }
  }
}

static void cycleGain() {
  gainIndex = (gainIndex + 1) % kGainCount;
  const GainPreset &g = kGainPresets[gainIndex];
  Serial.printf("\nanalog gain -> %s (0x5C=0x%02X)\n", g.name, g.afe);
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    if (moduleReady[m]) {
      mpr121::setAnalogConfig(Wire, MODULE_ADDR[m], g.afe, g.filter);
    }
  }
  Serial.println(F("applied; wait ~2 s for the baselines to settle"));
}

static void printHelp() {
  Serial.println();
  Serial.println(F("===== COMMANDS ====="));
  Serial.println(F("  s : probe the four MPR121 addresses"));
  Serial.println(F("  m : re-initialise all modules"));
  Serial.println(F("  d : one-shot dump of all 36 channels (f / b / delta)"));
  Serial.println(F("  r : record 32 keys in layout order, then print the map"));
  Serial.println(F("  x : abort recording"));
  Serial.println(F("  t : cycle touch/release threshold preset"));
  Serial.println(F("  g : cycle analog gain preset"));
  Serial.println(F("  c : toggle the 25 Hz CAL signal stream"));
  Serial.println(F("  T <ch> <touch> <release> ... : write thresholds by channel"));
  Serial.println(F("  Q : print the current threshold table"));
  Serial.println(F("  h : this help"));
  Serial.println(F("===================="));
}

static void handleCommand(char c) {
  switch (c) {
    case 's': probeAddresses(); break;
    case 'm':
      Serial.println(F("\n-- re-initialising all modules --"));
      for (uint8_t m = 0; m < MODULE_COUNT; m++) {
        moduleReady[m] = initModule(m);
        Serial.printf("   module %u @ 0x%02X (%s): %s\n", m + 1, MODULE_ADDR[m],
                      MODULE_STRAP[m], moduleReady[m] ? "OK" : "not present / init FAILED");
      }
      break;
    case 'd': dumpChannels(); break;
    case 'r': startRecording(); break;
    case 'x':
      if (recording) {
        recording = false;
        Serial.printf("\nrecording aborted after %u key(s); press 'r' to start over.\n",
                      (unsigned)recCount);
      } else {
        Serial.println(F("\nnot recording."));
      }
      break;
    case 't': cyclePreset(); break;
    case 'g': cycleGain(); break;
    case 'c': toggleCalibrationStream(); break;
    case 'h':
    case '?': printHelp(); break;
    default:
      Serial.printf("unknown command '%c' — press 'h'\n", c);
      break;
  }
}

// A line command starts with uppercase T or Q and ends at CR/LF. All other
// commands are still single characters, so typing 't' (preset) and 'T'
// (thresholds) cannot collide.
static void finishCommandLine() {
  commandLine[commandLineLen] = '\0';
  readingCommandLine = false;
  if (commandLine[0] == 'T') {
    writeThresholdTable(commandLine);
  } else if (commandLine[0] == 'Q' &&
             (commandLine[1] == '\0' || commandLine[1] == ' ' ||
              commandLine[1] == '\t')) {
    printThresholdTable();
  } else {
    Serial.println(F("ERR T 0"));
  }
  commandLineLen = 0;
}

static void feedCommandChar(char c) {
  if (discardingLine) {
    if (c == '\r' || c == '\n') {
      discardingLine = false;
    }
    return;
  }
  if (!readingCommandLine) {
    if (c == 'T' || c == 'Q') {
      readingCommandLine = true;
      commandLineLen = 0;
      commandLine[commandLineLen++] = c;
      return;
    }
    if (c == '\r' || c == '\n') {
      return;
    }
    handleCommand(c);
    return;
  }
  if (c == '\r' || c == '\n') {
    finishCommandLine();
    return;
  }
  if (commandLineLen + 1 >= MAX_COMMAND_LINE) {
    readingCommandLine = false;
    discardingLine = true;
    commandLineLen = 0;
    Serial.println(F("ERR T 0"));
    return;
  }
  commandLine[commandLineLen++] = c;
}

// ---------------------------------------------------------------------------
// Arduino entry points
// ---------------------------------------------------------------------------

void setup() {
  Serial.begin(115200);
  delay(400);  // let the USB CDC enumerate before the first print

  Serial.println();
  Serial.println(F("=== KeyBorad: 36-channel wiring test ==="));
  Serial.printf("I2C: SDA=GPIO%d SCL=GPIO%d @ %u Hz\n", PIN_I2C_SDA, PIN_I2C_SCL,
                I2C_CLOCK_HZ);

  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, I2C_CLOCK_HZ);
  Wire.setTimeOut(20);
  // The mirror must exist before the first initModule(): that function
  // re-applies it after begin() resets the thresholds.
  applyPresetToMirror();

  probeAddresses();

  Serial.println(F("\n-- initialising --"));
  for (uint8_t m = 0; m < MODULE_COUNT; m++) {
    Serial.printf("   module %u @ 0x%02X (%s), ", m + 1, MODULE_ADDR[m],
                  MODULE_STRAP[m]);
    printChannelRange(m);
    if (!i2cPresent(MODULE_ADDR[m])) {
      moduleReady[m] = false;
      Serial.println(F(" : not present"));
      continue;
    }
    moduleReady[m] = initModule(m);
    Serial.printf(" : %s\n", moduleReady[m] ? "OK" : "present but init FAILED");
  }

  Serial.printf("\nthreshold %u/%u, gain %s\n", kTouchPresets[presetIndex],
                kReleasePresets[presetIndex], kGainPresets[gainIndex].name);
  printHelp();
  printStatus();

  lastPoll = lastHeartbeat = lastHealthCheck = millis();
}

void loop() {
  const uint32_t now = millis();

  if (now - lastHealthCheck >= HEALTH_MS) {
    lastHealthCheck = now;
    healthCheck();
    pollOutOfRange();
  }

  if (now - lastPoll >= POLL_MS) {
    lastPoll = now;
    const uint64_t before = channelMask;
    pollTouch();
    if (recording) {
      recordTick();
    } else if (channelMask != before) {
      printStatus();
    }
  }

  if (now - lastHeartbeat >= HEARTBEAT_MS) {
    lastHeartbeat = now;
    printStatus();
  }

  while (Serial.available() > 0) {
    feedCommandChar((char)Serial.read());
  }

  if (calStream && now - lastCalStream >= CAL_STREAM_MS) {
    lastCalStream = now;
    streamCalibration();
  }
}
