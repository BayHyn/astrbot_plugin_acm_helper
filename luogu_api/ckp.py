import requests
import json
import time
from datetime import datetime, timedelta

# ============================ 配置区域 START ============================

# 在这里填入你需要查询的所有洛谷用户UID，用逗号隔开
USER_IDS_TO_CHECK = [
    "1114798",
    # "233",      # 在这里添加更多UID，像这样
    # "10086",    # 每个UID是字符串，用逗号隔开
]

# 在这里粘贴你从浏览器获取的身份凭证 (这是保证程序能运行的关键！)
MY_COOKIE = "__client_id=d332fcf8c057c4d368f3bbde54ae244c75f2a6b2; _uid=1114798; C3VK=cb8d22"
MY_CSRF_TOKEN = "1760931648:Ul+g0WFl50rk8/vFp9YI8kAqfYnSzZVlYSKIoENgbuw="

# ============================ 配置区域 END ============================


def get_luogu_recent_ac(uid, session, cutoff_timestamp):
    """
    【高效版】为单个用户获取最近一周内的 'Accepted' 记录。
    """
    recent_submissions = []
    page = 1
    print(f"--- 开始智能查询用户 {uid} 的近期 AC 记录 ---")
    
    while True:
        url = f"https://www.luogu.com.cn/record/list?user={uid}&page={page}&status=12&_contentOnly=1"
        try:
            response = session.get(url, timeout=15)
            if response.status_code == 403:
                print(f"错误: 请求用户 {uid} 时被拒绝(403)。Cookie或CSRF-Token可能已过期。")
                return []
            response.raise_for_status()
            data = response.json()
            
            records_on_page = data.get('currentData', {}).get('records', {}).get('result', [])
            if not records_on_page:
                print(f"用户 {uid} 的所有记录均在7天内，已全部获取完毕。")
                break
            
            stop_fetching = False
            for record in records_on_page:
                if record.get('submitTime', 0) > cutoff_timestamp:
                    recent_submissions.append(record)
                else:
                    stop_fetching = True
                    break
            
            if stop_fetching:
                print(f"  已找到7天前的记录边界，停止为用户 {uid} 获取更多数据。")
                break
            print(f"  已获取第 {page} 页 (全部为近期记录)...")
            page += 1
            time.sleep(0.3)
        except Exception as e:
            print(f"错误: 请求用户 {uid} 的第 {page} 页时发生错误: {e}")
            break
            
    return recent_submissions
def main():
    """
    主函数，执行整个流程
    """
    if "在此处粘贴" in MY_COOKIE or "在此处粘贴" in MY_CSRF_TOKEN:
        print("【运行失败】请先打开Python脚本，在顶部的“配置区域”填写你的 MY_COOKIE 和 MY_CSRF_TOKEN！")
        return
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
        'Cookie': MY_COOKIE,
        'x-csrf-token': MY_CSRF_TOKEN,
        'x-requested-with': 'XMLHttpRequest'
    })
    seven_days_ago_timestamp = (datetime.now() - timedelta(days=7)).timestamp()
    all_recent_submissions = []
    for uid in USER_IDS_TO_CHECK:
        user_recent_submissions = get_luogu_recent_ac(uid, session, seven_days_ago_timestamp)
        all_recent_submissions.extend(user_recent_submissions)
    
    if not all_recent_submissions:
        print("\n查询完毕：在过去7天内，所有指定用户都没有新的 Accepted 提交。")
        return
    # 按提交时间对所有记录进行降序排序
    all_recent_submissions.sort(key=lambda r: r['submitTime'], reverse=True)
    # ============================ 核心去重逻辑 START ============================
    
    unique_top_submissions = []
    seen_problem_pids = set() # 使用集合来高效存储已见过的题目ID
    for record in all_recent_submissions:
        pid = record['problem']['pid']
        if pid not in seen_problem_pids:
            # 这是一个新题目，采纳它
            unique_top_submissions.append(record)
            seen_problem_pids.add(pid)
        
        # 如果已经集够10条，就提前结束循环
        if len(unique_top_submissions) >= 10:
            break
            
    # ============================ 核心去重逻辑 END ============================
    # 格式化并打印去重后的最新记录
    print("\n====================【最近一周内最新AC记录 (每题仅计一次)】====================")
    
    for record in unique_top_submissions:
        user_name = record['user']['name']
        problem_title = record['problem']['title'].strip()
        problem_pid = record['problem']['pid']
        problem_url = f"https://www.luogu.com.cn/problem/{problem_pid}"
        submit_timestamp = record['submitTime']
        readable_time = datetime.fromtimestamp(submit_timestamp).strftime('%Y-%m-%d %H:%M')
        print(f"\n用户 '{user_name}' 在 {readable_time} 通过了题目:")
        print(f"  - 标题: {problem_title}")
        print(f"  - 链接: {problem_url}")
        
    print("\n=======================================================================")
if __name__ == "__main__":
    main()
