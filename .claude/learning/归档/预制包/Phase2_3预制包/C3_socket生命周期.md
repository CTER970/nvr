# C3 · socket 与 TCP 服务器生命周期（并入 3.4 开场，15–20min）

> **2026-09-02：取消独立 45min 开块。** 本文件是 `P3-3.4` 的开场材料，不推进 3.0A，不走 knowledge-tutor。
> 落卡随 3.4 写入 07_Web配置.md。
> 开场用法：阅读清单 + 两种 fd 三件套 + shutdown 唤醒一句；细节（异步启动/detach/bind 失败）留 3.4 正文。

## 0. 开块审查（由 3.4 执行，不单独开会话）

- grep 核对：`grep -n "socket\|bind\|listen\|accept\|shutdown" web.c`（964-1028 区域）。
- 前置迁移：Phase 1 已有 fd 概念（V4L2 open/ioctl/mmap）；本块把 fd 推广到网络对象。

## 1. 任务目的（四层）

① Phase 3 四张代码卡（3.1-3.4）都站在 web_thread 的 socket 生命周期上，分不清「监听 fd / 连接 fd」则 3.4 的启动停止语义读不动。② 项目背景：web 与 rtsp_server 都是自研 socket 服务器（无框架），main 一个 start/stop 对背后是完整的 socket→bind→listen→accept→线程→close 链——「自研 HTTP/RTSP 服务器」面试句的事实底座。③ 岗位背景：socket API 生命周期是 Linux 应用岗必考；「listen fd 和连接 fd 为什么是两个东西」直接筛出只背过 API 没写过 server 的人。④ 学完能画 3.4 三泳道生命周期图，并解释 web_stop 为什么要 shutdown。

## 2. 词源与前置（铁律 21/22）

- **socket**（套接字）：内核里的「通信端点」对象，fd 是它的句柄——与文件 fd 同一命名空间（所以 read/write/close 通用）。
- **bind**（绑定）：给端点定地址（IP:port）；**listen**（监听）：把 fd 转成被动模式并建排队队列（backlog=8，web.c:979）；**accept**（接受）：从队列取一个已完成连接，**返回一个新 fd**——旧的监听 fd 继续接客。
- **detach**（分离）：pthread_detach 后线程自回收，主线程不需 join。
- V4L2 桥：V4L2 一个 fd 反复 DQBUF；socket 服务器是「一个 fd 生育 fd」——accept 每次产新连接 fd。

## 3. 六阶段执行卡

**① 钩子（破坏式）**：浏览器敲回车到 connect 成功，你的程序一行没跑——内核做了什么（三次握手在你 accept 之前就完成了，躺在 backlog 队列里）？listen fd 和连接 fd 为什么必须是两个东西？谁创建谁关闭？

**② 最小模型（三件套）**：
- 全面概念：TCP 服务器=「总机+分机」模型：socket() 造总机 → bind 定号 → listen 开线 → accept 每次接通返回一个分机 fd；读写收发全走分机，总机只管接。
- 项目结合：web_thread（web.c:964-1000）：socket c:972 → SO_REUSEADDR c:974 → bind c:975 → listen c:979 → accept 循环 c:985-988 → pthread_create+detach c:994-997；分机 fd 交给 client_thread，由它 close（c:959）。
- 生动例子：客服总机永不占线（listen fd 常在），接通转分机（accept 返回新 fd），挂断由分机操作员处理（client_thread close）。

**③ 纸笔操作**：画「监听 fd → accept → 连接 fd → 客户端线程 → close」生命周期图，标两种 fd 各自的创建点/使用点/关闭点；再画 web_stop（1021-1028）在图上的动作。

**④ 闭卷重建**：不看代码口述 web_thread 主循环骨架 + 两种 fd 的生灭责任表。

**⑤ 变式纠偏（已过深度滤网）**：
- V1：accept 阻塞中 g_running=0，为什么线程醒不来？web_stop 的 shutdown(g_listen_fd) 起什么作用？（shutdown 让阻塞的 accept 立即返回错误→循环条件退出→join 才能返回；对照 Phase 1 停止延迟家族）
- V2：每个连接一线程，慢客户端为什么拖不垮别的连接？大量客户端的风险是什么？（线程栈内存/调度开销；一句话提 IO 多路复用，epoll 细节留通用八股）
- V3：SO_REUSEADDR 一句话作用？（绕过 TIME_WAIT 立即重绑，重启服务不卡端口。）

**⑥ 重逢绑定**：3.4 精读 web_start/stop；rtsp_server 对照（同为 socket server，控制+媒体双通道）；C4 的 HTTP 字节就流在这些 fd 上。

## 4. 关键事实表（已实测）

| 事实 | 位置 |
| --- | --- |
| socket/bind/listen 都发生在 web 线程（异步于 web_start 返回） | web.c:972-982 |
| backlog=8 | c:979 |
| accept 失败仅 continue | c:989-991 |
| 连接 fd 由 client_thread close | c:955-961 |
| bind 失败只 LOG_ERR 返回 NULL，调用者 start 已返 0 | c:975-978 vs 1003-1018 |
| web_stop：shutdown+close 监听 fd → join | c:1021-1028 |

## 5. 快问快答（收口用）

1. connect 完成时服务器代码跑到哪一行？（可能还在 accept 前——握手由内核完成）
2. 监听 fd 上能 recv 吗？（不能，只 accept）
3. 忘了 close 连接 fd 会怎样？（fd 泄漏+连接悬挂，直至客户端断开）
4. 两个客户端同时来，谁处理？（backlog 排队+accept 循环逐个取，各起线程）
5. web_start 返回 0 能断言「端口已监听」吗？（不能——3.4 核心审计题在此预埋）

## 6. 通过判定

④ 骨架口述 + ⑤ V1 独立讲清 shutdown 唤醒 accept 因果即 L2 通过；落卡：07_Web配置.md（卡方向：两种 fd/每连接一线程/异步启动边界）。

## 7. 本阶段说明草稿（收口用，铁律 23）

学了 socket 服务器生命周期 → 对应链路 D（Web）与本地 RTSP 转发的传输底座，解决「HTTP/RTSP 字节在什么对象上流动」问题 → 承接 fd 通用概念（V4L2 迁移），开启 3.4 精读与 C4（fd 上跑什么协议）→ 面试素材：自研双服务器句、listen/连接 fd 辨析、停止时如何唤醒 accept。
