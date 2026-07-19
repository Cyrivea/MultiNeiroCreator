from datetime import datetime

import pytz
from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """获取当前最新的北京时间以及全球主要城市的精准当地时间"""
    try:
        regions = {
            "中国 (北京)": "Asia/Shanghai",
            "美国 (纽约)": "America/New_York",
            "英国 (伦敦)": "Europe/London",
            "日本 (东京)": "Asia/Tokyo",
            "德国 (柏林)": "Europe/Berlin",
        }
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        result_lines = ["当前全球主要时刻对照："]

        for name, timezone_name in regions.items():
            timezone = pytz.timezone(timezone_name)
            now = datetime.now(timezone)
            time_str = now.strftime(f"%Y-%m-%d %H:%M:%S {weekdays[now.weekday()]}")
            result_lines.append(f"- **{name}**：{time_str}")

        return "\n".join(result_lines)
    except Exception as exc:
        return f"获取全球时间失败: {str(exc)}"
