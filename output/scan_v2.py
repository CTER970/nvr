# -*- coding: utf-8 -*-
"""27届秋招全表 v2 标准扫描：Linux应用主线准入 + 方向加分 + 红灯否决"""
import json, re

BASE = "C:/Users/Windows/Desktop/EdgeFusion_Smart_NVR/output/"
main = json.load(open(BASE + "feishu_27qiu_full.json", encoding="utf-8"))
data = main.get("data", main)
vr = data.get("value_ranges") or data.get("ranges")
cells = vr[0]["cells"] if isinstance(vr, list) else vr["cells"]
links_raw = json.load(open(BASE + "feishu_27qiu_links.json", encoding="utf-8"))
ld = links_raw.get("data", links_raw)
lvr = ld.get("value_ranges") or ld.get("ranges")
lcells = lvr[0]["cells"] if isinstance(lvr, list) else lvr["cells"]

def gv(row, idx):
    if not row or idx >= len(row): return ""
    c = row[idx]
    return (c.get("value", "") if isinstance(c, dict) else str(c or "")).strip()

# 已投49家
APPLIED = ["安克","小鹏","海兴电力","星际悦动","芯矩","迈普","华睿科技","360","清闲","南京青络","欧摩威","湘滨","北汽重卡","宇视","苍宇天基","通嘉宏瑞","中国通号","三一","韶音","歌尔","tp-link","tplink","tp link","普联","联洲","sharpa","小米","mova","海康","萤石","大华","大疆","影石","亿联","华为","vivo","荣耀","传音","oppo","紫光展锐","展锐","字节","博世","中兴","联想","比亚迪","理想","零跑","美团","京东","中国移动","西门子","京东方","星宸","全志","联发科","mtk","富瀚微"]
# 21号已核（结论文档在 21_官网JD逐岗复核）
VERIFIED = {"苏州科达":"A","寻影":"A","远东通信":"S","华曦达":"A","诺瓦星云":"B","奥比中光":"B","影微创新":"B","晶晨半导体":"C","爱芯元智":"C","翱捷科技":"D","联咏科技":"D","为旌科技":"C","大恒图像":"D","杰理科技":"C","凌云光":"C","康冠科技":"D(主岗)/A(软件工程师岗)"}
LAST_REC = ["恩智浦","nxp","恒玄","卓驭","乐鑫","埃科光电","虹软","芯原","经纬恒润","文远知行","卡尔动力","元戎启行","星尘智能","宇树","智元","普渡","格见","海克斯康","它石智航","正浩","ecoflow","航天智能院","穹彻","融创微","中科光电","阳光电源","新易盛","联合飞机","四方股份","昆仑芯","固胜","宇量昇","牧原","镭目","北电检测","易动宇航","舞肌","希夕","原力灵机","是为科技","科华","麦格米特","长飞","中广核","杰华特","精进电动","极目智能","禾赛"]

# v2 词表
KW_MAIN = ["linux应用","linux 应用","上层应用","应用层","应用软件","业务功能","业务逻辑","多线程","多进程","socket","网络编程","网络通讯","网络通信","进程间通信","系统集成","存储应用","应用开发","软件开发工程师","软件工程师","c++开发","上位机","服务端","后台服务","系统软件"]
KW_DIR  = ["音视频","流媒体","rtsp","ffmpeg","rtp","rtmp","hls","mp4","v4l2","camera","相机","摄像","ipc","nvr","录像","转码","编解码","视频会议","推流","拉流","多媒体","影像","图像"]
KW_RED  = ["ic设计","数字ic","模拟ic","版图","验证工程师","芯片设计","数字设计","数字后端","dft","射频","天线","结构工程师","光学工程师","pcb","laout","layout","stm32","freertos","rtos移植","单片机","mcu","bootloader","uboot","设备树","内核驱动","bring-up","bring up","寄存器配置","波形","示波器","pytorch","模型训练","算法设计","算法研究","rate control","标准提案","电机控制","bms","电源硬件","电力电子","dsp软件","物理层","autosar","fpga工程师","fpga开发","逻辑工程师","数字前端","固件测试"]

def is_ann(t):
    return bool(re.search(r"更新|公告|建议|休假|兄弟|注意|加油|月底|批次|面试流程|内推码的|有hc|还有机会|投的|陆续开启", t))

cands = []
for i, row in enumerate(cells):
    r = i + 5
    comp = gv(row, 0)
    if not comp or is_ann(comp): continue
    pos, cat, city, pub, biz = gv(row,1), gv(row,2), gv(row,3), gv(row,4), gv(row,5)
    link = gv(lcells[i] if i < len(lcells) else [], 0)
    low = (comp + " " + pos + " " + biz).lower()
    if any(a in low for a in APPLIED): continue
    ver = next((v for k,v in VERIFIED.items() if k in comp or comp in k), None)
    reds  = [k for k in KW_RED if k in low]
    mains = [k for k in KW_MAIN if k in low]
    dirs  = [k for k in KW_DIR if k in low]
    # v2 裁决：主线准入（mains>=1 且红灯<=1）→ 打分 = 主线*2 + 方向*1
    if mains and len(reds) <= 1:
        score = len(mains)*2 + len(dirs)*1 - len(reds)*2
        grade = "S" if (score >= 6 and dirs) else ("A" if score >= 4 else ("B" if score >= 3 else "C"))
    elif dirs and not reds and not mains:
        score = len(dirs); grade = "C"  # 只有方向没有主线证据 → 待核降档
    else:
        continue
    last = "📌" if any(a in low for a in LAST_REC) else ""
    cands.append((score, r, comp, pos[:52].replace("\n","/"), city[:18], pub, grade, ver, len(mains), len(dirs), len(reds), last, link[:46]))

cands.sort(key=lambda x: -x[0])
new_pool = [c for c in cands if c[7] is None]
verified_hits = [c for c in cands if c[7]]

print(f"v2 池：新候选 {len(new_pool)} 家 | 已核命中 {len(verified_hits)} 家（结论沿用21号）\n")
print("=== 新候选 TOP40（主线分+方向分排序）===")
for s,r,comp,pos,city,pub,g,v,nm,nd,nr,last,link in new_pool[:40]:
    print(f"[{g}·{s}分|R{r}] {comp}{last} | {pos} | {city} | {pub} | 主{nm}向{nd}红{nr}")
print("\n=== 已核公司命中行（沿用21号结论）===")
for s,r,comp,pos,city,pub,g,v,nm,nd,nr,last,link in verified_hits:
    print(f"[已核:{v}|R{r}] {comp} | {pos[:40]}")
json.dump([{"score":s,"row":r,"comp":comp,"pos":pos,"city":city,"pub":pub,"grade":g,"main":nm,"dir":nd,"red":nr,"lastrec":bool(last),"link":link} for s,r,comp,pos,city,pub,g,v,nm,nd,nr,last,link in new_pool], open(BASE+"scan_v2_result.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n[saved] scan_v2_result.json")
