/*
 * Minimal, dependency-free MPR121 driver.
 *
 * We talk to the chip's registers directly over Wire instead of pulling in a
 * library: for electrode tuning we want to see filtered data and baselines
 * per electrode anyway, and this keeps the project buildable offline.
 *
 * Register map is from the NXP MPR121 datasheet Rev. 4 (02/2013). Note that
 * the older 09/2010 datasheet still floating around has the ADDR/VDD/VSS
 * table swapped, so ignore its addressing table.
 */

#pragma once

#include <Arduino.h>
#include <Wire.h>

namespace mpr121 {

// 7-bit I2C addresses selectable via the ADDR pin.
static const uint8_t ADDR_GND = 0x5A;  // ADDR tied to GND  (module default)
static const uint8_t ADDR_VDD = 0x5B;  // ADDR tied to 3V3
static const uint8_t ADDR_SDA = 0x5C;  // ADDR tied to SDA
static const uint8_t ADDR_SCL = 0x5D;  // ADDR tied to SCL

static const uint8_t NUM_ELECTRODES = 12;

// The first 8 electrodes (ELE0..ELE7) are the ones brought out as the
// 0..7 key pins on the common breakout boards.
static const uint8_t NUM_KEY_ELECTRODES = 8;

enum Reg : uint8_t {
  REG_TOUCH_STATUS_L = 0x00,  // ELE0..ELE7 touch bits
  REG_TOUCH_STATUS_H = 0x01,  // ELE8..ELE11 + OVCF + ELEPROX
  REG_OOR_L          = 0x02,  // ELE0..ELE7 out-of-range bits
  REG_OOR_H          = 0x03,  // ELE8..ELE11 out-of-range bits

  REG_FILTERED_BASE  = 0x04,  // ELE0..ELE11 filtered data, 2 bytes each -> 0x04..0x1D
  REG_BASELINE_BASE  = 0x1E,  // ELE0..ELE11 baseline, 1 byte each -> 0x1E..0x29
  REG_ELEPROX_BASE   = 0x2A,

  REG_MAX_HALF_DELTA_RISE     = 0x2B,
  REG_NOISE_HALF_DELTA_RISE   = 0x2C,
  REG_NOISE_COUNT_LIMIT_RISE  = 0x2D,
  REG_FILTER_DELAY_LIMIT_RISE = 0x2E,
  REG_MAX_HALF_DELTA_FALL     = 0x2F,
  REG_NOISE_HALF_DELTA_FALL   = 0x30,
  REG_NOISE_COUNT_LIMIT_FALL  = 0x31,
  REG_FILTER_DELAY_LIMIT_FALL = 0x32,

  // Touch threshold at 0x41, release at 0x42, then +2 per electrode.
  REG_ELE0_TOUCH   = 0x41,
  REG_ELE0_RELEASE = 0x42,

  REG_DEBOUNCE   = 0x5B,
  REG_AFE_CFG    = 0x5C,  // FFI + global charge/discharge current
  REG_FILTER_CFG = 0x5D,  // CDT / SFI / ESI. Reads back 0x24 after reset.
  REG_ECR        = 0x5E,  // Electrode config: CL + ELE_EN. Write this LAST.

  REG_AUTOCFG_CTRL0 = 0x7B,
  REG_AUTOCFG_USL   = 0x7D,
  REG_AUTOCFG_LSL   = 0x7E,
  REG_AUTOCFG_TL    = 0x7F,

  REG_SOFT_RESET = 0x80,  // Write 0x63 to trigger a soft reset.
};

// --- register access -------------------------------------------------------

bool writeReg(TwoWire &wire, uint8_t addr, uint8_t reg, uint8_t value);
int readReg(TwoWire &wire, uint8_t addr, uint8_t reg);  // -1 on failure
bool readRegs(TwoWire &wire, uint8_t addr, uint8_t reg, uint8_t *buf, size_t len);

// --- high level ------------------------------------------------------------

// Soft-resets the chip and initialises it for 12 electrodes with the given
// touch/release thresholds. Returns false if the chip never answers.
bool begin(TwoWire &wire, uint8_t addr, uint8_t touchThreshold = 12,
           uint8_t releaseThreshold = 6);

// Re-write only the touch/release thresholds (applies to all 12 electrodes).
bool setThresholds(TwoWire &wire, uint8_t addr, uint8_t touchThreshold,
                   uint8_t releaseThreshold);

// Per-electrode thresholds: the PC calibration writes each key separately
// because a weak finger and a chord's coupled neighbours need lower values.
bool setElectrodeThreshold(TwoWire &wire, uint8_t addr, uint8_t electrode,
                           uint8_t touch, uint8_t release);

// Bitmask of ELE0..ELE7 that are currently touched.
uint16_t touched(TwoWire &wire, uint8_t addr);

// Filtered (10-bit) and baseline (8-bit) readings, -1 on I2C failure.
int filtered(TwoWire &wire, uint8_t addr, uint8_t electrode);
int baseline(TwoWire &wire, uint8_t addr, uint8_t electrode);

// All 12 electrodes in two I2C bursts (24 filtered bytes + 12 baseline
// bytes). deltas[i] = baseline - filtered: positive when touched, since a
// finger pulls the filtered reading down. Returns false on I2C failure.
bool readDeltas(TwoWire &wire, uint8_t addr, int16_t *deltas);

// Convenience: baseline - filtered, i.e. how far the electrode has moved
// from its resting state. This is the number the threshold is compared
// against, and the number we tune against.
int delta(TwoWire &wire, uint8_t addr, uint8_t electrode);

// Enables sensing for `n` electrodes (0 = stop mode, 12 = all).
bool setElectrodeCount(TwoWire &wire, uint8_t addr, uint8_t n);

// Enables the chip's automatic baseline/charge-current calibration.
bool enableAutoConfig(TwoWire &wire, uint8_t addr, bool enable);

// Sets the analogue front end (0x5C: FFI + charge current) and the filter
// configuration (0x5D: ESI + SFI + charge/discharge time). These are the two
// knobs that set the sensitivity: the measured reading is proportional to
// (charge current) x (charge time), and so is the size of the change a finger
// produces, for a given electrode capacitance.
bool setAnalogConfig(TwoWire &wire, uint8_t addr, uint8_t afeCfg, uint8_t filterCfg);

// Reads REG_FILTER_CFG back. A healthy chip answers 0x24 right after reset,
// which is the de-facto "chip is present and out of reset" test.
int probeFilterCfg(TwoWire &wire, uint8_t addr);

}  // namespace mpr121
