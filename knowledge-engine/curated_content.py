"""Curated starter collection: AI, consciousness, and scientific discovery."""
import json

from database import connection, new_id, now_iso


CONCEPTS = [
    ("人工智能", "研究如何让机器执行通常需要人类智能的任务；它既是一组工程方法，也是一场关于能力、理解与责任的持续实验。", "人工智能", ["AI", "智能系统", "认知"], "Atlas 策展"),
    ("大语言模型", "在大规模文本上训练、通过预测语言序列获得通用语言能力的神经网络模型。", "人工智能", ["LLM", "语言", "生成模型"], "Atlas 策展"),
    ("Transformer", "以注意力机制为核心的神经网络架构，允许模型并行处理序列并建立远距离依赖。", "人工智能", ["注意力机制", "神经网络", "架构"], "Atlas 策展"),
    ("基础模型", "在广泛数据上训练、可适配大量下游任务的大规模模型；其通用性同时放大了能力与系统性风险。", "人工智能", ["通用模型", "迁移学习", "规模化"], "Atlas 策展"),
    ("涌现能力", "模型规模跨过某些区间后，在特定测量中突然显现的能力；它可能反映真实相变，也可能受指标设计影响。", "人工智能", ["规模效应", "评测", "争议"], "Atlas 策展"),
    ("人类反馈强化学习", "利用人类偏好训练奖励模型，再通过强化学习调整生成模型行为的方法，通常简称 RLHF。", "人工智能", ["RLHF", "偏好学习", "对齐"], "Atlas 策展"),
    ("AI对齐", "研究如何使人工智能系统的行为与人类意图、价值和制度约束保持一致。", "人工智能", ["安全", "价值", "控制"], "Atlas 策展"),
    ("模型幻觉", "生成模型给出流畅但缺乏事实依据、错误引用或无效推理的现象。", "人工智能", ["可靠性", "事实性", "风险"], "Atlas 策展"),
    ("可解释人工智能", "让模型决策依据能够被人理解、审计或干预的一组方法与研究目标。", "人工智能", ["XAI", "透明度", "审计"], "Atlas 策展"),
    ("图灵测试", "以机器在文字对话中能否被人与人类区分作为智能行为判断的思想实验。", "认知科学", ["模仿游戏", "智能", "哲学"], "Turing, 1950"),
    ("主观体验", "一个主体从第一人称角度感受到世界的方式，也是意识研究中最难被第三人称测量的对象。", "认知科学", ["感质", "第一人称", "心灵哲学"], "Atlas 策展"),
    ("意识难题", "解释物理信息处理为何以及如何伴随主观体验的问题；它与解释注意、报告和行为功能不同。", "认知科学", ["困难问题", "心身问题", "解释鸿沟"], "Chalmers, 1995"),
    ("全局工作空间理论", "认为信息被广播到多个专门处理系统时，会形成可报告、可灵活使用的意识访问。", "认知科学", ["意识访问", "广播", "认知架构"], "Dehaene & Naccache, 2001"),
    ("神经相关物", "与某种意识体验共同出现、并可能构成其最小充分基础的神经活动模式。", "认知科学", ["NCC", "神经科学", "测量"], "Atlas 策展"),
    ("AI辅助科学发现", "使用机器学习参与提出假设、预测结构、设计实验或发现算法的研究范式。", "科学发现", ["AI for Science", "研究方法", "自动化"], "Atlas 策展"),
    ("蛋白质结构预测", "依据氨基酸序列预测蛋白质三维结构的问题，是连接序列、结构与生物功能的关键环节。", "科学发现", ["结构生物学", "蛋白质", "预测"], "Atlas 策展"),
    ("AlphaFold", "将进化信息、几何约束与深度学习结合，用于高精度预测蛋白质结构的系统。", "科学发现", ["蛋白质", "深度学习", "生物学"], "Jumper et al., 2021"),
    ("自动算法发现", "把算法设计表述为可搜索、可验证的空间，让学习系统发现满足正确性与效率目标的新算法。", "科学发现", ["算法", "搜索", "强化学习"], "Atlas 策展"),
    ("AlphaTensor", "使用深度强化学习搜索矩阵乘法张量分解，从而发现可验证的高效矩阵乘法算法。", "科学发现", ["矩阵乘法", "强化学习", "算法发现"], "Fawzi et al., 2022"),
    ("科学方法", "通过提出问题、形成假设、获取证据、尝试证伪和迭代解释来建立可靠知识的方法体系。", "科学哲学", ["假设", "证据", "复现"], "Atlas 策展"),
    ("可证伪性", "一个命题原则上能够被某种可能观察判为错误的性质，是区分可检验主张的重要标准。", "科学哲学", ["Popper", "检验", "反例"], "Atlas 策展"),
    ("假设生成", "从已有理论、数据异常或类比中提出可检验解释的过程，是发现链条的起点而非结论。", "科学发现", ["推理", "研究设计", "开放问题"], "Atlas 策展"),
]


RELATIONS = [
    ("机器学习", "人工智能", "is_a", "机器学习是人工智能的主要技术子领域。", .98),
    ("自然语言处理", "人工智能", "is_a", "自然语言处理是人工智能面向语言的分支。", .98),
    ("基础模型", "人工智能", "is_a", "基础模型是当前人工智能系统的一类通用技术底座。", .9),
    ("大语言模型", "基础模型", "is_a", "大语言模型是以语言数据为主要训练媒介的基础模型。", .95),
    ("大语言模型", "自然语言处理", "is_a", "大语言模型属于自然语言处理模型。", .95),
    ("Transformer", "大语言模型", "supports", "主流大语言模型普遍以 Transformer 为核心架构。", .95),
    ("Transformer", "深度学习", "is_a", "Transformer 是深度神经网络架构。", .96),
    ("大语言模型", "涌现能力", "related_to", "部分能力在规模扩大后的评测曲线上表现出非连续增长。", .7),
    ("大语言模型", "模型幻觉", "related_to", "自回归生成目标不保证输出具备事实依据。", .9),
    ("人类反馈强化学习", "强化学习", "depends_on", "RLHF 使用强化学习根据偏好奖励优化策略。", .95),
    ("人类反馈强化学习", "AI对齐", "supports", "RLHF 可改善模型对人类指令与偏好的遵循。", .8),
    ("可解释人工智能", "AI对齐", "supports", "可解释性为发现失配、审计行为和实施干预提供工具。", .75),
    ("模型幻觉", "AI对齐", "related_to", "事实失真是可靠性与对齐评估中的核心风险。", .85),
    ("人工智能伦理", "AI对齐", "related_to", "两者都讨论能力部署时的价值、责任与治理约束。", .85),
    ("图灵测试", "人工智能", "related_to", "图灵以可观察对话行为替代对机器是否思考的直接定义。", .9),
    ("图灵测试", "意识", "related_to", "通过行为测试并不能直接判定系统是否具有主观体验。", .65),
    ("主观体验", "意识", "part_of", "主观体验是现象意识的核心含义。", .95),
    ("意识难题", "主观体验", "depends_on", "困难问题源于对主观体验为何出现的解释要求。", .95),
    ("全局工作空间理论", "意识", "related_to", "该理论尝试解释意识访问与信息广播的功能机制。", .85),
    ("神经相关物", "意识", "related_to", "神经相关物研究寻找体验与脑活动之间的稳定对应。", .9),
    ("神经相关物", "意识难题", "related_to", "相关关系可以约束理论，但不自动消除从机制到体验的解释鸿沟。", .75),
    ("AI辅助科学发现", "机器学习", "depends_on", "当前多数 AI 科学系统以机器学习进行预测、搜索或生成。", .9),
    ("AI辅助科学发现", "科学方法", "related_to", "AI 可以增强发现链条，但仍需证据、检验与复现。", .9),
    ("AI辅助科学发现", "假设生成", "supports", "生成模型和模式发现系统可扩大候选假设空间。", .8),
    ("假设生成", "科学方法", "part_of", "形成可检验假设是科学方法的重要环节。", .95),
    ("科学方法", "可证伪性", "depends_on", "许多经验研究通过寻找可能反例来提高命题可检验性。", .8),
    ("AlphaFold", "AI辅助科学发现", "example", "AlphaFold 是 AI 改变科学工作流的代表案例。", .98),
    ("AlphaFold", "蛋白质结构预测", "supports", "AlphaFold 显著提高了多类蛋白质的结构预测精度。", .98),
    ("AlphaFold", "深度学习", "depends_on", "AlphaFold 的核心预测系统使用深度神经网络。", .98),
    ("蛋白质结构预测", "DNA", "related_to", "基因序列编码蛋白质序列，而结构影响蛋白质功能。", .7),
    ("自动算法发现", "AI辅助科学发现", "is_a", "算法发现是 AI 辅助发现的一种形式。", .9),
    ("AlphaTensor", "自动算法发现", "example", "AlphaTensor 在可验证搜索空间中发现矩阵乘法算法。", .98),
    ("AlphaTensor", "强化学习", "depends_on", "系统使用深度强化学习引导张量分解搜索。", .95),
    ("自动算法发现", "可证伪性", "related_to", "候选算法可以通过形式证明和运行测试接受明确检验。", .8),
]


SECTIONS = {
    "大语言模型": [
        ("importance", "为什么重要", "它把翻译、问答、写作、编程等任务统一到语言接口中，降低了调用复杂能力的门槛，也让一个模型的缺陷能够同时影响许多场景。"),
        ("mechanism", "核心机制", "模型从上下文预测后续词元。训练积累的是语言与世界模式的统计表示；生成时得到的是条件概率下的序列，而不是经过数据库核验的事实。"),
        ("debate", "主要争议", "流畅表现是否意味着理解仍无共识。行为能力、内部表征和主观体验是三个不同问题，不能由单一聊天测试相互替代。"),
        ("question", "开放问题", "怎样在不牺牲通用性的前提下，让模型知道何时不确定、给出可核查来源，并允许外部系统纠正其内部表征？"),
    ],
    "涌现能力": [
        ("importance", "为什么重要", "如果能力难以从小规模实验预测，训练更大模型就同时具有机会与风险，评估必须提前覆盖潜在的新行为。"),
        ("mechanism", "可能机制", "能力曲线可能来自模型内部表征的规模效应，也可能因为准确率等离散指标把平滑改进显示成突然跃迁。"),
        ("debate", "主要争议", "观察到评测突变不等于证明系统发生了本体上的相变；任务难度、提示方式和评分尺度都会改变曲线形状。"),
        ("question", "开放问题", "哪些能力可以通过缩放规律提前预测，哪些能力需要新的因果测量而不只是排行榜分数？"),
    ],
    "AI对齐": [
        ("importance", "为什么重要", "高能力系统即使准确执行了错误目标，也可能产生比普通软件更广的外部影响；对齐关注的正是目标、行为与社会约束之间的偏差。"),
        ("mechanism", "常用路径", "监督微调、偏好学习、RLHF、规则约束、红队测试和部署监控分别处理不同阶段的问题，没有一种方法能独立保证一致性。"),
        ("debate", "主要争议", "人类偏好并不天然一致或正确；把多数标注者的即时偏好当作价值本身，可能掩盖权利、文化与长期后果。"),
        ("question", "开放问题", "如何区分模型真正稳定遵循约束，与模型只在已知评测中表现得像是在遵循约束？"),
    ],
    "模型幻觉": [
        ("importance", "为什么重要", "幻觉把语言上的可信感与事实可靠性分离。在医疗、法律、科研等场景，错误引用和虚构依据比明显报错更危险。"),
        ("mechanism", "形成原因", "下一词预测奖励连贯延续，不直接奖励事实可验证性；训练数据冲突、知识过时、检索缺失和解码策略都会放大问题。"),
        ("boundary", "需要区分", "知识错误、推理错误、来源伪造和对歧义问题的武断回答不是同一种失败，应使用不同测试与修复方法。"),
        ("question", "开放问题", "系统能否把校准的不确定性传递给用户，而不是在信息不足时仍以相同语气生成答案？"),
    ],
    "意识": [
        ("importance", "为什么重要", "意识连接第一人称体验、神经机制、道德地位和人工智能边界。不同研究传统常用同一个词讨论不同对象。"),
        ("mechanism", "研究路径", "实验科学通常测量报告、注意、唤醒水平和神经活动；哲学则追问这些功能事实是否足以解释体验本身。"),
        ("debate", "核心分歧", "功能主义强调可实现的认知角色，生物自然主义强调神经基础，非还原观点则认为体验不能被纯功能描述穷尽。"),
        ("question", "开放问题", "在无法直接进入另一个主体经验的情况下，什么证据足以赋予动物或人工系统意识地位？"),
    ],
    "意识难题": [
        ("importance", "问题所在", "解释辨别刺激、整合信息或生成报告仍属于功能解释；困难问题进一步追问，为何这些过程会伴随‘有所感受’。"),
        ("boundary", "概念边界", "它不是声称意识永远无法研究，而是要求不要把行为功能的解释直接等同于主观体验的解释。"),
        ("debate", "主要争议", "有些研究者认为问题揭示了还原解释的缺口，另一些研究者认为它来自错误直觉或对意识概念的误用。"),
        ("question", "开放问题", "一个意识理论需要预测哪些可区分的实验结果，才能不只是重新命名我们想解释的现象？"),
    ],
    "全局工作空间理论": [
        ("importance", "为什么重要", "它把意识访问转化为可研究的认知架构问题：哪些信息被全局共享，何时进入报告、记忆与灵活控制。"),
        ("mechanism", "核心机制", "多个专门模块并行处理信息；获胜内容进入容量有限的全局工作空间，并向其他系统广播。"),
        ("boundary", "解释边界", "理论擅长解释可访问性与报告机制，但其是否解释了体验本身，取决于对意识问题的立场。"),
    ],
    "AI辅助科学发现": [
        ("importance", "为什么重要", "AI 可以在巨大候选空间中发现人类难以穷举的结构、材料和算法，但候选生成并不自动等于科学结论。"),
        ("mechanism", "发现链条", "高质量系统通常连接表征学习、候选生成、模拟或实验评估、失败反馈和再次搜索，而不是只生成一段看似合理的解释。"),
        ("boundary", "成功标准", "预测准确、提出新候选、给出可验证机制和形成可复现发现是不同层级，评价时必须明确系统完成了哪一步。"),
        ("question", "开放问题", "当模型提出人类尚不能解释但实验有效的规律时，谁拥有理解、验证和承担失败后果的责任？"),
    ],
    "AlphaFold": [
        ("importance", "为什么重要", "蛋白质结构长期依赖昂贵实验。AlphaFold 在 CASP14 盲测中的表现使计算预测可以更早进入许多结构生物学工作流。"),
        ("mechanism", "核心机制", "系统联合处理多序列比对与残基对表示，通过注意力和迭代结构模块把进化约束转化为三维坐标，并输出局部可信度。"),
        ("boundary", "能力边界", "高置信静态结构不等于完整描述蛋白质动力学、配体作用、复合体状态或细胞环境；低置信区域尤其需要谨慎。"),
        ("question", "开放问题", "如何把结构预测与实验设计、分子动力学和功能验证连接成可追踪的闭环？"),
    ],
    "AlphaTensor": [
        ("importance", "为什么重要", "它展示了机器学习不仅能拟合数据，还能在形式化空间中提出可证明正确、并改善既有结果的算法。"),
        ("mechanism", "核心机制", "矩阵乘法被表示为张量分解游戏，智能体学习选择秩一张量，搜索用更少标量乘法完成目标的分解。"),
        ("boundary", "能力边界", "成功依赖明确目标、可自动验证的正确性和可搜索表示；开放式理论发现通常不具备这些条件。"),
        ("question", "开放问题", "怎样把这类搜索扩展到评价昂贵、正确性不能立即判定、且目标本身会变化的科学问题？"),
    ],
    "科学方法": [
        ("importance", "为什么重要", "科学可靠性不来自某个权威答案，而来自命题能够被公开检验、被失败修正并被独立复现的过程。"),
        ("mechanism", "工作循环", "观察产生问题，理论压缩已有事实，假设导出预测，实验尝试区分竞争解释，结果再修改理论。真实研究往往在这些环节之间往返。"),
        ("debate", "主要争议", "不存在适用于所有学科的单一步骤配方；探索性分析、模型构建、因果推断和工程验证使用不同证据规范。"),
        ("question", "开放问题", "当研究流程越来越依赖不透明模型时，怎样保存足够的决策记录，使失败、偏差和偶然发现仍可追溯？"),
    ],
    "可证伪性": [
        ("importance", "为什么重要", "一个能够解释任何结果的主张实际上排除了不了任何可能世界。明确失败条件能让证据真正改变我们的信念。"),
        ("boundary", "适用边界", "可证伪性是重要规范但不是完整科学判据；统计命题、历史科学和复杂模型往往通过概率与比较检验，而非一次决定性反例。"),
        ("question", "实践问题", "在验证假设前，应记录什么观察会降低支持度、什么替代解释也能产生相同数据？"),
    ],
}


EVIDENCE = [
    ("图灵测试", "图灵在 1950 年把“机器能否思考”改写为可观察的模仿游戏，同时明确讨论了该测试可能受到的反对。", "Computing Machinery and Intelligence", "https://doi.org/10.1093/mind/LIX.236.433"),
    ("人类反馈强化学习", "InstructGPT 研究报告中，较小的 1.3B 模型在其提示分布的人类偏好评估中优于原始 175B GPT-3，说明训练目标会显著改变可用行为。", "Training language models to follow instructions with human feedback", "https://arxiv.org/abs/2203.02155"),
    ("涌现能力", "TMLR 论文汇总了多种随规模增加而在评测中突然出现的能力，同时将“不可由较小模型表现预测”作为操作性定义。", "Emergent Abilities of Large Language Models", "https://openreview.net/forum?id=yzkSU5zdwD"),
    ("AlphaFold", "AlphaFold 在 CASP14 中对多数目标达到接近实验结构的精度，并显著超过当时其他计算方法。", "Highly accurate protein structure prediction with AlphaFold", "https://doi.org/10.1038/s41586-021-03819-2"),
    ("蛋白质结构预测", "AlphaFold 人类蛋白质组研究覆盖 98.5% 的人类蛋白质，并报告 58% 残基达到可信预测水平；预测覆盖不等同于全部区域都高可信。", "Highly accurate protein structure prediction for the human proteome", "https://doi.org/10.1038/s41586-021-03828-1"),
    ("AlphaTensor", "AlphaTensor 在多个矩阵规模上发现改进算法，并在有限域 4×4 情况下改进了长期未被突破的两层 Strassen 方案。", "Discovering faster matrix multiplication algorithms with reinforcement learning", "https://doi.org/10.1038/s41586-022-05172-4"),
    ("意识难题", "Chalmers 区分了对认知功能的解释与对主观体验为何存在的解释，并把后者称为意识的困难问题。", "Facing Up to the Problem of Consciousness", "https://academic.oup.com/book/6996/chapter/151305365"),
    ("主观体验", "Nagel 以蝙蝠为例强调：关于生物体的客观知识并不会自动给出成为该生物体时的第一人称体验。", "What Is It Like to Be a Bat?", "https://doi.org/10.1093/oso/9780197752791.001.0001"),
    ("全局工作空间理论", "全局工作空间路径把意识访问与信息在多个认知系统之间的全局可用性联系起来，为报告和灵活控制提供可测试框架。", "Towards a cognitive neuroscience of consciousness", "https://doi.org/10.1016/S0010-0277(00)00123-2"),
    ("模型幻觉", "TruthfulQA 通过专门设计的问题显示，扩大模型并不保证减少模仿人类常见错误答案的倾向。", "TruthfulQA: Measuring How Models Mimic Human Falsehoods", "https://arxiv.org/abs/2109.07958"),
]


PAPERS = [
    ("Computing Machinery and Intelligence", ["Alan M. Turing"], "Mind", 1950, "10.1093/mind/lix.236.433", "", "图灵以模仿游戏构造机器智能的行为判据，并系统回应常见反对。", "https://doi.org/10.1093/mind/LIX.236.433", ["图灵测试", "人工智能"]),
    ("On the Opportunities and Risks of Foundation Models", ["Rishi Bommasani", "Drew A. Hudson", "Ehsan Adeli"], "arXiv", 2021, "", "2108.07258", "系统讨论基础模型的能力、适配方式、社会影响与系统性风险。", "https://arxiv.org/abs/2108.07258", ["基础模型", "人工智能伦理"]),
    ("Language Models are Few-Shot Learners", ["Tom B. Brown", "Benjamin Mann", "Nick Ryder"], "NeurIPS", 2020, "", "2005.14165", "展示扩大自回归语言模型后，通过上下文示例完成多任务的能力。", "https://arxiv.org/abs/2005.14165", ["大语言模型", "涌现能力"]),
    ("Training language models to follow instructions with human feedback", ["Long Ouyang", "Jeff Wu", "Xu Jiang", "John Schulman"], "NeurIPS", 2022, "", "2203.02155", "使用示范、偏好比较和强化学习提高模型遵循人类意图的表现。", "https://arxiv.org/abs/2203.02155", ["人类反馈强化学习", "AI对齐"]),
    ("Emergent Abilities of Large Language Models", ["Jason Wei", "Yi Tay", "Rishi Bommasani"], "TMLR", 2022, "", "2206.07682", "整理随模型规模出现非线性表现的任务，并提出涌现能力的操作性定义。", "https://openreview.net/forum?id=yzkSU5zdwD", ["涌现能力", "大语言模型"]),
    ("TruthfulQA: Measuring How Models Mimic Human Falsehoods", ["Stephanie Lin", "Jacob Hilton", "Owain Evans"], "ACL", 2022, "", "2109.07958", "用易诱发人类错误信念的问题评估语言模型事实性。", "https://arxiv.org/abs/2109.07958", ["模型幻觉", "大语言模型"]),
    ("Towards a cognitive neuroscience of consciousness: basic evidence and a workspace framework", ["Stanislas Dehaene", "Lionel Naccache"], "Cognition", 2001, "10.1016/s0010-0277(00)00123-2", "", "提出以全局可用性解释意识访问的认知神经框架。", "https://doi.org/10.1016/S0010-0277(00)00123-2", ["全局工作空间理论", "意识"]),
    ("Facing Up to the Problem of Consciousness", ["David J. Chalmers"], "Journal of Consciousness Studies", 1995, "", "", "区分意识的功能问题与解释主观体验的困难问题。", "https://academic.oup.com/book/6996/chapter/151305365", ["意识难题", "主观体验"]),
    ("Highly accurate protein structure prediction with AlphaFold", ["John Jumper", "Richard Evans", "Alexander Pritzel", "Demis Hassabis"], "Nature", 2021, "10.1038/s41586-021-03819-2", "", "报告 AlphaFold2 的架构与 CASP14 盲测结果。", "https://doi.org/10.1038/s41586-021-03819-2", ["AlphaFold", "蛋白质结构预测", "AI辅助科学发现"]),
    ("Discovering faster matrix multiplication algorithms with reinforcement learning", ["Alhussein Fawzi", "Matej Balog", "Aja Huang", "Pushmeet Kohli"], "Nature", 2022, "10.1038/s41586-022-05172-4", "", "用强化学习搜索可证明正确的矩阵乘法算法。", "https://doi.org/10.1038/s41586-022-05172-4", ["AlphaTensor", "自动算法发现", "AI辅助科学发现"]),
]


ISSUES = [
    {
        "title": "AI 能否独立完成科学发现？",
        "question": "当 AI 能提出候选、预测结构并发现算法时，它是否已经能够脱离人类独立完成科学发现？",
        "summary": "这个问题容易把搜索、预测、实验、解释和责任混成一个词。专题把“独立发现”拆成可验证环节，并比较 AlphaFold 与 AlphaTensor 提供的不同证据。",
        "current_assessment": "当前证据支持 AI 在目标明确、表示可计算、结果可自动验证的环节中高度自主地搜索和预测；但不足以支持 AI 已能独立完成从问题定义、实验设计到理论解释和责任承担的完整科学过程。",
        "status": "open",
        "concepts": [
            ("AI辅助科学发现", "核心问题"), ("AlphaFold", "预测案例"),
            ("AlphaTensor", "算法案例"), ("科学方法", "评价框架"),
            ("假设生成", "发现环节"), ("可证伪性", "检验标准"),
        ],
        "claims": [
            {
                "statement": "AI 可以在封闭且可自动验证的任务中自主发现优于既有方案的候选。",
                "position": "supports",
                "assessment": "证据较强，但适用范围受任务形式化程度限制。AlphaTensor 的候选具有明确正确性判据，不能直接外推到开放式理论发现。",
                "confidence": .9,
                "keywords": ["AI", "独立", "自主", "科学发现", "算法发现", "AlphaTensor"],
                "evidence": [
                    ("supports", "AlphaTensor 把矩阵乘法表示为张量分解游戏，发现了在多个矩阵规模上改进既有复杂度或实际运行时间的算法。", "strong", "Discovering faster matrix multiplication algorithms with reinforcement learning", "https://doi.org/10.1038/s41586-022-05172-4"),
                    ("limits", "候选可以通过数学等价性和运行测试自动验证；这种廉价、明确的反馈在许多开放科学问题中并不存在。", "strong", "任务边界分析", ""),
                ],
            },
            {
                "statement": "AI 可以显著推进科学预测，但预测突破不等于独立完成科学发现。",
                "position": "qualifies",
                "assessment": "AlphaFold 是强有力的能力证据，同时也是概念边界的证据：它改变了结构预测，却仍依赖人类定义目标、建立数据库、设计盲测并解释生物意义。",
                "confidence": .92,
                "keywords": ["AI", "独立", "科学发现", "预测", "AlphaFold", "蛋白质"],
                "evidence": [
                    ("supports", "AlphaFold 在 CASP14 盲测中对大量目标达到接近实验结构的精度，显著超过同期计算方法。", "strong", "Highly accurate protein structure prediction with AlphaFold", "https://doi.org/10.1038/s41586-021-03819-2"),
                    ("limits", "静态结构预测不自动给出蛋白质动力学、细胞环境中的功能，也不能替代所有实验验证。", "strong", "Highly accurate protein structure prediction with AlphaFold", "https://doi.org/10.1038/s41586-021-03819-2"),
                ],
            },
            {
                "statement": "现有案例不足以证明 AI 能独立完成从问题定义到理论解释的完整科学过程。",
                "position": "challenges",
                "assessment": "目前最成功的案例集中在问题与评价标准已经被人类明确表达的环节。完整自主性还要求选择值得研究的问题、处理失败实验、比较替代理论并承担结论责任。",
                "confidence": .88,
                "keywords": ["AI", "独立", "完整", "科学过程", "问题定义", "理论解释"],
                "evidence": [
                    ("challenges", "AlphaFold 的训练资料、预测目标与 CASP 评价体系由科学共同体长期建立，系统的成功发生在这套人类设计的认识框架内。", "moderate", "Highly accurate protein structure prediction with AlphaFold", "https://doi.org/10.1038/s41586-021-03819-2"),
                    ("challenges", "AlphaTensor 的奖励函数和正确性标准在搜索前已经确定；系统发现的是目标空间中的新方案，而不是自主决定研究目标。", "strong", "Discovering faster matrix multiplication algorithms with reinforcement learning", "https://doi.org/10.1038/s41586-022-05172-4"),
                ],
            },
            {
                "statement": "判断 AI 是否独立发现，必须分别评估假设生成、候选搜索、实验检验和理论解释。",
                "position": "qualifies",
                "assessment": "这是当前专题采用的操作性框架。一个系统可以在某一环节高度自主，同时在其他环节依赖人类；用单一标签会掩盖真正的能力与责任边界。",
                "confidence": .95,
                "keywords": ["AI", "独立", "科学发现", "假设生成", "实验", "理论解释"],
                "evidence": [
                    ("context", "可检验的科学发现至少需要把候选主张连接到区分性证据；生成新颖文本或候选本身还不是确认发现。", "moderate", "科学方法与可证伪性", ""),
                    ("context", "不同环节需要不同评价：生成看覆盖与新颖性，预测看盲测，实验看可复现性，解释看能否区分竞争机制。", "moderate", "Atlas 议题框架", ""),
                ],
            },
        ],
    },
]


def install():
    """Install or repair the curated collection without overwriting user content."""
    now = now_iso()
    with connection() as conn:
        for name, description, category, tags, source in CONCEPTS:
            conn.execute(
                """INSERT OR IGNORE INTO concepts
                   (id, name, description, category, tags, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (new_id(), name, description, category, json.dumps(tags), source, now, now),
            )
        concept_ids = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM concepts")}

        for source, target, relation_type, rationale, confidence in RELATIONS:
            if source not in concept_ids or target not in concept_ids:
                continue
            conn.execute(
                """INSERT OR IGNORE INTO relations
                   (id, source_id, target_id, relation_type, evidence, confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (new_id(), concept_ids[source], concept_ids[target], relation_type, rationale, confidence, now),
            )

        for concept_name, sections in SECTIONS.items():
            concept_id = concept_ids.get(concept_name)
            if not concept_id:
                continue
            for order, (section_type, title, content) in enumerate(sections):
                conn.execute(
                    """INSERT OR IGNORE INTO concept_sections
                       (id, concept_id, section_type, title, content, sort_order, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (new_id(), concept_id, section_type, title, content, order, now),
                )

        for concept_name, content, source_title, source_url in EVIDENCE:
            concept_id = concept_ids.get(concept_name)
            if not concept_id:
                continue
            exists = conn.execute(
                "SELECT 1 FROM evidence WHERE concept_id = ? AND source_title = ?",
                (concept_id, source_title),
            ).fetchone()
            if not exists:
                conn.execute(
                    """INSERT INTO evidence
                       (id, concept_id, content, source_url, source_title, added_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (new_id(), concept_id, content, source_url, source_title, now),
                )

        for title, authors, venue, year, doi, arxiv_id, abstract, url, links in PAPERS:
            paper = conn.execute(
                "SELECT id FROM papers WHERE title = ? OR (doi != '' AND doi = ?) OR (arxiv_id != '' AND arxiv_id = ?)",
                (title, doi, arxiv_id),
            ).fetchone()
            if paper:
                paper_id = paper["id"]
            else:
                paper_id = new_id()
                conn.execute(
                    """INSERT INTO papers
                       (id, title, authors, venue, year, doi, arxiv_id, abstract, bibtex, url, added_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)""",
                    (paper_id, title, json.dumps(authors), venue, year, doi, arxiv_id, abstract, url, now),
                )
            for concept_name in links:
                concept_id = concept_ids.get(concept_name)
                if concept_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO paper_concepts (paper_id, concept_id, relevance) VALUES (?, ?, 'primary')",
                        (paper_id, concept_id),
                    )

        paper_ids = {row["title"]: row["id"] for row in conn.execute("SELECT id, title FROM papers")}
        for issue_data in ISSUES:
            existing_issue = conn.execute("SELECT id FROM issues WHERE title = ?", (issue_data["title"],)).fetchone()
            issue_id = existing_issue["id"] if existing_issue else new_id()
            if not existing_issue:
                conn.execute(
                    """INSERT INTO issues
                       (id, title, question, summary, current_assessment, status, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (issue_id, issue_data["title"], issue_data["question"], issue_data["summary"],
                     issue_data["current_assessment"], issue_data["status"], now),
                )
            for order, (concept_name, role) in enumerate(issue_data["concepts"]):
                concept_id = concept_ids.get(concept_name)
                if concept_id:
                    conn.execute(
                        """INSERT OR IGNORE INTO issue_concepts
                           (issue_id, concept_id, role, sort_order) VALUES (?, ?, ?, ?)""",
                        (issue_id, concept_id, role, order),
                    )
            for claim_order, claim_data in enumerate(issue_data["claims"]):
                existing_claim = conn.execute(
                    "SELECT id FROM claims WHERE issue_id = ? AND statement = ?",
                    (issue_id, claim_data["statement"]),
                ).fetchone()
                claim_id = existing_claim["id"] if existing_claim else new_id()
                if not existing_claim:
                    conn.execute(
                        """INSERT INTO claims
                           (id, issue_id, statement, position, assessment, confidence, keywords, sort_order, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (claim_id, issue_id, claim_data["statement"], claim_data["position"],
                         claim_data["assessment"], claim_data["confidence"],
                         json.dumps(claim_data["keywords"]), claim_order, now),
                    )
                for evidence_order, (stance, summary, strength, source_title, source_url) in enumerate(claim_data["evidence"]):
                    conn.execute(
                        """INSERT OR IGNORE INTO claim_evidence
                           (id, claim_id, stance, summary, strength, source_title, source_url,
                            paper_id, sort_order, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (new_id(), claim_id, stance, summary, strength, source_title, source_url,
                         paper_ids.get(source_title), evidence_order, now),
                    )

        return {
            "concepts": len(CONCEPTS),
            "relations": len(RELATIONS),
            "sections": sum(len(items) for items in SECTIONS.values()),
            "evidence": len(EVIDENCE),
            "papers": len(PAPERS),
            "issues": len(ISSUES),
            "claims": sum(len(item["claims"]) for item in ISSUES),
        }
