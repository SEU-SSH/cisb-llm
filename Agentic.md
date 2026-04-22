# Agentic CISB++

主要思想：

让 LLM 自己学会从原始数据中提取信息，用人的思维改造 LLM，加入工具调用，给他装上手脚。

## Agentic Digestor

这样一部分可以将 Agent 和 静态分析结合起来。

我们需要将兼顾上下文窗口，又要保证足够聚焦。而 API 要么给出全文，要么只有 diff。

可以对超过窗口一定阈值的代码全文，根据 diff 代码所在的文件结合静态分析方法，提取函数上下文和数据流、控制流等信息。

## Agentic RAG——Liberian

把 RAG 模块做成一个独立的 Agent——Liberian，避免只在实际执行推理之前一次性检索提取。

让 LLM 每次遇到不知道或者不确定的问题就去找 Liberian 询问，检索相关知识。

## Agentic Reasoner

最小化的 RAG 证明了方法的有效性，现在我们同样将其 Agentic 改造。

首先在读取 digestor 提取的 compiler behavior、previous issue、patching purpose 之后，立刻调用 Liberian 获取相关概念。

之后在分步推理时，都应该将思考当前问题需要哪些信息，如果存在不知道或者不确定都必须询问 Liberian。

最后，将问题和得到的回答总结，发给 Judge。

## Judge

根据共同的窗口和记忆，接收 Reasoner 对问题的回答，按照原始 Reasoner 中规定的格式生成最终的判断报告。

如果确实属于 CISB，则结合漏洞的代码模式和触发条件额外生成 bug specification，spec 的形式交给我指定，另保存文件名后缀为 xxx_spec.md