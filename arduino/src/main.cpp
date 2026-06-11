/**
 * 서보 구동 검증 스케치 — 채널별 1개씩 각도 제어 / 스윕
 *
 * 목적: PCA9685 채널에 연결된 서보가 각도 명령에 따라 움직이는지 1개씩 확인.
 *       채널 ↔ 관절(J1~J7) 매핑도 함께 검증.
 *
 * 안전:
 *   - 부팅 직후 모든 채널 PWM OFF(무신호) → 서보는 가만히 있음(limp).
 *   - 명령을 받은 채널만 움직인다. 스윕은 느리게(2°/25ms) 진행.
 *   - 각도 범위는 설계 범위인 1000~2000us(= test 0~180)로 보수적으로 제한.
 *     이상음(버징)·정지(스톨) 발생 시 즉시 SMPS 전원 차단.
 *
 * 시리얼 명령 (115200, 줄 단위):
 *   a <ch> <angle>   채널 ch 를 angle(0~180)로 1회 이동
 *   s <ch>           채널 ch 느린 스윕 (90→0→90→180→90)
 *   n <ch>           채널 ch 중립(90)
 *   r <ch>           채널 ch 무신호(limp, 힘 풀기)
 *   r all            전체 채널 무신호
 *
 * 참고: docs/serial_protocol.md, docs/conventions.md (PWM 매핑)
 */
#include <Arduino.h>
#include <Wire.h>

static const uint8_t PCA = 0x40;
#define REG_MODE1     0x00
#define REG_PRESCALE  0xFE
#define REG_LED0_ON_L 0x06
static const uint8_t NUM_CH = 16;

static void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(PCA);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

static uint8_t readReg(uint8_t reg) {
  Wire.beginTransmission(PCA);
  Wire.write(reg);
  Wire.endTransmission();
  Wire.requestFrom(PCA, (uint8_t)1);
  return Wire.read();
}

static void pcaSetFreq(float freq) {
  float prescaleval = 25000000.0f / (4096.0f * freq) - 1.0f;
  uint8_t prescale = (uint8_t)floor(prescaleval + 0.5f);
  writeReg(REG_MODE1, 0x00);            // 리셋: SLEEP 비트 해제(깨움)
  delay(5);
  writeReg(REG_MODE1, 0x10);            // SLEEP=1 (prescale 변경에 필요)
  writeReg(REG_PRESCALE, prescale);
  writeReg(REG_MODE1, 0x00);            // SLEEP=0 (오실레이터 가동)
  delay(5);
  writeReg(REG_MODE1, 0xA0);            // RESTART + auto-increment, SLEEP=0
}

static void pcaSetPWM(uint8_t ch, uint16_t on, uint16_t off) {
  Wire.beginTransmission(PCA);
  Wire.write(REG_LED0_ON_L + 4 * ch);
  Wire.write(on & 0xFF);
  Wire.write(on >> 8);
  Wire.write(off & 0xFF);
  Wire.write(off >> 8);
  Wire.endTransmission();
}

// 50Hz, 주기 20000us, 12bit(4096)
static uint16_t usToCount(uint16_t us) {
  return (uint16_t)((uint32_t)us * 4096 / 20000);
}

// test 각도 0~180 → 1000~2000us (설계 범위, 보수적)
static uint16_t angleToUs(int angle) {
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;
  return (uint16_t)(1000 + (uint32_t)angle * 1000 / 180);
}

static void setAngle(uint8_t ch, int angle) {
  pcaSetPWM(ch, 0, usToCount(angleToUs(angle)));
}

static void releaseCh(uint8_t ch) {
  pcaSetPWM(ch, 0, 0);  // 무신호 → limp
}

static void slowMove(uint8_t ch, int from, int to) {
  int step = (to >= from) ? 2 : -2;
  for (int a = from; (step > 0) ? (a <= to) : (a >= to); a += step) {
    setAngle(ch, a);
    if (a % 30 == 0) { Serial.print(F("  ch")); Serial.print(ch); Serial.print(F(" -> ")); Serial.print(a); Serial.println(F(" deg")); }
    delay(25);
  }
}

// --- 와이드 범위(500~2500us, 270deg 서보 가정) 테스트 ---
// 펄스↔각도 캘리브레이션용으로 클램프를 넓게 둠(끝 스톱 없는 엔코더 서보 탐색).
// 50Hz 주기 20000us 이내라면 PCA9685는 출력 가능. 단, 양 끝은 천천히 접근할 것.
static const int US_MIN = 300;
static const int US_MAX = 4000;
static void setUs(uint8_t ch, int us) {
  if (us < US_MIN) us = US_MIN;
  if (us > US_MAX) us = US_MAX;
  pcaSetPWM(ch, 0, usToCount((uint16_t)us));
}

static void slowMoveUs(uint8_t ch, int from, int to) {
  int step = (to >= from) ? 20 : -20;
  for (int u = from; (step > 0) ? (u <= to) : (u >= to); u += step) {
    setUs(ch, u);
    if (u % 200 < 20) { Serial.print(F("  ch")); Serial.print(ch); Serial.print(F(" -> ")); Serial.print(u); Serial.println(F(" us")); }
    delay(30);
  }
}

static void wideSweep(uint8_t ch) {
  Serial.print(F("[wide] ch")); Serial.print(ch); Serial.println(F(" 중앙(1500us)으로 이동"));
  setUs(ch, 1500); delay(700);
  Serial.println(F("[wide] -> 2500us 방향(천천히)"));
  slowMoveUs(ch, 1500, 2500);
  slowMoveUs(ch, 2500, 1500);
  Serial.println(F("[wide] -> 500us 방향(천천히)"));
  slowMoveUs(ch, 1500, 500);
  slowMoveUs(ch, 500, 1500);
  Serial.print(F("[wide] ch")); Serial.print(ch); Serial.println(F(" 완료 (중앙 유지)"));
}

static void sweep(uint8_t ch) {
  Serial.print(F("[sweep] ch")); Serial.print(ch); Serial.println(F(" 시작: 중립(90)으로 이동"));
  setAngle(ch, 90); delay(600);
  slowMove(ch, 90, 0);
  slowMove(ch, 0, 90);
  slowMove(ch, 90, 180);
  slowMove(ch, 180, 90);
  Serial.print(F("[sweep] ch")); Serial.print(ch); Serial.println(F(" 완료 (중립 유지)"));
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Wire.begin();
  pcaSetFreq(50.0f);
  for (uint8_t c = 0; c < NUM_CH; c++) releaseCh(c);  // 전 채널 무신호로 시작

  Serial.println();
  Serial.println(F("=== 서보 구동 검증 준비 완료 (전 채널 무신호) ==="));
  Serial.println(F("명령: 'a <ch> <ang>' | 's <ch>' | 'n <ch>' | 'r <ch>' | 'r all'"));
}

void loop() {
  static char buf[24];
  static uint8_t idx = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (idx == 0) continue;
      buf[idx] = '\0';
      idx = 0;
      // 파싱
      char cmd = buf[0];
      if (cmd == 'r' && buf[1] == ' ' && buf[2] == 'a') {
        for (uint8_t c2 = 0; c2 < NUM_CH; c2++) releaseCh(c2);
        Serial.println(F("[ok] 전 채널 무신호(limp)"));
      } else {
        char *p = buf + 1;
        while (*p == ' ') p++;
        int ch = atoi(p);                 // 첫 숫자 = 채널
        char *q = strchr(p, ' ');         // 두 번째 숫자 = 각도(있으면)
        int ang = q ? atoi(q + 1) : -1;
        bool hasAng = (q != NULL);
        if (ch < 0 || ch >= NUM_CH) { Serial.println(F("[err] ch 범위(0~15)")); }
        else if (cmd == 'a' && hasAng) { setAngle(ch, ang); Serial.print(F("[ok] a ch")); Serial.print(ch); Serial.print(F(" -> ")); Serial.print(ang); Serial.println(F(" deg")); }
        else if (cmd == 's') { sweep(ch); }
        else if (cmd == 'w') { wideSweep(ch); }
        else if (cmd == 'u' && hasAng) { setUs(ch, ang); Serial.print(F("[ok] u ch")); Serial.print(ch); Serial.print(F(" -> ")); Serial.print(ang); Serial.println(F(" us")); }
        else if (cmd == 'n') { setAngle(ch, 90); Serial.print(F("[ok] n ch")); Serial.print(ch); Serial.println(F(" -> 90")); }
        else if (cmd == 'r') { releaseCh(ch); Serial.print(F("[ok] r ch")); Serial.print(ch); Serial.println(F(" limp")); }
        else { Serial.println(F("[err] 알 수 없는 명령")); }
      }
    } else if (idx < sizeof(buf) - 1) {
      buf[idx++] = c;
    }
  }
}
