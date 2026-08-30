# EdgeFusion 面试官 agent(CLI)

单会话、单项目面试官:嵌入式 Linux 应用开发一面 × EdgeFusion 云端协同智能 NVR。
一次只问一个问题;不表扬、不给标准答案、不替候选人补经历;状态落盘 JSON,支持中断续面。

按《可运行规格》实现:状态机在代码里,模型只负责「根据 state 出下一问 + 判定当前回答」。

## 快速开始

```bash
cd interview_agent

# 可选:接模型(OpenAI 兼容接口;不配则全自动走规则引擎,也能完整跑完一场)
export INTERVIEW_API_KEY=sk-xxx
export INTERVIEW_BASE_URL=https://open.bigmodel.cn/api/paas/v4   # 默认值
export INTERVIEW_MODEL=glm-4.6                                    # 默认值

python main.py new                  # 开一场(覆盖旧会话)
python main.py answer "回答内容"    # 每轮:判定→更新状态→只打印下一问
python main.py answer -             # 多行回答,从 stdin 读
python main.py status               # 看进度/轨道/pierce
python main.py recap                # 复盘(S4 答完会自动触发)
python selftest.py                  # 自测:禁令正则 + 离线全流程(不需要模型)
```

状态文件默认 `interview_state.json`(与脚本同目录),`--file PATH` 可换;复盘写
`recap_<session_id>.json`。写入走 `tmp + 原子替换`,中断不会损坏续面能力。

## 文件

| 文件 | 职责 |
|---|---|
| `spec_constants.py` | 白名单 ALLOWED_FACTS / 禁令 FORBIDDEN_CLAIMS / invented 正则 / 全部题库 / 评分表 |
| `state.py` | InterviewState 落盘读写(规格字段 + 簿记字段) |
| `judge_prompt.md` | 模型系统提示;`{{ALLOWED_FACTS}}`/`{{FORBIDDEN_CLAIMS}}` 由常量层注入 |
| `engine.py` | 一轮流程、状态机转移、规则引擎兜底、S5 复盘评分 |
| `main.py` | CLI:new / answer / status / recap |
| `selftest.py` | 离线自测(39 项断言) |

## 一轮流程(engine.run_round)

1. 读 state;
2. **规则引擎预检 invented**(先于模型):命中禁止清单正则 → 直接打断,不进模型;
3. 未命中且有 API → 模型判定(输出结构化 JSON);解析失败重试一次,再失败 → 规则引擎;
4. 更新 state 落盘;
5. **只打印下一问**。

无 API / `--offline` / 模型连续失败时,整场自动降级为规则引擎模式:`solid` 判定靠
「模块名/数据流 token + 长度」,出题按题库顺序;深挖题库不足 6 问时注入故障场景追问。

## 规则引擎的护栏(有意设计)

`invented` 预检正则自带否定/假设护栏:命中的整段(前 20 字、后 6 字)里出现
「没/未/无/仅配置/如果/假如/给你…」就放行,交给模型做语义级判定。
**有意偏向放行**——规则是预检不是终审,误放过的模型能兜住,误打断的没人救。
所以像「MQTT 没实现」「ULL 没有 VPU」「如果换带 VPU 的板子就能硬解」都不会被误杀;
代价是极少数精心构造的肯定句可能漏网,接模型时由模型终审。

## 对规格的实现说明(只加不改)

- 规格字段(section 1 schema)语义原样;另加**簿记字段**:`skeleton_verdicts`
  (逐句最终判定,过关门「第3、4句至少 solid」需要它)、`current_qid/current_question`
  (CLI 跨进程必须记当前待答问题)、`transcript`(复盘评分的证据)、`debug_priority` 等。
- 「第3句(排障)」按规格的 `skeleton_idx` 编号实现为 **idx=3**(排障句),过关门校验
  idx=3/4 两句;idx=3 连续两次 vague → 放行 + pierce「无真实排障」+ 深挖转 debug。
- S4 权衡题规格说「见题库」但未列出,按白名单补了 4 问(TCP/UDP、remux/转码、
  MJPEG/HLS、上云/端侧),规则模式固定问 3 问。
- S5 评分:有模型走模型(评分表原文进提示),否则启发式(token 证据计数);
  `homework` 恰好 3 条原理名,从最薄弱 3 维的池子里取。

## 和 `.claude/agents/nvr-interviewer.md` 的关系

那个是 ZCode 会话内的提示词面试官(专项拷打);本目录是**独立可运行的 CLI**,
带落盘状态机与规则兜底,可在任何终端/机器上跑,不依赖 ZCode。两者共用同一套项目事实。
