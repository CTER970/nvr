# S-12｜手写 strlen / strcmp / strstr

> **卡头**：S-12｜嵌入式原创（无 LC 对应）｜F2 库函数手写族｜P1｜嵌入式基础｜纯 C（原创轨）
> **实证**：MTK B2-39 组题（strcpy/strcmp/memcpy/memcmp 连撕）
> **定位**：库函数三连——strlen 的"到 '\0' 为止"、strcmp 的"返回差值不是 ±1"、strstr 的回溯匹配，三个契约坑各守一道。

---

## 一、题目解析

- **strlen**：输入 `const char *s`；输出长度（**不含 '\0'**）；空串返回 0。
- **strcmp**：输入两串；输出：相等 0；不等时**按首个不等字符的无符号差值**（正负号表大小关系）——**不是固定 ±1**。
- **strstr**：输入 haystack 与 needle；输出 needle 在 haystack 中首次出现的指针，找不到返回 NULL；needle 为空串返回 haystack。
- **契约三问**：都依赖 '\0' 结尾？→是（三者皆是）；NULL 防御？→assert；返回语义？→见上各条。
- **一句话考什么**：**终止条件与返回值语义的精确性**——三个函数三个坑。

## 二、解题思路

**strlen**：指针走到 `'\0'` 停，差值即长度。注意"先判断再走"防越界读。

**strcmp**：逐字符比较，先比当前字符；**任一串到尾也参与比较**（`'\0'` 与对方字符的差自动给出正确符号）——两指针同走，循环条件是"两字符相等且非 '\0'"，退出时返回差值。

**strstr**（朴素版）：外层 i 扫 haystack 起点，内层 j 逐位对 needle；不匹配则 **i 回退到本轮起点+1、j 归零**（回溯是朴素版的核心动作）。needle 空串特判返回 haystack。

```
haystack: a b a b c
needle:      a b c
i=2 起匹配: a==a, b==b, c==c → 返回 &haystack[2]

失败例: haystack=aab, needle=ab
i=0: a==a, a≠b → 回溯 i=1（不是 2！）j=0 重比 → a==a,b==b → 命中
```

## 三、代码（两版）

### 3.1 面试清爽版

```c
#include <assert.h>

size_t my_strlen(const char *s)
{
    assert(s);
    const char *p = s;
    while (*p) p++;
    return (size_t)(p - s);
}

int my_strcmp(const char *a, const char *b)
{
    assert(a && b);
    while (*a && *a == *b) { a++; b++; }
    return (int)(unsigned char)*a - (int)(unsigned char)*b;
}

char *my_strstr(const char *hay, const char *needle)
{
    assert(hay && needle);
    if (!*needle) return (char *)hay;
    for (const char *i = hay; *i; i++) {
        const char *p = i, *q = needle;
        while (*p && *q && *p == *q) { p++; q++; }
        if (!*q) return (char *)i;
    }
    return NULL;
}
```

### 3.2 教学讲解版

```c
size_t my_strlen(const char *s)
{
    assert(s);
    // 双指针游标法：p 负责走，s 留在原地做基准
    const char *p = s;
    while (*p) p++;              // '\0' 即停；空串走 0 步，返回 0
    return (size_t)(p - s);      // 指针差 = 元素个数（同一数组内才合法）
}

int my_strcmp(const char *a, const char *b)
{
    assert(a && b);
    // 循环继续的唯一条件：当前字符相等且还不是 '\0'。
    // 退出时刻两种：字符不等（比差值），或同时到 '\0'（差值 0）
    while (*a && *a == *b) { a++; b++; }
    // 转 unsigned char 再转 int 比较：
    // 1) char 符号性由实现定义，非 ASCII 段负值会翻转大小关系
    // 2) 返回的是【差值】——大小信息和差距幅度都在里面，不是 ±1
    return (int)(unsigned char)*a - (int)(unsigned char)*b;
}

char *my_strstr(const char *hay, const char *needle)
{
    assert(hay && needle);
    // 空模式串契约：任何串都"包含"空串 → 返回 hay 本身
    if (!*needle) return (char *)hay;

    for (const char *i = hay; *i; i++) {   // i = 本轮匹配起点
        const char *p = i, *q = needle;    // 工作指针独立于 i（i 不能动）
        while (*p && *q && *p == *q) { p++; q++; }
        if (!*q) return (char *)i;         // needle 走完 = 全部对上
        // 否则回溯：i 由 for 的 i++ 推进到下一起点，q 自动重置
    }
    return NULL;                            // hay 扫完未命中
}
```

## 四、代码解析

**三个函数三条纪律**：

1. **strlen**：`(size_t)(p - s)` 的指针差运算**仅在同一数组内合法**（这正是契约"字符串连续存放"的体现）；返回 size_t——负长度不存在，类型即文档。
2. **strcmp**：`(int)(unsigned char)` 双转换不是装饰——签名 char 平移到 int 会把 0x80+ 当负数，标准规定按**无符号字符值**比较；返回差值意味着 `"a"-"c"` 返回负数但**未必是 −1**，面试官专等你说 ±1。
3. **strstr**：内层用独立工作指针 `p/q` 而非直接动 `i`——起点指针必须保持纯洁，回溯才能靠 for 的 `i++` 一步完成；`!*q` 判命中（needle 耗尽）而非 `!*p`（hay 先尽是失败）。

**不变量视角**（以 strcmp 为例）：每轮退出比较时，`a[0..k)` 与 `b[0..k)` 已证相等——首个不等处即当前位，差值即整体序关系。

## 五、复杂度

- **时间**：strlen O(n)；strcmp O(min(m,n))；strstr 朴素版 **O(m·n)** 最坏（如 "aaaa…b" 找 "aab"），平均远优；KMP 可到 O(m+n)（口述级：失败函数记录前缀信息免回溯）。
- **空间 O(1)**
  - **口径说明**：三者辅助空间均为常数指针；朴素 strstr 的"回溯"不耗栈不耗数组。
- **口述模板**："strlen 双指针差值 O(n)；strcmp 返回首个不等字符的无符号差值；strstr 朴素 O(mn) 带回溯，KMP 用失败函数消回溯到 O(m+n)——现场写朴素版并说出 KMP 名字即可。"

---

*范式：算法刷题模板 v1.3（2026-10-19）· 过卡后回写 06 表 §五 S-12*
