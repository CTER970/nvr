# 02 stream_receiver · 八股卡片

> 来源:任务1.1/1.5A-C | 文件规范见 [README.md](README.md)

### Q: 一次 av_read_frame 之后,packet 的三个去向是什么?
- **一句话**: 同一个packet被同步借用给三个消费者——recorder写MP4(主路)、frame_grabber解JPEG(旁路)、rtsp_server转发(旁路),用完由receiver循环末尾统一unref。
- **要点**: ①先过滤 pkt.stream_index==vidx 只处理视频;②顺序:recorder→frame_grabber→rtsp_server;③三个消费者都是"借用"不改原packet(recorder内部clone);④两处unref兜底:每帧末尾c:170+提前break后循环外c:172。
- **不这样会怎样**: 消费者各自拉流=同一RTSP源被拉3遍,网络和CPU×3;消费者改动原packet会污染其他两个消费者。
- **源码**: stream_receiver.c:161-173(三分发),c:170/172(unref)
- **状态**: 2026-08-13 首次掌握;待 Phase 1 总验收抽查
- **关联**: ——

### Q: open_input 三步(alloc/open/find_stream_info)各干什么?ic的数据从哪来?
- **一句话**: alloc领空结构体;open建立RTSP连接并解析SDP填基础信息(codec_type/codec_id/时基);find_stream_info读几帧RTP解析SPS/PPS填详细参数(分辨率/帧率/extradata)。
- **要点**: ①ic不是"本来有数据",是V821通过SDP+RTP逐步告知、FFmpeg翻译填入;②analyzeduration 5s/probesize 10MB放大探测窗口,因V821在线编码首个IDR来得慢,默认1s/512KB收不够会报"not enough frames";③fflags=+discardcorrupt丢坏包不崩;④open后释放用close_input不是free_context(还绑着IO)。
- **不这样会怎样**: 探测窗口默认值在真实硬件上打不开流;free/close用错=IO泄漏。
- **源码**: stream_receiver.c open_input(c:34-90,行号按08-14后)
- **状态**: 2026-08-12 首次掌握;待复测
- **关联**: ——

### Q: receiver_thread 两层循环怎么分工?断线后怎么恢复?
- **一句话**: 外层管"一次连接生命周期"(连不上sleep重连,无限重试直到g_running=0),内层管"读包+三分发";断线break内层→清理输入→sleep→回外层重连,g_rec保留所以recorder不重建、当前段继续写。
- **要点**: ①重连等待用for逐秒sleep+检查g_running(可中断睡眠,最多1秒响应停止);②recorder_create失败break外层=线程退出(主路挂了没意义);frame_grabber/rtsp失败只降级旁路,标志保持0下次重连自动重试;③写错误连续20次break内层走重连。
- **不这样会怎样**: sleep(N)整段睡死无法响应停止;主路失败继续跑=空转;旁路失败杀线程=预览坏了录像也停,违反主路旁路优先级。
- **源码**: stream_receiver.c receiver_thread(c:91-189)
- **状态**: 2026-08-13 首次掌握;待断线情境变式复测
- **关联**: ——

### Q: stop流程为什么要 join 之后才能释放资源?
- **一句话**: g_running=0只是请求,线程可能还在av_read_frame阻塞或写文件中;pthread_join等到线程真结束,才能安全清理g_ic/g_rec,否则use-after-free。
- **要点**: ①volatile保证写方(stop)的修改对读方(线程循环条件)可见;②不用pthread_cancel——强杀可能在持锁/写文件中终止,MP4损坏+资源泄漏;③顺序:置标志→join→关输入→销毁recorder→deinit两个旁路。
- **不这样会怎样**: 不join直接释放=线程访问已释放的g_rec崩溃;用cancel=写一半的段损坏。
- **源码**: stream_receiver_stop(c:206-216)
- **状态**: 2026-08-12 首次掌握;待停止情境变式复测
- **关联**: ——

### Q: 帧率节流为什么用 CLOCK_MONOTONIC?
- **一句话**: 单调时钟不受系统改时间/NTP跳变影响,测"间隔"必须用它;墙钟会被改导致节流乱跳。
- **要点**: ①frame_grabber/状态查询用;②now_us差值和interval比较决定跳过本帧。
- **不这样会怎样**: 系统时间回拨→差值为负→狂发或停发;前跳→长时间不发。
- **源码**: frame_grabber.c:39(clock_gettime CLOCK_MONOTONIC)
- **状态**: 2026-08-08 接触;正式复测待1.7C
- **关联**: ——

### Q: frame_grabber 为什么只存最新帧不存队列?get_jpeg 为什么返回 malloc 拷贝?
- **一句话**: Web预览和云AI都只要"当前画面",旧帧无价值,单帧覆盖省内存;返回拷贝是锁内复制、锁外使用,调用方free,隔离所有权生命周期。
- **要点**: ①mutex只保护临界区一致性,不能保证解锁后内部指针仍有效——所以给拷贝;②多消费者(Web+cloud_ai)同时取互不影响。
- **不这样会怎样**: 返回内部指针=调用方读时生产者realloc覆盖=撕裂读;存队列=内存涨+旧帧永远没人要。
- **源码**: frame_grabber.c g_jpeg单帧(c:30-31),get_jpeg malloc拷贝(c:193-198)
- **状态**: 2026-08-08 首次掌握;待1.7系统复测
- **关联**: ——
