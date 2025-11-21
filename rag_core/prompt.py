RERANK_PROMPT = (
    "你是一个文本判定器。给定用户问题与候选文本，请判断该文本是否能**直接回答**用户问题。\n"
    "如果问题询问特定信息（如：释义、近义词、例句、短语），"
    "只匹配包含该信息的文本；若不包含，返回 NotRelevant。\n"
)

INTENT_EXAMPLES = {
    "synonym": [
        "sensible的同义词有哪些",
        "beautiful的近义词",
        "与happy意思相近的词汇",
        "smart的同义词是什么",
        "列出important的同义词",
        "happy的相似词有哪些",
        "给出sad的替代词",
        "有什么词可以替换good",
        "intelligent的同类词",
        "big的同义词和近义词"
    ],
    "definition": [
        "sensible的定义是什么",
        "explain的意思",
        "什么是metaphor",
        "clarify这个单词什么意思",
        "给一下comprehensive的定义",
        "sensible的释义有哪些",
        "ambiguity是什么意思",
        "什么叫paradox",
        "ephemeral的含义",
        "resilient什么意思",
        "翻译一下serendipity",
        "这个词啥意思"
    ],
    "example": [
        "sensible的用法例句",
        "用demonstrate造个句子",
        "illustrate的例句有哪些",
        "展示一下utilize的用法",
        "provide an example of analyze",
        "给perseverance举个例句",
        "ambiguity怎么造句",
        "用这个词造个句",
        "举几个mitigate的例子",
        "usage的用法举例"
    ],
    "phrase": [
        "sensible的常用搭配",
        "make的短语搭配",
        "take的常见词组",
        "break的固定搭配",
        "get的常用短语",
        "look的动词搭配",
        "give的介词搭配",
        "run的词组有哪些",
        "common的常用短语",
        "business的习惯搭配",
        "英语词伙查询"
    ],
    "pronunciation": [
        "sensible怎么读",
        "pronunciation的发音",
        "schedule的美式发音",
        "读一下entrepreneur",
        "这个单词怎么念",
        "colonel咋读",
        "音标怎么读",
        "英式发音怎么读",
        "念一下这个单词",
        "读音是什么"
    ],
    "etymology": [
        "sensible的词源",
        "etymology的词根",
        "photograph的词源学",
        "这个单词的来源",
        "词根词缀分析",
        "philosophy的起源",
        "biology的词根是什么",
        "这个词从哪里来的",
        "etymology的由来",
        "单词历史起源"
    ],
    "comparison": [
        "sensible和sensitive的区别",
        "affect和effect的不同",
        "compare和contrast的区别",
        "economic和economical的差异",
        "这两个词有什么不同",
        "big和large的区别在哪",
        "say和tell有何不同",
        "house和home差别",
        "compare对比compare to",
        "分辨这两个词"
    ],
    # --- 新增意图类别的例句 ---
    "antonym": [
        "happy的反义词",
        "big的相反词是什么",
        "beautiful的对立词",
        "fast的反义词有哪些",
        "列出rich的反义词",
        "positive的相反词",
        "antonym of good",
        "light的反义词"
    ],
    "usage_note": [
        "however的用法",
        "suggest怎么用",
        "这个单词使用注意",
        "recommend的语法",
        "在什么场合用这个词",
        "usage的用法说明",
        "使用场景有哪些",
        "语法规则是什么",
        "适用场合"
    ],
    "word_family": [
        "beautiful的词性",
        "happy的派生词",
        "create的相关词",
        "名词形式是什么",
        "动词变形有哪些",
        "形容词形式",
        "副词怎么变",
        "词性变化",
        "related words"
    ],
    "formality": [
        "kids是正式用语吗",
        "wanna的正式程度",
        "这个词正式吗",
        "口语表达有哪些",
        "书面语怎么说",
        "slang的意思",
        "正式场合用什么词",
        "informal的表达",
        "正式与非正式区别"
    ]
}

INTENT_KEYWORDS = {
    "synonym": [
        "同义词", "近义词", "相似词", "同类词", "意思相近的词", "替代词", "替换词",
        "synonym", "similar", "alternative word", "thesaurus"
    ],
    "definition": [
        "定义", "意思", "含义", "释义", "解释", "什么意思", "是什么意思", "什么叫", "啥意思",
        "翻译", "define", "definition", "meaning", "what does it mean",
        "是什么意思", "什么意思"  # 常见口语重复强化
    ],
    "example": [
        "例句", "例子", "造句", "用法", "举例", "造个句", "怎么用", "用例",
        "example", "usage", "sentence", "how to use", "in a sentence"
    ],
    "phrase": [
        "短语", "搭配", "词组", "固定搭配", "常用搭配", "习惯搭配", "词伙", "动词搭配", "介词搭配",
        "phrase", "collocation", "expression", "idiom", "word partnership"
    ],
    "pronunciation": [
        "发音", "读音", "怎么读", "念法", "咋读", "读法", "音标", "美式发音", "英式发音",
        "pronunciation", "read", "how to pronounce", "sound", "phonetic"
    ],
    "etymology": [
        "词源", "词根", "词缀", "来源", "起源", "由来", "出自", "词源学",
        "etymology", "origin", "root", "word origin", "where does it come from"
    ],
    "comparison": [
        "区别", "不同", "差异", "差别", "比较", "比对", "对比", "分辨", "区分",
        "difference", "compare", "comparison", "distinguish", "vs", " versus",
        "有什么区别", "有何不同"  # 完整短语补全
    ],
    # --- 以下是新增的意图类别，建议您考虑加入 ---
    "antonym": [
        "反义词", "相反词", "对立词", "antonym", "opposite", "reverse"
    ],
    "usage_note": [
        "用法", "使用", "怎么用", "用法注意", "使用场景", "适用场合", "语法",
        "usage", "how to use", "grammar", "context", "in what situation"
    ],
    "word_family": [
        "词性", "派生词", "相关词", "形容词", "副词", "名词", "动词", "变形",
        "part of speech", "derivative", "related words", "adjective", "adverb", "noun", "verb"
    ],
    "formality": [
        "正式", "非正式", "口语", "书面语", "俚语", "委婉语", "正式程度",
        "formal", "informal", "slang", "colloquial", "register"
    ]
}

## 词语释义
definition_prompt = ("请为单词 [target_word] 提供简洁、准确、面向学习者的释义。\n"
                     "要求：\n"
                     "1. 按词性分段输出（如 adj., n., v.）。\n"
                     "2. 每个词性下给出：\n"
                     "- 中文释义（尽量简短、面向学习者）\n"
                     "- 简短英文解释（如适用）\n"
                     "- 是否常用（常用 / 较少使用 / 正式 / 非正式）\n"
                     "3. 不要输出无关内容。\n")

synonym_prompt = ("## 同义词\n"
                  "请列出单词 [target_word] 的同义词，根据语义相近程度分为三组：\n"
                  "- 强同义（语义非常接近）\n"
                  "- 中等相似（部分场景可互换）\n"
                  "- 弱相关（只在特定语境下相似）\n"
                  "每组不超过 5 个词。\n"
                  "格式如下：\n"
                  "### 强同义\n"
                  "- word1（简短中文解释）\n"
                  "- word2（简短中文解释）\n"
                  "### 中等相似\n"
                  "...\n"
                  "### 弱相关\n"
                  "...\n"
                  "如无同义词，请明确说明。\n")

antonym_prompt = ("## 反义词\n"
                  "请为 [target_word] 列出反义词：\n"
                  "- 每个反义词附简短中文解释（不超过 8 字）\n"
                  "- 按场景分类（如语气类、情绪类、品质类）\n"
                  "格式示例：\n"
                  "### 反义词\n"
                  "- reckless：不计后果\n"
                  "- irrational：不理性\n"
                  "如无典型反义词，说明原因。\n")

example_prompt = ("## 例句 \n"
                  "请为单词 [target_word] 提供 3~5 个例句，要求：\n"
                  "1. 覆盖不同词性或语境（如果该词有多个词性）\n"
                  "2. 例句必须自然、符合母语者表达\n"
                  "3. 每个例句附简洁中文翻译（不超过 12 字）\n"
                  "4. 避免复杂句，不要过长\n"
                  "格式：\n"
                  "- Sentence 1  \n"
                  "  中文：xxx\n"
                  "- Sentence 2  \n"
                  "  中文：xxx\n")

usage_prompt = ("## 常见搭配与用法\n"
                "请给出单词 [target_word] 的常见搭配（collocations）和使用说明。\n"
                "需要包含：\n"
                "1. 常见搭配（每项提供英文 + 中文解释）\n"
                "2. 典型语法行为（如是否与介词搭配；是否可作表语/定语）\n"
                "3. 常见误用（如学习者常犯的错误）\n"
                "格式示例：\n"
                "### 常见搭配\n"
                "- sensible decision：明智决定\n"
                "- perfectly sensible：非常明智\n"
                "### 语法说明\n"
                "- 常作表语，如: xxx\n"
                "- 可修饰名词，如: xxx\n")

etymology_prompt = ("## 词源信息（Etymology）\n"
                    "请简要说明单词 [target_word] 的词源（如拉丁语/法语/古英语等）。\n"
                    "要求：\n"
                    "1. 保持简短，最多 3 行。\n"
                    "2. 如果词源不确定，请说明“该词源存在多种解释”。\n"
                    "3. 不要给出不可靠的猜测。\n")

pronunciation_prompt = ("## 发音\n"
                        "请提供：\n"
                        "- IPA 音标（英式 / 美式）\n"
                        "- 重音位置说明"
                        "- 简短发音提示（例如与哪些单词押韵）\n"
                        "格式：\n"
                        "### 英式 IPA\n"
                        "/xxxx/\n"
                        "### 美式 IPA\n"
                        "/xxxx/\n"
                        "### 发音提示\n"
                        "- 与 “xxx” 押韵\n")

general_prompt = ("你是一个专业英语学习助手，请为单词 [target_word] 提供完整且结构化的信息：\n"
                  "1. 释义（按词性分段）\n"
                  "2. 同义词（按强度分组）\n"
                  "3. 反义词（如有）\n"
                  "4. 常见搭配 / 用法说明\n"
                  "5. 例句（3~5 个，简短中文翻译）\n"
                  "6. 发音（英式/美式）\n"
                  "7. 词源（如有）\n"
                  "请严格分段输出，结构清晰，标题使用“##”。\n")
