# Phase 1.5 H.264 / RTSP / RTP 协议核心任务验收手册

> 版本：2026-08-13（2026-08-19处置修订）  
> 总预算：9.5h（旧口径）→ 16.5h（2026-08-17校准）→ **约10h（2026-08-19秋招策略压缩）**  
> 主源码：`rtsp_server.h/c`，输入调用点`stream_receiver.c:132-139,165-168`  
> 规范坐标：当前实现输出`RTSP/1.0`，以RFC 2326对照；H.264/RTP以RFC 6184对照；SDP以RFC 4566的格式角色为坐标。

## 处置修订（2026-08-19，用户确认）

按"先全图后深钻 + 面试命中率分层"策略，本阶段拆三层执行，原任务卡全文保留作参考与回补依据：

| 层 | 内容与做法 | 预算 |
| --- | --- | ---: |
| **概念层（必做）** | 四组知识块（组二H.264语法→组四RTP→组一RTSP→组三SDP从简），按`nvr-knowledge-tutor.md`六阶段闭环执行，认证L2 | ~6.5h |
| **实现层（压缩）** | P1全程 + P2/P5浅层：目标是能讲清一次完整点播时序（DESCRIBE→SDP→SETUP→PLAY→NALU→RTP→客户端）并支撑面试2-3层追问 | ~3-4h |
| **审计层（降级）** | P3走读SDP生成路径与风险；P4/P6不逐字节精读。五项缺陷（RTCP仅端口骨架、AVCC声称支持实未实现、SPS/PPS硬编码缺省、无PTS回退、慢客户端持锁阻塞）以**一句话结论**形式掌握，作为"项目问题与改进"面试素材 | ~0.5h |

深钻是否回补，由Phase 6模拟面试实测反馈决定，不预先投入。

**2026-08-23 二次精简（用户决定：通用 Linux 岗为主，AV 只留「秋招高频」或「项目自研句必答」）**：概念层 B2–B13 压为 7 个学习单元 ≈4h——B5/B7/B8/B12/B13 取消独立开块，核心以一句话并入相邻单元（B5→B4、B7/B8→B6 合并块、B12→B10/B11、B13→B2/B11），块文件保留为提升阶段材料；执行结构以 `Phase1.5预制包/README` 状态表为准。实现层同步合并：P1+P5 合为一次完整点播时序走读（~2–2.5h），P3 并入走读一句话；审计层 0.5h 不变。**本阶段总预算 10h→约 7h。**

## 审计学习原则

每个结论分三层：

| 层次 | 要回答什么 |
| --- | --- |
| 协议应然 | 规范定义了什么，解决什么问题 |
| 源码实然 | 本项目实际写了什么 |
| 工程结论 | 实现是完成、简化、有缺口还是与注释矛盾 |

不允许把函数名或注释当作已实现证据。

本手册中的“必交产出”和通过标准是诊断题库。Tutor可根据用户表现选择最有区分度的口述、图表、字节样例或变式追问,不要求逐项交齐；但协议角色、字节边界或阻塞风险等关键因果仍错时不得推进。

## 任务总表

| ID | 主题 | 时间 | 必交产出 | 状态 |
| --- | --- | ---: | --- | --- |
| P1 | RTSP信令、RTP媒体、RTCP反馈 | 1.5h | 信令/媒体泳道图、实现差距表 | 待办 |
| P2 | GOP/IDR/SPS/PPS、Annex B/AVCC | 2h | NALU类型表、两种格式样例、审查报告 | 待办 |
| P3 | codecpar/extradata到SDP | 1.5h | 参数路径图、SDP字段表 | 待办 |
| P4 | `parse_nalus`分析器 | 1.5h | 手工走样例、边界表 | 待办 |
| P5 | RTP单NALU、FU-A、序号/时间戳/marker | 2h | 大NALU分片图、RTP头表 | 待办 |
| P6 | 客户端生命周期、慢客户端与总验收 | 1h | 锁/阻塞时序图、完整口述 | 待办 |

## P1 · RTSP、RTP、RTCP的角色与会话骨架

源码：`rtsp_server.h:8-20`；`rtsp_server.c:145-176,329-535`；`stream_receiver.c:132-139,165-168`  
时间盒：20分钟角色 + 30分钟信令 + 20分钟实现对照 + 20分钟闭卷

### 阅读任务

1. 先画两条线：RTSP TCP控制信令；RTP在UDP或RTSP TCP interleaved中的媒体数据。
2. 将`OPTIONS → DESCRIBE → SETUP → PLAY → GET_PARAMETER/TEARDOWN`标出输入、输出和修改的`client_t`状态。
3. 定位UDP RTP/RTCP端口和TCP interleaved channel，不进入RTP字节头。

### 引导问题

1. RTSP是否通常自己承载持续视频？TCP interleaved为什么是一个特别情况？
2. DESCRIBE和SETUP分别建立“媒体描述”还是“传输方式”？PLAY改了哪个状态？
3. `session_id/playing/tr/rtp_channel/client_rtp_addr`各自在何时赋值？
4. 当前代码虽创建`udp_rtcp_fd`和RTCP地址，有没有收或发RTCP包？
5. 因此“支持RTCP”应该如何准确表述？

### 通过标准

- 闭卷纠正“RTSP把视频帧一帧帧发过来”的笼统说法。
- 能画出RTSP/1.0信令与RTP数据的分离/交织方式。
- 能指出RTCP只有端口骨架，尚无反馈逻辑。

## P2 · GOP/IDR/SPS/PPS与Annex B/AVCC识别

源码：`rtsp_server.c:50-127`；输入来源`stream_receiver.c:141-168`  
时间盒：30分钟概念 + 30分钟字节样例 + 30分钟源码 + 30分钟纠错/闭卷

### 阅读任务

- 只掌握本项目需要的NALU类型：1非IDR slice、5 IDR、7 SPS、8 PPS、28 FU-A。
- 对比Annex B“起始码分隔”和AVCC/avcC“配置记录或长度前缀”，不把两种AVCC场景混成一个格式。
- 给定一段字节，先判断边界怎样表示，再判NALU type。

### 引导问题

1. 新客户端在IDR前为什么需要SPS/PPS？只有IDR就一定够吗？
2. `nal[0] & 0x1f`取的是哪个字段？
3. Annex B的3字节和4字节起始码如何识别？
4. 普通AVCC sample的4字节NALU长度前缀，与`AVCDecoderConfigurationRecord`内SPS/PPS的2字节长度是同一层吗？
5. 当前`parse_nalus()`没有起始码时把整包当成单NALU；它是否真正支持“4字节大端长度前缀的AVCC packet”？

### 必交与通过

- 交NALU类型/作用表，两个Annex B与两个AVCC/avcC样例的手工判断。
- 闭卷说清SPS/PPS与IDR各自解决什么。
- 不把注释“支持AVCC”当作通过测试的事实。

## P3 · `codecpar/extradata → SPS/PPS → SDP`

源码：`rtsp_server.c:111-143,536-568`；`stream_receiver.c:132-139`  
时间盒：20分钟输入路径 + 25分钟SDP + 25分钟失败边界 + 20分钟闭卷

### 引导问题

1. `codecpar`从哪一路流获得，何时传给`rtsp_server_init()`？
2. extradata是否是持续媒体帧？`sdp_collect_cb`只保存哪两类NALU？
3. `m=video`、`a=control`、`a=rtpmap`、`a=fmtp`分别描述什么？
4. SDP传的是会话/媒体元数据，还是持续H.264帧？
5. 提取失败时代码使用硬编码缺省SPS/PPS；与真实源流不匹配会有什么风险？

### 必交与通过

- 交`AVStream.codecpar.extradata → parse → base64 → sprop-parameter-sets → DESCRIBE`路径图。
- 交SDP字段、数据来源、客户端用途表。
- 能说清SDP的边界，并识别硬编码缺省参数的工程风险。

## P4 · `parse_nalus()`手工走读与边界审查

源码：`rtsp_server.c:50-109`  
时间盒：25分钟伪代码 + 25分钟两样例 + 20分钟越界审查 + 20分钟闭卷

### 引导问题

1. Annex B分支中`pos/q/next_sc`分别指什么？回调是否包含起始码？
2. `len==1`时判断式访问`data[1]`是否安全？
3. avcC配置记录中SPS数量和首个SPS长度应从哪个字节开始？当前`data[4]`/`idx=5`是否对齐？
4. NALU长度超过剩余缓冲区时如何停止？零长NALU是否应回调？
5. 如何设计四个最小测试：3字节起始码、4字节起始码、avcC extradata、AVCC length-prefixed packet？

### 必交与通过

- 交不含C API的解析伪代码、两正常/两异常手工走读表。
- 必须识别三个现实：len=1越界风险、avcC偏移错误、普通AVCC packet未真正实现。
- 这一任务只要求审计和设计测试；修源码须作为另一动手任务授权。

## P5 · RTP头、单NALU与FU-A分片

源码：`rtsp_server.c:198-327`；调用点`stream_receiver.c:165-168`  
时间盒：30分钟RTP头 + 35分钟单NALU/FU-A + 25分钟手工分片 + 30分钟时间戳/marker

### 引导问题

1. RTP 12字节头中V/PT/M/sequence/timestamp/SSRC在源码哪些字节？
2. `nal_len <= MTU-RTP_HDR_LEN`时怎样发？为什么大NALU要跳过原NAL头后分片？
3. FU indicator怎样保留F/NRI并把type改28？FU header怎样保留原type并设S/E？
4. 同一NALU的所有FU-A包时间戳是否相同？sequence如何变化？
5. marker在一个访问单元的最后NALU最后一包置1；当前实现把一个`AVPacket`当成一个访问单元的前提是什么？
6. PTS怎样换算为90kHz？无PTS时恒为0会有什么播放风险？
7. TCP interleaved前的`$ + channel + len16`是RTP头的一部分吗？

### 必交与通过

- 交RTP头字段表，将一个4000字节NALU画成FU-A序列，标每包S/E/M/seq/ts。
- 能闭卷重建FU indicator/header，区分RTP包和TCP interleaved framing。
- 能说出90kHz时间戳换算与无PTS回退的实现边界。

## P6 · 客户端生命周期、慢客户端与协议总验收

源码：`rtsp_server.c:145-198,285-327,361-610`  
时间盒：15分钟生命周期 + 15分钟锁/阻塞 + 15分钟闭卷链路 + 15分钟纠错

### 引导问题

1. accept、SETUP、PLAY、TEARDOWN/断开、deinit分别获得或释放哪些资源？
2. `listen_thread()`是一客户端一线程，还是在同一线程阻塞处理一个客户端？第二个连接会怎样？
3. `rtsp_server_on_packet()`在哪个线程被调用？它持`g_mtx`遍历客户端时执行了什么？
4. TCP控制fd被恢复为阻塞，`send_all()`也可阻塞；慢TCP客户端能否在返回错误前已长时间拖住拉流分发？
5. `fail_count>3`只能处理已返回的发送错误，还是也能防止阻塞写？
6. 当前实现是否可以宣称“慢客户端不影响录像主链”？请用线程和调用栈证明。

### 总验收产出

1. 闭卷画`DESCRIBE → SDP → SETUP → PLAY → H.264 Packet → NALU → RTP/FU-A → TCP/UDP客户端`。
2. 每个箭头标数据形态；标RTSP线程、拉流线程、共享客户端锁。
3. 交“协议应然/源码实然/风险或改进”表，至少包含RTCP、AVCC、SPS/PPS缺省、无PTS、慢TCP客户端五项。

### 通过标准

- 能完整讲清一个H.264 NALU到RTP客户端的路径，正确率≥80%。
- RTSP/RTP角色、SPS/PPS+IDR、FU-A、慢客户端四道why必须正确。
- 必须识别“设计意图上有失败计数”不等于“现有实现不会阻塞主链”。
- 能定位至少8处源码证据。
