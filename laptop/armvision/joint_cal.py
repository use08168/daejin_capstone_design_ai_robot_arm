"""
관절 보정 스윕 — 안전 영역 정의 + 스윕 자세 생성 (트랙 2).

실측 안전·가시성 박스 (사용자 확인 2026-06-21):
- J5 = 180° 고정 (모든 ArUco 보임), J6·J7 고정 (J6 ArUco 없음)
- J2 ∈ [25, 70]   (25°↓ 바닥 쓸림: id7이 지면 ~220–250mm / 70°↑ 마커 가림)
- J3 범위는 J2에 의존:      J2=25 → [20,120],  J2=70 → [60,160]   (선형 보간)
- J4 범위는 (J2,J3)에 의존 (양선형 보간, 4코너):
    (J2,J3)=(70,60)→[0,90], (70,160)→[80,170], (25,20)→[0,90], (25,120)→[90,180]
- J1 은 스윕(수직축이라 중력 sag 없음·백래시/게인 확인용) — 좌·우 FOV 제한은
  실제 스윕에서 마커 미검출 샘플을 건너뛰어 처리(여기선 후보 범위만).

안쪽으로 MARGIN(°) 여유를 둬 절대 한계를 절대 안 건드린다.
이 모듈은 순수 함수(하드웨어/카메라 무관) — 단위 테스트 가능.
"""

J2_MIN, J2_MAX = 25.0, 70.0
J5_FIXED = 180.0
J6_FIXED = 90.0
J1_RANGE = (60.0, 120.0)   # 후보 스윕 범위(미검출 샘플은 실 스윕에서 skip)
MARGIN = 4.0               # 한계 안쪽 여유(°)


def _lerp(a, b, t):
    return a + (b - a) * t


def _f2(j2):
    return (min(J2_MAX, max(J2_MIN, j2)) - J2_MIN) / (J2_MAX - J2_MIN)   # 0@25 .. 1@70


def j3_bounds(j2):
    """J2에서 J3 [lo, hi] (margin 미적용 원시 한계)."""
    f = _f2(j2)
    return _lerp(20.0, 60.0, f), _lerp(120.0, 160.0, f)


def j4_bounds(j2, j3):
    """(J2,J3)에서 J4 [lo, hi] — J3는 자기 범위 내 비율로 정규화 후 양선형 보간."""
    f2 = _f2(j2)
    lo3, hi3 = j3_bounds(j2)
    f3 = 0.0 if hi3 <= lo3 else (min(hi3, max(lo3, j3)) - lo3) / (hi3 - lo3)
    j4_lo = f3 * ((1 - f2) * 90.0 + f2 * 80.0)
    j4_hi = (1 - f3) * 90.0 + f3 * ((1 - f2) * 180.0 + f2 * 170.0)
    return j4_lo, j4_hi


def _safe_range(lo, hi, m=MARGIN):
    """안쪽 여유 적용. 너무 좁으면 중앙 한 점."""
    a, b = lo + m, hi - m
    if a > b:
        mid = (lo + hi) / 2.0
        return mid, mid
    return a, b


def safe_j3(j2):
    return _safe_range(*j3_bounds(j2))


def safe_j4(j2, j3):
    return _safe_range(*j4_bounds(j2, j3))


def is_safe(j1, j2, j3, j4):
    """명령 자세가 안전 영역(여유 포함) 안인가 — 실 구동 직전 최종 가드."""
    if not (J2_MIN + MARGIN - 1e-6 <= j2 <= J2_MAX - MARGIN + 1e-6):
        return False
    lo3, hi3 = safe_j3(j2)
    if not (lo3 - 1e-6 <= j3 <= hi3 + 1e-6):
        return False
    lo4, hi4 = safe_j4(j2, j3)
    if not (lo4 - 1e-6 <= j4 <= hi4 + 1e-6):
        return False
    if not (0.0 <= j1 <= 180.0):
        return False
    return True


def _grid(lo, hi, n):
    if n <= 1 or hi <= lo:
        return [round((lo + hi) / 2.0, 1)]
    return [round(lo + (hi - lo) * i / (n - 1), 1) for i in range(n)]


def generate_sweep(n2=4, n3=4, n4=3, n1=3, j1_range=J1_RANGE):
    """안전 영역을 격자로 훑는 스윕 자세 목록 생성. 각 항목 {J1..J6}. is_safe 통과분만."""
    js1 = _grid(j1_range[0], j1_range[1], n1)
    poses = []
    for j2 in _grid(J2_MIN + MARGIN, J2_MAX - MARGIN, n2):   # 여유 적용 범위에서 격자
        lo3, hi3 = safe_j3(j2)
        for j3 in _grid(lo3, hi3, n3):
            lo4, hi4 = safe_j4(j2, j3)
            for j4 in _grid(lo4, hi4, n4):
                for j1 in js1:
                    if is_safe(j1, j2, j3, j4):
                        poses.append({"J1": j1, "J2": j2, "J3": j3, "J4": j4,
                                      "J5": J5_FIXED, "J6": J6_FIXED})
    return poses


SAFE_HOME = {"J1": 90.0, "J2": 45.0, "J3": 80.0, "J4": 90.0, "J5": J5_FIXED, "J6": J6_FIXED}   # 스윕 시작 전 권장 안전 자세(박스 내)

_J1234 = ("J1", "J2", "J3", "J4")


def transition_order(cur, tgt):
    """cur(안전)→tgt(안전)를 '단일 관절 이동'들의 순서로. 모든 중간 full-config가 안전한
    순서를 반환(없으면 None=그 자세 skip). 단일 관절 이동은 양 끝이 안전하면 경로 전체 안전
    (관절별 안전집합=구간)이라, 끝 자세만 is_safe로 검사하면 충분."""
    from itertools import permutations
    diff = [j for j in _J1234 if abs(cur.get(j, 0.0) - tgt[j]) > 0.05]
    if not diff:
        return []
    base = {**cur, "J5": J5_FIXED, "J6": J6_FIXED}
    for perm in permutations(diff):
        c = dict(base); seq = []; ok = True
        for j in perm:
            c2 = dict(c); c2[j] = tgt[j]
            if not is_safe(c2["J1"], c2["J2"], c2["J3"], c2["J4"]):
                ok = False; break
            seq.append((j, tgt[j])); c = c2
        if ok:
            return seq
    return None


def single_joint_sweep(n_per=7):
    """관절별 단일 스윕(한 관절만 n_per점, 나머지 고정) — 깨끗한 k 추출용.
    중력 sag 자세 의존(B) 위해 J2·J3·J4는 다른 관절을 몇 설정으로 바꿔가며 반복.
    is_safe 통과분만. 각 블록은 '나머지 관절이 같은' 부분스윕이라 원호 적합이 안정적."""
    out = []

    def add(joint, lo, hi, fixed):
        for v in _grid(lo, hi, n_per):
            p = {**SAFE_HOME, **fixed, joint: round(v, 1)}
            if is_safe(p["J1"], p["J2"], p["J3"], p["J4"]):
                out.append(p)

    for fx in ({"J2": 45, "J3": 80, "J4": 90}, {"J2": 35, "J3": 60, "J4": 70}):   # J1 (수직축)
        add("J1", J1_RANGE[0], J1_RANGE[1], fx)
    for (j3, j4) in ((80, 90), (60, 70), (110, 110)):                              # J2 (자세 의존)
        add("J2", J2_MIN + MARGIN, J2_MAX - MARGIN, {"J3": j3, "J4": j4})
    for j2 in (45, 60):                                                            # J3
        lo, hi = safe_j3(j2); add("J3", lo, hi, {"J2": j2, "J4": 90})
    for (j2, j3) in ((45, 80), (60, 120)):                                         # J4
        lo, hi = safe_j4(j2, j3); add("J4", lo, hi, {"J2": j2, "J3": j3})
    return out


def plan_summary(n_per=7):
    """스윕 계획 요약(움직임 없음·미리보기용) — 단일 관절 스윕."""
    poses = single_joint_sweep(n_per)
    def rng(key):
        vs = [p[key] for p in poses]
        return [min(vs), max(vs)] if vs else [None, None]
    # 어떤 관절이 변하는 블록인지 카운트(나머지 고정 기준)
    return {
        "count": len(poses),
        "ranges": {k: rng(k) for k in ("J1", "J2", "J3", "J4")},
        "fixed": {"J5": J5_FIXED, "J6": J6_FIXED},
        "n_per": n_per, "mode": "single-joint", "margin_deg": MARGIN,
        "sample": poses[:8],
    }


if __name__ == "__main__":   # 자가 검증 (하드웨어 없이)
    # 1) 코너가 실측값을 재현하나
    assert abs(j3_bounds(25)[0] - 20) < 1e-9 and abs(j3_bounds(25)[1] - 120) < 1e-9
    assert abs(j3_bounds(70)[0] - 60) < 1e-9 and abs(j3_bounds(70)[1] - 160) < 1e-9
    for (j2, j3, lo, hi) in [(70, 60, 0, 90), (70, 160, 80, 170), (25, 20, 0, 90), (25, 120, 90, 180)]:
        b = j4_bounds(j2, j3)
        assert abs(b[0] - lo) < 1e-9 and abs(b[1] - hi) < 1e-9, (j2, j3, b)
    print("[corners] OK — 실측 코너 재현")
    # 2) 생성된 모든 자세가 안전한가
    poses = generate_sweep()
    assert all(is_safe(p["J1"], p["J2"], p["J3"], p["J4"]) for p in poses)
    print(f"[sweep] {len(poses)}자세 · 모두 안전영역 내 OK")
    import json
    print(json.dumps(plan_summary(), ensure_ascii=False, indent=1))
