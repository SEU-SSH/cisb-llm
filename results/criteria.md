# Manual Evaluation

## CISB Semantics

**Compiler introduced security related bugs.** 

满足以下要求：

- 由编译器优化引入
- 优化结果可能导致漏洞
- 漏洞存在安全风险

## Reason validity

分为四档

- high：bug 定位正确，CISB 语义判断完全正确
- medium：bug 定位正确，CISB 语义判断正确 >= 2 项
- low：bug 定位正确，CISB 语义理解判断正确 < 2 项
- poor：bug 定位不正确