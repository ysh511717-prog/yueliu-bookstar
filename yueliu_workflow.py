"""
阅流·书星 — 分发工作流逻辑
分发时间策略、标题生成、爆款判定逻辑
"""

import json
import random
from datetime import datetime, timedelta


# ============================================================
#  分发时间策略 — 各平台最佳发布时间窗口
# ============================================================

PUBLISH_TIME_WINDOWS = {
    "抖音": {
        "黄金时段": ["07:00-09:00", "12:00-13:00", "18:00-20:00", "21:00-23:00"],
        "建议频率": "每天1-2条",
        "最佳间隔": "2小时以上",
    },
    "小红书": {
        "黄金时段": ["07:00-09:00", "12:00-14:00", "19:00-22:00"],
        "建议频率": "每天1条",
        "最佳间隔": "3小时以上",
    },
    "视频号": {
        "黄金时段": ["08:00-10:00", "12:00-13:00", "20:00-22:00"],
        "建议频率": "每天1条",
        "最佳间隔": "4小时以上",
    },
}


# ============================================================
#  分发时间计算
# ============================================================

def calculate_publish_times(start_time: datetime = None) -> dict:
    """
    计算三平台的最佳发布时间
    从当前时间开始，为每个平台选择最近的黄金时段
    """
    if start_time is None:
        start_time = datetime.now()

    result = {}

    for platform, config in PUBLISH_TIME_WINDOWS.items():
        best_time = _find_next_golden_time(start_time, config["黄金时段"])
        result[platform] = best_time.strftime("%Y-%m-%d %H:%M")

    return result


def _find_next_golden_time(now: datetime, windows: list) -> datetime:
    """找到最近的黄金时段"""
    for window in windows:
        start_str, end_str = window.split("-")
        start_hour, start_min = map(int, start_str.split(":"))

        # 今天的黄金时段
        today_golden = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)

        if today_golden > now:
            return today_golden

    # 今天所有黄金时段已过，取明天第一个
    tomorrow = now + timedelta(days=1)
    first_window = windows[0]
    start_str = first_window.split("-")[0]
    start_hour, start_min = map(int, start_str.split(":"))
    return tomorrow.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)


# ============================================================
#  标题生成 — 各平台爆款标题模板
# ============================================================

TITLE_TEMPLATES = {
    "抖音": [
        "📚{book_name}｜看完这本书，我整个人都变了",
        "{book_name}📖 一本被严重低估的好书，后悔没早看！",
        "🔥{book_name}：{book_type}必读！最后那一页直接封神",
        "谁还没看过《{book_name}》？这本书太绝了！📚",
        "豆瓣{score}分！{book_name}凭什么这么高分？看完我懂了",
    ],
    "小红书": [
        "📖读书笔记｜{book_name}读完真的会改变你",
        "推荐一本好书📕《{book_name}》后劲太大了",
        "📚{book_type}书单｜这本{book_name}值得反复读",
        "豆瓣高分推荐｜{book_name}读完泪目了😭",
        "睡前读物推荐💤{book_name}治愈又好读",
    ],
    "视频号": [
        "【好书推荐】{book_name}｜{book_type}爱好者必读",
        "📚这本书值得每个人读一遍：《{book_name}》",
        "{book_name}：一本让你重新认识自己的书",
        "读书分享📖｜{book_name}，{book_type}赛道精选",
        "推荐！{book_name}，读完收获满满💡",
    ],
}


def generate_titles(book_name: str, book_type: str, score: str = "9.0") -> dict:
    """
    为三平台各生成一条爆款标题
    """
    titles = {}
    for platform, templates in TITLE_TEMPLATES.items():
        template = random.choice(templates)
        title = template.format(
            book_name=book_name,
            book_type=book_type,
            score=score,
        )
        titles[platform] = title
    return titles


# ============================================================
#  爆款判定逻辑
# ============================================================

VIRAL_THRESHOLDS = {
    "抖音": {
        "views_24h": 10000,      # 24小时播放量阈值
        "likes_24h": 500,        # 24小时点赞阈值
        "comments_24h": 100,     # 24小时评论阈值
        "share_24h": 50,         # 24小时转发阈值
        "complete_rate": 0.3,    # 完播率阈值
    },
    "小红书": {
        "views_24h": 5000,
        "likes_24h": 300,
        "comments_24h": 50,
        "collect_24h": 100,      # 收藏阈值
        "complete_rate": 0.4,
    },
    "视频号": {
        "views_24h": 3000,
        "likes_24h": 200,
        "comments_24h": 30,
        "share_24h": 30,
        "complete_rate": 0.35,
    },
}


def judge_viral(video_stats: dict) -> dict:
    """
    爆款判定：根据视频24小时数据判断是否为爆款
    返回判定结果和推荐操作

    参数 video_stats 示例:
    {
        "platform": "抖音",
        "views": 15000,
        "likes": 800,
        "comments": 120,
        "shares": 60,
        "complete_rate": 0.35
    }
    """
    platform = video_stats.get("platform", "抖音")
    threshold = VIRAL_THRESHOLDS.get(platform, VIRAL_THRESHOLDS["抖音"])

    # 逐项判定
    checks = {
        "播放量": video_stats.get("views", 0) >= threshold["views_24h"],
        "点赞": video_stats.get("likes", 0) >= threshold["likes_24h"],
        "评论": video_stats.get("comments", 0) >= threshold["comments_24h"],
        "完播率": video_stats.get("complete_rate", 0) >= threshold["complete_rate"],
    }

    # 分享/收藏根据平台判断
    if "shares" in video_stats:
        checks["转发"] = video_stats["shares"] >= threshold.get("share_24h", 50)
    if "collects" in video_stats:
        checks["收藏"] = video_stats["collects"] >= threshold.get("collect_24h", 100)

    passed = sum(checks.values())
    total = len(checks)

    # 爆款等级判定
    if passed >= total * 0.8:
        level = "S级爆款"
        action = "建议立即加大流量投放，追加DOU+/薯条推广"
        boost = True
    elif passed >= total * 0.6:
        level = "A级潜力"
        action = "建议适度投流，观察48小时数据趋势"
        boost = True
    elif passed >= total * 0.4:
        level = "B级普通"
        action = "正常分发，无需额外投流"
        boost = False
    else:
        level = "C级待优化"
        action = "建议调整标题/封面，重新分发测试"
        boost = False

    return {
        "platform": platform,
        "level": level,
        "passed_checks": passed,
        "total_checks": total,
        "details": checks,
        "recommendation": action,
        "should_boost": boost,
    }


# ============================================================
#  分发策略构建 — 供 Coze 工作流节点7使用
# ============================================================

def build_distribute_plan(book_name: str, book_type: str) -> dict:
    """
    生成多平台分发策略 JSON
    包含：发布时间、标题、标签、爆款阈值
    """
    publish_times = calculate_publish_times()
    titles = generate_titles(book_name, book_type)

    # 各平台标签
    tags = {
        "抖音": [f"#{book_type}推荐", f"#{book_name}", "#好书推荐", "#读书分享", f"#{book_type}书单"],
        "小红书": [f"#{book_type}书单", f"#{book_name}读后感", "#读书笔记", "#好书推荐", f"#{book_type}必读"],
        "视频号": [f"#{book_type}", "#好书分享", f"#{book_name}", "#读书"],
    }

    return {
        "platforms": ["抖音", "小红书", "视频号"],
        "publish_times": publish_times,
        "titles": titles,
        "tags": tags,
        "viral_thresholds": {k: v for k, v in VIRAL_THRESHOLDS.items()},
        "remark": f"《{book_name}》{book_type}赛道多平台分发策略，按黄金时段错峰发布",
    }


# ============================================================
#  盈利增收点推荐
# ============================================================

MONETIZATION_TIPS = {
    "创作者会员": {
        "基础会员": {"price": 29, "benefits": ["每月可认领10个任务", "平台服务费降至8%", "优先接单权"]},
        "专业会员": {"price": 99, "benefits": ["每月无限认领任务", "平台服务费降至5%", "AI脚本优化5次/月", "专属爆款投流补贴"]},
    },
    "出版社增值": {
        "加急生产": {"price": "按次收费", "desc": "24小时内出片，标准为48小时"},
        "批量套餐": {"price": "按量阶梯", "desc": "10本以上享8折，50本以上享6折"},
    },
    "流量助推": {
        "dou_plus": "建议S级爆款投入100-500元DOU+",
        "xhs_tia": "建议A级潜力投入50-200元薯条",
    },
}


if __name__ == "__main__":
    # 测试
    print("=== 分发策略 ===")
    plan = build_distribute_plan("小王子", "童书")
    print(json.dumps(plan, ensure_ascii=False, indent=2))

    print("\n=== 爆款判定 ===")
    stats = {"platform": "抖音", "views": 15000, "likes": 800, "comments": 120, "shares": 60, "complete_rate": 0.35}
    result = judge_viral(stats)
    print(json.dumps(result, ensure_ascii=False, indent=2))
