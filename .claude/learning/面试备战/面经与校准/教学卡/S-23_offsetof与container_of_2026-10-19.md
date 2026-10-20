# S-23｜offsetof / container_of 宏

> **卡头**：S-23｜嵌入式原创｜C2 位运算/C 基本功/嵌入式特色族｜P1 第三批｜基础+｜纯 C
> **实证**：大疆 HS-053（笔试原题）
> **定位**：零地址假想法算偏移、成员地址减偏移反推宿主——Linux 内核链表/驱动的地基。

---

## 一、题目解析

- **输入**：①`offsetof(type, member)`：结构体类型与成员名；②`container_of(ptr, type, member)`：指向 member 的指针。
- **输出**：①成员在结构体内的字节偏移（size_t）；②宿主结构体的首地址指针。
- **约束确认**（写码前 30 秒口述）：offsetof 假想的 0 地址会被解引用吗？→不会，仅取地址不解引用，无 UB；container_of 的 ptr 一定来自该类型的成员吗？→是使用契约，传错类型结果无意义；对齐空隙会影响偏移吗？→会，offsetof 算的是"含填充"的真实偏移（见 S-24）。
- **一句话考什么**：`(size_t)&((type*)0)->member` 零地址假想 + "成员地址−偏移=宿主地址"的指针算术。

## 二、解题思路

**offsetof**：假设结构体放在地址 0，则成员地址的数值=偏移量。表达式拆解：`(type*)0` 把 0 强转为指向该类型的指针（假想首地址 0）→ `->member` 选中成员（**只取地址，绝无解引用**）→ `(size_t)&...` 把地址数值转成整数。地址 0+偏移=偏移，一步读出。编译器期即可算定（常见题眼："为什么不崩？"——取地址不访存）。

**container_of**：反向——已知某成员的**实际**地址 ptr，宿主首地址 = ptr − offsetof。`((char*)ptr) - offsetof(type, member)` 先退回宿主起点，再强转回 `type*`。Linux 版多两个润色：`const typeof(((type*)0)->member)* __mptr = ptr` 做一次类型校验；`({})` 语句表达式（见 S-21）。

```
struct task { int state; char name[8]; int prio; } t;

offsetof 推导（假想首地址 = 0）：
  (struct task*)0 ──→ 假对象从地址 0 开始
  &假对象->prio    ──→ 0 + offsetof(task, prio) = 12（含 name 后对齐填充）
  (size_t)…        ──→ 12

container_of 反推（设 t 实际在地址 0x2000_0000，prio 在 0x2000_000C）：
  ptr = &t.prio = 0x2000_000C
  宿主 = (char*)ptr - 12 = 0x2000_0000 = &t
         └─ 成员地址 ─ 偏移 ─┘

内核链表用法：list_head 嵌在宿主里，遍历时拿到的是 node 指针，
container_of(node, task, node) 反手取回宿主 —— 侵入式链表的核心一步
```

## 三、代码（两版）

### 3.1 面试清爽版（现场手写形态）

```c
#include <stddef.h>   /* offsetof 标准头 */

#define my_offsetof(type, member) \
    ((size_t)&(((type*)0)->member))

#define my_container_of(ptr, type, member) ({          \
    const typeof(((type*)0)->member)* _mp = (ptr);     \
    (type*)((char*)_mp - my_offsetof(type, member));   \
})
```

### 3.2 教学讲解版（关键决策注释）

```c
#define my_offsetof(type, member) \
    /* (type*)0：把整数 0 强转成"指向该类型"的假想指针——只是指针值，
       没有 Dereference 发生；&(((type*)0)->member) 取的是
       "若对象在 0 地址，成员会在哪"——0+偏移=偏移，全程不访存，
       所以不会崩；-> 优先级高于 &，外层括号保证先取成员再取地址 */
    ((size_t)&(((type*)0)->member))

#define my_container_of(ptr, type, member) ({               \
    /* 先把 ptr 收进带类型的 _mp：编译器会检查实参类型是否与
       member 一致（传错指针类型直接告警）——内核原版的防御层 */ \
    const typeof(((type*)0)->member)* _mp = (ptr);          \
    /* 指针算术必须走字节粒度：先 (char*) 再减偏移。
       若直接用 type* 减，减的单位是 sizeof(type)，一步差之千里 */ \
    (type*)((char*)_mp - my_offsetof(type, member));        \
})
```

## 四、代码解析

**两块结构**：

1. **my_offsetof**：零地址假想法三步——强转 0、`->member` 选成员、`&` 取地址转 size_t。要点：①`->` 在 `&` 之内（先定位成员再取址）；②无解引用无访存，不触发 UB（0 地址仅作数值参与加法）；③编译期常量，可塞进数组长度/静态断言（如 `static_assert(offsetof(...)==4)` 校验协议布局）。
2. **my_container_of**：反向两步——字节指针减偏移回宿主、强转回 type*。要点：①`typeof` 层既校验实参类型又避免手写成员类型；②减法必须 `(char*)` 粒度；③返回后宿主字段全可访问——因为 ptr 本就来自真宿主成员，偏移回退必落在宿主首地址。

**不变量视角**：恒等式 `container_of(&obj.member, type, member) == &obj` 对一切 obj 成立——offsetof 假想 0 地址与 container_of 用同一假想算偏移，正反两方向共用同一套地址加法，互为逆运算；内核侵入式链表全靠它把"通用 node 指针"还原为"各色宿主指针"。

## 五、复杂度

- **时间 O(1)**：offsetof 编译期常量直接折叠；container_of 展开为一次减法+两次强转，运行期 1~2 条指令；与结构体大小无关。
- **空间 O(1)**
  - **口径说明**：指**辅助空间**——container_of 的 `_mp` 一个指针临时（内核原版自备，语句表达式内）；offsetof 零辅助；无递归。
- **口述模板**："offsetof 是零地址假想：把 0 强转成类型指针，取成员地址不取值，0 加偏移就是偏移，编译期常量；container_of 反着来，成员地址减偏移退回宿主首址，字节粒度做减法——Linux 链表就是靠它从 node 指针拿回宿主，全程 O(1)。"

---

*范式：算法刷题模板 v1.3（2026-10-19）· 过卡后回写 06 表 §五 S-23*
