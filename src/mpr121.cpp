#include "mpr121.h"

namespace mpr121 {

// ---------------------------------------------------------------------------
// Register access
// ---------------------------------------------------------------------------

bool writeReg(TwoWire &wire, uint8_t addr, uint8_t reg, uint8_t value) {
  wire.beginTransmission(addr);
  wire.write(reg);
  wire.write(value);
  return wire.endTransmission() == 0;
}

int readReg(TwoWire &wire, uint8_t addr, uint8_t reg) {
  wire.beginTransmission(addr);
  wire.write(reg);
  // Repeated start, so the read stays in one transaction.
  if (wire.endTransmission(false) != 0) {
    return -1;
  }
  if (wire.requestFrom((int)addr, 1) != 1) {
    return -1;
  }
  return wire.read();
}

bool readRegs(TwoWire &wire, uint8_t addr, uint8_t reg, uint8_t *buf, size_t len) {
  wire.beginTransmission(addr);
  wire.write(reg);
  if (wire.endTransmission(false) != 0) {
    return false;
  }
  if (wire.requestFrom((int)addr, (int)len) != (int)len) {
    return false;
  }
  for (size_t i = 0; i < len; i++) {
    buf[i] = (uint8_t)wire.read();
  }
  return true;
}

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

int probeFilterCfg(TwoWire &wire, uint8_t addr) {
  return readReg(wire, addr, REG_FILTER_CFG);
}

bool begin(TwoWire &wire, uint8_t addr, uint8_t touchThreshold,
           uint8_t releaseThreshold) {
  // 1. Soft reset. The datasheet's reset value is 0x63.
  if (!writeReg(wire, addr, REG_SOFT_RESET, 0x63)) {
    return false;
  }
  delay(1);

  // 2. Wait for the chip to come back. REG_FILTER_CFG reads 0x24 when the
  //    part is out of reset and happy; this doubles as a presence test.
  bool ok = false;
  for (uint8_t i = 0; i < 5; i++) {
    if (probeFilterCfg(wire, addr) == 0x24) {
      ok = true;
      break;
    }
    delay(1);
  }
  if (!ok) {
    return false;
  }

  // 3. Both halves of the baseline filter: max half delta, noise half delta,
  //    noise count limit, filter delay limit (rising then falling).
  static const uint8_t kFilterDefaults[][2] = {
      {REG_MAX_HALF_DELTA_RISE, 0x01},
      {REG_NOISE_HALF_DELTA_RISE, 0x01},
      {REG_NOISE_COUNT_LIMIT_RISE, 0x0E},
      {REG_FILTER_DELAY_LIMIT_RISE, 0x00},
      {REG_MAX_HALF_DELTA_FALL, 0x01},
      {REG_NOISE_HALF_DELTA_FALL, 0x05},
      {REG_NOISE_COUNT_LIMIT_FALL, 0x01},
      {REG_FILTER_DELAY_LIMIT_FALL, 0x00},
      {REG_DEBOUNCE, 0x00},
      {REG_AFE_CFG, 0x10},     // 16 uA charge current, FFI = 4
      {REG_FILTER_CFG, 0x20},  // CDT = 0.5 us, SFI = 4 samples, ESI = 1 ms
  };
  for (const auto &kv : kFilterDefaults) {
    if (!writeReg(wire, addr, kv[0], kv[1])) {
      return false;
    }
  }

  // 4. Thresholds, then enable the electrodes. ECR must be written last.
  if (!setThresholds(wire, addr, touchThreshold, releaseThreshold)) {
    return false;
  }
  return setElectrodeCount(wire, addr, NUM_ELECTRODES);
}

bool setThresholds(TwoWire &wire, uint8_t addr, uint8_t touchThreshold,
                   uint8_t releaseThreshold) {
  for (uint8_t ele = 0; ele < NUM_ELECTRODES; ele++) {
    if (!setElectrodeThreshold(wire, addr, ele, touchThreshold,
                               releaseThreshold)) {
      return false;
    }
  }
  return true;
}

bool setElectrodeThreshold(TwoWire &wire, uint8_t addr, uint8_t electrode,
                           uint8_t touch, uint8_t release) {
  if (electrode >= NUM_ELECTRODES) {
    return false;
  }
  const uint8_t touchReg = REG_ELE0_TOUCH + electrode * 2;
  return writeReg(wire, addr, touchReg, touch) &&
         writeReg(wire, addr, touchReg + 1, release);
}

bool setElectrodeCount(TwoWire &wire, uint8_t addr, uint8_t n) {
  if (n > NUM_ELECTRODES) {
    n = NUM_ELECTRODES;
  }
  // Bits [7:6] = calibration lock, [5:4] = ELEPROX enable, [3:0] = ELE_EN.
  // CL = 0b10 keeps baseline tracking running and initialises the baseline
  // from the first samples.
  const uint8_t ecr = 0x80 | (n & 0x0F);
  return writeReg(wire, addr, REG_ECR, ecr);
}

bool enableAutoConfig(TwoWire &wire, uint8_t addr, bool enable) {
  // The auto-config registers are only writable with sensing stopped.
  const int ecr = readReg(wire, addr, REG_ECR);
  if (ecr < 0) {
    return false;
  }
  if (!writeReg(wire, addr, REG_ECR, 0x00)) {  // stop mode
    return false;
  }

  bool ok;
  if (enable) {
    // Target window in ADC counts for a ~3.3 V supply.
    ok = writeReg(wire, addr, REG_AUTOCFG_USL, 200) &&
         writeReg(wire, addr, REG_AUTOCFG_LSL, 130) &&
         writeReg(wire, addr, REG_AUTOCFG_TL, 180) &&
         writeReg(wire, addr, REG_AUTOCFG_CTRL0, 0x0B);  // ACE + ARE on
  } else {
    ok = writeReg(wire, addr, REG_AUTOCFG_CTRL0, 0x00);
  }
  return writeReg(wire, addr, REG_ECR, (uint8_t)ecr) && ok;
}

bool setAnalogConfig(TwoWire &wire, uint8_t addr, uint8_t afeCfg, uint8_t filterCfg) {
  const int ecr = readReg(wire, addr, REG_ECR);
  if (ecr < 0) {
    return false;
  }
  // These registers are only guaranteed writable with sensing stopped.
  if (!writeReg(wire, addr, REG_ECR, 0x00)) {
    return false;
  }
  const bool ok = writeReg(wire, addr, REG_AFE_CFG, afeCfg) &&
                  writeReg(wire, addr, REG_FILTER_CFG, filterCfg);
  return writeReg(wire, addr, REG_ECR, (uint8_t)ecr) && ok;
}

// ---------------------------------------------------------------------------
// Readings
// ---------------------------------------------------------------------------

uint16_t touched(TwoWire &wire, uint8_t addr) {
  const int lo = readReg(wire, addr, REG_TOUCH_STATUS_L);
  const int hi = readReg(wire, addr, REG_TOUCH_STATUS_H);
  if (lo < 0 || hi < 0) {
    return 0;
  }
  // Bits 0..11 are ELE0..ELE11.
  return (uint16_t)((hi << 8) | lo);
}

int filtered(TwoWire &wire, uint8_t addr, uint8_t electrode) {
  if (electrode >= NUM_ELECTRODES) {
    return -1;
  }
  uint8_t buf[2];
  if (!readRegs(wire, addr, REG_FILTERED_BASE + electrode * 2, buf, 2)) {
    return -1;
  }
  // Little endian: buf[0] = Out_L, buf[1] = Out_H. The 10-bit result lives in
  // bits [9:0] of the pair, i.e. the low two bits of Out_L are discarded.
  const uint16_t raw = (uint16_t)(buf[0] | (buf[1] << 8));
  return raw >> 2;
}

int baseline(TwoWire &wire, uint8_t addr, uint8_t electrode) {
  if (electrode >= NUM_ELECTRODES) {
    return -1;
  }
  return readReg(wire, addr, REG_BASELINE_BASE + electrode);
}

int delta(TwoWire &wire, uint8_t addr, uint8_t electrode) {
  const int f = filtered(wire, addr, electrode);
  const int b = baseline(wire, addr, electrode);
  if (f < 0 || b < 0) {
    return INT16_MIN;
  }
  // Positive on touch: the filtered reading falls below the baseline.
  return b - f;
}

bool readDeltas(TwoWire &wire, uint8_t addr, int16_t *deltas) {
  // 12 filtered readings are 2 bytes each (0x04..0x1D); baselines are one
  // byte each (0x1E..0x29). Burst-reading both keeps a 25 Hz calibration
  // frame down to six I2C transactions instead of 64 single-register reads.
  uint8_t filteredBuf[NUM_ELECTRODES * 2];
  uint8_t baselineBuf[NUM_ELECTRODES];
  if (!readRegs(wire, addr, REG_FILTERED_BASE, filteredBuf,
                sizeof(filteredBuf))) {
    return false;
  }
  if (!readRegs(wire, addr, REG_BASELINE_BASE, baselineBuf,
                sizeof(baselineBuf))) {
    return false;
  }
  for (uint8_t ele = 0; ele < NUM_ELECTRODES; ele++) {
    const uint16_t raw =
        (uint16_t)(filteredBuf[ele * 2] | (filteredBuf[ele * 2 + 1] << 8));
    const int filteredValue = raw >> 2;
    deltas[ele] = (int16_t)baselineBuf[ele] - filteredValue;
  }
  return true;
}

}  // namespace mpr121
