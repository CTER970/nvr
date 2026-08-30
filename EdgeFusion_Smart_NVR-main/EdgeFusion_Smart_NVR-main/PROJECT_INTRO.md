# EdgeFusion Smart NVR 项目说明文档

本文档用于帮助快速理解 EdgeFusion Smart NVR 的项目背景、系统架构、模块职责、数据流、接口定义和关键函数。阅读时建议先把它当作“项目地图”，再进入各个源码文件。

## 1. 项目背景

EdgeFusion Smart NVR 是一个面向低成本嵌入式场景的端边云协同智能网络录像机项目。

传统 NVR 的主要能力是视频接入、录像、回放和告警。这个项目在传统 NVR 的基础上加入了边缘网关和云端视觉理解能力：

- V821 端侧设备负责摄像头采集、ISP 处理、H.264 硬编码和 RTSP 推流。
- IMX6ULL 边缘网关负责拉取 V821 视频流、录像、关键帧抽取、Web 管理、本地事件库、报警联动和 RTSP 二次转发。
- 云端多模态模型负责对关键帧做视觉分析，返回结构化事件。

项目的核心目标不是在单板上堆满所有 AI 计算，而是根据硬件能力做分工：

- V821 有视频采集和硬编码能力，适合做无线摄像头端。
- IMX6ULL 算力有限，不适合做高成本视觉推理，但适合做稳定网关、录像管理和设备控制。
- 云端模型适合处理复杂视觉语义理解。

因此系统采用“端侧采集压缩、边缘稳定汇聚、云端智能分析”的架构。

## 2. 总体架构

```text
GC2083/MIPI Camera
        |
        v
+--------------------+
| V821 端侧摄像头     |
| VI/ISP/VENC         |
| H.264 RTSP 推流     |
+--------------------+
        |
        | rtsp://<V821-IP>:8554/ch0
        v
+-----------------------------+
| IMX6ULL 边缘网关             |
| stream_receiver              |
| recorder / frame_grabber     |
| cloud_ai / event_bus / alarm |
| web / rtsp_server            |
+-----------------------------+
    |           |          |
    |           |          +--> LED/蜂鸣器 GPIO 告警
    |           +-------------> Web 管理页面 / MJPEG / 回放
    +-------------------------> 云端多模态模型
                                  |
                                  v
                             结构化 JSON 事件
```

仓库主要分为两个子工程：

| 路径 | 角色 | 主要内容 |
| --- | --- | --- |
| `edgefusion_vision/` | V821 端侧摄像头 | 基于 Allwinner eyesee-mpp sample 的外部编译工程，完成 MIPI CSI 采集、ISP、H.264 硬编码、RTSP 推流 |
| `edgefusion_gateway/` | IMX6ULL 边缘网关 | C 语言多线程守护进程，完成拉流、录像、关键帧抽取、AI 上云、事件入库、Web 管理、RTSP 转发 |

## 3. 端侧子工程 edgefusion_vision

### 3.1 模块定位

`edgefusion_vision` 的定位是“无线摄像头端”。它不是完整 NVR，而是一个专注采集和编码的 RTSP 视频源。

核心能力：

- 读取配置文件 `sample_rtsp.conf`。
- 初始化 MPP 系统。
- 创建 VI/VIPP 摄像头采集通道。
- 启动 ISP。
- 创建 VENC 编码通道。
- 将 VI 通道和 VENC 通道绑定。
- 启动 H.264/H.265/MJPEG 编码。
- 通过 RTSP server 对外提供视频流。

### 3.2 核心源码

| 文件 | 作用 |
| --- | --- |
| `edgefusion_vision/sample/sample_rtsp/sample_rtsp.c` | 端侧主程序，负责配置解析、MPP 初始化、VI/VENC 创建、RTSP 推流、退出清理 |
| `edgefusion_vision/sample/common/rtsp_server.cpp` | V821 sample 使用的 RTSP server 封装 |
| `edgefusion_vision/sample/common/sample_common_venc.c` | VENC 参数辅助配置 |
| `edgefusion_vision/Makefile` | V821 RISC-V/musl 外部编译规则 |

### 3.3 关键流程

`sample_rtsp.c` 中的主流程大致为：

1. `ParseCmdLine()` 解析 `-path` 配置文件路径。
2. `loadSampleConfig()` 加载视频参数、编码参数、RTSP 网卡参数。
3. `AW_MPI_SYS_SetConf()` 设置 MPP 系统对齐参数。
4. `AW_MPI_SYS_Init()` 初始化 MPP 系统。
5. `configMainStream()` 根据配置生成主码流 VI/VENC 参数。
6. `AW_MPI_VI_CreateVipp()` 创建视频输入设备。
7. `AW_MPI_VI_SetVippAttr()` 设置采集属性。
8. `AW_MPI_ISP_Run()` 启动 ISP。
9. `AW_MPI_VI_EnableVipp()` 使能采集设备。
10. `AW_MPI_VI_CreateVirChn()` 创建 VI 虚拟通道。
11. `AW_MPI_VENC_CreateChn()` 创建编码通道。
12. `AW_MPI_VENC_SetRcParam()` 设置码率控制。
13. `AW_MPI_SYS_Bind()` 绑定 VI 到 VENC。
14. `AW_MPI_VI_EnableVirChn()` 使能 VI 通道。
15. `AW_MPI_VENC_StartRecvPic()` 启动编码收帧。
16. RTSP 模块将编码流对外推送。

### 3.4 端侧设计取舍

端侧只做推流，不做录像和复杂 AI，原因是：

- V821 的优势是视频采集和硬编码，适合持续产生 H.264 流。
- 把录像放在 IMX6ULL 网关侧，便于集中管理存储、回放和事件。
- 端侧保持轻量，降低端侧长期运行复杂度。
- 后续多路摄像头扩展时，网关可以统一汇聚多个 RTSP 输入。

## 4. 边缘网关子工程 edgefusion_gateway

### 4.1 进程定位

`edgefusion_gateway` 是 IMX6ULL 上运行的核心守护进程。它连接端侧视频源、录像系统、云端 AI、Web 前端和 GPIO 报警。

主入口是：

```text
edgefusion_gateway/src/main.c
```

它负责：

- 解析启动参数。
- 加载配置。
- 初始化日志。
- 初始化事件中心。
- 启动报警订阅。
- 启动拉流录像线程。
- 启动云端 AI 线程。
- 启动 Web 服务。
- 等待退出信号并按顺序释放模块。

### 4.2 启动顺序

`main()` 的启动顺序如下：

```text
conf_load()
  -> conf_apply_log()
  -> event_bus_init()
  -> alarm_init()
  -> stream_receiver_start()
  -> cloud_ai_start()
  -> web_start()
  -> 主循环等待 SIGINT/SIGTERM
```

退出顺序如下：

```text
web_stop()
  -> cloud_ai_stop()
  -> stream_receiver_stop()
  -> alarm_stop()
  -> event_bus_deinit()
```

这个顺序有依赖关系：

- `event_bus` 必须先于 `alarm` 和 `cloud_ai` 初始化，因为报警和 AI 事件都依赖事件中心。
- `stream_receiver` 必须先于 Web 预览和 AI 分析稳定运行，因为 JPEG 帧来自 `frame_grabber`，而 `frame_grabber` 由拉流线程喂包。
- 退出时先停 Web 和 AI，避免继续访问正在释放的视频资源。

## 5. 边缘网关模块职责

### 5.1 配置模块 conf

文件：

- `edgefusion_gateway/src/conf.c`
- `edgefusion_gateway/src/conf.h`

核心结构体：

```c
typedef struct {
    char  rtsp_url[256];
    char  rtsp_transport[8];
    int   rtsp_reconnect_s;
    int   rtsp_server_enable;
    int   rtsp_server_port;
    char  storage_dir[256];
    int   segment_seconds;
    long  storage_min_free_mb;
    char  sqlite_db_path[256];
    int   ai_enable;
    int   ai_fps;
    int   ai_frame_width;
    int   ai_jpeg_quality;
    int   ai_http_timeout_s;
    char  anthropic_base_url[256];
    char  anthropic_auth_token[256];
    char  anthropic_model[64];
    char  ai_prompt[1024];
    int   alarm_gpio_led;
    int   alarm_gpio_buzzer;
    char  alarm_trigger_types[128];
    float alarm_min_confidence;
    int   alarm_active_s;
    char  web_bind[64];
    int   web_port;
    int   web_mjpeg_fps;
    char  web_root[256];
    int   mqtt_enable;
    char  log_level[16];
    char  log_file[256];
} gateway_conf_t;
```

关键函数：

| 函数 | 作用 |
| --- | --- |
| `conf_load()` | 读取 key=value 配置文件，填充 `gateway_conf_t`，并设置默认值 |
| `conf_apply_log()` | 根据配置设置日志级别和日志文件 |
| `conf_dump()` | 打印脱敏后的配置摘要 |
| `conf_save()` | 将 Web 修改后的配置写回文件，保留注释和 key 顺序 |
| `conf_apply_hot()` | 将可热更新参数推送给运行中模块 |

可热更新内容包括：

- 日志级别。
- 报警参数。
- AI 开关、帧率、prompt、模型和端点。
- MJPEG 产出帧率。
- 录像分段时长。

注意：当前仓库中 README 提到 `edgefusion_gateway/config/gateway.conf`，但实际解压目录没有该文件。代码已支持配置加载和保存，后续需要补充一个示例配置文件，便于部署和面试展示。

### 5.2 拉流模块 stream_receiver

文件：

- `edgefusion_gateway/src/stream_receiver.c`
- `edgefusion_gateway/src/stream_receiver.h`

职责：

- 用 FFmpeg 从 V821 RTSP 地址拉取 H.264 视频流。
- 识别视频流索引。
- 创建录像器 `recorder`。
- 初始化帧抽取器 `frame_grabber`。
- 初始化本地 RTSP 转发服务 `rtsp_server`。
- 在主循环中读取 AVPacket，并分发给录像、JPEG 抽帧和 RTSP 转发。
- 拉流失败后等待 `rtsp_reconnect_s` 秒重连。

关键函数：

| 函数 | 作用 |
| --- | --- |
| `open_input()` | 打开 RTSP 输入，设置 `rtsp_transport`、`analyzeduration`、`probesize` 等 FFmpeg 参数 |
| `receiver_thread()` | 拉流线程主体，负责连接、读包、分发、重连 |
| `stream_receiver_start()` | 初始化 FFmpeg 网络层并创建拉流线程 |
| `stream_receiver_stop()` | 停止线程并释放 FFmpeg、recorder、frame_grabber、rtsp_server |
| `stream_receiver_get_status()` | 给 Web `/api/status` 聚合拉流和录像状态 |
| `stream_receiver_set_segment_seconds()` | 热更新录像分段时长 |

数据分发逻辑：

```text
av_read_frame()
  -> recorder_write_packet()
  -> frame_grabber_feed()
  -> rtsp_server_on_packet()
```

这里有一个重要设计：录像和 RTSP 转发都尽量复用 H.264 压缩包，不做不必要的解码和重编码。只有 Web 预览和 AI 上云需要 JPEG 时，才走 `frame_grabber` 旁路解码。

### 5.3 录像模块 recorder

文件：

- `edgefusion_gateway/src/recorder.c`
- `edgefusion_gateway/src/recorder.h`

职责：

- 将 RTSP 输入中的 H.264 AVPacket remux 到 MP4。
- 按时间分段生成录像文件。
- 确保新段从关键帧开始，避免 MP4 不可解码。
- 使用 fragmented MP4 参数提升断电安全性。
- 监控剩余空间，不足时删除最旧录像。
- 提供录像状态给 Web。

关键函数：

| 函数 | 作用 |
| --- | --- |
| `recorder_create()` | 保存配置和 codecpar，创建录像器 |
| `open_segment()` | 创建新的 MP4 输出上下文和输出文件 |
| `close_segment()` | 写 trailer、关闭文件、释放输出上下文 |
| `cleanup_disk()` | 空间不足时按文件名删除旧 MP4 |
| `recorder_write_packet()` | 写入一帧 H.264 packet，按关键帧和时间切段 |
| `recorder_get_status()` | 返回当前段、码率、录像状态 |
| `recorder_set_segment_seconds()` | 更新下一段生效的分段时长 |

关键细节：

- 首帧必须等待关键帧。
- 切段也在关键帧处进行。
- 输出 MP4 设置 `+frag_keyframe+empty_moov+default_base_moof`。
- 写入时使用 `av_packet_rescale_ts()` 做时间基转换。

### 5.4 JPEG 抽帧模块 frame_grabber

文件：

- `edgefusion_gateway/src/frame_grabber.c`
- `edgefusion_gateway/src/frame_grabber.h`

职责：

- 从 H.264 packet 旁路解码视频帧。
- 用 `libswscale` 缩放到目标宽度。
- 编码为 MJPEG/JPEG。
- 只缓存“最新一帧”，供 Web MJPEG、抓拍和云端 AI 读取。

关键函数：

| 函数 | 作用 |
| --- | --- |
| `frame_grabber_init()` | 根据源流 codecpar 打开解码器、MJPEG 编码器和 swscale |
| `frame_grabber_feed()` | 输入 H.264 AVPacket，内部解码并按帧率节流 |
| `emit_jpeg_from_frame()` | 缩放并编码 JPEG，更新最新帧缓存 |
| `frame_grabber_get_jpeg()` | 线程安全地复制最新 JPEG 给调用方 |
| `frame_grabber_set_target_fps()` | 热更新 JPEG 产出帧率 |

设计取舍：

- 不保存帧队列，只保存最新帧，降低内存压力。
- Web 和 AI 都消费同一份最新 JPEG 缓存。
- 通过 mutex 保护 JPEG 缓存，调用方拿到的是独立拷贝，需要释放。

### 5.5 云端 AI 模块 cloud_ai

文件：

- `edgefusion_gateway/src/cloud_ai.c`
- `edgefusion_gateway/src/cloud_ai.h`

职责：

- 周期性读取 `frame_grabber` 的最新 JPEG。
- 将 JPEG 编码为 base64。
- 构造 OpenAI Chat Completions 兼容格式请求。
- 调用云端多模态模型。
- 从响应中提取模型输出文本。
- 从文本中提取 JSON。
- 解析为本地事件结构 `event_t`。
- 将非 `none` 事件发布到 `event_bus`。

关键函数：

| 函数 | 作用 |
| --- | --- |
| `b64_encode()` | JPEG 二进制转 base64 |
| `build_request_body()` | 构造带文本 prompt 和 image_url data URL 的 JSON 请求体 |
| `call_cloud()` | 使用 libcurl 调用 OpenAI 兼容端点 |
| `parse_openai_response()` | 解析 `choices[0].message.content` |
| `extract_json_object()` | 从模型文本中截取第一个 JSON 对象 |
| `parse_event_json()` | 将模型 JSON 转为 `event_t` |
| `process_one_frame()` | 单帧完整 AI 处理流程 |
| `ai_thread()` | AI 线程主循环 |
| `cloud_ai_reload()` | 热更新 AI 参数并根据开关热启停线程 |

事件 JSON 期望字段：

```json
{
  "event_type": "person_detected",
  "confidence": 0.95,
  "description": "画面中检测到人员",
  "suggested_action": "send_alert"
}
```

启用条件：

```text
ai_enable = 1
anthropic_auth_token 非空
```

如果 token 为空或开关关闭，模块进入本地模式，不调用云端。

### 5.6 事件中心 event_bus

文件：

- `edgefusion_gateway/src/event_bus.c`
- `edgefusion_gateway/src/event_bus.h`

职责：

- 作为本地事件中枢。
- 将 AI 事件写入 SQLite。
- 将触发帧保存为 JPEG 快照。
- 支持事件订阅，报警模块通过订阅方式接收事件。
- 支持 Web 查询事件列表、分页筛选和详情。

核心结构体：

```c
typedef struct {
    long   id;
    int64_t created_at;
    char   event_type[32];
    float  confidence;
    char   description[256];
    char   suggested_action[32];
    char   jpeg_path[256];
} event_t;
```

关键函数：

| 函数 | 作用 |
| --- | --- |
| `event_bus_init()` | 打开 SQLite、建表、创建快照目录 |
| `event_bus_publish()` | 插入事件、保存快照、通知订阅者 |
| `event_bus_subscribe()` | 注册事件订阅回调 |
| `event_bus_query_filtered()` | 按类型、分页查询事件 |
| `event_bus_count()` | 统计事件数 |
| `event_bus_get()` | 查询单条事件详情 |
| `event_bus_deinit()` | 关闭数据库并清空订阅者 |

SQLite 表结构：

```sql
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at INTEGER NOT NULL,
  event_type TEXT,
  confidence REAL,
  description TEXT,
  suggested_action TEXT,
  jpeg_path TEXT
);
```

### 5.7 报警模块 alarm

文件：

- `edgefusion_gateway/src/alarm.c`
- `edgefusion_gateway/src/alarm.h`

职责：

- 订阅 `event_bus`。
- 根据 `event_type` 和 `confidence` 判断是否触发。
- 通过 Linux GPIO sysfs 控制 LED 和蜂鸣器。
- 支持报警参数热更新。

关键函数：

| 函数 | 作用 |
| --- | --- |
| `alarm_init()` | 初始化 GPIO 配置、启动报警线程、订阅事件 |
| `on_event()` | 事件回调，快速判断并唤醒报警线程 |
| `alarm_thread()` | 执行 LED/蜂鸣器拉高、延时、拉低 |
| `gpio_set()` | export GPIO 并写 value |
| `alarm_reload()` | 热更新 GPIO、触发类型、阈值和持续时间 |
| `alarm_stop()` | 停止线程并关闭 GPIO 输出 |

设计注意：

- `event_bus` 回调要求快速返回，因此真正的延时报警放在线程里做。
- GPIO 为 `-1` 时表示禁用该路输出。

### 5.8 本地 RTSP 转发 rtsp_server

文件：

- `edgefusion_gateway/src/rtsp_server.c`
- `edgefusion_gateway/src/rtsp_server.h`

职责：

- 从源流 codecpar 提取 SPS/PPS，生成 SDP。
- 监听 RTSP 控制连接。
- 支持 OPTIONS、DESCRIBE、SETUP、PLAY、GET_PARAMETER、TEARDOWN。
- 将 stream_receiver 收到的 H.264 packet 切分 NALU。
- 将 NALU 打成 RTP 包，转发给客户端。
- 支持 TCP interleaved 和 UDP unicast。

关键函数：

| 函数 | 作用 |
| --- | --- |
| `parse_nalus()` | 兼容 Annex B 和 AVCC 格式，切分 NALU |
| `sdp_collect_cb()` | 提取 SPS/PPS 并 base64，用于 SDP |
| `build_sdp()` | 构造 H.264 SDP |
| `handle_client()` | 处理 RTSP 控制信令 |
| `send_nal_to_client()` | 单 NAL 或 FU-A 分片打 RTP |
| `rtsp_server_on_packet()` | 接收 H.264 packet 并扇出给所有播放客户端 |
| `rtsp_server_init()` | 创建监听 socket 并启动线程 |
| `rtsp_server_client_count()` | 返回当前播放客户端数 |
| `rtsp_server_deinit()` | 停止监听并关闭客户端 |

设计取舍：

- 转发使用 H.264 passthrough，不解码不转码，降低 CPU 占用。
- 慢客户端失败次数过多会被标记断开，避免拖垮主链路。
- 如果 SPS/PPS 提取失败，会使用默认 SDP 参数兜底，但实际项目应尽量确保从源流中获取真实 SPS/PPS。

### 5.9 Web 服务 web

文件：

- `edgefusion_gateway/src/web.c`
- `edgefusion_gateway/src/web.h`
- `edgefusion_gateway/web/index.html`
- `edgefusion_gateway/web/app.js`
- `edgefusion_gateway/web/style.css`

职责：

- 提供嵌入式 HTTP server。
- 提供 Web 单页应用。
- 提供 MJPEG 实时预览。
- 提供录像列表、MP4 Range 播放和下载。
- 提供事件列表、事件详情和快照访问。
- 提供配置读取、配置保存和热更新入口。

主要 HTTP 接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/` | 返回 Web 前端首页 |
| `GET` | `/stream` | MJPEG 实时预览流 |
| `GET` | `/api/status` | 聚合拉流、录像、RTSP 客户端、AI、事件统计状态 |
| `GET` | `/api/snapshot` | 获取当前最新 JPEG 抓拍 |
| `GET` | `/api/recordings` | 获取 MP4 录像列表 |
| `GET` | `/rec/<name>` | 获取录像文件，支持 HTTP Range |
| `GET` | `/api/events?limit=&offset=&type=` | 查询事件列表 |
| `GET` | `/api/event/<id>` | 查询单个事件详情 |
| `GET` | `/snap/evt_<id>.jpg` | 读取事件快照 |
| `GET` | `/api/config` | 获取当前配置，敏感字段脱敏 |
| `POST` | `/api/config` | 更新配置、写回文件、热更新 |
| `GET` | `/<path>` | 静态资源 |

关键函数：

| 函数 | 作用 |
| --- | --- |
| `serve_mjpeg()` | 读取最新 JPEG 并持续输出 multipart MJPEG |
| `serve_snapshot_jpeg()` | 返回单张最新 JPEG |
| `serve_status()` | 聚合各模块状态生成 JSON |
| `serve_recordings()` | 扫描录像目录并返回列表 |
| `serve_file()` | 支持 Range 的 MP4 文件服务 |
| `serve_events()` | 查询事件列表 |
| `serve_event_detail()` | 查询事件详情 |
| `serve_snapshot()` | 读取事件快照文件 |
| `serve_config_get()` | 返回配置 JSON |
| `serve_config_post()` | 解析配置更新、保存并热更新 |
| `handle_client_inner()` | HTTP 路由分发 |
| `web_start()` | 启动 HTTP 监听线程 |
| `web_stop()` | 停止 HTTP 服务 |

### 5.10 日志模块 log

文件：

- `edgefusion_gateway/src/log.c`
- `edgefusion_gateway/src/log.h`

职责：

- 提供 `LOG_DBG`、`LOG_INF`、`LOG_WRN`、`LOG_ERR` 宏。
- 支持日志级别过滤。
- 支持输出到文件。

## 6. 主数据流

### 6.1 视频主链路

```text
V821 摄像头
  -> MIPI CSI / ISP / VENC
  -> H.264 RTSP
  -> IMX6ULL stream_receiver
  -> recorder 写 MP4
  -> rtsp_server 本地转发
  -> frame_grabber 生成 JPEG
```

这条链路是项目最核心的链路。面试时应优先讲清楚：

- H.264 压缩流从哪里来。
- 为什么 IMX6ULL 不做全量解码。
- 录像为什么是 remux 而不是转码。
- JPEG 为什么只是旁路抽帧。

### 6.2 AI 事件链路

```text
frame_grabber 最新 JPEG
  -> cloud_ai base64 编码
  -> OpenAI 兼容接口
  -> 云端多模态模型
  -> 结构化 JSON
  -> event_bus SQLite + 快照
  -> alarm GPIO
  -> Web 事件列表
```

### 6.3 Web 管理链路

```text
浏览器
  -> Web SPA
  -> /api/status 轮询状态
  -> /stream 预览
  -> /api/recordings 回放列表
  -> /rec/<name> Range 播放 MP4
  -> /api/events 查看 AI 事件
  -> /api/config 修改运行配置
```

### 6.4 配置热更新链路

```text
浏览器 POST /api/config
  -> web.c 更新 gateway_conf_t
  -> conf_save() 写回配置文件
  -> conf_apply_hot()
      -> log_set_level()
      -> alarm_reload()
      -> cloud_ai_reload()
      -> frame_grabber_set_target_fps()
      -> stream_receiver_set_segment_seconds()
```

## 7. 关键接口和数据结构

### 7.1 视频状态接口

`stream_receiver_get_status()` 返回：

```c
typedef struct {
    int  connected;
    int  width;
    int  height;
    int  fps;
    int  recording;
    char cur_segment[128];
    int  bitrate_kbps;
} stream_status_t;
```

该结构最终体现在 `/api/status` 的 `stream` 字段中。

### 7.2 录像器接口

```c
recorder_t *recorder_create(const recorder_cfg_t *cfg, AVCodecParameters *stream_codecpar);
int recorder_write_packet(recorder_t *r, AVPacket *pkt, int is_key, double ts);
int recorder_get_status(const recorder_t *r, recorder_status_t *st);
void recorder_destroy(recorder_t *r);
```

核心输入是源流 `AVPacket`，核心输出是 MP4 录像段。

### 7.3 JPEG 抽帧接口

```c
int frame_grabber_init(const frame_grabber_cfg_t *cfg, AVCodecParameters *codecpar);
int frame_grabber_feed(AVPacket *pkt);
int frame_grabber_get_jpeg(uint8_t **out_data);
void frame_grabber_deinit(void);
```

`frame_grabber_get_jpeg()` 返回的是拷贝出来的 JPEG，调用者需要 `free()`。

### 7.4 事件接口

```c
long event_bus_publish(event_t *ev, const uint8_t *jpeg, int jpeg_size);
int event_bus_query_filtered(event_t *out, int max_count, const char *type_filter, int offset);
int event_bus_get(long id, event_t *out);
void event_bus_subscribe(event_cb_t cb, void *user);
```

`event_bus_publish()` 同时负责入库、保存快照和通知订阅者。

### 7.5 Web 状态 JSON

`GET /api/status` 返回大致结构：

```json
{
  "stream": {
    "connected": true,
    "width": 1920,
    "height": 1080,
    "fps": 15,
    "recording": true,
    "cur_segment": "rec_20260708_120000_01.mp4",
    "bitrate_kbps": 2048
  },
  "rtsp_server": {
    "clients": 1
  },
  "cloud_ai": {
    "enabled": true,
    "running": true
  },
  "events_total": 10
}
```

## 8. 线程模型

边缘网关是多线程模型：

| 线程 | 来源 | 作用 |
| --- | --- | --- |
| 主线程 | `main.c` | 初始化模块、等待退出信号、统一清理 |
| 拉流线程 | `stream_receiver_start()` | RTSP 拉流、录像、抽帧、RTSP 转发分发 |
| AI 线程 | `cloud_ai_start()` | 周期性取 JPEG 并调用云端 |
| Web 线程 | `web_start()` | HTTP 监听和请求处理 |
| RTSP 监听线程 | `rtsp_server_init()` | 接收 RTSP 客户端控制连接 |
| 报警线程 | `alarm_init()` | 根据事件触发 GPIO 输出 |

共享资源和保护：

- `frame_grabber` 的 JPEG 缓存用 mutex 保护。
- `event_bus` 的 SQLite 访问和订阅者数组用 mutex 保护。
- `recorder` 的状态统计字段用 mutex 保护。
- `alarm` 的触发请求用 mutex + condition variable 保护。

## 9. 工程依赖和编译

### 9.1 V821

`edgefusion_vision/Makefile` 使用：

- RISC-V 32 位 musl 工具链。
- Allwinner eyesee-mpp 静态库。
- `liblog`、`libasound` 动态库。

编译目标：

```text
output/sample_rtsp
output/sample_rtsp_strip
```

### 9.2 IMX6ULL

`edgefusion_gateway/Makefile` 使用：

- `arm-buildroot-linux-gnueabihf-gcc`
- FFmpeg 相关库：`libavformat`、`libavcodec`、`libavutil`、`libswscale`、`libswresample`
- `libcurl`
- `openssl`
- `sqlite3`
- `json-c`
- `pthread`

输出目标：

```text
build/edgefusion_gateway
```

## 10. 当前仓库边界和待补项

从当前解压目录看，代码主体存在，但存在一些文档或配置缺口：

| 项 | 当前情况 | 建议 |
| --- | --- | --- |
| `PROJECT_INTRO.md` | 原 README 引用但缺失 | 本文档已补充 |
| `IMX6ULL_V821_Project.md` | README 引用但缺失 | 后续可补硬件选型和实施计划 |
| `edgefusion_gateway/docs/TASK.md` | README 引用但目录不存在 | 后续可补任务拆解和调试记录 |
| `edgefusion_gateway/config/gateway.conf` | README 引用但当前目录不存在 | 应补 `gateway.conf.example`，避免泄露 token |
| MQTT | 配置字段存在，但 README 说明未实现 | 面试时应说“预留配置，当前未接入 libmosquitto” |

## 11. 面试讲解主线

建议用下面这条主线讲项目：

1. 这个项目要解决低成本 NVR 的“采集、录像、回放、告警、智能分析”问题。
2. 我将系统拆成 V821 端侧、IMX6ULL 边缘网关、云端 AI 三层。
3. V821 负责摄像头采集和 H.264 硬编码，输出 RTSP 流。
4. IMX6ULL 负责拉流、H.264 remux 分段录像、Web 管理、本地事件库和报警。
5. 为了降低边缘端算力压力，只对关键帧或低帧率 JPEG 做云端视觉理解。
6. 云端返回结构化 JSON 后，网关写 SQLite、保存快照、触发 GPIO 告警，并在 Web 展示。
7. 系统通过配置热更新支持运行时调整 AI、报警、预览和录像参数。

## 12. 后续改进方向

优先级从高到低：

1. 补充 `gateway.conf.example`，明确每个配置项和默认值。
2. 给 Web 配置接口增加输入合法性校验。
3. 给 RTSP server 增加更严格的 session 管理和客户端清理。
4. 给 cloud_ai 增加请求失败统计、退避重试和事件去重。
5. 给 event_bus 增加事件级别、设备 ID、通道 ID 字段。
6. 抽象多路摄像头输入，支持多个 V821 通道。
7. 实现 MQTT 上报或 HTTP webhook。
8. 增加 24h/72h 稳定性测试记录和性能指标。
9. 增加 systemd/init 脚本或板端自启动脚本。
10. 增加工程级调试文档和常见问题定位流程。
