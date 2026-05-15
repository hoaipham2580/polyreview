## PolyReview Report
**Files changed:** 3 · **Hunks:** 3 · **Severity:** ⚠️ HIGH

> 整体风险偏高,优先修复 SQL 注入与索引越界,其余作为后续优化项。

### 🔒 Security (1 findings)
- **HIGH** `src/auth.py:42` — 字符串拼接构造 SQL,存在注入风险
  - 建议: 改用参数化查询或 ORM。

### 🧠 Logic (1 findings)
- **HIGH** `src/api.py:30` — 未处理空列表分支,会触发 IndexError
  - 建议: 在访问前判断长度并返回明确错误。

### ⚡ Performance (1 findings)
- **MED ** `src/loader.py:101` — 循环内重复打开同一文件
  - 建议: 把 open() 提到循环外,或使用流式读取。

### 🎨 Style (1 findings)
- **LOW ** `src/api.py:18` — 函数缺少 docstring
  - 建议: 添加简短的 docstring 描述返回值。
