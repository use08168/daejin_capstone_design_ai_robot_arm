"""6단계 스윕 데이터 → 관절별 보정계수 k → 펄스 보정 산출.

원리:
  관측 회전각 ≈ k · (명령각 − 기준각)   ... k = '명령 1도당 실제 몇 도 도는가'
  - k>1 : 명령보다 더 돈다(중력 sag 등) → 보정 필요
  - k<1 : 덜 돈다
  목표각 θ 를 실제로 달성하려면:  보정명령 θ_cmd = ref + (θ − ref)/k
  실제 전송 펄스 = _ang_to_us(ch, θ_cmd)   (nominal _SERVO_CAL 유지, 명령만 보정)

k 추출: 한 관절만 변하는 부분스윕(나머지 명령각 동일)에서 distal 마커가 그린 원호를
  fit_circle_3d 로 적합 → 회전각 obs vs 명령각 cmd 의 기울기 = k. (coldstart 방식)

실행: python calibration/joint_correct.py
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_validation import fit_circle_3d   # noqa: E402

DEG = np.pi / 180
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "joint_sweep.json")

# 마커 → 영향 관절 (coldstart.CHAIN)
CHAIN = {0: [], 1: ["J1"], 2: ["J1", "J2"], 3: ["J1", "J2", "J3"], 4: ["J1", "J2", "J3"],
         5: ["J1", "J2", "J3"], 6: ["J1", "J2", "J3", "J4"],
         7: ["J1", "J2", "J3", "J4", "J5", "J6"]}
# 실측 서보 펄스(채널별 us0/us180) — views._SERVO_CAL 과 동일
SERVO_CAL = {0: [600, 2740], 1: [530, 2670], 2: [520, 2700], 3: [540, 2720], 4: [600, 2750], 5: [560, 2750]}
JCH = {"J1": 0, "J2": 1, "J3": 2, "J4": 3, "J5": 4, "J6": 5}


def ang_to_us(ch, ang):
    a = max(0.0, min(180.0, 180.0 - ang))
    us0, us180 = SERVO_CAL[ch]
    return round(us0 + (a / 180.0) * (us180 - us0))


def _k_from_subsweep(angs, pts):
    """부분스윕(명령각 angs, distal 마커 3D pts) → (k, 각잔차°, n)."""
    center, r, normal, _ = fit_circle_3d(pts)
    base = pts[0] - center
    obs, cmd = [], []
    for a, p in zip(angs, pts):
        v = p - center
        s = np.arctan2(np.dot(normal, np.cross(base, v)), np.dot(base, v))
        obs.append(s); cmd.append((a - angs[0]) * DEG)
    obs, cmd = np.array(obs), np.array(cmd)
    if cmd @ cmd < 1e-9:
        return None
    k = float(cmd @ obs / (cmd @ cmd))
    resid = float(np.sqrt(np.mean((obs - k * cmd) ** 2)) / DEG)
    return k, resid, len(set(angs)), float(r)


def extract_joint(poses, joint):
    """관절 joint 의 부분스윕들을 모아 k 추정. (k_mean, 표본, 메모)"""
    others = [j for j in ("J1", "J2", "J3", "J4") if j != joint]
    groups = {}
    for p in poses:
        key = tuple(round(p["cmd"][o], 1) for o in others)
        groups.setdefault(key, []).append(p)
    cand_markers = [m for m, js in CHAIN.items() if joint in js]   # 이 관절 영향 마커(말단부터)
    ks = []
    for key, grp in groups.items():
        if len({round(p["cmd"][joint], 1) for p in grp}) < 3:      # 부분스윕 = 3각 이상
            continue
        for m in sorted(cand_markers, reverse=True):               # 가장 말단부터
            sub = [(p["cmd"][joint], p["markers"].get(str(m))) for p in grp if str(m) in p["markers"]]
            sub = [(a, np.array(v)) for a, v in sub if v]
            if len({round(a, 1) for a, _ in sub}) < 3:
                continue
            pts = [v for _, v in sub]
            if np.linalg.norm(np.ptp(pts, 0)) < 10:                 # 이동 충분해야(축에서 떨어진 마커)
                continue
            res = _k_from_subsweep([a for a, _ in sub], pts)
            if res and res[1] < 5.0 and res[3] > 30:               # 잔차<5°, 반경>30mm
                ks.append((res[0], res[2], m))
            break
    if not ks:
        return None
    kv = np.array([k for k, _, _ in ks])
    return {"k": float(np.mean(kv)), "k_std": float(np.std(kv)), "n_sub": len(ks),
            "markers": sorted({m for _, _, m in ks})}


def main():
    d = json.load(open(SRC, encoding="utf-8"))
    poses = d.get("poses", [])
    print(f"스윕 {len(poses)}자세 · frame={poses[0].get('frame') if poses else '-'}")
    print("\n=== 관절별 보정계수 k (명령 1°당 실제 회전°) ===")
    corr = {}
    for j in ("J1", "J2", "J3", "J4"):
        r = extract_joint(poses, j)
        if r is None:
            print(f"  {j}: 단일관절 부분스윕 없음 → 격자에서 분리 불가 (단일관절 스윕 필요)")
            continue
        corr[j] = r
        tag = "더 돈다(보정 필요)" if r["k"] > 1.02 else "덜 돈다(보정 필요)" if r["k"] < 0.98 else "양호"
        print(f"  {j}: k={r['k']:.3f} ±{r['k_std']:.3f}  ({r['n_sub']}개 부분스윕, id{r['markers']}) → {tag}")

    print("\n=== 펄스 보정 예시 (nominal 유지, 명령만 보정) ===")
    for j, r in corr.items():
        ch = JCH[j]; k = r["k"]; ref = 90.0
        print(f"  [{j}] ch{ch}, k={k:.3f}, 기준 {ref:.0f}° · 펄스식 us = {SERVO_CAL[ch][0]}+((180-ang)/180)*({SERVO_CAL[ch][1]}-{SERVO_CAL[ch][0]})")
        print(f"    {'목표각':>6} {'보정명령':>8} {'nominal펄스':>10} {'보정펄스':>9}")
        for tgt in (ref - 40, ref - 20, ref, ref + 20, ref + 40):
            cmd = ref + (tgt - ref) / k
            print(f"    {tgt:6.0f}° {cmd:7.1f}° {ang_to_us(ch, tgt):9d}us {ang_to_us(ch, cmd):8d}us")
    if not corr:
        print("  (추출된 관절 없음)")
    print("\n※ k는 '기울기(게인)' 보정. 절대 offset(상수 편차)은 절대기준이 필요해 별도. "
          "현재 격자는 J1·J4만 분리됨 — J2·J3(중력 sag)은 단일관절 스윕을 추가하면 같은 방식으로 산출.")


if __name__ == "__main__":
    main()
