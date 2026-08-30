# -*- coding: utf-8 -*-
"""
EdgeFusion 面试官 agent · CLI 入口

用法:
  python main.py new                 # 开一场新面试(覆盖旧 state)
  python main.py answer "回答内容"    # 回答当前问题,得到下一问
  python main.py answer -            # 从 stdin 读多行回答
  python main.py status              # 查看当前状态
  python main.py recap               # 手动触发复盘(S4 结束会自动触发)

选项:
  --file PATH    状态文件路径(默认 interview_state.json,与本脚本同目录)
  --offline      强制规则引擎,不调用模型(没配 INTERVIEW_API_KEY 时自动生效)

模型配置(环境变量,OpenAI 兼容接口):
  INTERVIEW_API_KEY    必填才启用模型判定
  INTERVIEW_BASE_URL   默认 https://open.bigmodel.cn/api/paas/v4
  INTERVIEW_MODEL      默认 glm-4.6
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
import state as st_mod  # noqa: E402


def _utf8_stdout():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:                            # noqa: BLE001
            pass


def cmd_new(args) -> str:
    existed = Path(args.file).exists()
    state = st_mod.new_session(args.file)
    engine._set_current(state, engine.C.INTRO_QUESTION_ID, engine.C.INTRO_QUESTION)
    st_mod.save(state, args.file)
    head = "(已覆盖上一场未完成的会话)\n" if existed else ""
    return f"{head}【S0·引言】\n{state['current_question']}"


def cmd_answer(args) -> str:
    if args.text == "-":
        print("(输入回答,Ctrl+Z+回车 / Ctrl+D 结束)", file=sys.stderr)
        answer = sys.stdin.read()
    else:
        answer = args.text
    if not answer.strip():
        return "空回答,不算一轮。"
    return engine.run_round(args.file, answer, offline=args.offline)


def cmd_status(args) -> str:
    try:
        state = st_mod.load(args.file)
    except FileNotFoundError as e:
        return str(e)
    lines = [
        f"会话 {state['session_id']}  阶段 {state['stage']}  "
        f"{'已结束' if state['ended'] else '进行中'}",
        f"骨架进度 {state['skeleton_idx']}/5  逐句判定 {state['skeleton_verdicts']}",
        f"深挖轨道 {state['deep_track']}  已问 {state['deep_q_count']} 问"
        f"  八股 {state['bagu_q_count']}  权衡 {state['tradeoff_q_count']}",
        f"判定 {state['last_verdict'] or '(无)'}  连续 vague {state['consecutive_vague']}",
        f"确认事实 {len(state['facts_confirmed'])} 条 / 否认 {len(state['facts_denied'])} 条"
        f"  pierce {len(state['pierce_points'])} 个",
        f"本轮判定走 {'模型' if state['model_mode'] == 'llm' else '规则引擎'}"
        f"  累计 {len(state['asked_ids'])} 问",
        "",
        f"当前问题 [{state['current_qid']}]:{state['current_question'] or '(无,可能已到复盘)'}",
    ]
    return "\n".join(lines)


def cmd_recap(args) -> str:
    return engine.do_recap(args.file, offline=args.offline)


def main():
    _utf8_stdout()
    ap = argparse.ArgumentParser(description="EdgeFusion NVR 面试官(单会话 CLI)")
    ap.add_argument("--file", default=engine.DEFAULT_STATE_FILE,
                    help="状态文件路径(默认 %(default)s)")
    ap.add_argument("--offline", action="store_true", help="强制规则引擎,不调用模型")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("new", help="开一场新面试")
    p_ans = sub.add_parser("answer", help="回答当前问题")
    p_ans.add_argument("text", help='回答文本;传 - 则从 stdin 读多行')
    sub.add_parser("status", help="查看状态")
    sub.add_parser("recap", help="触发复盘")
    args = ap.parse_args()

    handlers = {"new": cmd_new, "answer": cmd_answer, "status": cmd_status, "recap": cmd_recap}
    print(handlers[args.cmd](args))


if __name__ == "__main__":
    main()
