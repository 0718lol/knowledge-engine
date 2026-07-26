"""Seed the knowledge base with cross-domain concepts and relations."""
from database import init_db, connection
from knowledge import create_concept, create_relation
import sys


CONCEPTS = [
    # ── 人工智能 ──
    ("机器学习", "一种让计算机从数据中学习模式的技术，是人工智能的核心子领域。", "人工智能", ["AI", "数据科学", "模式识别"], "百科"),
    ("深度学习", "使用多层神经网络进行学习的机器学习方法，在图像识别和自然语言处理中表现卓越。", "人工智能", ["神经网络", "AI", "机器学习"], "百科"),
    ("自然语言处理", "使计算机能够理解、生成和处理人类语言的人工智能分支。", "人工智能", ["AI", "语言", "机器学习"], "百科"),
    ("强化学习", "智能体通过与环境交互学习最优策略的机器学习方法。", "人工智能", ["机器学习", "AI", "决策"], "百科"),

    # ── 计算机科学 ──
    ("数据库", "有组织地存储、管理和检索数据的系统，是现代信息系统的基石。", "计算机科学", ["数据", "存储", "SQL"], "百科"),
    ("TCP/IP协议", "互联网通信的基础协议族，定义了数据如何在网络中传输。", "计算机科学", ["网络", "协议", "互联网"], "百科"),
    ("操作系统", "管理计算机硬件和软件资源的系统软件，是用户与计算机的接口。", "计算机科学", ["计算机", "资源管理", "内核"], "百科"),
    ("区块链", "一种去中心化、不可篡改的分布式账本技术。", "计算机科学", ["分布式", "加密", "比特币"], "百科"),

    # ── 生物学 ──
    ("光合作用", "植物利用光能将二氧化碳和水转化为有机物和氧气的过程。", "生物学", ["植物", "能量", "氧气"], "百科"),
    ("进化论", "由达尔文提出的生物物种通过自然选择而演化的科学理论。", "生物学", ["演化", "自然选择", "物种"], "百科"),
    ("DNA", "脱氧核糖核酸，携带生物遗传信息的分子，决定生物体的性状。", "生物学", ["遗传", "基因", "分子生物学"], "百科"),
    ("细胞", "生命的基本结构和功能单位，一切生物体由细胞构成。", "生物学", ["生命", "组织", "微观"], "百科"),

    # ── 物理学 ──
    ("相对论", "爱因斯坦提出的关于时空和引力的理论，分为狭义和广义相对论。", "物理学", ["时空", "引力", "光速"], "百科"),
    ("量子力学", "描述微观粒子行为的物理学理论，揭示了概率性和不确定性原理。", "物理学", ["微观", "概率", "波粒二象性"], "百科"),
    ("热力学定律", "描述能量转化和传递的物理定律，包括能量守恒和熵增原理。", "物理学", ["能量", "熵", "温度"], "百科"),

    # ── 天文学 ──
    ("黑洞", "引力极强的天体，连光也无法逃脱，由大质量恒星坍缩形成。", "天文学", ["引力", "时空", "奇点"], "百科"),
    ("大爆炸理论", "宇宙起源于约138亿年前一个极高温高密度的奇点膨胀的理论。", "天文学", ["宇宙", "起源", "膨胀"], "百科"),

    # ── 数学 ──
    ("图论", "研究图结构的数学分支，用于建模网络、关系和路径问题。", "数学", ["网络", "顶点", "边"], "百科"),
    ("概率论", "研究随机现象和不确定性的数学分支，是统计学和机器学习的理论基础。", "数学", ["随机", "统计", "不确定性"], "百科"),

    # ── 哲学 ──
    ("意识", "主观体验和感知的能力，是哲学和神经科学的核心问题之一。", "哲学", ["心智", "感知", "自我"], "百科"),
    ("人工智能伦理", "研究人工智能系统的开发和使用对社会、道德和法律影响的交叉学科。", "哲学", ["AI", "道德", "责任"], "百科"),
]

RELATIONS = [
    ("深度学习", "机器学习", "is_a", "深度学习是机器学习的一个子集", 1.0),
    ("机器学习", "自然语言处理", "supports", "NLP 大量使用机器学习算法", 0.9),
    ("深度学习", "自然语言处理", "supports", "现代 NLP 基于深度神经网络", 0.95),
    ("机器学习", "概率论", "depends_on", "机器学习算法依赖概率论和统计", 0.9),
    ("深度学习", "图论", "related_to", "神经网络结构可看作有向图", 0.5),
    ("数据库", "机器学习", "supports", "数据库为机器学习系统存储训练数据", 0.7),
    ("自然语言处理", "意识", "related_to", "NLP 试图模拟语言能力，与意识有交集", 0.4),
    ("DNA", "进化论", "supports", "DNA 为进化论提供了分子层面的证据", 0.95),
    ("DNA", "细胞", "part_of", "DNA 位于细胞内，是细胞遗传系统的一部分", 1.0),
    ("光合作用", "细胞", "depends_on", "光合作用发生在植物细胞中", 0.9),
    ("相对论", "黑洞", "supports", "广义相对论预言了黑洞的存在", 0.95),
    ("量子力学", "相对论", "contradicts", "量子力学与广义相对论在极端条件下不一致", 0.6),
    ("大爆炸理论", "相对论", "depends_on", "大爆炸宇宙学模型以广义相对论为理论基础", 0.9),
    ("黑洞", "大爆炸理论", "related_to", "黑洞奇点与大爆炸奇点有相似性", 0.5),
    ("热力学定律", "黑洞", "related_to", "黑洞热力学是热门研究领域", 0.7),
    ("图论", "TCP/IP协议", "supports", "网络路由协议基于图论算法", 0.8),
    ("数据库", "操作系统", "depends_on", "数据库系统运行在操作系统之上", 0.85),
    ("区块链", "数据库", "related_to", "区块链可看作一种特殊的分布式数据库", 0.7),
    ("区块链", "TCP/IP协议", "depends_on", "区块链网络依赖 TCP/IP 协议通信", 0.8),
    ("概率论", "量子力学", "supports", "量子力学本质上是概率性的", 0.8),
    ("意识", "人工智能伦理", "related_to", "AI 是否可能有意识是伦理讨论的核心", 0.6),
    ("机器学习", "人工智能伦理", "supports", "AI 伦理问题源于机器学习能力", 0.85),
    ("深度学习", "强化学习", "related_to", "深度强化学习结合了深度学习和强化学习", 0.9),
    ("强化学习", "进化论", "related_to", "强化学习模拟了自然选择中的试错机制", 0.5),
    ("细胞", "进化论", "supports", "细胞是进化的基本单位", 0.8),
    ("光合作用", "热力学定律", "supports", "光合作用遵循能量守恒定律", 0.85),
    ("操作系统", "TCP/IP协议", "related_to", "操作系统通常实现 TCP/IP 协议栈", 0.9),
]

EVIDENCES = [
    ("机器学习", "深度学习在 ImageNet 竞赛中于 2012 年取得突破性进展，错误率降至 15.3%", "百科", "ImageNet 竞赛"),
    ("进化论", "达尔文 1859 年发表《物种起源》，提出了自然选择理论", "百科", "物种起源"),
    ("相对论", "爱因斯坦 1915 年完成广义相对论，1919 年日食观测验证了光线弯曲", "百科", "广义相对论"),
    ("量子力学", "2022 年诺贝尔物理学奖授予量子纠缠实验验证", "百科", "诺贝尔奖"),
    ("黑洞", "2019 年 Event Horizon Telescope 发布了首张黑洞照片 (M87*)", "百科", "EHT 项目"),
    ("大爆炸理论", "1964 年彭齐亚斯和威尔逊发现宇宙微波背景辐射", "百科", "CMB 发现"),
    ("DNA", "1953 年沃森和克里克提出 DNA 双螺旋结构模型", "百科", "DNA 双螺旋"),
    ("区块链", "2008 年中本聪发表比特币白皮书，区块链技术首次应用", "百科", "比特币白皮书"),
]

SEED_PAPERS = [
    ("Deep Residual Learning for Image Recognition", ["He, Kaiming", "Zhang, Xiangyu", "Ren, Shaoqing", "Sun, Jian"], "CVPR", 2016, "10.1109/CVPR.2016.90", "", "深度学习"),
    ("Attention Is All You Need", ["Vaswani, Ashish", "Shazeer, Noam", "Parmar, Niki", "Uszkoreit, Jakob"], "NeurIPS", 2017, "10.5555/3295222.3295349", "", "自然语言处理"),
    ("Playing Atari with Deep Reinforcement Learning", ["Mnih, Volodymyr", "Kavukcuoglu, Koray", "Silver, David", "Graves, Alex"], "arXiv", 2013, "", "1312.5602", "强化学习"),
    ("ImageNet Classification with Deep Convolutional Neural Networks", ["Krizhevsky, Alex", "Sutskever, Ilya", "Hinton, Geoffrey E."], "NeurIPS", 2012, "10.1145/3065386", "", "机器学习"),
    ("A Mathematical Theory of Communication", ["Shannon, Claude E."], "Bell System Technical Journal", 1948, "10.1002/j.1538-7305.1948.tb01338.x", "", "概率论"),
    ("On the Origin of Species by Means of Natural Selection", ["Darwin, Charles"], "John Murray", 1859, "", "", "进化论"),
    ("First M87 Event Horizon Telescope Results", ["Event Horizon Telescope Collaboration"], "ApJL", 2019, "10.3847/2041-8213/ab0ec7", "", "黑洞"),
    ("Planck 2018 Results: Overview and Cosmological Legacy", ["Planck Collaboration"], "Astronomy & Astrophysics", 2020, "10.1051/0004-6361/201833910", "", "大爆炸理论"),
    ("Bitcoin: A Peer-to-Peer Electronic Cash System", ["Nakamoto, Satoshi"], "White Paper", 2008, "", "", "区块链"),
    ("Molecular Structure of Nucleic Acids", ["Watson, James D.", "Crick, Francis H. C."], "Nature", 1953, "10.1038/171737a0", "", "DNA"),
]


def seed():
    init_db()
    with connection() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
        if existing > 0:
            from curated_content import install
            installed = install()
            print(f"Database already has {existing} concepts; curated collection is ready ({installed['sections']} dossier sections).")
            return

    concept_map = {}
    for name, desc, cat, tags, source in CONCEPTS:
        c = create_concept(name, desc, cat, tags, source)
        concept_map[name] = c["id"]
        print(f"  + Concept: {name}")

    for src_name, tgt_name, rtype, evidence, conf in RELATIONS:
        if src_name in concept_map and tgt_name in concept_map:
            create_relation(concept_map[src_name], concept_map[tgt_name], rtype, evidence, conf)
            print(f"  + Relation: {src_name} --{rtype}--> {tgt_name}")

    for cname, content, source_title, source_url in EVIDENCES:
        if cname in concept_map:
            from knowledge import create_evidence
            create_evidence(concept_map[cname], content, source_url, source_title)
            print(f"  + Evidence: {cname}")

    from papers import create_paper, link_paper_to_concept
    for title, authors, venue, year, doi, arxiv_id, concept_name in SEED_PAPERS:
        paper = create_paper(title, authors, venue, year, doi, arxiv_id)
        if concept_name in concept_map:
            link_paper_to_concept(paper["id"], concept_map[concept_name], "primary")
            print(f"  + Paper: {title} → {concept_name}")

    from curated_content import install
    installed = install()

    print(f"\n✓ Seeded base collection plus {installed['concepts']} curated concepts and {installed['sections']} dossier sections.")


if __name__ == "__main__":
    force = "--force" in sys.argv
    if force:
        import os
        db_path = __import__("database").DB_PATH
        os.remove(str(db_path))
        print("Removed existing database.")
    seed()
