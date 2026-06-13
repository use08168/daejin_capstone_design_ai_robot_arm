"""
콜드스타트 시각-운동학 자가보정 — 측정 데이터 {관절각 명령 θ, 마커 3D p} 로부터
관절 축(screw axis)을 복원하고 PoE(Product-of-Exponentials) 순기구학(FK) 모델을 세운다.

핵심 산출:
  1. 각 관절의 회전축(방향 ω·축상의 점 q) — 단독 스윕 시 distal 마커가 그리는 원에서 복원
  2. 명령각↔실제회전각 보정계수 k (서보 반전/기어비/각도불일치 흡수)
  3. PoE FK → 임의 관절각에서 말단(그리퍼 장착점) 3D 위치·자세 예측
  4. 바닥/그리퍼 도달 분석 — 말단 높이 vs 바닥평면, 그리퍼 길이 L 추가 시 최저 도달

PoE(공간형): p(θ) = e^{[S1]θ1} e^{[S2]θ2} … e^{[Sn]θn} · p_home
  θi = ki·(cmd_i − home_i)[rad],  Si = 홈자세에서의 관절 i 스크류축

사용: python calibration/coldstart.py [csv경로] [그리퍼길이mm]
"""
import sys

import numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else ".")
from analyze_validation import JOINTS, fit_circle_3d, load

DEG = np.pi / 180
HOME = {"J1": 90., "J2": 0., "J3": 90., "J4": 90., "J5": 180., "J6": 90.}
# 마커별 영향 관절(base→tip). J4는 id5와 id6 사이(데이터로 확인) → id6,id7만 J4 영향.
CHAIN = {1: ["J1"], 2: ["J1", "J2"], 3: ["J1", "J2", "J3"], 4: ["J1", "J2", "J3"],
         5: ["J1", "J2", "J3"], 6: ["J1", "J2", "J3", "J4"],
         7: ["J1", "J2", "J3", "J4", "J5", "J6"]}
FLOOR_Z = 0.0   # 바닥평면 z (id0 베이스 마커가 놓인 테이블면 = 0)


def rodrigues(w, th):
    w = np.asarray(w, float); w = w / np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * (K @ K)


def screw_T(w, q, th):
    """축 방향 w, 축상의 점 q 를 지나는 회전 th 의 4x4 변환."""
    R = rodrigues(w, th)
    T = np.eye(4); T[:3, :3] = R; T[:3, 3] = q - R @ q
    return T


def home_positions(data):
    """홈(기준)자세 = HOME 과 일치하는 자세들의 마커 평균."""
    base = [d for d in data if all(abs(d["ang"].get(j, HOME[j]) - HOME[j]) < 1 for j in JOINTS)]
    ids = sorted({i for d in base for i in d["mk"]})
    return {i: np.mean([d["mk"][i] for d in base if i in d["mk"]], 0) for i in ids}, len(base)


def recover_axis(data, joint, hp):
    """관절 단독 스윕 + 홈점 → 회전축(ω,q) + 각도 보정계수 k.
    distal(실제로 움직이는, span>10mm) 중 가장 말단 마커를 사용."""
    others = [j for j in JOINTS if j != joint]
    sweep = [d for d in data if abs(d["ang"][joint] - HOME[joint]) > 1
             and all(abs(d["ang"].get(o, HOME[o]) - HOME[o]) < 1 for o in others)]
    if not sweep:
        return None
    # 후보 마커: 모든 스윕자세에 보이고 + 이동범위>10mm + 홈위치 존재 → 가장 큰 id
    cand = []
    for i in range(8):
        pts = [d["mk"][i] for d in sweep if i in d["mk"]]
        # distal(이동>10mm) + 점 충분(홈점이 1개 더해짐) + 홈위치 존재
        if len(pts) >= 2 and i in hp and np.linalg.norm(np.ptp(pts, 0)) > 10:
            cand.append(i)
    if not cand:
        return None
    m = max(cand)
    # 데이터점 = 홈(θ=home) + 스윕점들(해당 마커 보이는 것만)
    angs = [HOME[joint]] + [d["ang"][joint] for d in sweep if m in d["mk"]]
    pts = [hp[m]] + [d["mk"][m] for d in sweep if m in d["mk"]]
    if len(set(angs)) < 3:
        return None
    center, r, normal, _ = fit_circle_3d(pts)
    # 각도 보정계수 k: 축 normal 기준 관측 회전각 ≈ k·(cmd−home)[rad]
    base_vec = pts[0] - center
    obs, cmd = [], []
    for a, p in zip(angs, pts):
        v = p - center
        s = np.arctan2(np.dot(normal, np.cross(base_vec, v)), np.dot(base_vec, v))
        obs.append(s); cmd.append((a - angs[0]) * DEG)
    obs, cmd = np.array(obs), np.array(cmd)
    k = float(cmd @ obs / (cmd @ cmd))
    resid = float(np.sqrt(np.mean((obs - k * cmd) ** 2)) / DEG)  # 각도 잔차(deg)
    n = len(set(angs))
    # 신뢰 조건: 각잔차<5° + 각도≥4 + 반경>50mm(축에서 충분히 떨어진 마커)
    reliable = (resid < 5.0) and (n >= 4) and (r > 50)
    return {"w": normal, "q": center, "r": r, "k": k, "marker": m,
            "n": n, "ang_resid_deg": resid, "reliable": reliable}


def fk(axes, hp, marker, cmd):
    """PoE FK: 마커 i 의 홈위치를 명령 cmd 자세로 변환한 3D 위치."""
    p = np.append(hp[marker], 1.0)
    T = np.eye(4)
    for j in CHAIN[marker]:
        ax = axes.get(j)
        if ax is None or not ax["reliable"]:   # 미복원/불량 관절 → 홈 유지(항등)
            continue
        th = ax["k"] * (cmd[j] - HOME[j]) * DEG
        T = T @ screw_T(ax["w"], ax["q"], th)
    return (T @ p)[:3]


def fk_R(axes, marker, cmd):
    """말단 회전(방향 벡터 변환용) — 영향 관절들의 회전 누적."""
    R = np.eye(3)
    for j in CHAIN[marker]:
        ax = axes.get(j)
        if ax is None or not ax["reliable"]:
            continue
        R = R @ rodrigues(ax["w"], ax["k"] * (cmd[j] - HOME[j]) * DEG)
    return R


def validate(data, axes, hp):
    """단독관절 자세에서 FK 예측 vs 측정 잔차(말단 id7 우선, 가려지면 id6)."""
    errs = []
    for d in data:
        moved = [j for j in JOINTS if abs(d["ang"][j] - HOME[j]) > 1]
        if not moved or any(j not in axes or not axes[j]["reliable"] for j in moved):
            continue
        for m in (7, 6):
            if m in d["mk"]:
                p = fk(axes, hp, m, d["ang"])
                errs.append(np.linalg.norm(p - d["mk"][m]))
                break
    errs = np.array(errs)
    return (float(errs.mean()), float(errs.max()), len(errs)) if len(errs) else (0, 0, 0)


def floor_analysis(data, axes, hp, grip_len):
    """바닥/그리퍼 도달 분석.
    (A) 측정값에서 실제 가장 낮았던 말단 높이
    (B) 모델 예측 — J2/J3/J4 스윕 시 말단 최저 높이 + 그리퍼 팁 + 충돌 여부"""
    print(f"\n=== 바닥 도달 분석 (바닥평면 z={FLOOR_Z:.0f}mm, 그리퍼 길이 L={grip_len:.0f}mm) ===")

    # (A) 측정값 기준 — 신뢰도 최상(실측)
    low = min(((d["mk"][7][2], d) for d in data if 7 in d["mk"]), key=lambda t: t[0])
    z, d = low
    pose = ", ".join(f"{j}{int(d['ang'][j])}" for j in JOINTS)
    print(f"[측정] 실측 최저 말단(id7) 높이 = {z:.1f}mm  @ {pose}")
    # 그 자세의 측정된 그리퍼 방향(id6→id7)으로 팁 추정 — 실측 기반(신뢰)
    if 6 in d["mk"] and grip_len > 0:
        u = d["mk"][7] - d["mk"][6]; u = u / np.linalg.norm(u)
        tip_z = d["mk"][7][2] + grip_len * u[2]
        print(f"[측정] 그 자세 그리퍼 팁(L={grip_len:.0f}) 높이 ≈ {tip_z:.1f}mm "
              f"(팁 방향 z성분 {u[2]:+.2f} → 팔이 {'아래' if u[2] < -0.3 else '수평' if abs(u[2]) <= 0.3 else '위'} 향함)")

    # (B) 모델 예측 — 신뢰 가능한 J2/J3/J4 축이 있어야 의미
    if not all(axes.get(j) and axes[j]["reliable"] for j in ("J2", "J3", "J4")):
        miss = [j for j in ("J2", "J3", "J4") if not (axes.get(j) and axes[j]["reliable"])]
        print(f"[모델] {'/'.join(miss)} 축 신뢰불가 → 예측 보류. "
              f"→ 아래 방향(팔이 바닥을 향하는) 전용 스윕 데이터 필요(아래 권고 참조).")
        return
    if 7 not in hp or 6 not in hp:
        print("[모델] 말단 홈위치 부족 → 예측 생략")
        return
    u_home = hp[7] - hp[6]; u_home = u_home / np.linalg.norm(u_home)   # 그리퍼 방향(말단 링크축)
    rng = {"J2": range(0, 91, 5), "J3": range(40, 146, 5), "J4": range(40, 146, 5)}
    best = None
    for j2 in rng["J2"]:
        for j3 in rng["J3"]:
            for j4 in rng["J4"]:
                cmd = dict(HOME); cmd.update({"J2": j2, "J3": j3, "J4": j4})
                tip = fk(axes, hp, 7, cmd)
                d_world = fk_R(axes, 7, cmd) @ u_home          # 현재 그리퍼 방향
                grip = tip + grip_len * d_world                # 그리퍼 팁
                if best is None or grip[2] < best[0]:
                    best = (grip[2], tip[2], cmd, grip, tip)
    gz, tz, cmd, grip, tip = best
    pose = ", ".join(f"{j}{int(cmd[j])}" for j in ("J2", "J3", "J4"))
    print(f"[모델] 스윕 범위 내 말단 최저 높이 = {tz:.1f}mm  @ {pose}")
    print(f"[모델] 그리퍼 팁(L={grip_len:.0f}) 최저 높이 = {gz:.1f}mm")
    margin = gz - FLOOR_Z
    if margin < 0:
        print(f"  ⚠ 바닥 침범 {abs(margin):.1f}mm — 이 자세는 충돌. J3/J4 하한을 올려야 함.")
    else:
        print(f"  ✓ 바닥까지 여유 {margin:.1f}mm")
    print("  ※ 스윕 범위 밖은 외삽(모델 예측, 미검증). J5/J6(손목)은 홈 고정 가정.")


def main(path, grip_len):
    data = load(path)
    hp, nbase = home_positions(data)
    print(f"콜드스타트: {len(data)}자세 · 홈 {nbase}회 평균 · 마커 {sorted(hp)}")

    axes = {}
    print("\n=== 관절 축 복원 (screw axis) ===")
    for j in ["J1", "J2", "J3", "J4", "J5", "J6"]:
        ax = recover_axis(data, j, hp)
        if ax is None:
            print(f"  {j}: 복원 불가(distal 마커 가려짐/스윕 없음)")
            continue
        axes[j] = ax
        w = ax["w"]
        flag = "신뢰 OK" if ax["reliable"] else "불량(제외)"
        print(f"  {j}: 축 [{w[0]:+.2f},{w[1]:+.2f},{w[2]:+.2f}]  "
              f"반경 {ax['r']:.0f}mm  k={ax['k']:+.3f}  "
              f"(id{ax['marker']}, {ax['n']}각, 잔차 {ax['ang_resid_deg']:.2f}°) → {flag}")

    mean, mx, n = validate(data, axes, hp)
    print(f"\n=== FK 검증 (단독관절 자세 {n}개) ===")
    print(f"  말단 위치 예측 잔차: 평균 {mean:.1f}mm · 최대 {mx:.1f}mm  (측정잡음 바닥 ≈0.3mm)")

    floor_analysis(data, axes, hp, grip_len)


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else r"calibration/validation_data/run2_30pose.csv"
    g = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    main(p, g)
