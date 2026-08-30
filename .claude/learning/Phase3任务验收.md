# Phase 3 Web 与配置热更新任务验收手册

> 版本：2026-08-22（二修：时间列同步08-17校准口径；新增前置概念层3.0A/3.0B）  
> 总预算：9h（前置概念1.5h + 代码7.5h）  
> 阅读取舍：MJPEG、HTTP Range、socket/线程生命周期、配置原子替换与热更新达L3；JSON拼接、静态资源和前端DOM只达L1–L2。  
> 前置概念层：开卡前先做 C3（socket/TCP服务器生命周期）+ C4（HTTP请求/响应模型）两个45min概念块，课程地图见 [`Phase2_3前置概念框架.md`](Phase2_3前置概念框架.md)。

> 使用方式：任务产出是诊断工具而非固定作业。Tutor可用口述、Range演算、控制流追踪或一个变式why作为等价证据；媒体链、socket生命周期和热更新边界仍有关键误解时再最小补测。

## 任务总表

| ID | 主题 | 时间 | 状态 | 主产出 |
| --- | --- | ---: | --- | --- |
| 3.0A | 前置概念C3：socket与TCP服务器生命周期 | 0.75h | 待办 | 两种fd（监听/连接）生命周期图 |
| 3.0B | 前置概念C4：HTTP请求/响应模型 | 0.75h | 待办 | 手写最小请求/响应样例 |
| 3.1 | HTTP路由与API地图 | 1h | 待办 | 方法/路径/输入/输出/数据源表 |
| 3.2 | MJPEG媒体输出链 | 1.5h | 待办 | JPEG到浏览器时序图 |
| 3.3 | MP4 HTTP Range | 1.5h | 待办 | Range演算、文件生命周期 |
| 3.4 | socket与客户端线程 | 1.25h | 待办 | 服务器/客户端生命周期图 |
| 3.5 | 配置保存与热更新边界 | 1.25h | 待办 | 落盘图、字段生效表 |
| 3.6 | 配置校验动手任务与闭卷 | 1h | 待办 | 校验矩阵、静态审查、口述 |

## 3.1 · HTTP路由与API地图

源码：`web.h:8-22`；`web.c:840-930`；各handler只读函数签名`100-812`  
时间盒：10分钟路由 + 10分钟数据源 + 5分钟表格 + 5分钟闭卷

### 阅读任务

1. 从`handle_client_inner()`提取GET/POST分支与所有路径。
2. 对每条路由只追踪到后端模块：stream status、frame_grabber、录像目录、event_bus、conf、静态前端。
3. 不读JSON字符串如何逐字段拼接。

### 引导问题

1. `/api/snapshot`、MJPEG预览和`/snapshot/<name>`三者数据源有何不同？
2. `/api/events`和`/api/event/<id>`是事件推送还是SQLite查询？
3. `/rec/<name>`的Range从哪个HTTP头获得？
4. POST只支持哪个API？它串起哪两个配置函数？
5. 哪些路由是媒体输出，哪些只是控制/状态面？

### 通过标准

- 列全部方法、路径、输入、成功输出、失败输出和后端数据源。
- 闭卷能把两条媒体输出链与通用JSON API分开。

## 3.2 · MJPEG预览：最新JPEG到浏览器

源码：`web.c:178-210`；`frame_grabber.h:27-33`；`conf.c:290-298`  
时间盒：15分钟数据流 + 15分钟multipart + 15分钟所有权/断连 + 15分钟审查

### 引导问题

1. 为什么浏览器预览不直接使用RTSP，而用`multipart/x-mixed-replace`？
2. 整体HTTP header、boundary、单帧`Content-Type/Content-Length`、JPEG字节按什么顺序发？
3. `get_jpeg()`返回的buffer由谁free？三个发送点失败后是否都收口？
4. 无新JPEG时循环怎样避免忙等？客户端断开怎样退出？
5. `web_mjpeg_fps`热更新直接改变的是发送线程的sleep，还是frame_grabber的产帧率？
6. `serve_mjpeg()`固定`usleep(200ms)`；因此“Web发送fps与配置严格一致”是否成立？
7. 一次`send()`成功返回是否保证整个buffer已发完？当前实现如何处理短写？

### 必交与通过

- 交JPEG拷贝→multipart header→JPEG→free→下一帧/断连时序图。
- 交生产fps、发送循环周期、实际可见帧率的区分表。
- 能指出慢客户端、阻塞send和短写的现有实现边界。

## 3.3 · MP4 HTTP Range与拖动回放

源码：`web.c:369-436`；路由`892-913`  
时间盒：15分钟请求解析 + 15分钟响应演算 + 15分钟文件/发送 + 15分钟异常

### 引导问题

1. 没有Range时返200还206？有`bytes=1000-1999`时start/end/length各是多少？
2. `Content-Range`、`Content-Length`和`Accept-Ranges`分别怎样写？
3. 为什么要`fseek/lseek`到start，而不是从文件头开始读？
4. 只给start未给end、end超文件、start超文件，当前代码如何处理？
5. start越界时实现重置为0，而不是返416；客户端会如何解读？
6. 循环如何避免超过请求范围？它是否处理短写？
7. Range为什么对大文件、断点和seek重要？它与MP4内部索引是不是同一层？

### 必交与通过

- 手工走3个Range样例，正确算响应码、start/end/length和头字段。
- 交open→stat→parse→seek→read/send→close生命周期图。
- 能识别越界语义和短写未处理两个工程问题。

## 3.4 · socket、accept和客户端线程生命周期

源码：`web.c:932-1005`；请求入口`840-930`  
时间盒：10分钟启动 + 15分钟accept/线程 + 10分钟stop + 10分钟异常审查

### 引导问题

1. `web_start()`和`web_thread()`分别负责什么？socket/bind/listen在哪个线程发生？
2. 每个accept的fd交给谁？线程detach后谁close？
3. `web_stop()`为什么要shutdown/close监听fd再join？
4. 一客户端一线程对慢客户端有什么隔离效果？对大量客户端有什么资源风险？
5. `web_start()`只要`pthread_create`成功就返0；若后台线程bind失败，调用者能否立即知道？`g_running/g_listen_fd`是否收口？
6. 这种“异步启动”的API怎样改造才能报告bind/listen真实结果？

### 必交与通过

- 交主线程、Web监听线程、客户端线程三泳道生命周期图。
- 能说清启动返回值与“端口已监听”不等价的现实。

## 3.5 · `conf_save/apply_hot`：原子替换与生效边界

源码：`conf.h:65-85`；`conf.c:189-298`；`web.c:558-812`  
时间盒：15分钟保存 + 10分钟热更新 + 10分钟敏感字段 + 10分钟闭卷

### 引导问题

1. 为什么先写`.tmp`再`rename`，不直接截断原文件？
2. `fflush → fsync(file) → fclose → rename`分别保证什么？缺少目录fsync时能否宣称“完整掉电安全”？
3. `conf_apply_hot()`向哪些模块下发什么字段？端口、bind地址、存储目录为何不会立即生效？
4. 判断热更新真实生效，是看赋值日志，还要看消费者是否重新读取？
5. GET将token输出为“前8位+****”，POST只对精确`****`特判；将整张表单回传可能写入什么？
6. 前端日志级别若为大写，后端`parse_log_level()`只识别小写，最终会怎样？

### 必交与通过

- 交临时文件落盘/替换图和“可热更新/传值但存疑/需重启”字段表。
- 能区分“原子替换”、“数据已fsync”和“完整掉电持久性”。
- 识别token掩码回写与日志级别大小写两个实现风险。

## 3.6 · POST配置校验动手任务与闭卷验收

源码：`web.c:643-812`；`conf.h:6-64`  
时间盒：10分钟边界矩阵 + 10分钟设计/实现 + 5分钟静态审查 + 5分钟闭卷

### 动手任务

在用户确认修码后，给`POST /api/config`增加最小校验，至少覆盖：

| 字段 | 必须验证 |
| --- | --- |
| Web/RTSP/MQTT端口 | 1–65535，必要时考虑特权端口 |
| `web_mjpeg_fps/ai_fps` | 正值且有合理上限 |
| `segment_seconds` | 正值且不造成过度切段 |
| JPEG quality | 1–100 |
| `alarm_min_confidence` | 0–1 |
| 字符串 | 长度、空值、token掩码语义 |

### 验收问题

1. 校验应在写入`new_cfg`前、全部解析后、还是`conf_save`后？如何保证不会部分应用？
2. 失败响应应返什么HTTP码和可机读字段？
3. 为什么字符串长度安全不等于业务值合法？
4. 怎样用边界值、越界值、类型错误和缺失字段设计测试？

### Phase 3通过标准

- API地图完整，MJPEG和Range两图各≥80%。
- 能闭卷讲清socket生命周期、停止如何唤醒accept、配置热更新边界。
- 校验任务标记“静态完成”与“Ubuntu/板端已验证”两个独立状态。
- 必须识别短写、Range越界、异步启动失败、目录fsync缺口、token掩码回写至少5项现实边界。
