from rouge_score import rouge_scorer

# 参考文本（Ground Truth）
reference = "Invention of illegal instructions of certain environments"

# 预测文本（LLM 生成的推理）
prediction = "Invention of illegal instructions from non-compliant puts override"

# 计算 ROUGE-N（1-gram, 2-gram）和 ROUGE-L（最长公共子序列）
scorer = rouge_scorer.RougeScorer(['rouge1', 'rouge2', 'rougeL'], use_stemmer=True)
scores = scorer.score(reference, prediction)

print(f"ROUGE-1: {scores['rouge1'].fmeasure:.4f}")
print(f"ROUGE-2: {scores['rouge2'].fmeasure:.4f}")
print(f"ROUGE-L: {scores['rougeL'].fmeasure:.4f}")

