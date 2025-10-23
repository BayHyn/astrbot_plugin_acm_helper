# 文件路径: acm-helper-plugin/core/crawler.py (V12.0 完整版)

import aiohttp
import time
import aiosqlite
import asyncio
import hashlib
import random
from astrbot.api import logger

luogu_difficulty_map = {0: "未评定", 1: "入门", 2: "普及-", 3: "普及/提高-", 4: "普及+/提高", 5: "提高+/省选-", 6: "省选/NOI-", 7: "NOI/NOI+/CTSC"}

class Crawler:
    @staticmethod
    def _generate_cf_api_sig(method_name: str, params: dict, api_key: str, api_secret: str) -> str:
        rand = ''.join([chr(random.randint(ord('a'), ord('z'))) for _ in range(6)])
        param_str = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        text = f"{rand}/{method_name}?{param_str}#{api_secret}"
        sha512_hash = hashlib.sha512(text.encode('utf-8')).hexdigest()
        return f"{rand}{sha512_hash}"

    @staticmethod
    async def fetch_luogu_submissions(session: aiohttp.ClientSession, user_row, start_timestamp: int, db: aiosqlite.Connection, config: dict) -> int:
        luogu_uid, qq_id = user_row['luogu_id'], user_row['qq_id']
        added_count = 0
        luogu_cookie = config.get("luogu_cookie")
        luogu_csrf_token = config.get("luogu_csrf_token")
        
        if not luogu_cookie or not luogu_csrf_token:
            logger.warning("[同步模块] 洛谷 Cookie 或 CSRF-Token 未配置，跳过。")
            return 0
            
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Cookie': luogu_cookie, 'x-csrf-token': luogu_csrf_token}
        page, stop_fetching = 1, False

        while not stop_fetching:
            url = f"https://www.luogu.com.cn/record/list?user={luogu_uid}&page={page}&status=12&_contentOnly=1"
            try:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 403:
                        logger.error(f"洛谷API拒绝访问(403)，Cookie可能已过期。")
                        break
                    response.raise_for_status()
                    data = await response.json()
                
                records = data.get('currentData', {}).get('records', {}).get('result', [])
                if not records:
                    break

                insert_tasks = []
                for record in records:
                    if record['submitTime'] >= start_timestamp:
                        pid = record['problem']['pid']
                        async with db.execute("SELECT 1 FROM submissions WHERE user_qq_id = ? AND platform = 'luogu' AND problem_id = ?", (qq_id, pid)) as c:
                            if not await c.fetchone():
                                difficulty = luogu_difficulty_map.get(record['problem'].get('difficulty', 0), "未知")
                                insert_tasks.append((qq_id, 'luogu', pid, record['problem']['title'], difficulty, f"https://www.luogu.com.cn/problem/{pid}", record['submitTime']))
                    else:
                        stop_fetching = True
                        break
                
                if insert_tasks:
                    await db.executemany("INSERT INTO submissions (user_qq_id, platform, problem_id, problem_name, problem_rating, problem_url, submit_time) VALUES (?, ?, ?, ?, ?, ?, ?)", insert_tasks)
                    await db.commit()
                    added_count += len(insert_tasks)
                page += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"处理洛谷用户 {luogu_uid} 第 {page} 页时出错: {e}")
                break
        return added_count

    @staticmethod
    async def fetch_cf_submissions(session: aiohttp.ClientSession, user_row: aiosqlite.Row, start_timestamp: int, db: aiosqlite.Connection, config: dict) -> int:
        handle = user_row['cf_handle']; qq_id = user_row['qq_id']
        api_key = config.get("cf_api_key"); api_secret = config.get("cf_api_secret")
        method_name = "user.status"; params = {"handle": handle, "from": "1", "count": "100"}
        
        if api_key and api_secret:
            params["apiKey"] = api_key; params["time"] = str(int(time.time()))
            params["apiSig"] = Crawler._generate_cf_api_sig(method_name, params, api_key, api_secret)
        
        url = f"https://codeforces.com/api/{method_name}?" + '&'.join([f"{k}={v}" for k, v in params.items()])
        
        added_count = 0
        try:
            async with session.get(url, timeout=15) as response:
                response.raise_for_status(); data = await response.json()
            if data.get('status') != 'OK':
                logger.error(f"CF API 请求失败 (用户: {handle}): {data.get('comment')}")
                return 0

            insert_tasks, processed_in_sync = [], set()
            for sub in data.get('result', []):
                if not isinstance(sub, dict) or sub.get('verdict') != 'OK' or 'problem' not in sub: continue
                
                prob = sub.get('problem')
                if not isinstance(prob, dict): continue

                if sub.get('creationTimeSeconds', 0) >= start_timestamp:
                    problem_name, contest_id, problem_index = prob.get('name'), prob.get('contestId'), prob.get('index')
                    if not problem_name and not (contest_id and problem_index): continue
                    
                    if contest_id and problem_index:
                        stable_pid = f"cf_{contest_id}{problem_index}"
                    else:
                        name_norm = ''.join(filter(str.isalnum, problem_name or '')).lower()
                        if not name_norm: continue
                        stable_pid = f"cf_{name_norm}_{prob.get('rating', -1)}"
                        
                    if stable_pid in processed_in_sync: continue
                    
                    async with db.execute("SELECT 1 FROM submissions WHERE user_qq_id = ? AND platform = 'codeforces' AND problem_id = ?", (qq_id, stable_pid)) as c:
                        if not await c.fetchone():
                            url_part = f"gym/{contest_id}/problem/{problem_index}" if contest_id and contest_id >= 100000 else f"problemset/problem/{contest_id}/{problem_index}"
                            problem_url = f"https://codeforces.com/{url_part}" if contest_id and problem_index else ""
                            insert_tasks.append((qq_id, 'codeforces', stable_pid, problem_name or "Unknown Problem", str(prob.get('rating', -1)), problem_url, sub['creationTimeSeconds']))
                            processed_in_sync.add(stable_pid)
                elif sub.get('creationTimeSeconds', 0) < start_timestamp:
                    break
                    
            if insert_tasks:
                await db.executemany("INSERT INTO submissions (user_qq_id, platform, problem_id, problem_name, problem_rating, problem_url, submit_time) VALUES (?, ?, ?, ?, ?, ?, ?)", insert_tasks)
                await db.commit()
                added_count += len(insert_tasks)

        except Exception as e:
            logger.error(f"处理 CF 用户 {handle} 时发生严重错误: {e}", exc_info=True)
            
        return added_count
    
    @staticmethod
    async def fetch_cf_submissions_paginated(session: aiohttp.ClientSession, user_row: aiosqlite.Row, start_timestamp: int, db: aiosqlite.Connection, config: dict) -> int:
        """深度、分页的CF爬虫，获取指定时间内所有记录。用于/acm sql命令。"""
        handle = user_row['cf_handle']; qq_id = user_row['qq_id']
        api_key = config.get("cf_api_key"); api_secret = config.get("cf_api_secret")
        method_name = "user.status"
        
        from_index, stop_fetching = 1, False
        all_insert_tasks = []; processed_in_sync = set()
        while not stop_fetching:
            params = {"handle": handle, "from": str(from_index), "count": "100"}
            if api_key and api_secret:
                params["apiKey"] = api_key; params["time"] = str(int(time.time()))
                params["apiSig"] = Crawler._generate_cf_api_sig(method_name, params, api_key, api_secret)
            
            url = f"https://codeforces.com/api/{method_name}?" + '&'.join([f"{k}={v}" for k, v in params.items()])
            
            try:
                async with session.get(url, timeout=30) as response:
                    response.raise_for_status(); data = await response.json()
                if data.get('status') != 'OK': logger.error(f"CF API 请求失败 (用户: {handle}, 页码: {from_index // 100 + 1}): {data.get('comment')}"); break
                
                subs = data.get('result', [])
                if not subs: break
                
                page_insert_tasks = []
                for sub in subs:
                    if not isinstance(sub, dict) or sub.get('verdict') != 'OK' or 'problem' not in sub: continue
                    prob = sub.get('problem');
                    if not isinstance(prob, dict): continue
                    submission_time = sub.get('creationTimeSeconds', 0)
                    if submission_time >= start_timestamp:
                        problem_name, contest_id, problem_index = prob.get('name'), prob.get('contestId'), prob.get('index')
                        if not all([problem_name, contest_id, problem_index]): continue
                        stable_pid = f"cf_{contest_id}{problem_index}"
                        if stable_pid in processed_in_sync: continue
                        async with db.execute("SELECT 1 FROM submissions WHERE user_qq_id = ? AND platform = 'codeforces' AND problem_id = ?", (qq_id, stable_pid)) as c:
                            if not await c.fetchone():
                                url_part = f"gym/{contest_id}/problem/{problem_index}" if contest_id >= 100000 else f"problemset/problem/{contest_id}/{problem_index}"
                                problem_url = f"https://codeforces.com/{url_part}"
                                page_insert_tasks.append((qq_id, 'codeforces', stable_pid, problem_name, str(prob.get('rating', -1)), problem_url, submission_time))
                                processed_in_sync.add(stable_pid)
                    else:
                        stop_fetching = True
                
                if page_insert_tasks: all_insert_tasks.extend(page_insert_tasks)
                from_index += 100
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"处理 CF 用户 {handle} (深度同步) 时发生错误: {e}", exc_info=False)
                break
        
        if all_insert_tasks:
            await db.executemany("INSERT OR IGNORE INTO submissions (user_qq_id, platform, problem_id, problem_name, problem_rating, problem_url, submit_time) VALUES (?, ?, ?, ?, ?, ?, ?)", all_insert_tasks)
            await db.commit()
            return len(all_insert_tasks)
        return 0
    
    @staticmethod
    async def fetch_luogu_submission(session: aiohttp.ClientSession, user_row, start_timestamp: int, db: aiosqlite.Connection, config: dict) -> int:
        luogu_uid, qq_id = user_row['luogu_id'], user_row['qq_id']
        luogu_cookie = config.get("luogu_cookie")
        luogu_csrf_token = config.get("luogu_csrf_token")
        
        if not luogu_cookie or not luogu_csrf_token:
            logger.warning("[同步模块] 洛谷 Cookie 或 CSRF-Token 未配置，跳过。")
            return 0
            
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Cookie': luogu_cookie, 'x-csrf-token': luogu_csrf_token}
        page, stop_fetching = 1, False
        
        # --- 优化1: 创建一个大列表，用于存储所有页面找到的新记录 ---
        all_insert_tasks = [] 
        # --- 优化2: 创建一个集合，用于在本次同步中去重 ---
        processed_in_sync = set()
        while not stop_fetching:
            url = f"https://www.luogu.com.cn/record/list?user={luogu_uid}&page={page}&status=12&_contentOnly=1"
            try:
                async with session.get(url, headers=headers, timeout=30) as response: # 增加超时时间
                    if response.status == 403:
                        logger.error(f"洛谷API拒绝访问(403)，Cookie可能已过期。")
                        break
                    response.raise_for_status()
                    data = await response.json()
                
                records = data.get('currentData', {}).get('records', {}).get('result', [])
                if not records:
                    break
                # --- 优化3: 创建一个临时列表，只用于存储当前页的新记录 ---
                page_insert_tasks = []
                for record in records:
                    if record['submitTime'] >= start_timestamp:
                        pid = record['problem']['pid']
                        
                        # --- 优化2的应用: 如果本次同步已经处理过此题，直接跳过 ---
                        if pid in processed_in_sync:
                            continue
                        # 检查数据库中是否已存在
                        async with db.execute("SELECT 1 FROM submissions WHERE user_qq_id = ? AND platform = 'luogu' AND problem_id = ?", (qq_id, pid)) as c:
                            if not await c.fetchone():
                                difficulty = luogu_difficulty_map.get(record['problem'].get('difficulty', 0), "未知")
                                page_insert_tasks.append((qq_id, 'luogu', pid, record['problem']['title'], difficulty, f"https://www.luogu.com.cn/problem/{pid}", record['submitTime']))
                                # 将处理过的pid加入集合
                                processed_in_sync.add(pid)
                    else:
                        stop_fetching = True
                        break
                
                # --- 优化1的应用: 将当前页的新记录汇总到大列表中 ---
                if page_insert_tasks:
                    all_insert_tasks.extend(page_insert_tasks)
                page += 1
                await asyncio.sleep(0.5) # 礼貌性延时
            except Exception as e:
                logger.error(f"处理洛谷用户 {luogu_uid} 第 {page} 页时出错: {e}")
                break
                
        # --- 优化1的应用: 所有页面处理完后，执行一次总的数据库写入 ---
        if all_insert_tasks:
            await db.executemany("INSERT OR IGNORE INTO submissions (user_qq_id, platform, problem_id, problem_name, problem_rating, problem_url, submit_time) VALUES (?, ?, ?, ?, ?, ?, ?)", all_insert_tasks)
            await db.commit()
            return len(all_insert_tasks)
            
        return 0
