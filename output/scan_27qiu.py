# -*- coding: utf-8 -*-
"""27届秋招全表定向扫描：嵌入式Linux应用·音视频方向"""
import json, re

BASE = "C:/Users/Windows/Desktop/EdgeFusion_Smart_NVR/output/"

def load_cells(path, col_idx):
    d = json.load(open(path, encoding="utf-8"))
    data = d.get("data", d)
    vr = data.get("value_ranges") or data.get("ranges")
    cells = vr[0]["cells"] if isinstance(vr, list) else vr["cells"]
    out = {}
    for i, row in enumerate(cells):
        if not row: continue
        c = row[col_idx] if col_idx < len(row) else None
        v = (c.get("value", "") if isinstance(c, dict) else str(c or "")).strip()
        if v: out[i] = v
    return out

# B=0公司 C=1岗位 D=2类别 E=3城市 F=4发布时间 G=5业务
main = json.load(open(BASE + "feishu_27qiu_full.json", encoding="utf-8"))
data = main.get("data", main)
vr = data.get("value_ranges") or data.get("ranges")
cells = vr[0]["cells"] if isinstance(vr, list) else vr["cells"]

def gv(row, idx):
    if not row or idx >= len(row): return ""
    c = row[idx]
    return (c.get("value", "") if isinstance(c, dict) else str(c or "")).strip()

links = load_cells(BASE + "feishu_27qiu_links.json", 0)  # I列
codes = load_cells(BASE + "feishu_27qiu_links.json", 1)  # J列

# 已投49家（子串匹配）
APPLIED = ["安克","小鹏","海兴电力","星际悦动","芯矩","迈普","华睿","360","清闲","南京青络","欧摩威","湘滨","北汽重卡","宇视","苍宇天基","通嘉宏瑞","中国通号","三一","韶音","歌尔","tp-link","tplink","tp link","普联","联洲","sharpa","小米","mova","海康","萤石","大华","大疆","影石","亿联","华为","vivo","荣耀","传音","oppo","紫光展锐","展锐","字节","博世","中兴","联想","比亚迪","理想","零跑","美团","京东","中国移动","西门子","京东方"]
# 上次18号已推荐
LAST_REC = ["恩智浦","nxp","联发科","mediatek","恒玄","卓驭","乐鑫","极目智能","埃科光电","虹软","芯原","经纬恒润","文远知行","卡尔动力","元戎启行","星尘智能","宇树","智元","普渡","格见","海克斯康","它石智航","正浩","ecoflow","航天智能","穹彻","融创微","中科光电","阳光电源","新易盛","联合飞机","四方股份","昆仑芯","固胜","宇量昇","航空无线电","牧原","镭目","北电检测","502所","易动宇航","舞肌","希夕","原力灵机","是为科技","科华","麦格米特","长飞","中广核","杰华特","精进电动"]

# 方向关键词
KW_STRONG = ["音视频","视频","流媒体","camera","相机","图像","多媒体","ffmpeg","rtsp","编解码","ipc","监控","视觉应用","媒体"]
KW_CORE   = ["嵌入式软件","嵌入式开发","linux","固件","嵌入式工程","软件工程师","嵌入式系统","c++"]
KW_DROP   = ["ic设计","数字ic","模拟ic","版图","验证工程师","芯片设计","数字设计","结构工程师","电气工程师","电力系统","电机设计","硬件工程师","fpga工程师","天线","射频","算法工程师","slam","pcB设计","pcb设计","电机控制","测试工程师","光学","工艺","量化"]

def is_announcement(comp):
    return bool(re.search(r"更新|公告|建议|休假|兄弟|注意|加油|月底|批次|面试流程|内推码的|有hc|还有机会|投的", comp))

rows = []
for i, row in enumerate(cells):
    r = i + 5
    comp = gv(row, 0)
    if not comp or is_announcement(comp): continue
    pos  = gv(row, 1)
    cat  = gv(row, 2)
    city = gv(row, 3)
    pub  = gv(row, 4)
    biz  = gv(row, 5)
    link = links.get(i, "")
    code = codes.get(i, "")
    low = (comp + " " + pos + " " + biz).lower()
    applied = any(a in low for a in APPLIED)
    lastrec = any(a in low for a in LAST_REC)
    strong = [k for k in KW_STRONG if k in low]
    core   = [k for k in KW_CORE if k in low]
    drops  = [k for k in KW_DROP if k in low]
    # 打分：strong命中且非drop主导 -> A；core命中且drop<=2 -> B；边界存疑 -> S
    if strong and not applied:
        grade = "A" if len(drops) <= 1 else "S"
    elif core and not applied:
        grade = "B" if len(drops) <= 2 else "S"
    elif applied:
        grade = "已投"
    else:
        continue
    rows.append(dict(r=r, comp=comp, pos=pos[:60].replace("\n","/"), cat=cat, city=city[:20], pub=pub, biz=biz[:40].replace("\n","/"), link=link[:50], code=code[:30].replace("\n","/"), grade=grade, applied=applied, lastrec=lastrec, strong=",".join(strong), drops=",".join(drops)))

# 已投公司的复出行：有 strong 命中的单独列出
recheck = [x for x in rows if x["applied"] and x["strong"]]
rows_new = [x for x in rows if not x["applied"]]

print(f"总数据行 {len(cells)+5-5} | 新推荐候选 {len(rows_new)} | 已投复出行 {len(recheck)}\n")
print("=== A 档候选（强方向命中）===")
for x in [r for r in rows_new if r["grade"]=="A"]:
    tag = " [上次已荐]" if x["lastrec"] else ""
    print(f"R{x['r']} {x['comp']}{tag} | {x['pos']} | {x['city']} | {x['pub']} | 命中:{x['strong']} | 剔:{x['drops']}")
print("\n=== S 档存疑（命中但drop多，需人工）===")
for x in [r for r in rows_new if r["grade"]=="S"]:
    tag = " [上次已荐]" if x["lastrec"] else ""
    print(f"R{x['r']} {x['comp']}{tag} | {x['pos']} | 命中:{x['strong']} | 剔:{x['drops']}")
print("\n=== B 档候选（嵌入式软件通用）===")
for x in [r for r in rows_new if r["grade"]=="B"]:
    tag = " [上次已荐]" if x["lastrec"] else ""
    print(f"R{x['r']} {x['comp']}{tag} | {x['pos'][:40]} | {x['city'][:16]} | {x['pub']}")
print("\n=== 已投公司复出行（有方向命中，可能有新岗）===")
for x in recheck:
    print(f"R{x['r']} {x['comp']} | {x['pos'][:50]} | 命中:{x['strong']}")

json.dump(rows_new, open(BASE + "scan_result.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n[saved] scan_result.json")
