"""Built-in sample material used when no LLM key is configured (demo mode).

It lets you click through the whole flow before connecting a model. The
content does not change with the topic; scores use only the measured signals.
"""

SAMPLES = {
    "en": {
        "article": {
            "title": "My First Week at a New Job",
            "titleTranslation": "新工作的第一周",
            "sentences": [
                {"text": "Last Monday, I started a new job at a small design company.", "translation": "上周一，我在一家小型设计公司开始了新工作。"},
                {"text": "I was nervous, but my manager welcomed me with a cup of coffee.", "translation": "我很紧张，但经理端着一杯咖啡欢迎了我。"},
                {"text": "She introduced me to the team and showed me around the office.", "translation": "她把我介绍给团队，并带我参观了办公室。"},
                {"text": "On Wednesday, I joined my first project meeting.", "translation": "周三，我参加了第一次项目会议。"},
                {"text": "Everyone spoke quickly, so I took a lot of notes.", "translation": "大家说话都很快，所以我记了很多笔记。"},
                {"text": "By Friday, I felt much more comfortable and confident.", "translation": "到了周五，我感觉自在多了，也更有信心了。"},
            ],
            "questions": [
                {"text": "What kind of company did the speaker start working at?", "translation": "说话人开始在什么样的公司工作？", "answerHint": "A small design company."},
                {"text": "What did the speaker do during the project meeting, and why?", "translation": "说话人在项目会议上做了什么？为什么？", "answerHint": "Took a lot of notes because everyone spoke quickly."},
                {"text": "How did the speaker feel at the end of the week?", "translation": "说话人在周末时感觉如何？", "answerHint": "More comfortable and confident."},
            ],
        },
        "dialogue": {
            "title": "Ordering at a Café",
            "scene": "你在一家咖啡店点单，店员会和你确认需求。",
            "roles": [{"id": "A", "name": "Barista", "description": "咖啡店店员"}, {"id": "B", "name": "Customer", "description": "顾客"}],
            "lines": [
                {"role": "A", "text": "Hi there! What can I get for you today?", "translation": "你好！今天想喝点什么？"},
                {"role": "B", "text": "Hi, could I have a medium latte, please?", "translation": "你好，请给我一杯中杯拿铁。"},
                {"role": "A", "text": "Sure. Would you like regular milk or oat milk?", "translation": "好的。要普通牛奶还是燕麦奶？"},
                {"role": "B", "text": "Oat milk, please. And can I get it a little less sweet?", "translation": "燕麦奶，谢谢。可以少甜一点吗？"},
                {"role": "A", "text": "No problem. Is that for here or to go?", "translation": "没问题。在这里喝还是带走？"},
                {"role": "B", "text": "To go, please. How much is it?", "translation": "带走，谢谢。多少钱？"},
                {"role": "A", "text": "That'll be four fifty. Your name for the order?", "translation": "四块五。请问您的名字？"},
                {"role": "B", "text": "It's Eric. Thanks a lot!", "translation": "我叫 Eric。非常感谢！"},
            ],
        },
        "questions": {
            "title": "Job Interview Practice",
            "intro": "你正在参加一场英文求职面试，面试官会依次提问。",
            "questions": [
                {"text": "Could you briefly introduce yourself?", "translation": "可以简单介绍一下你自己吗？", "tip": "背景、经验、一个亮点，控制在一分钟内"},
                {"text": "Why are you interested in this position?", "translation": "你为什么对这个职位感兴趣？", "tip": "把你的兴趣和公司/岗位的特点联系起来"},
                {"text": "Tell me about a challenge you faced at work and how you handled it.", "translation": "讲一个你在工作中遇到的挑战以及你如何处理的。", "tip": "用 STAR 法：情境、任务、行动、结果"},
                {"text": "Where do you see yourself in five years?", "translation": "你觉得五年后的自己会是什么样？", "tip": "说出成长方向，并与这个岗位挂钩"},
            ],
        },
    },
    "ja": {
        "article": {
            "title": "週末の過ごし方",
            "titleTranslation": "周末的度过方式",
            "sentences": [
                {"text": "私は週末によく近くの公園を散歩します。", "translation": "我周末经常在附近的公园散步。"},
                {"text": "朝早く行くと、空気がとても気持ちいいです。", "translation": "早上早点去的话，空气非常舒服。"},
                {"text": "散歩のあとは、駅の前のカフェでコーヒーを飲みます。", "translation": "散步之后，我会在车站前的咖啡店喝咖啡。"},
                {"text": "そのカフェのパンはとてもおいしくて、人気があります。", "translation": "那家咖啡店的面包非常好吃，很受欢迎。"},
                {"text": "午後は家で本を読んだり、映画を見たりします。", "translation": "下午在家看看书、看看电影。"},
                {"text": "静かな週末は、次の一週間のための大切な時間です。", "translation": "安静的周末是为下一周做准备的重要时间。"},
            ],
            "questions": [
                {"text": "この人は週末によくどこへ行きますか。", "translation": "这个人周末经常去哪里？", "answerHint": "近くの公園へ散歩に行きます。"},
                {"text": "散歩のあと、何をしますか。", "translation": "散步之后做什么？", "answerHint": "駅の前のカフェでコーヒーを飲みます。"},
                {"text": "この人にとって、静かな週末はどんな時間ですか。", "translation": "对这个人来说，安静的周末是怎样的时间？", "answerHint": "次の一週間のための大切な時間です。"},
            ],
        },
        "dialogue": {
            "title": "レストランで",
            "scene": "你在日本的餐厅，店员为你点餐。",
            "roles": [{"id": "A", "name": "店員", "description": "餐厅店员"}, {"id": "B", "name": "客", "description": "顾客"}],
            "lines": [
                {"role": "A", "text": "いらっしゃいませ。何名様ですか。", "translation": "欢迎光临。请问几位？"},
                {"role": "B", "text": "一人です。", "translation": "一个人。"},
                {"role": "A", "text": "こちらへどうぞ。ご注文がお決まりでしたら、お呼びください。", "translation": "这边请。决定好点什么请叫我。"},
                {"role": "B", "text": "すみません、おすすめは何ですか。", "translation": "不好意思，有什么推荐的吗？"},
                {"role": "A", "text": "本日は天ぷら定食がおすすめです。", "translation": "今天推荐天妇罗套餐。"},
                {"role": "B", "text": "じゃあ、それをお願いします。", "translation": "那就要那个吧。"},
                {"role": "A", "text": "お飲み物はいかがですか。", "translation": "需要喝点什么吗？"},
                {"role": "B", "text": "温かいお茶をください。", "translation": "请给我热茶。"},
            ],
        },
        "questions": {
            "title": "面接の練習",
            "intro": "你正在参加日本公司的面试，面试官会依次提问。",
            "questions": [
                {"text": "簡単に自己紹介をお願いします。", "translation": "请简单做一下自我介绍。", "tip": "名字、背景、经验，最后加一句「よろしくお願いいたします」"},
                {"text": "弊社を志望した理由を教えてください。", "translation": "请告诉我们你应聘本公司的理由。", "tip": "说明对公司的了解和自己的契合点"},
                {"text": "あなたの長所と短所は何ですか。", "translation": "你的优点和缺点是什么？", "tip": "缺点要配上你正在如何改进"},
                {"text": "最後に、何か質問はありますか。", "translation": "最后，你有什么问题吗？", "tip": "准备一个关于工作内容或团队的问题"},
            ],
        },
    },
}


def sample_content(language: str, mode: str, topic: str) -> dict:
    import copy

    data = copy.deepcopy(SAMPLES[language][mode])
    return data


def sample_judgement(turns, metrics, obj, has_voice) -> dict:
    """Heuristic stand-in for the model's judgement in demo mode."""
    avg_units = sum(m["units"] for m in metrics) / max(len(metrics), 1)
    content = max(40, min(90, 45 + avg_units * 3))
    base = obj.get("listening") or 70
    scores = {
        "listening": base,
        "pronunciation": obj.get("pronunciation") if has_voice else None,
        "fluency": obj.get("fluency") if has_voice else None,
        "grammar": 70,
        "vocabulary": max(50, min(85, 50 + avg_units * 2)),
        "content": content,
    }
    note = "（演示模式：配置大模型后会给出真实点评）"
    return {
        "scores": scores,
        "comments": {k: note for k in scores},
        "summary": "这是演示模式的报告。发音和流利度来自你本次录音的实测数据，其余维度为估算。在 backend/.env 中填写大模型 Key 后即可获得完整的批改和点评。",
        "strengths": ["完成了整个练习流程"],
        "improvements": ["配置大模型 Key，获取逐句批改和更地道的表达"],
        "items": [
            {"index": i, "corrected": t.get("answer", ""), "better": t.get("reference", ""), "notes": note}
            for i, t in enumerate(turns)
            if t.get("kind") != "shadow"
        ],
        "vocabulary": [],
    }
