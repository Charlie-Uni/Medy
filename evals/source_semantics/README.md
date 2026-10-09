# 来源约束评测契约

状态：`source-compliance-v1-provisional`。该层只补充评测语义，不改写冻结主集，也不自动改变历史成功分数。

## 1. 为什么单独建模

问题里的文件编号可能有四种作用：

1. **被询问的文件或产品**：答案必须引用该文件的适用版本；同成分他牌仿单、转载或同句不能自动替代。
2. **经确认的等价载体**：问题指向法规字段或条款，已经复核的有效转载、合订本或引用载体可以作为替代来源。
3. **宿主文件中的引用**：问题问 A 文件怎样讨论、引用或采用 B；必须引用 A，不能因为出现 B 的编号就要求直接检索 B。
4. **嵌入原文或文件关系**：合订文件内的旧版正文、一个文件对另一个文件关系的陈述，可由实际承载该陈述的文件支持。

仅用正则判断“问题出现 ICH/GVP 编号”会混淆上述角色。记录 115 的旧候选规则会把正常成功题改成弃答，因此不能作为运行规则。

## 2. 当前范围

[main-v5-provisional.json](main-v5-provisional.json)绑定主集版本、dataset hash、每条 query hash 和完整来源身份，当前包含 34 条已裁决或已诊断样本：

- 14 条明确点名产品、文件或版本；
- 2 条经确认的等价载体；
- 18 条宿主引用、嵌入旧文或文件关系反例，用来防止把“提及”误判为“指定来源”。

未列入的主集题不进入来源符合率分母。当前契约仍是 provisional，因为没有第二独立人工；它不能单独成为正式验收门禁。

## 3. 两种组语义

- `required_gold_groups`：事实证据组，组间全部必需，组内任一证据块即可。
- `required_source_groups`：来源身份组，组间全部必需，组内任一经复核的等价来源即可。

两者分别计分。命中正确文档不能证明答案完整；命中事实相同的错误文档也不能满足明确的来源要求。

## 4. 离线检查

新的真实问答运行保存 answer-review snapshot 后，可零费用生成来源符合率：

```bash
venv/bin/python evals/harness/tools/source_check.py \
  --run RUN_DIR \
  --dataset evals/main_set/main-v5-provisional \
  --contracts evals/source_semantics/main-v5-provisional.json \
  --out RUN_DIR/source_compliance.json
```

缺运行行或缺快照的条目保持 `pending`，总 rate 为 `null`；工具不会把缺材料当通过。`make eval-check` 会验证契约文件哈希以及契约与冻结 query、corpus、gold 来源的一致性。
