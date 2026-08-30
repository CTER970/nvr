# 04 · frame_grabber（抽帧、JPEG、节流）

> 建立:2026-08-20,1.7A 收口时初始化。

### Q: 为什么 recorder 切段必须等关键帧，而 frame_grabber 的抽帧节流完全不看帧类型？
- **一句话**: 挑不挑帧取决于输出边界落在哪个域——压缩域边界必须落在参考链重置点（IDR）上，原始域边界每帧都是完整图、随便落。
- **要点**: ①recorder 只 remux 不解码：段首样本必须是关键帧，否则段内 P 帧缺参考帧、整段不可解码（waiting_key 机制）②frame_grabber 工作在解码出口之后：receive_frame 吐出的每一帧（含 P 帧）都是参考解析完毕的完整 YUV 图片 ③节流只挡缩放+编码+缓存；feed 对每个包无条件 send_packet 解码——参考链必须逐包维护，跳过即断
- **不这样会怎样**: recorder 用 P 帧起段→播放器段首解码失败/花屏；grabber 在解码前节流→参考帧缺失→后续解码错误传递（I/P/B 依赖）
- **源码**: frame_grabber.c:138-145（节流判断只有时间差、无帧类型字段）；frame_grabber.c:175（无条件 send）；recorder.c waiting_key
- **状态**: 2026-08-20 首次掌握（两域原则由学生独立合成，闭卷对比题通过；"CPU 取舍解释为何节流、不解释为何不挑帧"已纠偏）
- **关联**: 03_recorder.md 关键帧/fMP4 卡；1.6A 参考帧依赖知识迁移

### Q: g_dst_frame 为什么要两步释放（先 av_freep(&data[0]) 再 av_frame_free），而 g_dec_frame 一步就够？
- **一句话**: 两帧图像内存走的挂载通道不同——解码器分配的登记在引用计数系统内（一步全收），av_image_alloc 分配的是裸内存（av_frame_free 不认识，必须自己摘）。
- **要点**: ①g_dec_frame 的 buffer 由 receive_frame 从解码器 buffer 池填充，包成带计数的 AVBufferRef→av_frame_free 连数据带壳回收 ②g_dst_frame 的内存在 init 里 av_image_alloc 手工分配、裸指针写入 data[]→不在计数系统→先 av_freep 再 free 壳 ③YUVJ420P planar 一整块连续内存，data[1]/data[2] 是块内偏移，free data[0] 即全部平面 ④顺序不能反：av_frame_free 先执行会把帧指针置 NULL，data[0] 永久丢失=泄漏 ⑤av_freep=free+置 NULL，防悬垂指针的工具
- **不这样会怎样**: 漏 av_freep→帧壳释放后内存无人能 free=内存泄漏（不是悬垂指针）；若内存来自 av_frame_get_buffer（登记在册）还手动 av_freep→unref 计数归零再释放同一块=双重释放、堆损坏
- **源码**: frame_grabber.c:101（av_image_alloc 裸挂）；frame_grabber.c:123-126（两种释放写法对照）
- **状态**: 2026-08-20 首次掌握（V1 av_frame_get_buffer 变式、V2 对调变式均通过；"泄漏 vs 悬垂指针"术语当场纠偏）
- **关联**: 1.6B pb 所有权原则（谁分配谁释放）；03_recorder.md avio_closep 卡

### Q: 为什么 send 一次包要用 while 循环 receive 帧，而编码侧只 receive 一次？
- **一句话**: H.264 帧间编码使解码输入输出非一一对应（一包可产出 0/1/N 帧），必须循环排空；JPEG 帧内编码一帧一包，无重排序无积压，一次即够。
- **要点**: ①0 帧：SPS/PPS 参数集包、B 帧重排序等待（显示顺序在前、解码顺序靠后）②N 帧：参考帧齐了积压帧一次放行 ③receive 循环三个出口：EAGAIN（常态=输出空）/EOF（本代码无 flush 实际不可达，防御性出口）/其他负值（解码器坏状态）④同样的 API，语义随编码域变——帧内编码不需要循环
- **不这样会怎样**: 解码侧只 receive 一次→积压帧滞留解码器内部→下次 send 可能 EAGAIN；编码侧加循环→无货可取成死循环或纯多余
- **源码**: frame_grabber.c:180-185（while 循环）；frame_grabber.c:155-156（编码侧各一次）
- **状态**: 2026-08-21 首次掌握（0/1/N 三情境独立构造；收口闭卷通过）
- **关联**: 05_协议.md H.264 B 帧重排序；02卡三分发

### Q: send/receive 的 EAGAIN 在两侧各是什么意思？send 返回 EAGAIN 时这个包丢了吗？
- **一句话**: receive 侧 EAGAIN=输出队列空（正常出口，等下一个包）；send 侧 EAGAIN=解码器攒的帧没被取走而拒收输入——官方契约要求先排空输出再重发同一包，本代码不重发=这个包真的丢了。
- **要点**: ①契约原文：input not accepted→必须先 read output→packet should be resent ②丢包后果放大：H.264 参考链断裂，到下个 IDR 前预览花屏/解不出 ③本代码每次 send 后都排空 receive→send-EAGAIN 几乎不可达（唯一现实入口：上轮以硬错误提前 break 且输出残留）→该分支是防御性容错 ④与 V4L2 非阻塞 DQBUF 的 EAGAIN 同语义（输出空），直觉可迁移
- **不这样会怎样**: 把 send-EAGAIN 理解成"输入排队"会误判丢包位置；假设一进一出配对会漏排空、丢积压帧
- **源码**: frame_grabber.c:175-178（send 分支）
- **状态**: 2026-08-21 首次掌握（"输入积压"方向纠偏后经收口追问内化，契约已查 ffmpeg doxygen）
- **关联**: 02卡 receiver 循环；05_协议.md

### Q: 从 H.264 包到 web 拿到 JPEG，所有权怎么交割？为什么全程有三次拷贝？
- **一句话**: 六对象链（输入pkt→g_dec_frame→g_dst_frame→JPEG pkt→g_jpeg→get_jpeg buf）上，凡跨所有权或线程边界就用拷贝断开——clone 给 recorder、memcpy 进 g_jpeg、malloc 拷出给调用方，三次拷贝同属一个模式。
- **要点**: ①输入 pkt 全链纯借用：本模块不建不写不毁，由调用方 c:171 归还——唯一"没被本模块写过数据"的节点 ②JPEG pkt 私有：alloc/free 封闭在 emit 内 ③g_jpeg 单帧覆盖=生产者-多消费者解耦点（Web+云AI 共用一份最新帧）④get_jpeg 拷贝=跨线程交割：锁内复制、锁外使用、调用方 free ⑤nb=realloc 防御：失败返回 NULL 直接覆盖 g_jpeg=旧缓存泄漏+预览断供 ⑥像素/压缩字节的写入者全是 FFmpeg API，项目代码只写元数据（pts/指针/size）+两次 memcpy——"驱动库干活、只搬运所有权"
- **不这样会怎样**: unref 写进 feed→三分发后面的 rtsp_server 拿到空包；返回内部指针→消费者读时被覆盖=撕裂读；省掉 g_jpeg 层=两个消费者抢一份数据
- **源码**: frame_grabber.c:148-168（缩放/编码/缓存）；frame_grabber.c:190-207（get_jpeg）；stream_receiver.c:157-171（三分发+归还）
- **状态**: 2026-08-21 首次掌握（1.7B-2 四问独立作答+1.7B-3 闭卷拓扑通过）
- **关联**: 本文件双通道释放卡；02卡 get_jpeg malloc 拷贝卡

### Q: c:150 的 pts 拷贝在本代码有下游消费者吗？
- **一句话**: 没有——帧带 pts 进编码器是管线惯例，但缓存环节只 memcpy data+记 size，pts 从未进入 g_jpeg；下游真实时间来自 MJPEG 发送节奏和 cloud_ai 墙钟。
- **要点**: 三层证据法示范：应然（管线惯例时间戳跟着帧走）/实然（c:163 只拷 pkt->data、g_jpeg_size=size，pts 未存）/结论（防御性惯例传递，删了当前无实际后果）。"管线里传了"≠"有人用"——讲设计先查消费点
- **不这样会怎样**: 面试时声称"预览靠 pts 控节奏"会被追问打穿——真实机制是服务器发送节奏
- **源码**: frame_grabber.c:150（拷 pts）；frame_grabber.c:159-165（缓存只存 data/size）
- **状态**: 2026-08-21 首次掌握（纠偏后闭卷复述通过，正式关闭）
- **关联**: 05_协议.md 时间基卡

### Q: 节流闸门为什么只在"放行"时更新 g_last_emit_us？改成每帧更新会怎样？
- **一句话**: 门槛是"距上次**放行**的时长 ≥ interval"，基准必须挂在放行事件上；挂到每帧上，稳定帧流里 now-last 永远只有两帧间隔(远小于 interval)，一帧都放不出——不是松紧变化，是饿死。
- **要点**: ①throttle=固定间隔放行(速率上限)，基准=上次放行 ②每帧更新=把基准挂在被丢弃的事件上，坏 throttle ③与 debounce 区分：debounce 是输入停止静默期后才触发(输入框停打字 500ms 才搜索)，帧流持续到来时永不满足 ④时钟用 CLOCK_MONOTONIC：只增、减不了、无人能 set；墙钟被 NTP 回拨→now-last 变负→全丢，前跳→恒放 ⑤target_fps==0 时 c:138 守卫为假，节流块整体跳过=不限速 ⑥热更新 set_target_fps 只改门槛 interval、不重置 last——刚放行过就继续丢到满足新 interval。
- **不这样会怎样**: 每帧更新→预览/上云一帧不出；墙钟→校时瞬间节流失控(全丢或全放)。
- **源码**: frame_grabber.c:137-145(节流)；37-42(now_us)；210-215(set_target_fps)
- **状态**: 2026-08-22 首次掌握（饿死变式独立推出；debounce 术语标签当场纠偏；热更新计数闭卷题通过）
- **关联**: 本文件两域边界卡（节流不看帧类型的原始域理由）

### Q: 慢消费者拿 buf 用 500ms，为什么生产者不受阻、buf 也不被污染？两个保证者分别是什么？
- **一句话**: 不受阻的保证者是**锁划得小**(临界区只装 malloc+memcpy 微秒级动作，慢活在锁外)；buf 不被污染的保证者**根本不是锁**(那时锁已释放)，是 malloc+memcpy 深拷贝断开别名+所有权归调用方。
- **要点**: ①锁的必要性来自**共享**、不来自重要：单线程私有变量(g_dec_frame/g_dst_frame/g_sws/g_enc)永远免锁 ②锁粒度=临界区只包共享状态读写，重活(CPU 密集的缩放/编码、网络 IO)留锁外 ③直接返回 g_jpeg 有两层死法：锁外被 realloc 搬家 free 旧块=use-after-free；被 memcpy 逐字节覆盖=撕裂读(半新半旧缝合帧) ④锁外访问要分级：g_last_emit_us 锁外=单线程免锁；target_fps 读锁外=实践良性 int 读(与 set_segment_seconds 无锁读同族)；**g_jpeg_size 锁外读(c:206 return)=有真实后果**——返回值可能对应新帧 size 而 buf 是旧帧拷贝，调用方按返回值当长度用=堆越界读，修法=锁内存局部 `int sz` 返回 ⑤realloc 失败原块不释放：nb 接住、失败则旧帧继续可读、本帧丢弃(失败就地降级)。
- **不这样会怎样**: 把 send 写进临界区→拉流线程卡 500ms；直接返回内部指针→UAF+撕裂读;`g_jpeg = realloc(g_jpeg,...)`→失败即泄漏+size 与 NULL 不一致。
- **源码**: frame_grabber.c:159-166(锁内覆盖)；190-207(get_jpeg)；204-206(L206 锁外读)
- **状态**: 2026-08-22 首次掌握（审计表独立挖出 L206 锁外读=手册进阶题埋点；"不是锁本身保证了不阻塞，是锁划得小""②根本不是锁"为学生原创表述）
- **关联**: 02卡 get_jpeg malloc 拷贝卡；recorder set_segment_seconds 无锁读(补强池同族)

### Q: 锁迁移变式：把 g_last_emit_us 也搬进 g_lock，能消除 get_jpeg 锁外读 g_jpeg_size 的竞争吗？
- **一句话**: 不能——判断搬锁有没有用看**访问集**：只在泵线程读写的变量搬进锁不消除任何竞争，要修的是跨线程变量的锁外读点。
- **要点**: ①给每个共享变量列访问集（谁/哪个线程/锁内锁外）：g_jpeg_size 写=泵线程锁内(c:164)、读=web/ai 锁内(c:193/198/203)+锁外(c:206)；g_last_emit_us 读写=仅泵线程(c:141/144) ②访问集无交集→搬锁只新增临界区，L206 裸读原样 ③「锁不是模块级驱魔结界」（学生原创句式）——锁只保护"确实共享且双方都进临界区"的访问对 ④超额发现：真正未同步对=g_cfg.target_fps(c:138 无锁读 vs set_target_fps 锁内写；规范级 data race/实践良性 int) ⑤L206 修法=锁内存局部 int sz 再返回。
- **不这样会怎样**: 凭直觉"多加锁总没错"→临界区白放大，真后果（旧 buf+新 size→调用方按返回值越界读）反而没修。
- **源码**: frame_grabber.c:141/144、164、193-206、138
- **状态**: 2026-08-27 首次掌握（V1 强通过，「访问集分析法」自主构建）；08-28 收口落卡
- **关联**: 本文件慢消费者双保证卡；recorder set_segment_seconds 无锁读（补强池同族）
