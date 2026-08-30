# -*- coding: utf-8 -*-
"""
面试官引擎:读 state → 规则预检 invented →(有 API 则)模型判定 → 更新 state → 给下一问。
模型解析失败重试一次,再失败用规则引擎按 stage 取题库下一条(规格第 9 节)。
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

import spec_constants as C
import state as st_mod

_HERE = Path(__file__).resolve().parent
DEFAULT_STATE_FILE = str(_HERE / "interview_state.json")

VERDICTS = {"solid", "vague", "contradiction", "invented", "skip"}
_QUESTIONISH = re.compile(r"[?？]|吗|什么|怎么|为什么|哪|如何|多少|几个|会不会|是否")


def warn(msg: str):
    print(f"[面试官] {msg}", file=sys.stderr)


# =====================================================================
# LLM 客户端(OpenAI 兼容 /chat/completions,stdlib 实现,无三方依赖)
# =====================================================================

class LLMClient:
    def __init__(self):
        self.api_key = os.environ.get("INTERVIEW_API_KEY", "").strip()
        self.base_url = os.environ.get("INTERVIEW_BASE_URL", "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        self.model = os.environ.get("INTERVIEW_MODEL", "glm-4.6")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 700) -> str:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        last_err = None
        for _ in range(2):                      # 网络层重试一次
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]
            except Exception as e:               # noqa: BLE001
                last_err = e
        warn(f"模型调用失败,转规则引擎:{last_err}")
        return ""


# =====================================================================
# 系统提示(judge_prompt.md + 白名单/禁令注入)
# =====================================================================

def build_system_prompt() -> str:
    text = (_HERE / "judge_prompt.md").read_text(encoding="utf-8")
    text = text.replace("{{ALLOWED_FACTS}}", C.allowed_facts_text())
    text = text.replace("{{FORBIDDEN_CLAIMS}}", "\n".join(f"- {x}" for x in C.FORBIDDEN_CLAIMS))
    return text


def extract_json(text: str):
    """剥掉 ```json 围栏,取首个配平的 {...} 解析。"""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text).strip()
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


# =====================================================================
# 题库取题
# =====================================================================

def _deep_followup(state, track: str):
    """题库问完但还没到 6 问:注入故障场景追问(规则兜底)。"""
    fault = C.DEEP_FOLLOWUP_FAULTS.get(track, "链路里任一依赖突然失效")
    templates = [
        (f"{track}_fu_phen", f"假设{fault},你的系统会有什么现象?你从哪里第一时间看出来?"),
        (f"{track}_fu_shared", "这条链路上哪个数据或资源是跨线程共享的?谁持有锁?阻塞了会拖住谁?"),
        (f"{track}_fu_verify", "回头看这段实现:哪一步在板子上的表现和你在 PC 上想的不一样?你怎么验证的?"),
    ]
    for qid, q in templates:
        if qid not in state["asked_ids"]:
            return qid, q
    return None


def next_by_rules(state):
    """按 stage 从题库取下一条(规则引擎选题)。返回 (qid, text) 或 None。"""
    stage = state["stage"]
    if stage == "S0_INTRO":
        return C.INTRO_QUESTION_ID, C.INTRO_QUESTION
    if stage == "S1_SKELETON":
        i = min(state["skeleton_idx"], 4)
        item = C.SKELETON_QUESTIONS[i]
        attempt = state["skeleton_attempts"][i]
        pool = [item["text"]] + item.get("variants", [])
        return item["id"], pool[attempt % len(pool)]
    if stage == "S2_DEEP":
        track = state["deep_track"]
        for qid, q in C.DEEP_QUESTIONS.get(track, []):
            if qid not in state["asked_ids"]:
                return qid, q
        return _deep_followup(state, track)
    if stage == "S3_BAGU":
        track = state["deep_track"]
        hooks = C.BAGU_HOOKS.get(track, C.BAGU_HOOKS["stream"])
        fact = state["facts_confirmed"][-1] if state["facts_confirmed"] else ""
        anchor = f"(结合你亲口说过的:{fact})" if fact else ""
        for i, hook in enumerate(hooks):
            qid = f"bagu_{track}_{i}"
            if qid not in state["asked_ids"]:
                return qid, f"不背名词,用你项目里的实际代码讲:{hook}{anchor}——它在你这条链路上对应哪一段?为什么需要它?"
        for k in range(9):
            qid = f"bagu_{track}_x{k}"
            if qid not in state["asked_ids"]:
                return qid, f"继续上一问往下压一层:{anchor}这里换成白名单里的另一种做法,代价差在哪?"
        return None
    if stage == "S4_TRADEOFF":
        for qid, q in C.TRADEOFF_QUESTIONS:
            if qid not in state["asked_ids"]:
                return qid, q
        return None
    return None  # S5_RECAP


def candidate_questions_for_prompt(state) -> str:
    """给模型的候选题切片(按 stage 动态过滤已问)。"""
    stage = state["stage"]
    if stage == "S1_SKELETON":
        item = C.SKELETON_QUESTIONS[min(state["skeleton_idx"], 4)]
        return f"{item['id']}(换问法可用变体,别原样重复)"
    if stage == "S2_DEEP":
        track = state["deep_track"]
        left = [f"{qid}:{q}" for qid, q in C.DEEP_QUESTIONS.get(track, []) if qid not in state["asked_ids"]]
        adj = adjacent_track(state, track)
        adj_left = [f"{qid}:{q}" for qid, q in C.DEEP_QUESTIONS.get(adj, []) if qid not in state["asked_ids"]][:2]
        return (f"当前轨道 {track} 剩余:\n" + "\n".join(left) +
                f"\n(候选人承认不是自己写的时可切轨道 {adj}):\n" + "\n".join(adj_left) +
                "\n也可自拟跟进问,id 形如 stream_3_fu1")
    if stage == "S3_BAGU":
        hooks = C.BAGU_HOOKS.get(state["deep_track"], [])
        return (f"八股挂钩(必须贴着当前轨道 {state['deep_track']} 和 facts_confirmed 出题):\n" +
                ";".join(hooks) + "\n自拟 id 形如 bagu_{track}_{n}")
    if stage == "S4_TRADEOFF":
        left = [f"{qid}:{q}" for qid, q in C.TRADEOFF_QUESTIONS if qid not in state["asked_ids"]]
        return "权衡题候选:\n" + "\n".join(left)
    return "(本阶段固定问法)"


# =====================================================================
# 轨道推断 / 相邻切换
# =====================================================================

def infer_track_from_text(text: str):
    text = text.lower()
    best, best_n = None, 0
    for track, kws in C.TRACK_INFERENCE_KEYWORDS.items():
        n = sum(1 for k in kws if k in text)
        if n > best_n:
            best, best_n = track, n
    return best


def adjacent_track(state, track: str) -> str:
    if track in C.TRACK_CYCLE:
        idx = C.TRACK_CYCLE.index(track)
        return C.TRACK_CYCLE[(idx + 1) % len(C.TRACK_CYCLE)]
    # debug 轨道:从候选人确认过的事实里挑,挑不到回数据流起点
    guess = infer_track_from_text(" ".join(state["facts_confirmed"]))
    return guess if guess in C.TRACK_CYCLE else "stream"


# =====================================================================
# 规则引擎判定(模型不可用 / 解析失败时兜底)
# =====================================================================

def rule_judge(state, qid: str, question: str, answer: str) -> dict:
    """规则引擎判定。不在此处选题/递增换问法计数——那是 apply_verdict 的单一职责。

    额外收割证据:solid 时把候选人点到的模块名收进 facts_confirmed(规格允许
    "来自白名单或候选人具体模块名"),skip 时把否认片段收进 facts_denied,
    否则纯规则模式下复盘的个人边界维度永远零证据。
    """
    a = answer.strip()
    low = a.lower()
    new_facts, new_denied = [], []
    if len(a) < 6:
        verdict = "vague"
    elif any(p in a for p in C.SKIP_PATTERNS):
        verdict = "skip"
        new_denied = [a[:40]]
    else:
        has_module = any(t in low for t in C.MODULE_TOKENS)
        has_flow = any(t in low for t in C.FLOW_TOKENS)
        verdict = "solid" if (has_module or has_flow) and len(a) >= 30 else "vague"
        if verdict == "solid":
            new_facts = [t for t in C.MODULE_TOKENS if t in low][:2]
    return {
        "verdict": verdict,
        "one_line_reason": "规则引擎:模块/数据流 token " + ("命中" if verdict == "solid" else "不足"),
        "new_facts": new_facts, "new_denied": new_denied, "pierce": None,
        "next_question_id": "auto", "next_question": "",
    }


def call_judge(llm: LLMClient, state, qid: str, question: str, answer: str):
    """模型判定 + 解析失败重试一次。返回 dict 或 None。"""
    system = build_system_prompt()
    tail = "\n".join(
        f"[{e['qid']}|{e['verdict']}] 问:{e['q'][:60]}\n答:{e['a'][:200]}"
        for e in state["transcript"][-6:]
    )
    user = (
        f"【当前状态】\n{st_mod.render_state_for_prompt(state)}\n\n"
        f"【最近几轮】\n{tail or '(无)'}\n\n"
        f"【当前问题】{qid}:{question}\n"
        f"【候选人回答】\n{answer}\n\n"
        f"【候选下一问】\n{candidate_questions_for_prompt(state)}\n\n"
        "按系统提示输出判定 JSON,不要输出 JSON 以外的文字。"
    )
    for attempt in range(2):
        raw = llm.chat(system, user)
        parsed = extract_json(raw)
        if parsed and parsed.get("verdict") in VERDICTS:
            parsed.setdefault("one_line_reason", "")
            parsed.setdefault("new_facts", [])
            parsed.setdefault("new_denied", [])
            parsed["pierce"] = parsed.get("pierce") or None
            return parsed
        user += "\n\n[重试] 上一次输出不是合法 JSON 或 verdict 非法。只输出一个 JSON 对象。"
    return None


# =====================================================================
# invented 打断话术
# =====================================================================

def invented_challenge(label: str, answer: str) -> str:
    quote = answer.strip()[:60]
    return (f"打断。你说的「{label}」——原话「{quote}…」——和这个仓库的事实对不上。"
            f"这段你到底做没做、做到哪一步,按真实情况重讲一遍?")


def _label_of(v: dict) -> str:
    return (v.get("_label")
            or (v.get("pierce") or {}).get("why_bad")
            or (v.get("one_line_reason") or "").strip()
            or "与仓库事实对不上")


# =====================================================================
# 状态机:判定落地与阶段转移(规格第 4 节)
# =====================================================================

def _push_recent(state, verdict: str):
    state["recent_verdicts"].append(verdict)
    state["recent_verdicts"] = state["recent_verdicts"][-3:]


def _add_fact(lst, item):
    item = (item or "").strip()
    if item and item not in lst and not C.rule_check_invented(item):
        lst.append(item[:80])


def _set_current(state, qid: str, text: str):
    state["current_qid"] = qid
    state["current_question"] = text
    if qid and qid not in state["asked_ids"]:
        state["asked_ids"].append(qid)


def _last_two_not_invented(state) -> bool:
    tail = state["recent_verdicts"][-2:]
    return all(v != "invented" for v in tail)


def _enter_s2(state):
    state["stage"] = "S2_DEEP"
    sv = state["skeleton_verdicts"] + [""] * 5
    # 过关门:排障句(idx=3)与结果句(idx=4)至少 solid(规格第 4 节)
    state["pass_skeleton"] = (sv[3] == "solid" and sv[4] == "solid")
    if state["debug_priority"]:
        state["deep_track"] = "debug"
    else:
        skel2 = next((e["a"] for e in reversed(state["transcript"]) if e["qid"] == "skel_2"), "")
        state["deep_track"] = infer_track_from_text(skel2) or "stream"
    nxt = next_by_rules(state)
    if nxt:
        _set_current(state, *nxt)


def apply_verdict(state, v: dict, qid: str, question: str, answer: str):
    verdict = v["verdict"]
    state["last_verdict"] = verdict
    state["consecutive_vague"] = state["consecutive_vague"] + 1 if verdict == "vague" else 0
    _push_recent(state, verdict)
    for f in v.get("new_facts") or []:
        _add_fact(state["facts_confirmed"], f)
    for d in v.get("new_denied") or []:
        _add_fact(state["facts_denied"], d)
    if v.get("pierce"):
        p = dict(v["pierce"])
        p.setdefault("id", qid)
        p.setdefault("quote", answer.strip()[:80])
        p.setdefault("why_bad", "")
        p.setdefault("need", "")
        if not any(x.get("id") == p["id"] and x.get("quote") == p["quote"] for x in state["pierce_points"]):
            state["pierce_points"].append(p)

    stage = state["stage"]

    # ---- 模型给的下一问(先存着,后面按阶段校验是否采用) ----
    m_qid = str(v.get("next_question_id") or "auto")
    m_q = str(v.get("next_question") or "").strip()
    m_ok = bool(m_q) and _QUESTIONISH.search(m_q)

    def use_model_next():
        if m_qid != "auto" and m_qid in state["asked_ids"]:
            return False
        _set_current(state, m_qid if m_qid != "auto" else f"{qid}_fu{len(state['asked_ids'])}", m_q)
        return True

    # ================= S0 =================
    if stage == "S0_INTRO":
        if verdict == "invented":
            if not (m_ok and use_model_next()):
                _set_current(state, f"{qid}_retry", invented_challenge(_label_of(v), answer))
            return
        # 任何有效回答都进 S1,不过严(规格第 4 节)
        state["stage"] = "S1_SKELETON"
        nxt = next_by_rules(state)
        _set_current(state, *nxt)
        return

    # ================= S1 =================
    if stage == "S1_SKELETON":
        i = min(state["skeleton_idx"], 4)
        if verdict == "invented":
            if not (m_ok and use_model_next()):
                _set_current(state, f"{qid}_retry", invented_challenge(_label_of(v), answer))
            return
        if verdict in ("solid", "skip"):
            need = state["skeleton_verdicts"]
            while len(need) <= i:
                need.append("")
            need[i] = verdict
            state["skeleton_idx"] = i + 1
            if state["skeleton_idx"] >= 5:
                _enter_s2(state)
            else:
                nxt = next_by_rules(state)
                _set_current(state, *nxt)
            return
        # vague / contradiction:同句换问法
        state["skeleton_attempts"][i] += 1
        if i == 3 and state["consecutive_vague"] >= 2:
            # 排障句(skeleton_idx=3)连续两次 vague:放行,记 pierce,深挖优先 debug
            need = state["skeleton_verdicts"]
            while len(need) <= 3:
                need.append("")
            need[3] = "vague"
            state["skeleton_3_waived"] = True
            state["debug_priority"] = True
            state["pierce_points"].append({
                "id": "skel_3", "quote": answer.strip()[:80],
                "why_bad": "排障句两次 vague,疑似无真实排障经历",
                "need": "补一个现象→工具→修改→验证的完整案例",
            })
            state["skeleton_idx"] = 4
            nxt = next_by_rules(state)
            _set_current(state, *nxt)
            return
        if not (m_ok and use_model_next()):       # 模型的换问法优先
            nxt = next_by_rules(state)
            _set_current(state, *nxt)
        return

    # ================= S2 =================
    if stage == "S2_DEEP":
        state["deep_q_count"] += 1
        if verdict == "skip":
            guess = infer_track_from_text(" ".join(state["facts_confirmed"][-5:]))
            new_track = guess if (guess and guess != state["deep_track"]) else adjacent_track(state, state["deep_track"])
            state["deep_track"] = new_track
            state["consecutive_vague"] = 0
        elif state["consecutive_vague"] >= 3:
            state["deep_track"] = adjacent_track(state, state["deep_track"])
            state["consecutive_vague"] = 0
        # 出口:>=6 且最近 2 次不是 invented;>=10 强制
        if state["deep_q_count"] >= 10 or (
                state["deep_q_count"] >= 6 and _last_two_not_invented(state)):
            state["stage"] = "S3_BAGU"
            nxt = next_by_rules(state)
            _set_current(state, *nxt)
            return
        if verdict == "invented":
            if not (m_ok and use_model_next()):
                _set_current(state, f"{qid}_retry", invented_challenge(_label_of(v), answer))
            return
        if not (m_ok and use_model_next()):
            nxt = next_by_rules(state)
            if nxt is None:                        # 题库与兜底全干完,提前进 S3
                state["stage"] = "S3_BAGU"
                nxt = next_by_rules(state)
            _set_current(state, *nxt)
        return

    # ================= S3 =================
    if stage == "S3_BAGU":
        state["bagu_q_count"] += 1
        if state["bagu_q_count"] >= 6 or (
                state["bagu_q_count"] >= 4 and _last_two_not_invented(state)):
            state["stage"] = "S4_TRADEOFF"
            nxt = next_by_rules(state)
            _set_current(state, *nxt)
            return
        if verdict == "invented":
            if not (m_ok and use_model_next()):
                _set_current(state, f"{qid}_retry", invented_challenge(_label_of(v), answer))
            return
        if not (m_ok and use_model_next()):
            nxt = next_by_rules(state)
            if nxt is None:
                state["stage"] = "S4_TRADEOFF"
                nxt = next_by_rules(state)
            _set_current(state, *nxt)
        return

    # ================= S4 =================
    if stage == "S4_TRADEOFF":
        state["tradeoff_q_count"] += 1
        if state["tradeoff_q_count"] >= 3:
            state["stage"] = "S5_RECAP"
            state["current_qid"] = ""
            state["current_question"] = ""
            return
        if verdict == "invented":
            if not (m_ok and use_model_next()):
                _set_current(state, f"{qid}_retry", invented_challenge(_label_of(v), answer))
            return
        nxt = next_by_rules(state)                 # 权衡题按题库顺序
        _set_current(state, *nxt)
        return


# =====================================================================
# 一轮完整流程
# =====================================================================

def run_round(state_path: str, answer_text: str, offline: bool = False) -> str:
    state = st_mod.load(state_path)
    if state["ended"]:
        return "面试已结束。运行 recap 查看复盘。"
    if not state["current_question"]:
        return "没有待回答的问题,请先运行 new。"

    qid, question = state["current_qid"], state["current_question"]

    # 1) 规则引擎预检 invented(先于模型,规格第 9 节第 7 条)
    label = C.rule_check_invented(answer_text)
    if label and state["stage"] != "S5_RECAP":
        v = {
            "verdict": "invented", "one_line_reason": f"规则命中禁令:{label}",
            "new_facts": [], "new_denied": [], "pierce": {
                "id": qid, "quote": answer_text.strip()[:80],
                "why_bad": f"命中禁止编造清单:{label}", "need": "按真实进度改口"},
            "next_question_id": f"{qid}_retry",
            "next_question": invented_challenge(label, answer_text),
            "_label": label,
        }
        state["model_mode"] = "rules"
    else:
        # 2) 模型判定;失败→规则引擎
        llm = LLMClient()
        v = None
        if not offline and llm.available:
            v = call_judge(llm, state, qid, question, answer_text)
            state["model_mode"] = "llm" if v else "rules"
        else:
            state["model_mode"] = "rules"
        if v is None:
            v = rule_judge(state, qid, question, answer_text)

    # 3) 记 transcript(复盘证据,保存原始回答)
    state["transcript"].append({
        "qid": qid, "q": question,
        "a": answer_text.strip()[:400],
        "verdict": v["verdict"],
        "reason": (v.get("one_line_reason") or "")[:60],
    })

    # 4) 状态机转移 + 落盘
    apply_verdict(state, v, qid, question, answer_text)
    st_mod.save(state, state_path)

    # 5) 输出:只打印下一问(规格第 9 节第 3 条)
    if state["stage"] == "S5_RECAP":
        return do_recap(state_path, offline=offline)
    header = stage_header(state)
    return f"{header}\n{state['current_question']}"


def stage_header(state) -> str:
    s = state["stage"]
    names = {"S0_INTRO": "引言", "S1_SKELETON": "骨架", "S2_DEEP": "深挖",
             "S3_BAGU": "八股", "S4_TRADEOFF": "权衡", "S5_RECAP": "复盘"}
    if s == "S1_SKELETON":
        return f"【S1·骨架 {min(state['skeleton_idx'] + 1, 5)}/5】"
    if s == "S2_DEEP":
        return f"【S2·深挖 {state['deep_track']} 第{state['deep_q_count']}问】"
    return f"【{s[:2]}·{names.get(s, s)}】"


# =====================================================================
# S5 复盘(评分表 + pierce + 简历删词 + homework)
# =====================================================================

def _band(total: int):
    for cap, name, advice in C.BANDS:
        if total <= cap:
            return name, advice
    return C.BANDS[-1][1], C.BANDS[-1][2]


def heuristic_scores(state) -> dict:
    text = "\n".join(e["a"] for e in state["transcript"]).lower()
    sv = (state["skeleton_verdicts"] + [""] * 5)[:5]
    solids = sum(1 for x in sv if x == "solid")
    invented_n = sum(1 for e in state["transcript"] if e["verdict"] == "invented")

    def has(words):
        return any(w in text for w in words)

    def group_count(groups):
        return sum(1 for g in groups if any(w in text for w in g))

    scores = {}
    scores["骨架完整"] = 2 if solids >= 5 else (1 if solids >= 3 else 0)
    scores["个人边界"] = (2 if (state["facts_denied"] and len(state["facts_confirmed"]) >= 3 and invented_n == 0)
                        else (1 if (state["facts_denied"] or len(state["facts_confirmed"]) >= 3) else 0))
    pull = has(["拉流", "rtsp", "av_read_frame"])
    outs = group_count([["录像", "mp4", "remux"], ["抽帧", "jpeg", "mjpeg"], ["转发", "rtsp_server", "track0"]])
    scores["数据流"] = (2 if pull and outs >= 2 and has(["队列", "锁", "缓冲", "拷贝", "引用"])
                       else (1 if pull and outs >= 2 else 0))
    scores["并发"] = (2 if has(["锁", "互斥", "线程安全", "共享"]) and has([t.lower() for t in C.MODULE_TOKENS])
                    else (1 if has(["线程", "thread"]) else 0))
    net = group_count([["tcp"], ["重连", "断流"], ["ip", "dhcp"], ["https", "ca", "dns", "403"]])
    scores["网络"] = 2 if net >= 3 else (1 if net >= 1 else 0)
    scores["存储"] = (2 if has(["fmp4", "frag", "断电", "循环", "500", "scandir", "删除"]) and has(["60s", "分段", "mp4"])
                     else (1 if has(["60s", "分段", "mp4"]) else 0))
    dbg = [e for e in state["transcript"] if "skel_3" in e["qid"] or e["qid"].startswith("debug")]
    waived = state.get("skeleton_3_waived", False)
    if waived or not dbg:
        scores["排障"] = 0
    elif any(e["verdict"] == "solid" and any(t in e["a"].lower() for t in C.TOOL_TOKENS) for e in dbg):
        scores["排障"] = 2
    elif any(len(e["a"]) > 60 for e in dbg):
        scores["排障"] = 1
    else:
        scores["排障"] = 0
    scores["资源约束"] = (2 if has(["无vpu", "软解", "800mhz", "1fps", "限速"]) and has(["软解", "swscale", "fps", "限速"])
                        else (1 if has(["无vpu", "软解"]) else 0))
    bagu = [e for e in state["transcript"] if e["qid"].startswith("bagu")]
    if bagu:
        r = sum(1 for e in bagu if e["verdict"] == "solid") / len(bagu)
        scores["八股贴项目"] = 2 if (len(bagu) >= 3 and r >= 0.7) else (1 if r > 0 else 0)
    else:
        scores["八股贴项目"] = 0
    solid_answers = [e["a"] for e in state["transcript"] if e["verdict"] == "solid"]
    avg = sum(len(a) for a in solid_answers) / max(len(solid_answers), 1)
    scores["表达"] = 2 if (avg >= 60 or has(["画", "伪代码", "流程图"])) else (1 if avg >= 25 else 0)
    return scores


def model_scores(state):
    llm = LLMClient()
    if not llm.available:
        return None, ""
    system = (
        "你是冷面面试官。按评分表给这位 EdgeFusion NVR 候选人打分,只依据答题记录与判定,"
        "不脑补。输出严格 JSON:{\"scores\":{10 项各 0-2},\"reasons\":{每项≤20字},"
        "\"resume_words_to_cut\":[简历里该删的词],\"homework\":[恰好 3 个原理名,不给讲解],"
        "\"summary\":\"≤120 字冷面总评\"}。10 项为:" + "、".join(C.SCORE_DIMS) +
        "\n评分表:\n" + C.SCORING_RUBRIC_TEXT
    )
    tail = "\n".join(
        f"[{e['qid']}|{e['verdict']}] 问:{e['q'][:60]}\n答:{e['a'][:240]}"
        for e in state["transcript"][-14:]
    )
    user = (f"状态:\n{st_mod.render_state_for_prompt(state)}\n\n答题记录:\n{tail}\n\n"
            f"pierces:{json.dumps(state['pierce_points'], ensure_ascii=False)}")
    parsed = extract_json(llm.chat(system, user, temperature=0.1, max_tokens=900))
    if not parsed or "scores" not in parsed:
        return None, ""
    scores = parsed["scores"]
    if not all(k in scores and isinstance(scores[k], int) and 0 <= scores[k] <= 2 for k in C.SCORE_DIMS):
        return None, ""
    parsed.setdefault("reasons", {})
    parsed.setdefault("resume_words_to_cut", [])
    parsed.setdefault("homework", [])
    parsed.setdefault("summary", "")
    return parsed, parsed.get("summary", "")


def do_recap(state_path: str, offline: bool = False) -> str:
    state = st_mod.load(state_path)
    if not state["transcript"]:
        return "还没有任何答题记录,先 answer 几轮。"

    result, summary = (None, "")
    if not offline:
        result, summary = model_scores(state)
    if result is None:
        scores = heuristic_scores(state)
        reasons = {k: "启发式:证据计数" for k in scores}
        result = {"scores": scores, "reasons": reasons,
                  "resume_words_to_cut": [], "homework": [], "summary": summary}
    scores = result["scores"]

    # 简历删词:默认检查 + 答题记录扫描
    all_answers = "\n".join(e["a"] for e in state["transcript"])
    cut = [w for w in C.RESUME_FLAGS if w in all_answers]
    for w in result.get("resume_words_to_cut") or []:
        if w and w not in cut:
            cut.append(w[:30])
    # homework:最薄弱 3 维 → 原理名池
    homework = list(result.get("homework") or [])[:3]
    if len(homework) < 3:
        weak = sorted(C.SCORE_DIMS, key=lambda d: scores.get(d, 0))[:3]
        for dim in weak:
            for name in C.HOMEWORK_POOL.get(dim, []):
                if name not in homework:
                    homework.append(name)
                    break
    homework = homework[:3]
    while len(homework) < 3:                      # 池子意外取不满时兜底
        homework.append(C.HOMEWORK_POOL["数据流"][len(homework) % 3])

    total = sum(scores.values())
    band, advice = _band(total)

    recap = {
        "session_id": state["session_id"],
        "total": total, "band": band, "advice": advice,
        "scores": scores, "reasons": result.get("reasons", {}),
        "pierce_points": state["pierce_points"],
        "resume_words_to_cut": cut,
        "homework": homework,
        "summary": result.get("summary", "") or f"总分 {total}/20,档位「{band}」。{advice}。",
        "pass_skeleton": state["pass_skeleton"],
        "model_mode": state["model_mode"],
        "transcript_len": len(state["transcript"]),
    }
    recap_path = str(Path(state_path).with_name(f"recap_{state['session_id']}.json"))
    with open(recap_path, "w", encoding="utf-8") as f:
        json.dump(recap, f, ensure_ascii=False, indent=2)

    state["stage"] = "S5_RECAP"
    state["ended"] = True
    state["resume_words_to_cut"] = cut
    state["homework"] = homework
    st_mod.save(state, state_path)

    lines = ["==== 复盘 ====",
             f"总分 {total}/20 · 档位「{band}」——{advice}", ""]
    for dim in C.SCORE_DIMS:
        lines.append(f"  {dim:<6} {scores.get(dim, 0)}/2  {str(result.get('reasons', {}).get(dim, ''))[:20]}")
    lines.append("")
    lines.append("被打穿的点:")
    if state["pierce_points"]:
        lines.extend(f"  - [{p['id']}] {p.get('quote','')[:50]} → {p.get('need','')}"
                     for p in state["pierce_points"])
    else:
        lines.append("  (无)")
    lines.append("简历删词: " + ("、".join(cut) if cut else "未检出"))
    lines.append("homework: " + "、".join(homework))
    lines.append(f"总评:{recap['summary']}")
    lines.append(f"复盘 JSON 已写入 {recap_path}")
    return "\n".join(lines)
