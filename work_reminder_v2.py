import requests
import datetime
import time
import json
import os
import fcntl
import sys

WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/{replace_your_feishu_webhook_uid}"
INTERVAL = 3600  # 每隔多少秒发一次
LOG_FILE = "reminder.log"
LOCK_FILE = "reminder.lock"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB

MONTHLY_SALARY = 12000
WORK_DAYS_PER_MONTH = 22
WORK_HOURS_PER_DAY = 8

def acquire_lock():
    """尝试获取文件锁，获取失败则退出"""
    lock_fh = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("检测到已有脚本在运行，退出。")
        sys.exit(0)
    return lock_fh

def log(message):
    """写日志并检查大小"""
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{now_str}] {message}\n"

    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
        os.remove(LOG_FILE)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)

    print(log_line, end="")  # 同时输出到终端

def calc_earned(now: datetime.datetime):
    """计算今天已经挣了多少钱"""
    start_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    hourly_salary = MONTHLY_SALARY / WORK_DAYS_PER_MONTH / WORK_HOURS_PER_DAY

    if now < start_time:
        return 0.0
    worked_seconds = (now - start_time).total_seconds()
    worked_hours = worked_seconds / 3600
    return max(0, worked_hours * hourly_salary)

def send_card(title, content_lines, header_title="提醒", color="turquoise"):
    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "elements": [
                {
                    "tag": "div",
                    "text": {"tag": "lark_md", "content": "\n".join(content_lines)}
                }
            ],
            "header": {
                "title": {"tag": "plain_text", "content": header_title},
                "template": color
            }
        }
    }
    try:
        response = requests.post(
            WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=5
        )
        if response.status_code == 200:
            log(f"[{header_title}] 消息卡片发送成功")
        else:
            log(f"[{header_title}] 发送失败：{response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        log(f"[{header_title}] 网络请求异常: {e}")

def lunch_reminder():
    now = datetime.datetime.now()
    earned = calc_earned(now)
    send_card(
        title="🍚 饭点提醒",
        content_lines=[
            f"📅 现在是 {now.strftime('%Y-%m-%d')} {now.strftime('%H:%M')}",
            "🍱 马上到饭点啦，记得点外卖或者准备午餐～",
            f"💰 今天已经挣了 **{earned:.2f} 元**"
        ],
        header_title="🍜 饭点提醒",
        color="blue"
    )

def work_reminder():
    now = datetime.datetime.now()
    earned = calc_earned(now)
    end_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
    remaining = end_time - now
    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
    minutes, _ = divmod(remainder, 60)

    send_card(
        title="🏢 下班倒计时",
        content_lines=[
            f"📅 今天是 {now.strftime('%Y-%m-%d')} {now.strftime('%H:%M')}",
            f"⏳ 距离下班还有 **{hours} 小时 {minutes} 分钟**",
            f"💰 今天已经挣了 **{earned:.2f} 元**",
            "💡 再坚持一下，等会就能快乐下班！"
        ],
        header_title="⏳ 下班倒计时",
        color="turquoise"
    )

def off_reminder():
    now = datetime.datetime.now()
    earned = calc_earned(now)
    send_card(
        title="🔚 下班提醒",
        content_lines=[
            f"📅 现在是 {now.strftime('%Y-%m-%d')} {now.strftime('%H:%M')}",
            "🏃 再坚持 10 分钟就下班啦！",
            f"💰 今天已经挣了 **{earned:.2f} 元**",
            "🚻 该上厕所的上厕所，该带饭盒的带饭盒"
        ],
        header_title="🏁 下班前提醒",
        color="green"
    )

def is_afternoon_work_time():
    """工作日下午 13:00-18:00"""
    now = datetime.datetime.now()
    return now.weekday() < 5 and 13 <= now.hour < 18

if __name__ == "__main__":
    lock_fh = acquire_lock()
    while True:
        now = datetime.datetime.now()
        # 特殊时间提醒
        if now.weekday() < 5:  # 工作日
            if now.strftime("%H:%M") == "10:50":
                lunch_reminder()
            elif now.strftime("%H:%M") == "17:50":
                off_reminder()
            elif is_afternoon_work_time() and now.minute == 0:  # 整点提醒
                work_reminder()
        time.sleep(60)  # 每分钟检查一次
