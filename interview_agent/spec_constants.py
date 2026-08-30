# -*- coding: utf-8 -*-
"""
EdgeFusion 面试官 agent —— 事实层常量。

内容按用户提供的《可运行规格》第 2/3/5/6/8 节写死:
  - ALLOWED_FACTS      只能当作事实的内容(白名单)
  - FORBIDDEN_CLAIMS   候选人一旦声称即判 invented 的清单
  - INVENTED_PATTERNS  规则引擎预检用的正则(带否定词护栏,防止误伤"没实现/无硬解")
  - 题库               S0 引言 / S1 骨架五问(含换问法变体) / S2 六轨道 / S3 八股挂钩 / S4 权衡

本文件是唯一事实来源,engine / judge_prompt 均从这里取值,运行期不允许改。
"""

import re

# =====================================================================
# 1. 项目白名单(规格第 2 节,只能当事实)
# =====================================================================

ALLOWED_FACTS = {
    "架构": [
        "端:V821 / Tina Linux / musl / MIPI CSI → H.264 硬编 → Wi-Fi RTSP rtsp://<ip>:8554/ch0,1080p@15fps",
        "边:IMX6ULL-Pro / Buildroot / glibc / Cortex-A7 800MHz,无 H.264 硬解 VPU",
        "云:阿里百炼 qwen3.6-plus,OpenAI 兼容 HTTPS,字段名 anthropic_* 是历史遗留",
        "边侧工程:edgefusion_gateway,C 多线程守护进程",
    ],
    "边侧模块(源文件级)": [
        "main.c 入口/信号/启动顺序",
        "conf key=value + 原子保存 + 热加载",
        "stream_receiver RTSP 拉流 + 扇出(录像/抽帧/转发)+ 重连,rtsp_transport=tcp,重连 3s",
        "recorder H.264 remux → fragmented MP4,60s 分段,循环覆盖,frag_keyframe+empty_moov",
        "frame_grabber 软解 H.264 → swscale → MJPEG,缓存最新帧",
        "cloud_ai JPEG 上云 + JSON 解析 + 热启停;ai_fps=1,实际被云端 3–4s/次限速",
        "event_bus SQLite + 快照 + 订阅广播",
        "alarm GPIO sysfs,引脚当前 -1 禁用",
        "rtsp_server 自研轻量 RTSP,H.264 passthrough,rtsp://<ull-ip>:8554/track0",
        "web 自研 HTTP:MJPEG / API / MP4 Range 回放 / 配置热加载",
        "MQTT:仅配置项,未实现(缺 libmosquitto)",
    ],
    "工程约束": [
        "交叉编译 arm-buildroot-linux-gnueabihf",
        "链 FFmpeg / curl / openssl / sqlite3 / json-c / pthread",
        "V821 无 setsid,必须串口拉起;ULL 可用 setsid + adb 后台",
        "V821 IP 走 wlan0 DHCP,会变,需改 rtsp_url",
        "板上 HTTPS 需要 CA bundle + DNS",
    ],
    "已验证/未做(README 2026-07-02)": [
        "已做:拉流录像、上云视觉、事件入库、Web、本地 RTSP 转发",
        "未做:MQTT 网络代码、V821 pdet 预筛选、OTA、多路、72h 稳定性",
        "GPIO 报警代码有,引脚未定",
    ],
}


def allowed_facts_text() -> str:
    """渲染成嵌入系统提示的纯文本。"""
    parts = []
    for sec, items in ALLOWED_FACTS.items():
        parts.append(f"【{sec}】")
        parts.extend(f"- {x}" for x in items)
    return "\n".join(parts)


# =====================================================================
# 2. 禁止编造清单(规格第 3 节)
# =====================================================================

FORBIDDEN_CLAIMS = [
    "MQTT 已打通上报",
    "IMX6ULL 有硬解 VPU / 硬解 H.264",
    "端侧做了完整智能检测/pdet 预筛选并已上线",
    "多路摄像头已接入",
    "OTA / 72h 稳定性已完成",
    "GPIO 引脚已定且现场联动已验证",
    "使用 epoll 高性能服务器、线程池框架、零拷贝、自研协议栈等(仓库未写)",
    "把云端视觉说成「端侧模型推理」",
    "把 sample_rtsp 说成自研编码器",
]

# 允许的说法(命中禁令主题但带否定/限定时不算编造)
FORBIDDEN_ALLOWED_PHRASES = [
    "配置里有 MQTT 但没实现",
    "GPIO 模块在,引脚还是 -1",
]

# =====================================================================
# 3. 规则引擎预检:invented 正则(先于模型执行,规格第 9 节第 7 条)
#    每条 = (标签, 正则)。命中后先看前面一小段有没有否定词,有则放行。
# =====================================================================

# (label, pattern)  pattern 里不含否定词;命中后由 rule_check_invented 做否定/假设护栏
INVENTED_PATTERNS = [
    ("MQTT 已打通/已实现",
     r"mqtt[^。\n,;,;]{0,16}(打通|完成|实现|接入|上报成功|上报过)|(打通|完成|实现|接入|成功上报)[^。\n,;,;]{0,16}mqtt"),
    ("IMX6ULL 硬解/VPU",
     r"(硬解|硬件解码|vpu\s*解码)|(imx6ull|ull|这块板|板子)[^。\n,;,;]{0,8}(?<![没不无])(有|带|支持)[^。\n,;,;]{0,8}(vpu|硬解)"),
    ("端侧智能/pdet 已上线",
     r"(端侧|边缘端|本地)[^。\n,;,;]{0,10}(推理|跑(了)?模型|跑(了)?检测|做了检测|智能检测|检测模型|识别模型)|pdet[^。\n,;,;]{0,10}(已|完成|上线|跑通)"),
    ("多路摄像头已接入",
     r"(多路|多路摄像头|多个摄像头|几路摄像头|四路|八路)[^。\n,;,;]{0,10}(接入|接了|支持|同时跑|已经)|(接入|接了|支持|同时跑|已经)[^。\n,;,;]{0,6}(多路|多路摄像头|多个摄像头|几路摄像头|四路|八路)"),
    ("OTA / 72h 稳定性已完成",
     r"(ota|72\s*小时|72h|七十二小时)[^。\n,;,;]{0,10}(完成|已|通过|跑完|验证)|(稳定运行|连续运行)[^。\n,;,;]{0,8}(72|三天|3天)"),
    ("GPIO 引脚已定且联动已验证",
     r"gpio[^。\n,;,;]{0,12}(引脚)?(已定|定了|已验证|联动成功)|引脚[^。\n,;,;]{0,6}已?定(且|并)[^。\n,;,;]{0,8}验证"),
    ("epoll/线程池/零拷贝/自研协议栈",
     r"(用|基于|实现|写了|搭了)[^。\n,;,;]{0,10}(epoll|线程池|零拷贝|自研协议栈)"),
    ("云端视觉说成端侧推理",
     r"(端侧|本地)(的)?(大模型|多模态|视觉模型)"),
    ("sample_rtsp 说成自研编码器",
     r"(自研|自己写)[^。\n,;,;]{0,12}(编码器|encoder)|sample_rtsp[^。\n,;,;]{0,8}自研"),
]

_INVENTED_COMPILED = [(lbl, re.compile(p, re.IGNORECASE)) for lbl, p in INVENTED_PATTERNS]
# 否定/假设护栏词:出现在匹配段内部或前 14 字内 → 放行,交给模型做语义判定。
# 有意偏向放行:规则引擎是预检不是终审,误放过的由模型兜,误打断的没人救。
_GUARD = re.compile(r"没|未|不是|不|无|非|缺|尚未|还没|仅配置|只是配置|还在?规划|如果|假如|要是|假设|给你")


def rule_check_invented(text: str):
    """规则引擎预检。返回命中标签(str)或 None。

    护栏:命中的整段(含前 20 字、后 6 字)里出现否定词(没/未/无/仅配置…)
    或假设词(如果/假如/给你…)则放行,交给模型做语义级判定,
    避免「MQTT 没实现」「ULL 没有 VPU」「如果换带 VPU 的板子就能硬解」被误杀。
    """
    for label, cre in _INVENTED_COMPILED:
        m = cre.search(text)
        if not m:
            continue
        window = text[max(0, m.start() - 20):m.end() + 6]
        if _GUARD.search(window):
            continue
        return label
    return None


# =====================================================================
# 4. 题库
# =====================================================================

# ---- S0 引言(固定一问) ----
INTRO_QUESTION_ID = "intro_0"
INTRO_QUESTION = "用 60 秒介绍这个项目解决什么问题、你负责哪一层。"

# ---- S1 骨架五问(规格第 6 节;每句带换问法变体,vague 时轮换) ----
SKELETON_QUESTIONS = [
    {"id": "skel_0",
     "text": "这套 NVR 要解决什么,和普通只录像的 NVR 差在哪?",
     "variants": ["换个说法:客户问你「这盒子比市面 NVR 多了什么」,用两句话讲清。"]},
    {"id": "skel_1",
     "text": "为什么拆成 V821 + ULL + 云三层?边侧这些 .c 为什么按模块拆?",
     "variants": ["假如把全部功能塞进 V821 一层做,会先坏在哪?边侧为什么拆成这十来个模块、这些线程?"]},
    {"id": "skel_2",
     "text": "你写的是哪几个文件,数据从 RTSP 进到事件出怎么走?",
     "variants": ["别讲整体架构,只点名:哪几个 .c 是你亲手写的?里面数据怎么流的?"]},
    {"id": "skel_3",
     "text": "讲一个板上真实问题:现象、定位步骤、修改。",
     "variants": ["不讲顺利的,讲卡住最久的一次:当时现象是什么?你用什么手段定位?最后改了什么?"]},
    {"id": "skel_4",
     "text": "怎样证明能跑(Web 预览、事件置信度、MP4 段、VLC 转发择一讲细)?",
     "variants": ["我不看 README。现场凭什么让我相信系统跑起来了?挑一个证据讲细。"]},
]

# ---- S2 深挖六轨道(规格第 5 节) ----
DEEP_QUESTIONS = {
    "stream": [
        ("stream_1", "拉流线程和录像/抽帧/转发如何扇出,拷贝还是引用?"),
        ("stream_2", "为何 RTSP 用 TCP,UDP 会怎样?"),
        ("stream_3", "断流怎么发现、3 秒重连会不会叠连接?"),
        ("stream_4", "为何不用 stimeout(与仓库 FAQ 对齐)?"),
        ("stream_5", "粘包/半包对 RTSP/TCP 意味着什么,FFmpeg 在哪一层处理?"),
        ("stream_6", "锁/队列在哪,会不会阻塞抽帧?"),
    ],
    "record": [
        ("record_1", "为何不解码直接 remux?"),
        ("record_2", "fragmented MP4 + frag_keyframe+empty_moov 解决断电什么问题?"),
        ("record_3", "60s 切段时时间戳/关键帧怎么对齐?"),
        ("record_4", "磁盘 <500MB 怎么删,会不会删正在写的段?"),
        ("record_5", "vfat/TF 卡写失败怎么处理?"),
    ],
    "frame": [
        ("frame_1", "为何必须软解(无 VPU)?"),
        ("frame_2", "1fps 上云和 5fps MJPEG 是否同一解码器?"),
        ("frame_3", "最新帧缓存几个、谁读谁写、要不要锁?"),
        ("frame_4", "640 宽缩放在哪做,CPU 占用怎么看过?"),
    ],
    "cloud": [
        ("cloud_1", "请求是独立线程还是同步挡拉流?"),
        ("cloud_2", "云端 3–4 秒一次,本地 1fps 如何限速/丢帧?"),
        ("cloud_3", "JSON 解析失败、403、无 CA、无 DNS 分别怎么处理?"),
        ("cloud_4", "热关 ai_enable 如何停在途请求?"),
        ("cloud_5", "为何字段叫 anthropic 却走 OpenAI 兼容?"),
    ],
    "web_rtsp": [
        ("web_rtsp_1", "HTTP 和 RTSP 是否独立线程?"),
        ("web_rtsp_2", "MJPEG 边界怎么切,多浏览器连接会否拖垮软解?"),
        ("web_rtsp_3", "MP4 Range 回放怎么实现?"),
        ("web_rtsp_4", "passthrough 转发还要不要解包 RTP?"),
        ("web_rtsp_5", "配置热加载哪些项即时生效?"),
    ],
    "debug": [
        ("debug_1", "举一次真实失败(IP 变化 / CA / 403 / 录像 probe 失败 / adb 进程被杀)。"),
        ("debug_2", "用什么看:log、ps、netstat、adb、VLC?"),
        ("debug_3", "改了哪一行配置或哪段代码?"),
        ("debug_4", "如何确认修好?"),
    ],
}

# 轨道推进方向(数据流顺序环),consecutive_vague>=3 时换"相邻"轨道用
TRACK_CYCLE = ["stream", "record", "frame", "cloud", "web_rtsp"]

# 从 S1 第 2 句(你写了什么)推断深挖轨道的关键词
TRACK_INFERENCE_KEYWORDS = {
    "stream":    ["拉流", "断流", "重连", "av_read_frame", "扇出", "stream_receiver"],
    "record":    ["录像", "mp4", "remux", "分段", "切段", "循环覆盖", "recorder"],
    "frame":     ["抽帧", "mjpeg", "软解", "swscale", "解码", "jpeg", "frame_grabber"],
    "cloud":     ["上云", "云端", "json", "https", "百炼", "限速", "cloud_ai"],
    "web_rtsp":  ["web", "http", "转发", "range", "rtsp_server", "浏览器", "回放"],
    "debug":     ["排障", "定位", "排查", "查问题", "修 bug", "调试"],
}

# 规则引擎兜底用的"深挖追加问"(题库不足 6 问时,注入故障场景追问)
DEEP_FOLLOWUP_FAULTS = {
    "stream":    "V821 断电重启后 wlan0 DHCP 拿到了新 IP",
    "record":    "写段写到一半 TF 卡被拔",
    "frame":     "云端限速到 3–4 秒才回一次、本地还是 1fps 在抽帧",
    "cloud":     "板上没装 CA bundle、也没配 DNS",
    "web_rtsp":  "两个浏览器同时开 MJPEG 预览",
    "debug":     "把你修过的那个问题在板上重新复现一次",
}

# ---- S3 八股挂钩(必须从 deep_track + facts_confirmed 长出,禁止题库空降) ----
BAGU_HOOKS = {
    "stream":    ["TCP 与 UDP 的取舍", "阻塞 I/O", "重连与幂等", "线程间传递缓冲"],
    "record":    ["文件 I/O 与缓冲", "fsync 时机", "原子替换", "循环缓冲思想"],
    "frame":     ["生产者消费者", "环形缓冲", "锁粒度", "YUV 与 JPEG"],
    "cloud":     ["HTTPS 握手", "超时与重试", "背压", "配置热更新"],
    "web_rtsp":  ["HTTP 基础", "Range 语义", "线程模型 vs select/poll(用了什么问什么,没说 epoll 不默认)"],
    "debug":     ["日志级别设计", "netstat/ps 用法", "最小复现"],
}

# ---- S4 权衡题(规格第 4 节说"见题库",此处按白名单补齐) ----
TRADEOFF_QUESTIONS = [
    ("tw_1", "拉流为什么走 TCP?换成 UDP 会省什么、会新增什么麻烦?现场哪种故障更常见?"),
    ("tw_2", "录像为什么只 remux 不转码?给你一块带 VPU 的板子,你会改哪几处?为什么现在不改?"),
    ("tw_3", "浏览器预览为什么选 MJPEG 而不是 HLS/WebRTC?延迟、CPU、兼容各付出了什么?"),
    ("tw_4", "为什么抽 JPEG 上云而不是端侧跑模型?1fps 是怎么定的,再提高会先撞上什么墙?"),
]

# =====================================================================
# 5. 判定辅助 token(rule_judge / 启发式评分用)
# =====================================================================

MODULE_TOKENS = [
    "stream_receiver", "recorder", "frame_grabber", "cloud_ai", "event_bus",
    "alarm", "rtsp_server", "web", "conf", "main.c", "gateway",
]
FLOW_TOKENS = [
    "扇出", "分发", "队列", "锁", "互斥", "线程", "重连", "断流", "关键帧",
    "时间戳", "remux", "转码", "解码", "软解", "缩放", "swscale", "上云",
    "https", "json", "gpio", "sqlite", "range", "mjpeg", "mp4", "分段",
    "循环", "磁盘", "日志", "log", "复现", "定位", "probe", " adb", "vlc",
    "串口", "dhcp", "ca", "dns", "403", "setsid", "tcp", "rtp", "sps", "pps",
]
SKIP_PATTERNS = [
    "不是我写", "没写", "不是我做的", "队友写的", "不熟", "没参与",
    "原项目就有", "开源带来", "抄的", "没做过", "不了解",
]
TOOL_TOKENS = ["log", "日志", "ps", "netstat", "adb", "vlc", "串口", "probe", "复现", "top"]

# =====================================================================
# 6. 评分表(规格第 8 节,S5 用)
# =====================================================================

SCORE_DIMS = [
    "骨架完整", "个人边界", "数据流", "并发", "网络",
    "存储", "排障", "资源约束", "八股贴项目", "表达",
]

SCORING_RUBRIC_TEXT = """| 项 | 0 | 1 | 2 |
|----|---|---|---|
| 骨架完整 | 缺 2 句以上 | 5 句有但虚 | 5 句具体 |
| 个人边界 | 端边云全揽 | 能区分模块 | 能说清自己写/没写(MQTT/GPIO/pdet) |
| 数据流 | 讲不清扇出 | 能说拉流→三路 | 能说缓冲/是否解码 |
| 并发 | 只会说多线程 | 能点模块 | 能说共享帧/锁或「没锁但如何避」 |
| 网络 | 只会 RTSP 单词 | TCP 拉流+重连 | 能讲断流、IP 变化、HTTPS 失败 |
| 存储 | 不会切段 | 知道 60s fMP4 | 懂断电与循环删 |
| 排障 | 没有真实案例 | 有现象无步骤 | 有 log/工具/复现 |
| 资源约束 | 当 PC 软件讲 | 知道 ULL 无 VPU | 能连到软解/1fps/限速 |
| 八股贴项目 | 空背 | 能挂钩 | 能用项目例子解释 |
| 表达 | 套话 | 能跟追问 | 能画/能伪代码 |"""

BANDS = [
    (8,  "入门", "先改简历,删「MQTT/多路/端侧智能」"),
    (13, "能面", "补排障和第 2 条数据流"),
    (17, "稳面", "可投目标厂"),
    (20, "能冲", "主项目可打 25 分钟"),
]

# 简历删词默认检查(规格第 8 节)
RESUME_FLAGS = ["精通", "MQTT 已", "MQTT 已完成", "打通 MQTT", "硬解", "多路", "OTA", "零拷贝", "线程池", "端侧推理"]

# homework 候选池(按薄弱维度取"原理名",只给名字不给讲解)
HOMEWORK_POOL = {
    "骨架完整": ["三层架构职责划分", "模块边界与进程内组合", "项目一段话定位"],
    "个人边界": ["个人贡献表述", "开源与自研边界", "简历真实性检查"],
    "数据流": ["av_read_frame 三去向", "packet 引用与拷贝语义", "旁路与主路分离"],
    "并发": ["pthread 互斥锁粒度", "生产者消费者模式", "锁竞争与避让"],
    "网络": ["RTP over TCP 粘包", "重连幂等设计", "HTTPS 证书链与 CA"],
    "存储": ["fragmented MP4 结构", "断电可恢复写入", "循环覆盖删除策略"],
    "排障": ["最小复现方法", "板上日志链路", "网络工具三件套"],
    "资源约束": ["无 VPU 下的软解选型", "CPU 占用测量", "帧率节流"],
    "八股贴项目": ["TCP 与 UDP 取舍", "阻塞 I/O 模型", "HTTP Range 语义"],
    "表达": ["白板数据流图", "伪代码描述线程", "追问下的收敛表达"],
}
