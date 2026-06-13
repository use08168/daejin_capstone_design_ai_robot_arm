"""
노트북 ↔ Arduino 시리얼 브리지.

설계 원칙: 아두이노는 단순 실행자. 노트북(여기)이 각도→펄스 변환을 마치고
펄스값만 보낸다. 현재 펌웨어(테스트)는 ASCII 명령 `u <ch> <us>`(채널 ch에 us 마이크로초
펄스)를 이해하므로 그대로 사용한다 → 펌웨어 수정 불필요.

카메라 스레드처럼 연결을 프로세스 동안 유지하고, 모든 쓰기는 락으로 직렬화한다.
"""
import threading
import time

import serial  # pyserial

_ser = None
_port = None
_baud = 115200
_want = False          # 사용자가 연결 유지를 원하는 상태 (자동 재연결 판단)
_mon_started = False
_reader_started = False
_reset_count = 0       # 펌웨어 부팅 배너 감지 횟수 = 아두이노 리셋(전압부족 등) 횟수
_lock = threading.Lock()


def is_connected() -> bool:
    return _ser is not None and _ser.is_open


def _open_locked(port, baud):
    """실제 포트 오픈 (락 보유 상태에서 호출). 실패 시 예외."""
    global _ser, _port, _baud
    if _ser is not None:
        try:
            _ser.close()
        except Exception:
            pass
        _ser = None
    # write_timeout: 아두이노가 응답을 멈춰(리셋/브라운아웃 등) 쓰기가 막혀도 무한 대기 안 함.
    s = serial.Serial(port, baud, timeout=0.2, write_timeout=0.4)
    # 포트 오픈 시 DTR 토글로 아두이노가 리셋됨 → 부팅 대기 후 입력 버퍼 비우기
    time.sleep(2.0)
    try:
        s.reset_input_buffer()
        s.write(b"\n")            # 첫 명령에 붙는 노이즈 바이트 흡수용 더미 개행
        s.flush()
    except Exception:
        pass
    _ser = s
    _port = port
    _baud = int(baud)


def _monitor():
    """연결이 끊기면(쓰기 실패 등) 사용자가 원하는 한 자동으로 다시 연다 → 수동 재연결 불필요."""
    while True:
        time.sleep(2.0)
        if _want and not is_connected() and _port:
            try:
                with _lock:
                    if _want and not is_connected():
                        _open_locked(_port, _baud)
            except Exception:
                pass


def _start_monitor():
    global _mon_started
    if _mon_started:
        return
    _mon_started = True
    threading.Thread(target=_monitor, daemon=True).start()


def _reader():
    """시리얼 수신을 읽어 펌웨어 부팅 배너('===...준비 완료')를 감지한다.
    배너가 나오면 = 아두이노가 리셋된 것(전압 부족/브라운아웃 등) → _reset_count 증가.
    동시에 RX 버퍼를 비워 오버플로도 방지."""
    global _reset_count
    while True:
        ser = _ser
        if ser is None or not getattr(ser, "is_open", False):
            time.sleep(0.3)
            continue
        try:
            line = ser.readline()      # read timeout=0.2s
        except Exception:
            time.sleep(0.3)
            continue
        if line and b"===" in line:    # 부팅 배너에만 있는 표식
            _reset_count += 1


def _start_reader():
    global _reader_started
    if _reader_started:
        return
    _reader_started = True
    threading.Thread(target=_reader, daemon=True).start()


def connect(port: str = "COM9", baud: int = 115200):
    global _want
    with _lock:
        if is_connected() and _port == port:
            _want = True
            return {"ok": True, "port": _port, "already": True}
        _open_locked(port, int(baud))
        _want = True
    _start_monitor()
    _start_reader()
    return {"ok": True, "port": port}


def disconnect():
    global _want, _port
    _want = False          # 자동 재연결 중단
    with _lock:
        _drop()
        _port = None
        return {"ok": True}


def status():
    return {"connected": is_connected(), "port": _port,
            "reconnecting": bool(_want and not is_connected()),
            "resets": _reset_count}


def _write(channel: int, us: int):
    _ser.write(f"u {int(channel)} {int(us)}\n".encode("ascii"))


def _drop():
    """쓰기 실패(연결 끊김) 시 핸들만 닫고 포트 이름은 남겨 재연결을 쉽게 한다."""
    global _ser
    try:
        if _ser is not None:
            _ser.close()
    except Exception:
        pass
    _ser = None


def send_pulse(channel: int, us: int):
    with _lock:
        if not is_connected():
            return {"ok": False, "error": "not connected"}
        try:
            _write(channel, us)
            return {"ok": True}
        except Exception as e:
            _drop()
            return {"ok": False, "error": str(e), "disconnected": True}


def send_many(items):
    """items: [{'channel': int, 'us': int}, ...] — 여러 관절을 한 번에 전송."""
    with _lock:
        if not is_connected():
            return {"ok": False, "error": "not connected"}
        try:
            for it in items:
                _write(it["channel"], it["us"])
            _ser.flush()
            return {"ok": True, "n": len(items)}
        except Exception as e:
            _drop()
            return {"ok": False, "error": str(e), "disconnected": True}
