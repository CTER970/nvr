# -*- coding: utf-8 -*-
"""
自测:不依赖模型与网络,全部走规则引擎。

  python selftest.py

覆盖:
  1) rule_check_invented 正/负用例(含否定词与假设句护栏)
  2) 离线全流程:S0→S1(5 句)→S2(≥6 问)→S3(4 问)→S4(3 问)→S5 自动复盘
  3) invented 当场打断:阶段不前进、记 pierce
  4) S2 skip:记 facts_denied、切换轨道
"""

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import engine  # noqa: E402
import spec_constants as C  # noqa: E402
import state as st_mod  # noqa: E402

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {extra}")


# ---------------------------------------------------------------------
print("== 1) rule_check_invented ==")
positives = [
    "MQTT 已经打通上报了",
    "板子上有 VPU,解码很快",
    "IMX6ULL 支持 H.264 硬解",
    "我在服务端用了 epoll",
    "端侧跑了检测模型",
    "项目接入了四路摄像头",
    "OTA 升级已经完成",
    "GPIO 引脚已定并且联动验证过",
]
negatives = [
    "MQTT 只是配置里有,还没实现",
    "ULL 没有 VPU,全是软解",
    "板子不带硬解,只能 remux",
    "项目里没用 epoll,就是普通阻塞线程",
    "检测在云端做,端侧只负责推流",
    "GPIO 模块在,但引脚还是 -1 禁用",
    "如果换一块带 VPU 的板子,就能硬解了",
    "多路还没做,现在就单路",
]
for s in positives:
    check(f"应命中: {s[:18]}", C.rule_check_invented(s) is not None,
          f"got={C.rule_check_invented(s)}")
for s in negatives:
    check(f"应放行: {s[:18]}", C.rule_check_invented(s) is None,
          f"got={C.rule_check_invented(s)}")

# ---------------------------------------------------------------------
print("== 2) invented 打断(S0) ==")
with tempfile.TemporaryDirectory() as td:
    f = str(Path(td) / "s.json")
    st = st_mod.new_session(f)
    engine._set_current(st, C.INTRO_QUESTION_ID, C.INTRO_QUESTION)
    st_mod.save(st, f)
    out = engine.run_round(f, "这个项目我做的,MQTT 已经打通上报,还接了多路摄像头。", offline=True)
    st = st_mod.load(f)
    check("阶段停在 S0", st["stage"] == "S0_INTRO", st["stage"])
    check("记了 pierce", len(st["pierce_points"]) >= 1)
    check("输出含打断", "打断" in out)
    # 改口后前进
    out = engine.run_round(f, "项目是边侧网关,拉RTSP流后录像抽帧上云,我负责ULL上的C多线程守护进程。", offline=True)
    st = st_mod.load(f)
    check("改口后进 S1", st["stage"] == "S1_SKELETON", st["stage"])

# ---------------------------------------------------------------------
print("== 3) 离线全流程 ==")
with tempfile.TemporaryDirectory() as td:
    f = str(Path(td) / "s.json")
    st = st_mod.new_session(f)
    engine._set_current(st, C.INTRO_QUESTION_ID, C.INTRO_QUESTION)
    st_mod.save(st, f)

    answers = [
        # S0
        "边侧智能NVR:V821推流,IMX6ULL拉流录像加抽帧上云,我负责边侧gateway守护进程。",
        # S1 五句
        "普通NVR只录像;这套在ULL上拉RTSP后三路分发:recorder存mp4、抽帧mjpeg预览、事件上云进sqlite,web能查。",
        "V821只做摄像头H264推流,ULL跑C多线程守护进程做录像和转发,云端大模型做识别;分层是算力和网络成本决定的。",
        "我写了recorder和frame_grabber:av_read_frame拉流后packet给recorder remux成mp4,frame_grabber软解抽jpeg上云。",
        "V821断电后DHCP换了IP,拉流一直超时;看log发现重连失败,串口登V821查wlan0地址,改conf里rtsp_url,重跑后web出图。",
        "证据:浏览器开MJPEG预览有实时画面,事件列表有云端置信度,录像目录每60s一个mp4段,VLC能拉转发流。",
        # S2 record 轨道(5 题 + 1 追问 = 6)
        "不解码直接remux:ULL没有VPU,av_packet_rescale_ts重打时间戳,CPU占用几乎为零。",
        "movflags用frag_keyframe+empty_moov,每个fragment独立可解码,断电后最后fragment外的数据还能播。",
        "切段必须等关键帧:非关键帧起头缺参考帧不可解码;首帧同样要IDR,时间基1/90000重打。",
        "scandir按文件名时间戳排序,磁盘小于500MB删最旧的段,并跳过当前正在写的段。",
        "写失败时av_write_frame返回负,记日志关当前段重开;启动时statvfs查磁盘水位。",
        "假设写一半拔卡:这段fmp4尾部损坏但前面fragment还在,下次启动cleanup按最旧删除,不碰它。",
        # S3 八股 4 问
        "fsync只在切段边界做一次avio_flush,不逐包刷,TF卡写放大扛不住。",
        "原子替换:conf保存先写tmp再rename,配置文件不会写一半。",
        "循环缓冲思想:只保留最新N个段加磁盘水位删除,逻辑上像ringbuffer落成文件。",
        "文件IO走avio带缓冲,MP4顺序追加写对TF卡友好,随机写少。",
        # S4 权衡 3 问
        "TCP保证字节流完整,UDP丢包会花屏;现场Wi-Fi丢包常见,选TCP重连逻辑也简单。",
        "remux是因为ULL没VPU;如果换带VPU的板子,我会把预览那路改成硬解来降CPU,录像仍remux。",
        "MJPEG实现轻、浏览器兼容好;代价是带宽大、每帧JPEG编码占CPU,没有HLS那种秒级切片延迟。",
    ]
    for i, a in enumerate(answers):
        out = engine.run_round(f, a, offline=True)
        assert out, f"第{i}轮无输出"
    st = st_mod.load(f)
    check("走到 S5 且结束", st["stage"] == "S5_RECAP" and st["ended"])
    check("深挖轨道=record", st["deep_track"] == "record", st["deep_track"])
    check("深挖满6问", st["deep_q_count"] >= 6, str(st["deep_q_count"]))
    check("八股满4问", st["bagu_q_count"] >= 4, str(st["bagu_q_count"]))
    check("权衡满3问", st["tradeoff_q_count"] >= 3, str(st["tradeoff_q_count"]))
    check("骨架过关(3、4句solid)", st["pass_skeleton"] is True)
    recap_files = list(Path(td).glob("recap_*.json"))
    check("复盘 JSON 落盘", len(recap_files) == 1)
    if recap_files:
        recap = json.loads(recap_files[0].read_text(encoding="utf-8"))
        check("评分 10 维齐全", set(recap["scores"]) == set(C.SCORE_DIMS))
        check("分数 0-2 合法", all(isinstance(v, int) and 0 <= v <= 2 for v in recap["scores"].values()))
        check("homework 恰好 3 条", len(recap["homework"]) == 3, str(recap["homework"]))
        check("总分与档位存在", "total" in recap and "band" in recap)
        print(f"  [info] 总分 {recap['total']}/20 档位 {recap['band']} "
              f"scores={recap['scores']}")

# ---------------------------------------------------------------------
print("== 4) S2 skip 换轨 ==")
with tempfile.TemporaryDirectory() as td:
    f = str(Path(td) / "s.json")
    st = st_mod.new_session(f)
    engine._set_current(st, C.INTRO_QUESTION_ID, C.INTRO_QUESTION)
    st_mod.save(st, f)
    fast = [
        "边侧网关项目,我负责ULL上的C多线程守护进程,拉流录像抽帧上云。",   # S0
        "比普通NVR多了上云识别和web事件,数据拉流后三路分发到mp4、mjpeg、云端。",  # skel0
        "三层是算力分工;边侧按模块拆线程,每个.c管一条链路。",                 # skel1
        "我写了recorder,拉流packet进来remux成mp4分段存储。",                  # skel2 → record
        "遇到过写段失败,看log定位到磁盘水位,改了删除策略后正常。",             # skel3
        "web预览能出图,录像目录每60s一个mp4段。",                              # skel4
        "remux不解码,因为ULL没有VPU,时间戳重打就行。",                        # S2 q1
        "这段不是我写的,是recorder我写的。",                                  # S2 skip?
    ]
    for a in fast:
        engine.run_round(f, a, offline=True)
    st = st_mod.load(f)
    # 第 8 条含"不是我写的"→ skip;规则下 facts_denied 应有记录
    check("skip 记入 facts_denied", len(st["facts_denied"]) >= 1, str(st["facts_denied"]))
    check("仍在面试(未结束)", not st["ended"])

print("== 5) 排障句(idx=3)两次 vague → 放行 + pierce + 深挖转 debug ==")
with tempfile.TemporaryDirectory() as td:
    f = str(Path(td) / "s.json")
    st = st_mod.new_session(f)
    engine._set_current(st, C.INTRO_QUESTION_ID, C.INTRO_QUESTION)
    st_mod.save(st, f)
    seq = [
        "边侧NVR项目,我负责ULL上的gateway守护进程,拉流录像抽帧上云。",   # S0 → S1
        "比普通NVR多了上云识别和web事件:拉流后三路分发到录像mp4、抽帧mjpeg、事件sqlite。",  # skel_0 solid
        "三层是算力分工:V821只推流,ULL跑多线程守护进程,云端识别;边侧每个.c管一条链路。",  # skel_1 solid
        "我写了recorder和frame_grabber:packet进来remux成mp4,frame_grabber软解抽jpeg。",   # skel_2 solid
        "挺稳定的,做了很多优化,没出过什么问题。",   # skel_3 vague #1
        "一直很稳,没遇到什么故障。",                 # skel_3 vague #2 → 放行
    ]
    for a in seq:
        engine.run_round(f, a, offline=True)
    st = st_mod.load(f)
    check("放行后 idx=4(进最后一句)", st["skeleton_idx"] == 4, str(st["skeleton_idx"]))
    check("waived+debug_priority", st["skeleton_3_waived"] and st["debug_priority"])
    check("pierce 记在 skel_3", any(p["id"] == "skel_3" for p in st["pierce_points"]))
    check("当前问题切到 skel_4", st["current_qid"] == "skel_4", st["current_qid"])
    engine.run_round(f, "浏览器MJPEG预览有实时画面,事件列表有置信度,录像每60s一个mp4段。", offline=True)
    st = st_mod.load(f)
    check("进 S2 且轨道=debug", st["stage"] == "S2_DEEP" and st["deep_track"] == "debug",
          f"{st['stage']}/{st['deep_track']}")
    check("pass_skeleton=False(排障句未solid)", st["pass_skeleton"] is False)


print(f"\n结果:{PASS} 通过,{FAIL} 失败")
sys.exit(1 if FAIL else 0)
