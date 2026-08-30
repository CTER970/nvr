# -*- coding: utf-8 -*-
"""
InterviewState:状态落盘(JSON),支持中断续面。

字段分两类:
  - 规格字段:与《可运行规格》第 1 节的 schema 一一对应,语义不得改动;
  - 簿记字段:规格 schema 没写、但状态机/复盘实现必需的记录
    (逐句判定、当前待答问题、答题记录等)。只做加法,不动规格字段语义。
"""

import json
import os
import time


def _new_state() -> dict:
    return {
        # ---------- 规格字段(第 1 节) ----------
        "session_id": time.strftime("s_%Y%m%d_%H%M%S"),
        "stage": "S0_INTRO",            # S0_INTRO|S1_SKELETON|S2_DEEP|S3_BAGU|S4_TRADEOFF|S5_RECAP
        "skeleton_idx": 0,
        "deep_track": "none",           # none|stream|record|frame|cloud|web_rtsp|debug
        "deep_q_count": 0,
        "bagu_q_count": 0,
        "tradeoff_q_count": 0,
        "asked_ids": [],
        "facts_confirmed": [],
        "facts_denied": [],
        "pierce_points": [],            # {id, quote, why_bad, need}
        "resume_words_to_cut": [],
        "homework": [],
        "last_verdict": "",
        "consecutive_vague": 0,
        "pass_skeleton": False,
        "ended": False,

        # ---------- 簿记字段(实现需要) ----------
        "current_qid": "",              # 当前待回答的问题 ID
        "current_question": "",         # 当前待回答的问题文本
        "skeleton_verdicts": [],        # 五句各自最终判定(solid/vague/skip)
        "skeleton_attempts": [0, 0, 0, 0, 0],  # 每句换问法次数
        "skeleton_3_waived": False,     # 第 3 句两次 vague 被放行
        "debug_priority": False,        # 「无真实排障」pierce → 深挖优先 debug
        "recent_verdicts": [],          # 最近若干次判定(取尾部 3 个)
        "transcript": [],               # [{qid,q,a,verdict,reason}] 复盘证据
        "model_mode": "rules",          # rules|llm(本轮判定实际走哪条路)
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def new_session(path: str) -> dict:
    state = _new_state()
    existed = os.path.exists(path)
    save(state, path)
    state["_overwrote"] = existed      # 仅给 CLI 提示用,不落盘
    return state


def load(path: str) -> dict:
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到状态文件 {path},先运行 new 开一场面试。")
    with open(path, "r", encoding="utf-8") as f:
        state = json.load(f)
    # 兼容旧文件缺簿记字段
    base = _new_state()
    for k, v in base.items():
        state.setdefault(k, v)
    return state


def save(state: dict, path: str) -> None:
    state.pop("_overwrote", None)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)              # 原子替换,防止写一半损坏续面能力


def render_state_for_prompt(state: dict) -> str:
    """给模型看的紧凑状态快照(不带 transcript 全文,由 engine 另拼尾部几轮)。"""
    lines = [
        f"stage={state['stage']}",
        f"skeleton_idx={state['skeleton_idx']}/5 已判定={state['skeleton_verdicts']}",
        f"deep_track={state['deep_track']} deep_q_count={state['deep_q_count']}",
        f"bagu_q_count={state['bagu_q_count']} tradeoff_q_count={state['tradeoff_q_count']}",
        f"consecutive_vague={state['consecutive_vague']} last_verdict={state['last_verdict']}",
        f"facts_confirmed={state['facts_confirmed'][-8:]}",
        f"facts_denied={state['facts_denied']}",
        f"pierce={len(state['pierce_points'])} 个",
    ]
    return "\n".join(lines)
