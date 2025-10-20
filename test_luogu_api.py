import requests
import json
import time

def get_luogu_ac_submissions_with_auth(uid):
    """
    最终方案：直接使用从浏览器复制的 Cookie 和 CSRF-Token 进行认证，
    这是最稳定可靠的爬取方式。
    """
    
    # ------------------- 在这里粘贴你复制的内容 -------------------
    # 在英文双引号""之间，完整粘贴你从浏览器复制的值
    
    MY_COOKIE = "__client_id=d332fcf8c057c4d368f3bbde54ae244c75f2a6b2; _uid=1114798; C3VK=cb8d22"
    
    MY_CSRF_TOKEN = "1760931648:Ul+g0WFl50rk8/vFp9YI8kAqfYnSzZVlYSKIoENgbuw="
    
    # -------------------------------------------------------------
    
    # 检查一下是否已填写
    if "在此处粘贴" in MY_COOKIE or "在此处粘贴" in MY_CSRF_TOKEN:
        print("错误：请先在代码中填写你从浏览器复制的 MY_COOKIE 和 MY_CSRF_TOKEN！")
        return None

    print(f"开始使用身份凭证获取UID {uid} 的 Accepted 记录...")
    
    # 将你的凭证设置到请求头中
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0',
        'Cookie': MY_COOKIE,
        'x-csrf-token': MY_CSRF_TOKEN,
        'x-requested-with': 'XMLHttpRequest',
        'referer': f'https://www.luogu.com.cn/record/list?user={uid}&status=12' # 伪造一个来源
    }
    
    session = requests.Session()
    session.headers.update(headers)

    accepted_submissions = []
    page = 1
    
    while True:
        url = f"https://www.luogu.com.cn/record/list?user={uid}&page={page}&status=12&_contentOnly=1"
        print(f"  正在请求第 {page} 页...")
        
        try:
            response = session.get(url, timeout=15)
            
            # 检查是否因为凭证错误而被拒绝
            if response.status_code == 403:
                print("错误: 请求被拒绝(403 Forbidden)。你的 Cookie 或 CSRF-Token 可能已过期或不正确。")
                break

            response.raise_for_status()
            data = response.json()
            
            records_on_page = data.get('currentData', {}).get('records', {}).get('result', [])
            if not records_on_page:
                print("  当前页无数据，获取结束。")
                break
                
            accepted_submissions.extend(records_on_page)
            page += 1
            time.sleep(0.5) # 保持礼貌的请求间隔

        except Exception as e:
            print(f"错误: 请求第 {page} 页失败: {e}")
            break
            
    if accepted_submissions:
        print(f"获取完成！用户 {uid} 总共找到 {len(accepted_submissions)} 条 Accepted 记录。")
    
    return accepted_submissions

# --- 测试一下 ---
if __name__ == "__main__":
    test_uid = "1114798" # 你可以换成任何你想查询的UID
    ac_submissions = get_luogu_ac_submissions_with_auth(test_uid)
    
    if ac_submissions:
        print(f"\n成功获取到 {len(ac_submissions)} 条AC记录。")
        # 随便打印一条看看结果
        print("最新一条AC记录详情:", ac_submissions[0])
