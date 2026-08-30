# C4 · HTTP 请求/响应模型（概念块，45min）

> ID 3.0B · 认证 L2（不推进任务 ID）· 落卡方向：07_Web配置.md
> 状态：待开（C3 后）

## 0. 开块审查

- grep 核对：`grep -n "HTTP/1.1\|Content-Length" web.c | head`（send_http 104-125、handle_client_inner 862-951）。
- 前置：C3 已建「字节在连接 fd 上流动」；本块讲字节长什么样。2.2 已见过 curl=HTTP 客户端侧，可反向印证。

## 1. 任务目的（四层）

① 3.1 的路由解析、3.2 的 multipart、3.3 的 Range 全是 HTTP 头的语法游戏，没有「请求行+头+空行+体」四段式模型，三张卡都要现场补课。② 项目背景：web.c 用 sprintf 手拼响应、strstr 手解请求——因为作者吃透了协议是纯文本；「自研 HTTP 服务器」的底气来自这 45 分钟。③ 岗位背景：HTTP 模型是测开/后端/嵌入式通用题；「无 Content-Length 怎么知道结束」一题区分背状态码和理解定界的人。④ 学完能默写最小 GET/响应、解释 send_http 每一行、为 3.3 预留 206 接口。

## 2. 词源与前置（铁律 21/22）

- **HTTP** = HyperText Transfer Protocol；**请求行**（request line）=`方法 路径 版本`；**头**（header）=`名字: 值` 每行一个；**空行**（\r\n\r\n）=头体分界；**体**（body）=字节数据。
- **Content-Length**（内容长度）：体的字节数——接收方据此定界；**Connection: close**：响应发完即断（本项目无 keep-alive）。
- 无状态（stateless）：每个请求独立，服务器不记得上一个请求——所以前端才要反复 GET /api/status。

## 3. 六阶段执行卡

**① 钩子（破坏式）**：curl 发出的字节和你 telnet 手敲的是不是同一种文本？（是——HTTP 是人可读文本协议）web.c 为什么 sprintf 就能拼出浏览器认识的响应？没有 Content-Length，接收方怎么知道正文在哪结束？

**② 最小模型（三件套）**：
- 全面概念：请求/响应都是「起始行+头+空行+体」四段文本；靠头字段传达元信息（长度/类型/范围），靠空行定界。
- 项目结合：handle_client_inner sscanf 请求行（c:871）、req_hdr_get 逐行扫头（c:834-859）、找 \r\n\r\n 定体（c:885）；send_http 拼状态行+Content-Type+Content-Length+close（c:104-125）；curl 是同一协议的客户端侧（cloud_ai.c:201-242，2.2 已学）。
- 生动例子：寄信——信封格式（头）必须合规范，邮局只认格式不认内容；空行=信封口，之后才是信纸（体）。

**③ 纸笔操作**：手写最小 GET 请求（GET /api/status HTTP/1.1 + Host + 空行）与 200 响应各一条；在响应头区留一个「206 Partial Content + Content-Range」空位（3.3 填）。

**④ 闭卷重建**：口述一次 POST /api/config 从浏览器到 web.c 的字节旅程（请求行→头含 Content-Length→空行→JSON 体；web.c 读头算长度、补读体 c:879-909）。

**⑤ 变式纠偏（已过深度滤网）**：
- V1：POST body 长度谁告诉服务器？如果实际 body 比 Content-Length 长会怎样？（头声明；web.c 只补读声明长度，多余字节留在内核缓冲成「下一个请求」——但本实现 Connection: close 不复用，一句话带过）
- V2：MJPEG 流为什么可以没有 Content-Length 地一直发？（multipart 每帧自带小定界；连接关闭=结束——3.2 展开）
- V3：本项目用到的状态码清单 200/206/400/403/404/405/500/503 各在哪触发？（send_http c:106-111 映射表 + 各 handler）
- 提升池（一句话）：chunked 传输编码=另一种无长度定界，HTTP/2 是二进制分帧——本项目都不涉及。

**⑥ 重逢绑定**：3.1 路由=请求行的路径字段；3.2 multipart=体的高级形态；3.3 Range=一个请求头改写响应语义；2.2 反向印证（curl 客户端视角已考过）。

## 4. 关键事实表（已实测）

| 事实 | 位置 |
| --- | --- |
| 一次 recv 读请求（≤4096B 假设） | web.c:865 |
| 请求行 sscanf %15s/%1023s | c:871 |
| 头逐行大小写不敏感匹配 | c:834-859 |
| 体靠 Content-Length 补读 | c:879-909 |
| 响应头模板（状态行+两头+close） | c:104-125 |
| 全部响应 Connection: close | c:116,121 |

## 5. 快问快答（收口用）

1. 头和体靠什么分界？（空行 \r\n\r\n）
2. HEAD/PUT 来了会怎样？（405，c:946）
3. 为什么说 HTTP 无状态？项目里谁在弥补？（服务器不记请求历史；前端 JS 定时轮询 /api/status）
4. telnet 8080 端口手敲 `GET /api/status HTTP/1.1` +两次回车，能得到什么？（JSON——协议是文本的铁证）
5. Content-Type 的作用？（告诉接收方怎么解释体字节：html/json/jpeg/mp4/multipart）

## 6. 通过判定

③ 两条手写样例结构正确 + ④ 字节旅程口述完整即 L2 通过；落卡：07_Web配置.md（卡方向：四段式模型/Content-Length 定界/无状态）。

## 7. 本阶段说明草稿（收口用，铁律 23）

学了 HTTP 请求/响应模型 → 对应链路 D 的应用层语法，解释「为什么 sprintf/strstr 就能实现服务器」→ 承接 C3（fd 上的字节有了语法），开启 3.1-3.3 三张媒体/路由卡；与 2.2 的 curl 客户端侧合璧成完整协议观 → 面试素材：自研 HTTP server 的协议依据、定界与无状态题。
