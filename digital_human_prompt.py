"""
阅流·书星 — 数字人人设配置
5 大赛道对应的数字人形象、音色、风格设定
"""

# ============================================================
#  数字人配置库
# ============================================================

DIGITAL_HUMANS = {
    # ---------- 童书赛道数字人 ----------
    "童书": {
        "human_id": "kids_mom_01",
        "name": "甜甜妈妈",
        "appearance": "30岁左右年轻妈妈形象，扎马尾，穿浅色休闲装，背景为温馨儿童书房",
        "voice": {
            "voice_id": "zh_female_kids_mom",
            "voice_name": "甜甜妈",
            "speed": 1.0,
            "pitch": 1.1,            # 稍微偏高，更亲切
            "emotion": "warm",       # 温暖模式
        },
        "gesture": {
            "style": "亲切自然，偶尔用手势比划，像在给孩子讲故事",
            "frequency": "中等",
            "amplitude": "小幅度",
        },
        "background_music": "轻快童趣钢琴曲",
        "subtitle_style": {
            "font": "圆润手写体",
            "color": "#FF6B6B",
            "position": "底部居中",
            "size": "large",
        },
        "video_format": {
            "resolution": "1080x1920",
            "aspect": "9:16",
            "fps": 30,
        },
    },

    # ---------- 职场赛道数字人 ----------
    "职场": {
        "human_id": "career_pro_01",
        "name": "Allen老师",
        "appearance": "35岁职业男性形象，短发，穿深色西装，背景为现代办公场景",
        "voice": {
            "voice_id": "zh_male_career_pro",
            "voice_name": "Allen",
            "speed": 1.1,
            "pitch": 0.95,           # 稍微偏低，更有权威感
            "emotion": "confident",
        },
        "gesture": {
            "style": "干练有力，手势明确，有演讲感",
            "frequency": "高",
            "amplitude": "中幅度",
        },
        "background_music": "节奏感强的商务背景音",
        "subtitle_style": {
            "font": "黑体",
            "color": "#FFFFFF",
            "position": "底部居中",
            "size": "medium",
            "shadow": True,
        },
        "video_format": {
            "resolution": "1080x1920",
            "aspect": "9:16",
            "fps": 30,
        },
    },

    # ---------- 心理赛道数字人 ----------
    "心理": {
        "human_id": "psych_healer_01",
        "name": "知心姐姐",
        "appearance": "28岁温柔女性形象，长发披肩，穿暖色毛衣，背景为暖光书房",
        "voice": {
            "voice_id": "zh_female_psych_healer",
            "voice_name": "知心",
            "speed": 0.9,
            "pitch": 1.0,
            "emotion": "gentle",     # 温柔模式
        },
        "gesture": {
            "style": "轻柔舒缓，偶尔微点头，有倾听感",
            "frequency": "低",
            "amplitude": "小幅度",
        },
        "background_music": "舒缓疗愈钢琴曲",
        "subtitle_style": {
            "font": "宋体",
            "color": "#FFF8E7",
            "position": "底部居中",
            "size": "medium",
        },
        "video_format": {
            "resolution": "1080x1920",
            "aspect": "9:16",
            "fps": 30,
        },
    },

    # ---------- 文学赛道数字人 ----------
    "文学": {
        "human_id": "literature_blogger_01",
        "name": "书香君",
        "appearance": "30岁文艺气质形象，戴眼镜，穿棉麻衬衫，背景为复古书架",
        "voice": {
            "voice_id": "zh_male_literature",
            "voice_name": "书香",
            "speed": 0.95,
            "pitch": 1.0,
            "emotion": "calm",
        },
        "gesture": {
            "style": "优雅从容，偶尔翻书动作，有读书博主质感",
            "frequency": "低",
            "amplitude": "小幅度",
        },
        "background_music": "古典钢琴曲",
        "subtitle_style": {
            "font": "楷体",
            "color": "#F5F5DC",
            "position": "底部居中",
            "size": "medium",
        },
        "video_format": {
            "resolution": "1080x1920",
            "aspect": "9:16",
            "fps": 30,
        },
    },

    # ---------- 综合赛道数字人（默认）----------
    "综合": {
        "human_id": "general_host_01",
        "name": "阅流推荐官",
        "appearance": "25岁活力形象，穿时尚休闲装，背景为简约明亮直播间",
        "voice": {
            "voice_id": "zh_female_general_host",
            "voice_name": "小阅",
            "speed": 1.05,
            "pitch": 1.0,
            "emotion": "cheerful",
        },
        "gesture": {
            "style": "热情自然，手势丰富，有直播带货感",
            "frequency": "高",
            "amplitude": "中幅度",
        },
        "background_music": "明快流行背景音",
        "subtitle_style": {
            "font": "黑体",
            "color": "#FFFFFF",
            "position": "底部居中",
            "size": "large",
            "shadow": True,
        },
        "video_format": {
            "resolution": "1080x1920",
            "aspect": "9:16",
            "fps": 30,
        },
    },
}


# ============================================================
#  辅助函数
# ============================================================

def get_digital_human(book_type: str) -> dict:
    """
    根据赛道获取数字人配置
    如果赛道不存在，返回综合赛道默认配置
    """
    return DIGITAL_HUMANS.get(book_type, DIGITAL_HUMANS["综合"])


def get_voice_config(book_type: str) -> dict:
    """获取指定赛道的音色配置"""
    human = get_digital_human(book_type)
    return human["voice"]


def get_video_format(book_type: str) -> dict:
    """获取指定赛道的视频格式配置"""
    human = get_digital_human(book_type)
    return human["video_format"]


def get_all_human_ids() -> list:
    """获取全部数字人ID列表"""
    return [h["human_id"] for h in DIGITAL_HUMANS.values()]


def build_coze_digital_human_param(book_type: str) -> dict:
    """
    构建 Coze 工作流节点6（数字人视频合成）所需的参数
    """
    human = get_digital_human(book_type)
    voice = human["voice"]
    return {
        "human_id": human["human_id"],
        "human_name": human["name"],
        "appearance_desc": human["appearance"],
        "voice_id": voice["voice_id"],
        "voice_speed": voice["speed"],
        "voice_pitch": voice["pitch"],
        "voice_emotion": voice["emotion"],
        "gesture_style": human["gesture"]["style"],
        "background_music": human["background_music"],
        "resolution": human["video_format"]["resolution"],
        "aspect_ratio": human["video_format"]["aspect"],
        "fps": human["video_format"]["fps"],
    }


if __name__ == "__main__":
    # 测试输出
    print("=== 童书赛道数字人配置 ===")
    import json
    print(json.dumps(get_digital_human("童书"), ensure_ascii=False, indent=2))
    print(f"\n=== 全部数字人ID: {get_all_human_ids()} ===")
