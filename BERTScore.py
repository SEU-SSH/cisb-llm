from bert_score import score
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# bert_tokenizer = AutoTokenizer.from_pretrained('roberta-large')
# bert_model = AutoModelForSequenceClassification.from_pretrained('roberta-large')

# 定义参考句子和生成句子
refs = ["Reordering order-sensitive security code"]
cands = ["GCC assumes no aliasing, optimizing out `uint16_t*` write due to UB. "]

# 使用bert_score计算分数
P, R, F1 = score(cands, refs, lang='en', model_type="roberta-large", verbose=True, rescale_with_baseline=False)

# 打印结果
print("Precision:", P)
print("Recall:", R)
print("F1 score:", F1)
