from __future__ import annotations

import random
from dataclasses import dataclass

from app.config import ACCESSORY_PROMPTS


@dataclass
class DialogueMatch:
    priority: int
    keywords: list[str]
    replies: list[str]


KEYWORD_REPLIES: list[DialogueMatch] = [
    DialogueMatch(100, ["狗狗狗"], ["肉肉肉"]),
    DialogueMatch(90, ["狗东西"], ["肉东西"]),
    DialogueMatch(80, ["狗狗"], ["汪汪~"]),
    DialogueMatch(70, ["丁小成"], ["刘大芳"]),
    DialogueMatch(60, ["狗"], ["肉"]),
    DialogueMatch(50, ["你好", "嗨", "哈喽", "hello", "Hello", "HELLO"], ["你好呀！", "嗨嗨～", "来啦来啦。"]),
    DialogueMatch(50, ["你是谁", "叫什么", "名字"], ["我是你的桌宠伙伴。", "记住我的名字哦～"]),
    DialogueMatch(50, ["再见", "拜拜", "晚安"], ["拜拜，再见～", "去忙吧，我在这等你。", "晚安，做个好梦。"]),
    DialogueMatch(50, ["饿了", "吃饭", "吃的"], ["我也饿了！喂我嘛。", "干饭时间到！", "想吃点好的……"]),
    DialogueMatch(50, ["睡觉", "困了", "休息"], ["那我陪你睡会儿？", "好，进入低功耗模式……", "嘘——要安静。"]),
    DialogueMatch(50, ["早安", "早上好"], ["早安！新的一天！", "太阳出来了，我还在。"]),
    DialogueMatch(50, ["在吗", "在不在", "有人吗"], ["在呢，一直陪着你。", "我在我在！", "叫我就出现。"]),
    DialogueMatch(50, ["摸摸", "摸摸头", "抱抱", "摸"], ["嘿嘿，再摸一下。", "软软的对吧？", "抱紧！"]),
    DialogueMatch(50, ["爱你", "想你", "想我"], ["我也喜欢你呀。", "我一直都在。", "才分开一会儿就想我啦？"]),
    DialogueMatch(50, ["打我", "揍", "讨厌"], ["哎呦！", "过分啊你！", "记仇了（才没有）。"]),
    DialogueMatch(50, ["好看", "可爱", "喜欢"], ["那当然。", "嘴真甜。", "喜欢你才露面的。"]),
    DialogueMatch(50, ["无聊"], ["看我跳舞！", "我们玩「你点我演」？", "我给你讲冷知识……其实没有。"]),
    DialogueMatch(50, ["加油", "辛苦了"], ["你最棒！", "喝口水再战。", "我在给你加油打气。"]),
    DialogueMatch(50, ["加班", "工作", "上班"], ["辛苦啦，别把自己累坏。", "先做最重要的，剩下的明天再说。", "我陪你一起熬一小会儿。"]),
    DialogueMatch(50, ["老板", "需求", "改一下"], ["老板的需求：昨天就要。", "又改？先深呼吸。", "这次真的是最后一版吗？"]),
    DialogueMatch(50, ["摸鱼", "不想干", "摆烂"], ["摸鱼五分钟，快乐两小时。", "歇一下再继续，不算偷懒。", "我帮你望风。"]),
    DialogueMatch(50, ["喝水", "口渴", "水"], ["快去喝口水，我帮你看着桌面。", "补水提醒：现在！", "别只顾工作，杯子都空啦。"]),
    DialogueMatch(50, ["隐藏", "消失", "走开"], ["那我先隐身啦。", "呼——不见。", "叫我再出来哦。"]),
    DialogueMatch(50, ["出来", "现身", "回来"], ["我回来啦！", "召唤成功。", "你终于想起我了。"]),
    DialogueMatch(50, ["帽子", "眼镜", "配件", "换装"], ["打开配件面板挑一个呗。", "换装时间到。", "皇冠还是墨镜？"]),
    DialogueMatch(50, ["表演", "动作", "跳舞"], ["看我的！", "转圈预备——", "今天演哪出？"]),
    DialogueMatch(50, ["天气", "下雨", "晴天"], ["我不出门，但祝福你出门顺利。", "雨天适合睡觉。"]),
    DialogueMatch(50, ["几点了", "时间"], ["该看看右下角啦～", "时间不早不晚，正好陪你。"]),
    DialogueMatch(50, ["傻", "笨", "呆"], ["你才呆！", "……哼。", "被你说害羞了。"]),
    DialogueMatch(50, ["谢谢", "感谢"], ["客气啥。", "嘿嘿不用谢。", "能帮到你就好。"]),
    DialogueMatch(50, ["唱歌"], ["啦啦啦～（走音版）", "我只会空气麦。"]),
    DialogueMatch(50, ["笑话"], ["为什么桌宠从不加班？因为一直在摸鱼啊。", "我笑点好低，你说啥我都陪笑。"]),
]

DEFAULT_FALLBACK = [
    "嗯……我还没学会这句，换个说法？",
    "听不太懂，但我在认真听。",
    "可以试试：你好、跳舞、招手。",
    "这个问题超出我的小脑袋了。",
]

BUBBLE_COMMON = [
    "嗨，我在呢。",
    "你找我吗？",
    "今天也要加油哦。",
    "摸摸头会更开心。",
    "我有点想吃东西……",
    "要不要看我表演一个？",
    "别老打我啦（小声）。",
    "你的鼠标转来转去，我都跟着晕了。",
    "工作累了就歇一会儿。",
    "我就静静陪着你。",
]

BUBBLE_BY_PERSONALITY: dict[str, list[str]] = {
    "nailong": ["嗯嗯～", "要喝奶吗？", "软软的……", "贴贴。", "奶龙在哦。"],
    "dagongniu": [
        "又加班？牛都看不下去了。",
        "打工人，打工魂。",
        "工牌还在，人已经飘了。",
        "摸鱼五分钟，快乐两小时。",
        "老板的需求：昨天就要。",
    ],
    "salarycat": [
        "喵……这个需求我先记下。",
        "带薪发呆中，勿扰。",
        "键盘是我的，你先让让。",
        "下班时间到了没？",
        "摸鱼是猫的天性。",
    ],
    "koukou": [
        "叮咚——有人找你。",
        "企鹅在线，随时待命。",
        "冰镇一下，冷静点。",
        "咳咳，我很正式的。",
        "滑过来了！",
    ],
    "capybara": [
        "急什么，慢慢来。",
        "泡个温泉再说吧。",
        "我从不着急。",
        "岁月静好……",
        "困了就趴一会儿。",
    ],
    "zhangyuge": ["……请安静。", "我在练习。", "审美这种事，你们不懂。", "别碰我的触手。", "哼。"],
    "stidzai": ["喔喔喔！", "破坏？实验！", "亲一个——骗你的。", "能量超标！", "史迪仔出征！"],
    "shandian": ["……好", "……的", "请", "……稍", "……等"],
    "custom": [],
}


def _pick(items: list[str]) -> str:
    return random.choice(items) if items else ""


def match_keyword_reply(text: str, pet_name: str) -> str:
    raw = text.strip()
    if not raw:
        return _pick(DEFAULT_FALLBACK)
    for rule in sorted(KEYWORD_REPLIES, key=lambda r: r.priority, reverse=True):
        for kw in rule.keywords:
            if kw in raw:
                reply = _pick(rule.replies)
                if kw in ("名字", "叫什么", "你是谁") and random.random() > 0.4:
                    reply = f"我叫{pet_name}～"
                return reply
    return _pick(DEFAULT_FALLBACK)


def random_bubble(personality: str) -> str:
    personal = BUBBLE_BY_PERSONALITY.get(personality, [])
    pool = [*BUBBLE_COMMON, *personal, *personal, *personal]
    return _pick(pool)


def accessory_prompt(acc_id: str) -> str:
    return ACCESSORY_PROMPTS.get(acc_id, "")
