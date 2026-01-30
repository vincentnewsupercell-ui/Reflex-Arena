# -*- coding: utf-8 -*-
"""
Study Toolkit (大學科目版 / 起點=12日 / 手動輸入日期
- 含今日限定 Bonus（登入禮）
- 30:00 專注回合（每回合固定 +25 EXP）
- 等級 & 角色稱號 & EXP 血條（含 EXP 動畫）
- 收尾儀式：今日總結（成就角）
"""


import json
import os
import random
import time
from datetime import datetime

# ---- 多益戰略指南（原樣保留）----
GUIDE_TEXT = """《      指南》
 （略）
"""

def show_toeic_guide(save=True, path="uni_study_guide.txt"):
    print("\n" + GUIDE_TEXT)
    if save:
        with open(path, "w", encoding="utf-8") as f:
            f.write(GUIDE_TEXT)
        print(f"\n📄 已另存成檔案：{path}")

# ---------- 共用設定 ----------
PROGRESS_FILE = "uni_progress.json"
HISTORY_FILE = "uni_history.json"
CHART_FILE = "uni_progress.png"
BONUS_FILE = "uni_daily_bonus.json"  # 今日登入禮 + 回合進度 + 當日 EXP + 登入抽獎元
EXP_FILE   = "uni_exp.json"          # 全局等級 EXP

# 每回合固定 +25 EXP
EXP_PER_ROUND = 25

FIELDS = [
    ("calculus", "微積分"),
    ("data_structures", "資料結構"),
    ("discrete_math", "離散數學"),
    ("circuits", "電子電路"),
]

# ---------- 等級 EXP 升級表（總量 = 3750，後期較難） ----------
# Lv.2~10 ：每級 +10  （9 次，90）
# Lv.11~20：每級 +20  （10 次，200）
# Lv.21~40：每級 +30  （20 次，600）
# Lv.41~60：每級 +40  （20 次，800）
# Lv.61~80：每級 +50  （20 次，1000）
# Lv.81~100：每級 +53 （20 次，1060）
# 總計 = 3750 EXP

LEVEL_SEGMENTS = [
    (2, 10, 10),   # Lv.2~10
    (11, 20, 20),  # Lv.11~20
    (21, 40, 30),  # Lv.21~40
    (41, 60, 40),  # Lv.41~60
    (61, 80, 50),  # Lv.61~80
    (81, 100, 53), # Lv.81~100
]

def _build_level_thresholds():
    """
    依 LEVEL_SEGMENTS 建立等級門檻表。
    Lv.1 = 0 EXP
    Lv.2~100 依區段累加 EXP。
    最後 Lv.100 總量 = 3750 EXP。
    """
    thresholds = {1: 0}  # Lv.1 從 0 EXP 開始
    cur_exp = 0
    for start_lv, end_lv, inc in LEVEL_SEGMENTS:
        for lv in range(start_lv, end_lv + 1):
            cur_exp += inc
            thresholds[lv] = cur_exp
    total_exp = cur_exp  # 3750
    return thresholds, total_exp

LEVEL_THRESHOLDS, LEVEL_TOTAL_EXP = _build_level_thresholds()

# ---------- 共用函式：JSON 存取 ----------
def _load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def _save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------- EXP 狀態 ----------
def load_exp_state():
    return _load_json(EXP_FILE, {"exp": 0})

def save_exp_state(state: dict):
    _save_json(EXP_FILE, state)

def exp_to_level(exp: int) -> int:
    """
    依照 LEVEL_THRESHOLDS 判斷目前等級
    """
    exp = max(0, int(exp))
    current_level = 1
    for lv in range(2, 101):
        if exp >= LEVEL_THRESHOLDS.get(lv, LEVEL_TOTAL_EXP + 1):
            current_level = lv
        else:
            break
    return current_level

def level_progress(exp: int):
    """
    回傳：
      current_level, percent_in_level, overall_percent
    """
    exp = max(0, int(exp))
    lvl = exp_to_level(exp)
    base = LEVEL_THRESHOLDS.get(lvl, 0)
    if lvl >= 100:
        percent_in_level = 100.0
    else:
        next_base = LEVEL_THRESHOLDS.get(lvl + 1, LEVEL_TOTAL_EXP)
        span = max(1, next_base - base)
        percent_in_level = (exp - base) / span * 100.0
    overall_percent = min(100.0, exp / LEVEL_TOTAL_EXP * 100.0)
    return lvl, percent_in_level, overall_percent

def get_role_name(level: int) -> str:
    """
    L1~L25 新手
    L25~L50 穩定學習者
    L50~L80 技術進化者
    L80~L90 學術戰士
    L90~L99 未來創業家
    L100 國際創業家
    """
    if level >= 100:
        return "國際創業家"
    elif level >= 90:
        return "未來創業家"
    elif level >= 80:
        return "學術戰士"
    elif level >= 50:
        return "技術進化者"
    elif level >= 25:
        return "穩定學習者"
    else:
        return "新手"

# ---------- 2) 日期→整數值（以 12 號為起點） ----------
DATE_MAP = {
    1:10, 2:11, 3:12, 4:13, 5:14, 6:16, 7:17, 8:19, 9:21, 10:23,
    11:25, 12:27, 13:30, 14:33, 15:36, 16:39, 17:43, 18:47, 19:51, 20:56,
    21:62, 22:67, 23:74, 24:81, 25:89, 26:97, 27:106, 28:116, 29:127, 30:138,
}

def _seq_index_from_calendar_day(day_of_month: int) -> int:
    """
    把「日(1~31)」換成序列索引 1..30
    12 -> 1, 13 -> 2, ..., 30 -> 19, 31 -> 20, 1 -> 21, ..., 11 -> 30
    """
    if not (1 <= day_of_month <= 31):
        raise ValueError("日需在 1~31 之間")
    return ((day_of_month - 13) % 30) + 1

def lookup_value_by_day_from_12(day_of_month: int) -> int:
    idx = _seq_index_from_calendar_day(day_of_month)
    return DATE_MAP[idx]

# ---------- 3) 學科進度儲存/歷史 ----------
def _clamp01pct(x: float) -> float:
    return max(0.0, min(100.0, float(x)))

def load_progress():
    data = _load_json(PROGRESS_FILE, {})
    # 確保所有科目欄位存在，缺少則以0補足
    return {k: _clamp01pct(data.get(k, 0)) for k, _ in FIELDS}

def save_progress(progress: dict):
    _save_json(PROGRESS_FILE, progress)

def load_history():
    return _load_json(HISTORY_FILE, [])

def save_history(history: list):
    _save_json(HISTORY_FILE, history)

def append_history(progress: dict):
    history = load_history()
    history.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **{k: float(progress.get(k, 0.0)) for k, _ in FIELDS},
    })
    save_history(history)

# ---------- 4) 顯示/圖表 ----------
def _text_bar(pct: float, width: int = 30) -> str:
    pct = _clamp01pct(pct)
    filled = int(round(pct / 100 * width))
    return f"[{'#' * filled}{'-' * (width - filled)}] {pct:5.1f}%"

def show_character_panel(show_title: bool = True):
    """
    等級血條＋角色稱號
    show_title=True：在前面印「致未來工程師／創業家版的你」
    show_title=False：只印等級＆稱號＆血條，不印那行標題
    """
    exp_state = load_exp_state()
    exp_val = int(exp_state.get("exp", 0))
    lvl, _, overall_pct = level_progress(exp_val)
    role = get_role_name(lvl)

    if show_title:
        print("\n致未來工程師／創業家版的你")
    else:
        print()  # 單純換行

    print(f"角色稱號：{role}")
    print(f"等級：Lv.{lvl:3d}   EXP：{exp_val}/{LEVEL_TOTAL_EXP}")
    print(_text_bar(overall_pct))

def show_dashboard(progress: dict):
    # 顯示等級＆名稱，但不印標題行
    show_character_panel(show_title=False)
    print("\n=== 🎯 學科血條進度 ===")
    for k, zh in FIELDS:
        print(f"{zh: <8} {_text_bar(progress[k])}")

def plot_chart(progress: dict):
    try:
        import matplotlib.pyplot as plt
    except Exception:
        print("（提示）未安裝 matplotlib，略過圖表輸出。")
        return
    labels = [zh for _, zh in FIELDS]
    values = [_clamp01pct(progress[k]) for k, _ in FIELDS]
    plt.figure(figsize=(6, 3.6))
    y_positions = range(len(labels))
    plt.barh(y_positions, values)
    plt.yticks(y_positions, labels)
    plt.xlabel("百分比（%）")
    plt.xlim(0, 100)
    plt.title("學習進度")
    plt.tight_layout()
    plt.savefig(CHART_FILE, dpi=150)
    plt.close()
    print(f"🖼️ 已輸出圖表：{CHART_FILE}")

# ---------- EXP 動畫效果 ----------
def _animate_exp_gain(old_exp: int, new_exp: int, delay: float = 0.02):
    """
    在終端上做簡單的 EXP 進度動畫：
    EXP  123/3750  Lv. 10 [###-----]
    """
    old_exp = int(old_exp)
    new_exp = int(new_exp)
    if new_exp <= old_exp:
        return
    diff = new_exp - old_exp
    step = 1 if diff <= 80 else max(1, diff // 80)
    current = old_exp
    while current < new_exp:
        current = min(current + step, new_exp)
        lvl, _, overall_pct = level_progress(current)
        bar = _text_bar(overall_pct)
        print(f"\rEXP {current:4d}/{LEVEL_TOTAL_EXP}  Lv.{lvl:3d} {bar}", end="", flush=True)
        time.sleep(delay)
    print()  # 動畫結束換行

def add_exp(amount: int):
    """
    每讀半小時 +EXP（含動畫）
    """
    state = load_exp_state()
    old_exp = int(state.get("exp", 0))
    new_exp = old_exp + int(amount)
    state["exp"] = new_exp
    save_exp_state(state)
    _animate_exp_gain(old_exp, new_exp)
    return new_exp

# ---------- 5) 趨勢 GUI ----------
def run_trend_gui():
    import tkinter as tk
    from tkinter import messagebox

    try:
        import matplotlib.pyplot as plt
    except Exception:
        messagebox.showinfo("提示", "未安裝 matplotlib，請先安裝：pip install matplotlib")
        return

    def load_hist_sorted():
        hist = load_history()
        if not hist:
            prog = load_progress()
            # 若尚無歷史紀錄且目前進度有數值，則產生初始紀錄
            if any(prog.values()):
                hist = [{"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), **prog}]
                save_history(hist)
        hist.sort(key=lambda x: x.get("timestamp", ""))
        return hist

    def show_trend():
        hist = load_hist_sorted()
        if not hist:
            messagebox.showwarning("提示", "尚無歷史資料（請先更新一次進度）。")
            return
        x_values = range(1, len(hist) + 1)
        for key, label in FIELDS:
            y_values = [float(h.get(key, 0)) for h in hist]
            plt.figure()
            plt.plot(x_values, y_values, marker="o")
            plt.title(f"{label} 趨勢")
            plt.xlabel("紀錄序號")
            plt.ylabel("百分比（%）")
            plt.tight_layout()
        plt.show()

    root = tk.Tk()
    root.title("學習進度趨勢顯示器（大學科目版）")
    tk.Button(root, text="顯示趨勢", width=15, command=show_trend).pack(padx=10, pady=10)
    tk.Button(root, text="關閉", width=15, command=root.destroy).pack(padx=10, pady=5)
    root.mainloop()

# ---------- 6) 今日限定 Bonus（登入禮） + 30 分鐘計時 ----------
# 每回合 30 分鐘，EXP 固定 +25。
# 「登入抽獎」是 +元（15~50），不加 EXP。

BONUS_TASK_POOL = [
    "🔢 微積分：半小時內，把一個重要公式從頭推一次，寫在紙上。",
    "📚 資料結構：半小時內手寫今天最重要的一個函式（例如 push/pop），不看筆記，多寫幾遍。",
    "📐 離散數學：半小時內重畫、重想一個最近學過的證明或推導流程。",
    "💡 電子電路：半小時內畫出一個基本電路，標上元件並快速複習一次原理。",
    "🧠 自由加碼：選一科，半小時內把今天最想補強的一個觀念從頭掃一遍。",
]

def _load_bonus_state():
    return _load_json(BONUS_FILE, {})

def _save_bonus_state(state: dict):
    _save_json(BONUS_FILE, state)

def countdown(seconds: int) -> bool:
    """
    倒數計時，格式 mm:ss。
    回傳 True = 正常結束；False = 被 Ctrl+C 中斷。
    """
    try:
        for remaining in range(seconds, 0, -1):
            m, s = divmod(remaining, 60)
            print(f"\r⏱️ 倒數計時：{m:02d}:{s:02d}", end="", flush=True)
            time.sleep(1)
        print("\r⏱️ 倒數計時：00:00              ")
        return True
    except KeyboardInterrupt:
        print("\n⏹️ 計時已中止（Ctrl+C）。")
        return False

def run_30min_session(state: dict):
    """
    一天主線目標：6 回合，每回合 30 分鐘。
    之後可繼續「額外回合」，每回合固定 +25 EXP。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    if state.get("last_date") != today:
        print("⚠️ 今日登入禮尚未啟動或日期已變更，請先重新抽今日 Bonus。")
        return

    main_rounds = int(state.get("rounds_completed", 0))
    extra_rounds = int(state.get("extra_rounds", 0))
    exp_today = int(state.get("exp_gained_today", 0))

    print("\n📊 目前今日進度：")
    print(f"主線回合：完成 {min(main_rounds, 6)} / 6 回合")
    if extra_rounds > 0:
        print(f"額外回合：{extra_rounds} 回")
    print(f"今日已獲得 EXP：+{exp_today}")
    print(f"今日每完成 1 回合：+{EXP_PER_ROUND} EXP")

    while True:
        if main_rounds < 6:
            label = f"第 {main_rounds + 1} / 6 回合（主線）"
        else:
            label = f"額外加碼回合 #{extra_rounds + 1}"

        print(f"\n▶️ {label} 開始（30 分鐘）")
        ok = countdown(30 * 60)  # 30 分鐘 = 1800 秒

        if not ok:
            print(f"\n📌 目前進度：主線 {min(main_rounds, 6)} / 6，額外 {extra_rounds} 回")
            break

        # 正常完成一回合 → 固定 +25 EXP（含動畫）
        new_exp = add_exp(EXP_PER_ROUND)
        lvl, _, overall_pct = level_progress(new_exp)

        if main_rounds < 6:
            main_rounds += 1
            state["rounds_completed"] = main_rounds
        else:
            extra_rounds += 1
            state["extra_rounds"] = extra_rounds

        exp_today += EXP_PER_ROUND
        state["exp_gained_today"] = exp_today
        _save_bonus_state(state)

        print(f"\n✅ 完成 {min(main_rounds, 6)} / 6 回合（額外 {extra_rounds} 回）")
        print(f"🔼 EXP +{EXP_PER_ROUND}，目前 EXP={new_exp}，等級 Lv.{lvl}（總進度約 {overall_pct:4.1f}% ）")

        ans = input("要再來下一回合嗎？(Enter=繼續 / n=收工)：").strip().lower()
        if ans == "n":
            print(f"📌 收工！今日累積：主線 {min(main_rounds, 6)} / 6，額外 {extra_rounds} 回，EXP +{exp_today}")
            break

def draw_today_bonus():
    """
    抽卡 = 今日限定 Bonus（今日登入禮）
    - 抽到的是「元」（例如 +15 元），不加 EXP
    - 每完成一個 30 分鐘回合固定 +25 EXP
    """
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_bonus_state()
    last_date = state.get("last_date")

    # 顯示角色目標（此處印出大標題行）
    show_character_panel(show_title=True)

    if last_date != today:
        task = random.choice(BONUS_TASK_POOL)
        exp_state = load_exp_state()
        start_exp = int(exp_state.get("exp", 0))
        start_level = exp_to_level(start_exp)

        # 每日抽獎：給「元」，不給 EXP
        login_money = random.randint(15, 50)

        state = {
            "last_date": today,
            "bonus_task": task,
            "rounds_completed": 0,
            "extra_rounds": 0,
            "exp_gained_today": 0,
            "start_exp": start_exp,
            "start_level": start_level,
            "login_money": login_money,
        }
        _save_bonus_state(state)

        print("\n✅ 今日限定 Bonus 抽卡成功！（今日登入禮）")
        print("今日登入獎勵任務：")
        print(f"👉 {task}")
        print(f"👉 今日登入抽獎：+{login_money} 元（虛擬獎勵，不加 EXP）")
        print(f"👉 今日每完成 1 回合：+{EXP_PER_ROUND} EXP")
    else:
        login_money = int(state.get("login_money", 0))

        print("\n🎁 今日登入禮已抽過。")
        print(f"👉 今日任務：{state.get('bonus_task', '（無紀錄）')}")
        if login_money > 0:
            print(f"👉 今日登入抽獎：+{login_money} 元（虛擬獎勵，不加 EXP）")
        print(f"👉 今日每完成 1 回合：+{EXP_PER_ROUND} EXP")

    run_30min_session(state)

# ---------- 收尾儀式：今日總結（成就角） ----------
def daily_summary():
    """
    ✔ 今日總結（成就角）
    """
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_bonus_state()

    if state.get("last_date") != today:
        print("\n✔ 今日總結（成就角）")
        print("今天尚未啟動今日登入禮或無紀錄。")
        return

    main_rounds = int(state.get("rounds_completed", 0))
    extra_rounds = int(state.get("extra_rounds", 0))
    total_rounds = main_rounds + extra_rounds
    exp_today = int(state.get("exp_gained_today", 0))
    start_exp = int(state.get("start_exp", 0))
    start_level = int(state.get("start_level", 1))
    login_money = int(state.get("login_money", 0))

    exp_state = load_exp_state()
    current_exp = int(exp_state.get("exp", 0))
    current_level = exp_to_level(current_exp)
    level_gain = max(0, current_level - start_level)
    bonus_task = state.get("bonus_task", "（今日尚未抽取）")

    print("\n✔ 今日總結（成就角）")
    print("回顧今天：\n")
    print(f"完成幾回合？  主線 {min(main_rounds, 6)} / 6，額外 {extra_rounds} 回，合計 {total_rounds} 回")
    print(f"今日加幾 EXP？ +{exp_today} EXP（{start_exp} → {current_exp}）")
    print(f"登入抽到幾元？ +{login_money} 元（虛擬獎勵）")

    if level_gain > 0:
        print(f"角色升級了？  是！Lv.{start_level} → Lv.{current_level}（+{level_gain} 級）")
    else:
        print(f"角色升級了？  尚未升級（維持 Lv.{current_level}）")

    print(f"屬性提升多少？EXP +{exp_today}，等級 +{level_gain}")
    print(f"今日 Bonus？   {bonus_task}")

    show_character_panel(show_title=False)

# ---------- 更新進度（四科血條） ----------
def update_progress_interactive():
    progress = load_progress()
    print("📘 上次的進度如下：")
    show_dashboard(progress)
    if input("\n是否要更新學科血條？(y/n)：").strip().lower() != "y":
        return progress
    for key, label in FIELDS:
        raw = input(f"請輸入 {label} 進度（0~100，Enter 保留 {progress[key]:.1f}%）：").strip()
        if raw == "":
            continue
        try:
            progress[key] = _clamp01pct(float(raw))
        except ValueError:
            print("格式錯誤，已保留原值。")
    save_progress(progress)
    append_history(progress)
    print("\n✅ 已更新並儲存新進度！")
    show_dashboard(progress)
    return progress

# ---------- 主選單 ----------
def menu():
    while True:
        print("""
======== Study Toolkit (大學科目版 / 起點=12日 / 手動輸入日期) ========
1) 抽今天限定 Bonus（今日登入禮＋30:00 專注＋EXP）
2) 日期→對應值
3) 顯示 / 更新角色＆四科血條
4) 輸出當下進度長條圖（uni_progress.png）
5) 打開趨勢 GUI
6) 顯示《     指南》
7) ✔ 今日總結（成就角 / 收尾儀式）
0) 離開
""")
        choice = input("> ").strip()
        try:
            if choice == "1":
                draw_today_bonus()
            elif choice == "2":
                day = int(input("輸入日期（1~31）："))
                val = lookup_value_by_day_from_12(day)
                print(f"✅ 以 13 號為起點，輸入的 {day} 日 → 為 {val} 元")
            elif choice == "3":
                update_progress_interactive()
            elif choice == "4":
                progress = load_progress()
                show_dashboard(progress)
                plot_chart(progress)
            elif choice == "5":
                run_trend_gui()
            elif choice == "6":
                show_toeic_guide()
            elif choice == "7":
                daily_summary()
            elif choice == "0":
                print("再見！")
                break
            else:
                print("無效選項。")
        except Exception as e:
            print("⚠️ 發生錯誤：", e)

if __name__ == "__main__":
    menu()