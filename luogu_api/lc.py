import requests
import json
import time
from datetime import datetime, timedelta

# ============================ 配置区域 START ============================

# 在这里填入你需要查询的所有 LeetCode 中国站用户名
LEETCODE_CN_USERNAMES_TO_CHECK = [
    "fei-cun-yu-xian-shi-zhi-yi",
    # "li-kou-jia-suan-fa", # 你的用户名
]

# 在这里粘贴你从浏览器 (leetcode.cn) 获取的身份凭证
# 关键！获取方式请参考脚本下方的详细说明
LEETCODE_CN_COOKIE = "gr_user_id=f91e08f4-04ec-4c23-9496-833111c9a99b; _bl_uid=4ymswf3zgbUeUU7424y1xb1r6mjh; a2873925c34ecbd2_gr_last_sent_cs1=fei-cun-yu-xian-shi-zhi-yi; _ga_PDVPZYN3CW=GS2.1.s1757659712$o2$g1$t1757659789$j59$l0$h0; aliyungf_tc=c0afbb12083d4c3b557b9f396a872b61c65077469ae37c6955fb39901f7ee91d; sl-session=+WQ4dzvC9WjN2bJ1d9QMOg==; Hm_lvt_f0faad39bcf8471e3ab3ef70125152c3=1760850114; HMACCOUNT=932378D423C14188; a2873925c34ecbd2_gr_session_id=e040274b-ebe5-4ac7-aa88-11be27791c19; a2873925c34ecbd2_gr_last_sent_sid_with_cs1=e040274b-ebe5-4ac7-aa88-11be27791c19; a2873925c34ecbd2_gr_session_id_sent_vst=e040274b-ebe5-4ac7-aa88-11be27791c19; _ga=GA1.2.795351928.1757654625; _gid=GA1.2.485880408.1760850114; _gat=1; Hm_lpvt_f0faad39bcf8471e3ab3ef70125152c3=1760850117; a2873925c34ecbd2_gr_cs1=fei-cun-yu-xian-shi-zhi-yi; csrftoken=ubVNyPxFGQHA0xxwl0a0d2aP7SIikF7wnDqmN3ehFgvIh8RXOgGvn24cBGRgfMBv; tfstk=g4erF9cPUTBPuF8fFrHe0h9OV9k-Kv7_EJgIxkqnV40uRgpExy4Yd7ZhyWz4RyeSP0ZIx200o4a7Nka22-zwdL_RwkvEdvb15O6_2uMKKN6n6ClkycoMt9GkEED-AU-fHwX_2uKmKN_1COteEkdq-24nZjYmxqmoxL4HmI0xvDYoxLj4mq3DEevorocmXcTnKv43mioKo0DnZyqc0D3m-xarKALsjbjVdhyZoGWxZVqoupvwXDllOkRBIdvx2bui-qvh4-oraVquepxU7m2b3fGXA1H0XSao0AWXZAq4tPPgJ1OxUkVuJjzRkIubi8En-b-HCoraq5D0dMxtgrmEsvc2xpqqe2zUEAXMumF0VW28zHJn28wsTVhVxphInRGgsz-dXoDoxyhTdNp-rkqTB5MNhQDg0W4aTgl6JmXhOJFy-BloDmu10iR0TJQY6YJsfBdKwnnq5ghH9Bhu2mu1mZOp9b9o0Vsls; LEETCODE_SESSION=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJfYXV0aF91c2VyX2lkIjoiNDc4MjAyNyIsIl9hdXRoX3VzZXJfYmFja2VuZCI6ImRqYW5nby5jb250cmliLmF1dGguYmFja2VuZHMuTW9kZWxCYWNrZW5kIiwiX2F1dGhfdXNlcl9oYXNoIjoiYjI2MDg4ZmE0ZmNkYzViZmVmYWU4ZDFmODAyN2E5MWU0MDcxNDM4M2M4ZjliNDE2ZTMwNmMxYzRiMTNjZGI1NSIsImlkIjo0NzgyMDI3LCJlbWFpbCI6IiIsInVzZXJuYW1lIjoiZmVpLWN1bi15dS14aWFuLXNoaS16aGkteWkiLCJ1c2VyX3NsdWciOiJmZWktY3VuLXl1LXhpYW4tc2hpLXpoaS15aSIsImF2YXRhciI6Imh0dHBzOi8vYXNzZXRzLmxlZXRjb2RlLmNuL2FsaXl1bi1sYy11cGxvYWQvdXNlcnMvZmVpLWN1bi15dS14aWFuLXNoaS16aGkteWkvYXZhdGFyXzE2OTU2MTcwODkucG5nIiwicGhvbmVfdmVyaWZpZWQiOnRydWUsImRldmljZV9pZCI6IjY1NDcyZTZkMDkzMjQ4Y2VkYzA3MmQ4ZjIyYTE1YjMxIiwiaXAiOiIxODIuMTE4LjIzOS4yMDAiLCJfdGltZXN0YW1wIjoxNzYwODUwMTM4LjczMTgwMDgsImV4cGlyZWRfdGltZV8iOjE3NjM0MDYwMDAsInZlcnNpb25fa2V5XyI6MSwibGF0ZXN0X3RpbWVzdGFtcF8iOjE3NjA4NTAxNDF9.8RbU9UXbm-TLjsjrBHOgezHJ5izLMLRWTw_6bYt6hEU"
LEETCODE_CN_CSRFTOKEN = "ubVNyPxFGQHA0xxwl0a0d2aP7SIikF7wnDqmN3ehFgvIh8RXOgGvn24cBGRgfMBv"

# ============================ 配置区域 END ============================


# 这是要发送给 LeetCode GraphQL API 的查询模板，与国际版通用
RECENT_SUBMISSIONS_QUERY = """
query userProfileSubmissions($userSlug: String!, $offset: Int!, $limit: Int!) {
    userProfileSubmissions(userSlug: $userSlug, offset: $offset, limit: $limit) {
        submissions {
            title
            titleSlug
            timestamp
            statusDisplay
            lang
        }
    }
}
"""

def get_leetcode_cn_recent_ac(username, session, cutoff_timestamp):
    """
    【高效版】为单个 LeetCode 中国站用户获取最近一周内 'Accepted' 的记录。
    """
    recent_submissions = []
    print(f"--- 开始智能查询用户 {username} 的近期 AC 记录 ---")

    # 关键修改 1: API URL 指向中国站
    graphql_url = "https://leetcode.cn/graphql/"
    offset = 0
    limit = 20 # LeetCode 每次最多返回20条

    while True:
        # 构造 GraphQL 请求体 (注意：变量名可能为 userSlug)
        payload = {
            "query": RECENT_SUBMISSIONS_QUERY,
            "variables": {
                "userSlug": username, # 使用 userSlug，更标准
                "offset": offset,
                "limit": limit
            },
            "operationName": "userProfileSubmissions"
        }

        try:
            response = session.post(graphql_url, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            # 检查是否有数据错误，例如用户不存在
            if 'errors' in data:
                print(f"错误: API返回错误，可能是用户名 '{username}' 不存在或无效。")
                print(f"  > API响应: {data['errors']}")
                break

            submissions = data.get('data', {}).get('userProfileSubmissions', {}).get('submissions')
            if submissions is None:
                # 这种情况可能是用户存在但没有任何提交记录
                print(f"  用户 {username} 没有任何提交记录。")
                break
            if not submissions:
                print(f"  用户 {username} 的记录已全部获取完毕。")
                break
            
            stop_fetching = False
            for sub in submissions:
                if sub.get('statusDisplay') != 'Accepted' and sub.get('statusDisplay') != '通过':
                    continue

                submit_time = int(sub.get('timestamp', 0))
                
                if submit_time > cutoff_timestamp:
                    recent_submissions.append(sub)
                else:
                    stop_fetching = True
                    break
            
            if stop_fetching:
                print(f"  已找到7天前的记录边界，停止为用户 {username} 获取更多数据。")
                break
            
            print(f"  已获取 {offset + len(submissions)} 条记录 (全部为近期记录)...")
            offset += limit
            time.sleep(1)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                print(f"错误 (400 Bad Request): 请求用户 {username} 时发生客户端错误。")
                print(">>> 极有可能是 Cookie 或 CSRF Token 已过期或不正确。请重新获取！")
            else:
                 print(f"错误: 请求用户 {username} 时发生HTTP错误: {e}")
            break
        except Exception as e:
            print(f"错误: 请求用户 {username} 的数据时发生未知错误: {e}")
            break
            
    return recent_submissions


def main():
    """主函数"""
    if "在此处粘贴" in LEETCODE_CN_COOKIE or "在此处粘贴" in LEETCODE_CN_CSRFTOKEN:
        print("【运行失败】请先打开Python脚本，在顶部的“配置区域”填写你的 LeetCode 中国站 Cookie 和 CSRF Token！")
        return

    session = requests.Session()
    # 关键修改 2 & 3: 更新 Headers
    session.headers.update({
        'Cookie': LEETCODE_CN_COOKIE,
        'x-csrftoken': LEETCODE_CN_CSRFTOKEN,
        'Content-Type': 'application/json',
        'Referer': 'https://leetcode.cn/', # Referer 必须指向中国站
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    })

    seven_days_ago_timestamp = (datetime.now() - timedelta(days=7)).timestamp()

    all_recent_submissions = []
    for username in LEETCODE_CN_USERNAMES_TO_CHECK:
        all_recent_submissions.extend(
            get_leetcode_cn_recent_ac(username, session, seven_days_ago_timestamp)
        )
    
    if not all_recent_submissions:
        print("\n查询完毕：在过去7天内，所有指定用户都没有新的通过(Accepted)提交。")
        return

    all_recent_submissions.sort(key=lambda r: int(r['timestamp']), reverse=True)

    unique_top_submissions = []
    seen_problem_slugs = set()

    for sub in all_recent_submissions:
        slug = sub.get('titleSlug')
        if slug and slug not in seen_problem_slugs:
            unique_top_submissions.append(sub)
            seen_problem_slugs.add(slug)
        
        if len(unique_top_submissions) >= 10:
            break

    print("\n====================【力扣(cn) 最近一周内最新AC记录 (每题仅计一次)】====================")
    
    if not unique_top_submissions:
        print("\n在过去7天内，所有指定用户都没有新的、不重复的通过(Accepted)提交。")
    
    for sub in unique_top_submissions:
        problem_title = sub.get('title')
        problem_slug = sub.get('titleSlug')
        # 关键修改 4: 题目URL指向中国站
        problem_url = f"https://leetcode.cn/problems/{problem_slug}/"
        
        submit_timestamp = int(sub.get('timestamp'))
        readable_time = datetime.fromtimestamp(submit_timestamp).strftime('%Y-%m-%d %H:%M')
        
        # LeetCode API 不在提交记录里返回用户名，所以我们不在每条记录里打印
        print(f"\n在 {readable_time}，有新题目被通过:")
        print(f"  - 标题: {problem_title}")
        print(f"  - 链接: {problem_url}")
        
    print("\n=====================================================================================")
main()