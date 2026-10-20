# S-29｜socket TCP echo server 最小版

> **卡头**：S-29｜嵌入式原创｜F5 特色族｜P1｜嵌入式基础+｜纯 C（原创轨）
> **实证**：海康 HS-022/078 两场（网络摄像头/嵌入式设备厂必考）
> **定位**：socket 五步是 Linux 网络编程的"hello world"——设备侧所有网络服务（RTSP、SDK 通信、升级接收）都是在这副骨架上加肉；追问"粘包"引出定界，是流式协议理解的第一课。

---

## 一、题目解析

- **输入**：客户端经 TCP 发来的任意字节流。
- **输出**：原样回发（echo）——收到什么回什么，不解析内容。
- **约束确认**（写码前 30 秒口述）：单客户端还是并发？→最小版单连接（accept 一次循环服务）；\n 算消息边界吗？→echo 不需要边界（字节流原样回），但**追问粘包时必须定界**；recv 返回 0 代表什么？→对端关闭，必须退出读循环。
- **一句话考什么**：五步调用顺序+fd 语义（listen_fd 收连接、conn_fd 收数据）+字节流无消息边界的意识。

## 二、解题思路

TCP echo server 的固定骨架：socket（要插座）→ bind（定门牌）→ listen（挂耳机等铃）→ accept（接起电话，拿到一条专线）→ recv/send（专线上收发）。**两个 fd 分工**是理解核心：listen_fd 只管接连接，conn_fd 才是数据通道。

```
                                    TCP 三次握手在 accept 队列里完成
 client                          server
   │  connect ──────────────────→  listen_fd（backlog 队列）
   │                               │ accept() 摘出一条已建连 → 返回 conn_fd
   │  "hello" ──────────────────→  │
   │ ←──────────────────── echo    │ recv(conn_fd) → send(conn_fd)
   │                               │ recv()==0 → 对端关闭 → close(conn_fd)
   │  close ───────────────────→   │

 字节流视角（粘包现场）：
 client 发:  [AA][BB]     [CC]        ← 两次 send，应用层两条"消息"
 server 收:  recv→"AA BB"  recv→"CC"  ← TCP 不保证按发送次数交付！
             （第一次可能收到两条粘在一起——字节流无边界，
              消息边界必须应用层协议自己定：定长/分隔符/长度前缀）
```

echo 对粘包免疫（收什么回什么，不解析），所以最小版不需要定界；一旦改成"处理消息"就必须三选一：定长结构体、`\n` 分隔、4 字节长度前缀+payload。

## 三、代码（两版）

### 3.1 面试清爽版（最小可运行）

```c
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>

#define PORT 9000

int main(void)
{
    int lfd = socket(AF_INET, SOCK_STREAM, 0);          /* 1. socket */
    if (lfd < 0) return 1;

    struct sockaddr_in addr = {0};
    addr.sin_family      = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_ANY);           /* 0.0.0.0=本机所有网卡 */
    addr.sin_port        = htons(PORT);                 /* 端口必须网络字节序 */
    if (bind(lfd, (struct sockaddr *)&addr, sizeof(addr)) < 0) return 1;   /* 2. bind */

    if (listen(lfd, 8) < 0) return 1;                   /* 3. listen */

    for (;;) {
        int cfd = accept(lfd, NULL, NULL);              /* 4. accept：阻塞到有连接 */
        if (cfd < 0) continue;

        char buf[512];
        ssize_t n;
        while ((n = recv(cfd, buf, sizeof(buf), 0)) > 0) {   /* 5. recv */
            ssize_t off = 0;
            while (off < n) {                           /* send 可能短写，循环补齐 */
                ssize_t m = send(cfd, buf + off, n - off, 0);
                if (m <= 0) break;
                off += m;
            }
        }
        close(cfd);                                     /* n==0：对端关闭 */
    }
}
```

### 3.2 教学讲解版（关键决策注释）

```c
int lfd = socket(AF_INET, SOCK_STREAM, 0);
/* SOCK_STREAM=TCP 字节流。返回的是"监听插座"，不是数据通道——
   后续 accept 返回的 conn_fd 才用于 recv/send，两个 fd 各司其职 */

struct sockaddr_in addr = {0};
addr.sin_family      = AF_INET;
addr.sin_addr.s_addr = htonl(INADDR_ANY);
/* 端口/IP 走网络必须转网络字节序（大端）：htons/htonl。
   忘记 htons 是现场最高频 bug：连 9000 变成连 0x2823(10275) */

bind(lfd, (struct sockaddr *)&addr, sizeof(addr));
/* bind 把 socket 绑到本地"IP:port"。省略 bind 的话 connect 会随机分配端口，
   但 server 必须固定端口等客户端上门，所以 bind 不能省 */

listen(lfd, 8);
/* 8=backlog：已完成三次握手、等待 accept 摘取的连接队列上限。
   队列满时新连接被拒——并发高的设备要调大 */

int cfd = accept(lfd, NULL, NULL);
/* 阻塞直到队列里有连接；返回新 fd 代表"这一条连接"。
   TCP 握手由内核完成，accept 只是摘连接，不参与握手 */

ssize_t n;
while ((n = recv(cfd, buf, sizeof(buf), 0)) > 0) {
/* recv>0=收到的字节数；==0=对端有序关闭（唯一判断点，漏写则死循环）；
   <0=出错。返回值是"本次到达的字节数"，与客户端 send 次数无关——
   这就是粘包的根源：TCP 是字节流，不是消息流 */
    ...
}
close(cfd);
/* conn_fd 用完必关；listen_fd 继续留在 accept 循环里服务下一个客户端 */
```

## 四、代码解析

**三块结构**：

1. **建连块**（socket→bind→listen→accept 四步）：顺序不可换——没有 fd 不能 bind，没 bind 端口无从 listen，没 listen 的 fd 不能 accept；每步判错返回，现场口述"这套模板我每步都查返回值"。
2. **收发块**：recv 循环以 `>0` 为条件，**==0（对端关闭）是唯一退出途径**；send 外面套偏移循环处理**短写**（内核发送缓冲满时 send 只写入部分，必须补齐——面试加分点）。
3. **回绕块**：close(cfd) 后回到 accept——单连接串行版；并发追问升级路径：fork per connection / 每连接一个 pthread / select-poll-epoll 多路复用，一口带过即可。

**不变量视角**：任意时刻"listen_fd 只出现在 accept 参数里，conn_fd 只出现在 recv/send 参数里"——两个 fd 不混用，就是骨架正确的全部秘密。

## 五、复杂度

- **时间 O(n)/连接**（n=该连接收发字节总量）：每字节被 recv、send 各搬运 O(1) 次；accept/绑定等建连开销 O(1)/连接，与流量无关。
- **空间 O(1)**（口径：辅助空间）
  - **口径说明**：辅助=512B 栈上缓冲+两个 fd 整数，固定大小；内核为连接分配的收发缓冲（数 KB/连接）属**内核资源**，面试提及但不计入算法空间；单连接版无每连接堆分配（无 malloc）。
- **口述模板**："时间每字节 O(1) 搬运、每连接 O(1) 建连；辅助空间一块栈缓冲，真正的开销在内核侧每连接的收发缓冲——所以高并发才要 epoll 事件驱动，把 fd 轮询的 O(n) 降掉。"

---

*范式：算法刷题模板 v1.3（2026-10-19）· 过卡后回写 06 表 §五 S-29*
