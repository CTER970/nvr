# S-11｜手写 memcpy/memmove（重叠处理）

> **卡头**：S-11｜嵌入式原创（无 LC 对应）｜F2 库函数手写族｜P0（签到四件套之一）｜嵌入式基础+｜纯 C（原创轨）
> **实证**：CVTE HS-014（现场 9 题连撕之一）、MTK B2-39 组题
> **定位**：**写得出重叠处理 = 懂内存模型**——嵌入式岗身份题的核心一道；memmove 的"先判方向再选路线"是全部考点。

---

## 一、题目解析

- **输入**：`void *dst, const void *src, size_t n`（n 字节；memcpy 契约**不保证**区域不重叠，重叠时 UB；memmove 保证重叠正确）。
- **输出**：返回 dst 原值；副作用为 n 字节复制。
- **契约三问**：看 `'\0'` 吗？→**不看，只认长度 n**（与 strcpy 的分界线）；参数可 NULL？→不可（n>0 时）；返回什么？→dst 原值。
- **一句话考什么**：**重叠三区判断**（dst 在 src 前/中/后）与拷贝方向选择——正向拷什么时候毁数据。

## 二、解题思路

memcpy 正向逐字节拷即可（契约要求不重叠）。但若 dst 落在 `(src, src+n)` 区间内（dst 在 src 后方且重叠），正向拷会**先踩掉还没读的源字节**：

```
src:  [A][B][C][D]
dst 落在 src+1（重叠）:
正向: 先把 A 写到 src+1 → 覆盖了 B！下一轮读到的是 A 而非 B
      结果 [A][A][A][A]  ← 数据污染

反向: 从尾部 D 开始：D→src+4, C→src+3, B→src+2, A→src+1
      读 C 时 src+1 已写但 C 在 src+2 未被踩 → 安全
```

结论：dst 在 src 前方（`dst <= src`）或完全不相交 → 正向；dst 在 `(src, src+n)` 内 → 反向。memmove = memcpy + 这层方向判断。

## 三、代码（两版）

### 3.1 面试清爽版

```c
#include <assert.h>

void *memcpy(void *dst, const void *src, size_t n)
{
    assert(dst && src);
    unsigned char *d = dst;
    const unsigned char *s = src;
    while (n--) *d++ = *s++;
    return dst;
}

void *memmove(void *dst, const void *src, size_t n)
{
    assert(dst && src);
    unsigned char *d = dst;
    const unsigned char *s = src;
    if (d < s || d >= s + n) {
        while (n--) *d++ = *s++;
    } else {
        while (n--) d[n] = s[n];
    }
    return dst;
}
```

### 3.2 教学讲解版

```c
void *memmove(void *dst, const void *src, size_t n)
{
    assert(dst && src);

    // void* 不能直接解引用（它只是"某地址"，无类型宽度），
    // 必须逐字节操作 → 转 unsigned char*。
    // 选 unsigned：签名 char 的整型提升会把 ≥0x80 字节当负数，
    // 虽然此处只作搬运不比较，习惯上仍用无符号防患
    unsigned char *d = dst;
    const unsigned char *s = src;

    if (d < s || d >= s + n) {
        // 不重叠 或 dst 在 src 前方：正向安全。
        // （dst 在 src 前时即使重叠，写入位置永远追不上读取位置）
        while (n--) *d++ = *s++;
    } else {
        // dst 落在 (src, src+n) 内：正向会踩掉未读源字节 → 从尾反向。
        // 反向时 d+n-1 与 s+n-1 同步递减，写区永远在读区后方 → 安全
        while (n--) d[n] = s[n];
    }
    return dst;
}
```

## 四、代码解析

**两块结构**：方向判定（一次比较）+ 双路线拷贝。

判定式的正确性：`d < s`（dst 前方，含相邻）或 `d >= s+n`（dst 越过 src 尾，不重叠）→ 正向；否则（dst 在 src 区间内/与尾相接）→ 反向。**只需判 dst 相对 src 的位置**，不用再判 src 在 dst 内——因为重叠区由"dst 与 [src,src+n) 的关系"唯一决定。

反向循环 `d[n] = s[n]` 与正向 `*d++ = *s++` 的等价性：n 从原值递减到 0，访问序 d[n-1], d[n-2]…d[0]——从尾到头，且循环结束时 n==0 恢复初值，无需额外下标变量。

**高频追问**（对话层）：为什么标准库要分两个函数？→memcpy 允许实现走 SIMD 快路径（不用考虑反向），memmove 多一次判断更慢——语义换性能；`n==0`？→两循环都零次执行，安全返回。

**不变量视角**：反向拷贝全程保持"写区恒在读区后方"（d+n-1 与 s+n-1 同步递减）——已写位置永不覆盖尚未读取的源字节，这正是方向判断要守护的性质。

## 五、复杂度

- **时间 O(n)**：每字节恰好一次读+一次写；方向判断 O(1)。最坏=平均。
- **空间 O(1)**
  - **口径说明**：辅助空间=两个字节指针；源/目标缓冲区属调用者提供的输入空间，不计入。
- **口述模板**："O(n) 单遍逐字节；重叠时 dst 在 (src,src+n) 内必须反向拷，否则踩掉未读源字节——memmove 就是先判方向再选路线的 memcpy；空间 O(1)。"

---

*范式：算法刷题模板 v1.3（2026-10-19）· 过卡后回写 06 表 §五 S-11*
