import requests
import time
from datetime import datetime, timedelta

# ============================ 配置区域 START ============================

# 在这里填入你需要查询的所有Codeforces用户Handle，用逗号隔开
CF_HANDLES_TO_CHECK = [
    "suzakudry",
    #"Radewoosh",
    # "orz_suzakudry",  # 在这里添加更多CF Handle
]

# (可选) Codeforces API密钥。对于简单查询不是必须的，但可以提高请求频率限制
# 如果你有，可以填在这里。没有的话留空即可。
CF_API_KEY = "aeb6b181edb66f093bf69a0b247978f85f717441"
CF_API_SECRET = "0adb7369e45b62a738f1bf6d77cf2708b959cc55"

# ============================ 配置区域 END ============================


def get_cf_recent_ac(handle, cutoff_timestamp):
    """
    【高效版】为单个CF用户获取最近一周内的 'OK' (Accepted) 记录。
    利用CF API返回数据按时间倒序的特性，一旦找到旧记录就停止。
    """
    recent_submissions = []
    print(f"--- 开始智能查询用户 {handle} 的近期 AC 记录 ---")

    # CF API使用 `from` 和 `count` 分页，而不是 `page`
    # 我们一次取100条，一般足够覆盖一周的量
    from_index = 1
    count = 100
    
    url = f"https://codeforces.com/api/user.status?handle={handle}&from={from_index}&count={count}"
    
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status() # 检查请求是否成功
        data = response.json()

        if data.get('status') != 'OK':
            print(f"错误: 请求用户 {handle} 的数据时API返回错误: {data.get('comment')}")
            return []

        submissions = data.get('result', [])
        if not submissions:
            print(f"用户 {handle} 近期没有提交。")
            return []
        
        # 遍历返回的提交记录
        for sub in submissions:
            # 筛选条件1: 必须是 'OK' 的提交
            if sub.get('verdict') != 'OK':
                continue

            submit_time = sub.get('creationTimeSeconds', 0)
            
            # 筛选条件2: 必须在截止日期之后
            if submit_time > cutoff_timestamp:
                recent_submissions.append(sub)
            else:
                # 关键优化点：遇到了第一条7天前的记录，立刻停止
                print(f"  已找到7天前的记录边界，停止为用户 {handle} 获取更多数据。")
                return recent_submissions

        # 如果第一页的所有'OK'记录都在7天内，则说明该用户非常活跃，
        # 完整的实现需要继续请求下一页，但对于周报，通常100条足够了。
        # 这里为了简化，我们只获取了第一批。
        print(f"  已获取用户 {handle} 最近的 {len(submissions)} 条记录进行分析。")
        time.sleep(1) # CF API有频率限制，礼貌性等待

    except Exception as e:
        print(f"错误: 请求用户 {handle} 数据时发生网络或解析错误: {e}")
            
    return recent_submissions


def format_cf_problem_url(submission):
    """根据提交信息构造CF题目链接"""
    contest_id = submission['problem'].get('contestId')
    problem_index = submission['problem'].get('index')
    if contest_id and problem_index:
        # CF的Gym题目和普通比赛题目URL格式不同
        if contest_id >= 100000: # Gym题目
            return f"https://codeforces.com/gym/{contest_id}/problem/{problem_index}"
        else: # 普通比赛
            return f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}"
    return "链接构造失败"


def main():
    """主函数，执行整个流程"""
    if not CF_HANDLES_TO_CHECK:
        print("【运行提醒】请先在脚本顶部的 CF_HANDLES_TO_CHECK 列表中填写至少一个Codeforces用户名。")
        return

    # 计算7天前的时间戳
    seven_days_ago_timestamp = (datetime.now() - timedelta(days=7)).timestamp()

    all_recent_submissions = []
    for handle in CF_HANDLES_TO_CHECK:
        user_recent_submissions = get_cf_recent_ac(handle, seven_days_ago_timestamp)
        all_recent_submissions.extend(user_recent_submissions)
    
    if not all_recent_submissions:
        print("\n查询完毕：在过去7天内，所有指定用户都没有新的 Accepted 提交。")
        return

    # 1. 按提交时间对所有记录进行降序排序
    all_recent_submissions.sort(key=lambda r: r['creationTimeSeconds'], reverse=True)

    # 2. 核心去重逻辑：确保每个题目只出现一次
    unique_top_submissions = []
    seen_problem_ids = set()

    for sub in all_recent_submissions:
        # CF中，一个题目的唯一标识是 (contestId, index) 的组合
        problem_id = (sub['problem'].get('contestId'), sub['problem'].get('index'))
        
        if problem_id not in seen_problem_ids:
            unique_top_submissions.append(sub)
            seen_problem_ids.add(problem_id)
        
        if len(unique_top_submissions) >= 10:
            break

    # 3. 格式化并打印去重后的最新记录
    print("\n====================【CF 最近一周内最新AC记录 (每题仅计一次)】====================")
    
    if not unique_top_submissions:
        print("\n在过去7天内，所有指定用户都没有新的、不重复的 Accepted 提交。")
    
    for sub in unique_top_submissions:
        user_name = sub['author']['members'][0]['handle']
        problem_title = sub['problem'].get('name', 'N/A')
        problem_url = format_cf_problem_url(sub)
        
        submit_timestamp = sub['creationTimeSeconds']
        readable_time = datetime.fromtimestamp(submit_timestamp).strftime('%Y-%m-%d %H:%M')

        print(f"\n用户 '{user_name}' 在 {readable_time} 通过了题目:")
        print(f"  - 标题: {problem_title}")
        print(f"  - 链接: {problem_url}")
        
    print("\n================================================================================")


if __name__ == "__main__":
    main()
