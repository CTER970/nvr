# Phase 2/3 预制包（开块即用教学材料）

> 预制：2026-08-28（应用户要求，对标 `Phase1.5预制包/` 模式）
> 行号基准：2026-08-28 实测 `edgefusion_gateway/src/`（cloud_ai.c 391 行 / event_bus.c 295 行 / alarm.c 167 行 / web.c 1029 行 / conf.c 304 行 / main.c 停机段）。

## 定位（避免多事实源冲突）

| 文档 | 唯一责任 |
| --- | --- |
| `Phase2任务验收.md` / `Phase3任务验收.md` | 验收标准与任务范围的**事实源** |
| 本预制包 | **开块脚本**：目的四层/脚手架/前置声明/引导问题/闭卷变式/快问快答，已按源码核实行号 |
| `progress.md` | 实时位置 |
| 八股卡片 06/07 | **不预写**，随块收口增量落卡（08-21 规则） |

## 开块审查流程（每块开教前 3 分钟，必做）

1. 重读 `progress.md`「当前位置」，确认无并行会话已推进该块（并行会话常编辑 progress）。
2. `grep -n` 抽查本卡 2–3 个锚点（源码可能因用户执行 TODO 修码而漂移：码率恒0 / L206 锁内快照 / 快照I/O锁外化等）。
3. 快速过一遍本卡「预制时审计发现」小节：若源码已改动，按新代码核实后再用。

## 文件索引

| 文件 | 对应 ID | 时间盒 | 八股出口 |
| --- | --- | ---: | --- |
| `C1_回调与发布订阅.md` | 2.0A | 45min | 06_云AI事件.md |
| `C2_条件变量.md` | 2.0B | 45min | 06_云AI事件.md |
| `P2-2.1_AI线程与JPEG所有权.md` | 2.1 | 60min | 06_云AI事件.md |
| `P2-2.2_云请求与分层失败.md` | 2.2 | 45min | 06_云AI事件.md |
| `P2-2.3A_event_bus发布链.md` | 2.3A | 60min | 06_云AI事件.md |
| `P2-2.3B_alarm与查询支路.md` | 2.3B | 45min | 06_云AI事件.md |
| `P2-2.4_热启停与降级.md` | 2.4 | 60min | 06_云AI事件.md |
| `P2-2.5_Phase2闭卷.md` | 2.5 | 45–60min | 收口收割 |
| `C3_socket生命周期.md` | 3.0A | 45min | 07_Web配置.md |
| `C4_HTTP请求响应.md` | 3.0B | 45min | 07_Web配置.md |
| `P3-3.1_路由与API地图.md` | 3.1 | 60min | 07_Web配置.md |
| `P3-3.2_MJPEG.md` | 3.2 | 90min | 07_Web配置.md |
| `P3-3.3_Range.md` | 3.3 | 90min | 07_Web配置.md |
| `P3-3.4_socket与线程.md` | 3.4 | 75min | 07_Web配置.md |
| `P3-3.5_配置保存与热更新.md` | 3.5 | 75min | 07_Web配置.md |
| `P3-3.6_校验动手与闭卷.md` | 3.6 | 60min | Phase 3 收口 |
| `P3-附_前端appjs略读.md` | 弹性（并入 3.1/3.5） | 20min | 07_Web配置.md |

## 源码锚点速查（2026-08-28 实测；手册 08-22 版行号已漂移，以本表为准）

**cloud_ai.c**：b64_encode 26-43 / write_cb 52-63 / g_cfg区 66-69 / build_request_body 76-117（enable_thinking 108-110）/ extract_json_object 120-140 / parse_event_json 143-159（缺 type 默认 none 157）/ parse_openai_response 163-198 / call_cloud 201-242（超时 223-224、CAINFO 227）/ process_one_frame 245-286（none 过滤 276、publish 277）/ ai_thread 289-317（启用判定 293-299、interval_us 一次性 302、get_jpeg 305、free 312、usleep 314）/ start 320-334 / get_status 337-347 / reload 350-380（热字段 355-363、三分支 370-379）/ stop 383-390

**event_bus.c**：状态 21-29（MAX_SUBS=8）/ subscribe 32-41 / cleanup_snapshots 44-69 / init 72-107（建表 87-96）/ **publish 110-180**（时间戳 113-114 → 锁 117 → INSERT 118-142 → 快照 144-167【锁内 I/O】→ 拷订阅数组 170-173 → 解锁 174 → 同步回调 176-178）/ row_to_event 183-194 / query 197-200 / count 203-222 / query_filtered 225-259 / get 262-281 / deinit 284-294

**alarm.c**：状态 19-30（g_pending 单槽）/ sysfs_write 33-39 / gpio_set 42-58（负引脚 return 44）/ type_matches 61-73 / on_event 76-86（无锁读配置 79、锁内置 pending+signal 80-83）/ alarm_thread 89-111（while 谓词 95-97、取走清零 98-99、GPIO 104-108、每秒查 running 106）/ init 114-137（统一线程+订阅 122-129）/ stop 140-152 / reload 155-166

**web.c**：send_http 104-125（单次 send，无短写处理）/ send_json 128-131 / serve_static 135-181（..防护 141）/ serve_mjpeg 185-215（multipart 头 187-192、空帧退避 194-203、part_hdr 206-208、usleep 200ms 213）/ serve_snapshot_jpeg 219-237 / serve_status 241-301 / serve_recordings 311-376（动态数组+qsort）/ **serve_file 380-446**（Range 解析 399-409、越界重置 406-407、206 头 414-422、lseek 434、循环 437-444）/ serve_events 450-509（evs[64] 栈数组 473）/ serve_event_detail 513-531 / serve_snapshot 535-569 / serve_config_get 573-655（token 前8位掩码 607-621、mqtt_pass "****" 646）/ json_get_str/int/float/bool 659-728（strstr 简易解析）/ serve_config_post 732-830（new_cfg 起步 745、掩码特判 773-777/804-807、conf_save 816、apply_hot 823、g_cfg 更新 826）/ req_hdr_get 834-859 / **handle_client_inner 862-951**（recv 一次 865、请求行 871、body 补读 879-909、GET 路由 912-937、POST 仅 config 938-944）/ client_thread 955-961（close 959）/ web_thread 964-1000（socket/bind/listen 972-982、accept 循环 985-998、bind 失败仅日志 975-978）/ web_start 1003-1018（异步启动）/ web_stop 1021-1028（shutdown 唤醒 accept）

**conf.c**：trim 22-29 / strip_comment 32-37（不识别引号内 #）/ conf_load 55-155（默认值 59-87、逐行 100-151、未知 key 忽略 150）/ parse_log_level 157-164（只认小写、未知→LOG_INFO）/ format_value 197-240（敏感字段实际在白名单 218/235/236，与 195-196 注释相反）/ conf_save 243-293（tmp+fsync+rename 281-290）/ conf_apply_hot 296-304（**五项**：log_level / alarm / cloud_ai / frame_grabber_set_target_fps(web_mjpeg_fps) / stream_receiver_set_segment_seconds）

**main.c**：SIGPIPE 忽略 130-131 / 快照目录=storage_dir/../snapshots 136-137 / 启动顺序 event_bus(140)→alarm(145)→stream(150)→cloud_ai(156)→web(161) / 停机 web→cloud_ai→receiver→alarm→event_bus 174-178

## 预制时新审计观察（开块核实后启用；均未写入代码质量 TODO 主档，待各卡收口收割）

1. **event_bus_publish 快照 I/O 持锁**（c:145-167）：fopen/fwrite/UPDATE/cleanup_snapshots 全在 g_lock 内 → 慢 TF 卡拖住 web 事件查询（查询也抢 g_lock）→ 2.3A 审计题。
2. **interval_us 一次性计算**（cloud_ai.c:302）：ai_fps 热更新对运行中线程不生效，仅下次启停后生效 → 2.4 核心题（手册 Q3 的实然答案）。
3. **早退线程 running 残留**（ai_thread 296-299 早退但 g_running 保持 true → get_status c:343 报 running=true 假象）→ 2.4 状态语义题。
4. **cloud_ai_stop 停止延迟**：join 等阻塞中的 curl_easy_perform 返回（上限 ai_http_timeout_s=30s 默认）→ 2.4 与 alarm stop（≤1s，因 c:106 每秒查 running）对比素材。
5. **on_event 无锁读配置**（c:79 读 g_min_conf/g_trigger_types vs alarm_reload c:157-164 锁内写）→ 规范级 data race，字符串撕裂比 1.7C L47 整型更敏感 → 2.3B。
6. **g_pending 单槽非队列**（c:81 取最近 active_s，连续事件合并）→ 2.3B「队列/计数器/单槽」题的实然答案。
7. **web 侧所有 send 单次调用不处理短写**（send_http c:123-124 等）→ 与 rtsp_server send_all 对照 → 3.2/3.3 审计。
8. **web_mjpeg_fps 热更新作用于生产端**（conf_apply_hot c:301 → frame_grabber_set_target_fps），发送循环固定 usleep(200ms)≈上限5fps → 3.2 Q5/Q6 实然答案。
9. **handle_client_inner 只 recv 一次 4096B**（c:865）：请求头+部分 body 超 4KB 即截断，body 补读逻辑假设头完整到达 → 3.1/3.4 审计。
10. **token 掩码不对称**：GET 回显「前8位+****」（c:607-615），POST 只对精确 "****" 特判（c:775）→ 整表单回传会把掩码串「abcd1234****」当新 token 写入（mqtt_pass 两边都是 "****" 能挡住，token 挡不住）→ 3.5 核心审计题。
11. **publish c:115 疑似残留**：`if (ev->jpeg_path[0]==0) ev->jpeg_path[0]=0;` 无操作 → 2.3A 小观察。
12. **parse_log_level 只认小写**（c:159-163）：前端传 "DEBUG" → 落默认 LOG_INFO（不是拒绝，是静默降级）→ 3.5 Q6 实然答案。

## 使用规则

- 各卡引导问题/闭卷题均已过**深度滤网**（秋招通用层+自研句追问层）；卡内标注「提升池」的内容只给一句话结论。
- **铁律 18 情境边界**：C1/C2 变式仅用 Phase 2 模块与通用场景；P3 各卡可用 Phase 2 已学模块（届时已收口）。
- 分段模式：≥1h 卡已含分段说明，按学生状态弹性合并/再拆；每段以自然收口点为休息边界。
- 收口流程：判定 + 本阶段说明（铁律 23 四问，各卡已预填草稿）→ 落八股卡（增量）→ progress 轻量更新；模块/Phase 收口才做五文档同步。

## 更新记录

- 2026-08-28：建立。17 文件全预制；行号全量实测；登记预制时审计观察 12 条。
- 2026-08-28（补）：新增 `P3-附_前端appjs略读.md`（app.js 679 行实测锚点+五个后端呼应点），共 18 文件；Phase 2/3 待生成内容至此**全部就绪**。
