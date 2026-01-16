# 空管语言规范化（LLM Few-shot）流程说明

本文档说明空管语言规范化中 LLM few-shot 的具体流程与数据流转。

## 1) 预处理（Stage 1：规则归一化）

- 位置：`agent/nodes/input_parser.py`
- 目的：将容易误解析的读法先标准化为稳定格式
- 主要动作：
  - 数字读法转字符：洞→0、幺→1、拐→7 等
  - 字母读法转字母：阿尔法→A、布拉沃→B 等
  - 跑道方向统一：`跑道27左` → `跑道27L`（避免“左发”误匹配）
  - 位置顺序规范化：`12滑行道` → `滑行道12`
- 数据来源：`Radiotelephony_ATC.json`（digits / letters / normalization_rules）
- 输出：`normalized_message`

## 2) 关键词抽取（Stage 2 前置）

- 位置：`tools/information/radiotelephony_normalizer.py`
- 目的：为示例检索做语义特征准备
- 动作：从输入文本抽取关键词类别（runway / taxiway / stand / flight / oil_spill / bird_strike 等）

## 3) Few-shot 示例检索（非向量 RAG）

- 位置：`RadiotelephonyNormalizer.retrieve_examples()`
- 目的：选出最相似的少量示例（top-3）
- 逻辑：
  - 扫描 `Radiotelephony_ATC.json` 示例对
  - 按“关键词命中数”打分（非 embedding）
  - 取分数最高的 top-3

## 4) 构造提示词（Few-shot Prompt）

- 位置：`RadiotelephonyNormalizer._build_prompt()`
- 目的：让 LLM 学习“读法 → 标准格式”映射
- 组成：
  - 规范化规则（来自 `Radiotelephony_ATC.json`）
  - top-3 示例输入/输出对
  - 当前待处理输入文本

## 5) LLM 规范化推理

- 位置：`RadiotelephonyNormalizer.normalize_with_llm()`
- 动作：
  - 使用上一步构建的 prompt 调用 LLM
  - 返回：
    - `normalized_text`
    - `entities`（flight_no / position / event_type 等）
    - `confidence`

## 6) 结果解析与合并

- 位置：`agent/nodes/input_parser.py`
- 逻辑：
  - 将 LLM 输出的 `entities` 与后续实体抽取结果合并
  - **LLM 规范化阶段输出优先级最高**，覆盖规则/正则抽取结果
- 输出：完整一致的 `incident` 结构进入后续 FSM 与工具链

## 关键路径总结

规则先做“粗标准化”，LLM 通过 few-shot 规则 + 示例做“细语义规范化”，再将 LLM 实体结果作为最高优先级合并进状态。
