# 文件路径: acm-helper-plugin/main.py

import asyncio
import aiohttp
import time
from pathlib import Path
import aiosqlite
from multiprocessing import Process
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain

# 请在类顶层或合适位置定义这个映射
luogu_difficulty_map = {0: "未评定", 1: "入门", 2: "普及-", 3: "普及/提高-", 4: "普及+/提高", 5: "提高+/省选-", 6: "省选/NOI-", 7: "NOI/NOI+/CTSC"}

# 从我们的 webui.py 导入 run_server 函数
from .webui import run_server 

@register("acm_helper", "YourName", "一个强大的 ACM 训练助手", "1.0.0")
class AcmHelperPlugin(Star):
    db: aiosqlite.Connection
    db_path: Path
    webui_process: Process | None = None
    webui_port: int = 8088
    scheduler: AsyncIOScheduler
    notification_group_id: str | None = None

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        
        # --- 加载所有配置 ---
        self.webui_port = self.config.get("webui_port", 8088)
        self.notification_group_id = self.config.get("notification_group_id")
        
        # 加载洛谷认证信息
        self.luogu_cookie = self.config.get("luogu_cookie")
        self.luogu_csrf_token = self.config.get("luogu_csrf_token")
        
        # 加载CF认证信息 (可选)
        self.cf_api_key = self.config.get("cf_api_key")
        self.cf_api_secret = self.config.get("cf_api_secret")

    async def initialize(self):
        """插件初始化时调用"""
        logger.info("ACM 助手插件开始初始化 (V3.0)...")
        await self.connect_db()

        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        
        # 1. 15分钟一次的后台数据同步任务
        self.scheduler.add_job(self.sync_all_users_data, 'interval', minutes=15, id='sync_data_job')
        
        # 2. 每小时整点执行的“小时榜”播报任务
        if self.notification_group_id:
            logger.info(f" -> 小时榜播报已启用，将推送到群：{self.notification_group_id}")
            self.scheduler.add_job(self.report_hourly_solves, 'cron', hour='*', minute='0', id='hourly_report_job')
        else:
            logger.warning(" -> 未配置 notification_group_id，小时榜播报功能已禁用。")
        
        self.scheduler.start()
        
        # --- 临时测试代码 ---
        logger.info("----------- 为了立即测试，手动触发一次数据同步... -----------")
        await self.sync_all_users_data()
        logger.info("----------- 手动同步任务已调用，请检查后续日志。 -----------")
        # --- 临时测试代码结束 ---

        logger.info("✅ ACM 助手插件初始化成功！")

    async def terminate(self):
        """插件关闭/卸载时调用"""
        logger.info("正在关闭 ACM 助手插件...")
        if hasattr(self, 'scheduler') and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info(" -> 定时任务已关闭。")
        
        await self.stop_webui_process()
        if hasattr(self, 'db') and self.db:
            await self.db.close()
        logger.info("ACM 插件已安全关闭。")

    async def connect_db(self):
        """连接数据库并创建表"""
        self.db_path = Path(__file__).parent / "data" / "acm_helper.db"
        self.db_path.parent.mkdir(exist_ok=True)
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        logger.info(f" -> 数据库已连接: {self.db_path}")

        await self.db.execute("CREATE TABLE IF NOT EXISTS users (qq_id TEXT PRIMARY KEY, name TEXT NOT NULL, cf_handle TEXT, luogu_id TEXT, status TEXT, school TEXT);")
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_qq_id TEXT NOT NULL,
                platform TEXT NOT NULL, problem_id TEXT NOT NULL, problem_name TEXT,
                problem_rating TEXT, problem_url TEXT, submit_time INTEGER NOT NULL,
                UNIQUE(user_qq_id, platform, problem_id)
            );
        """)
        await self.db.commit()

    # --- WebUI 控制 ---
    async def start_webui_process(self):
        if self.webui_process and self.webui_process.is_alive():
            return f"管理后台已在运行！\n访问: http://<你的服务器IP>:{self.webui_port}"
        
        logger.info(f"正在端口 {self.webui_port} 上启动 WebUI 子进程...")
        self.webui_process = Process(target=run_server, args=(str(self.db_path), self.webui_port))
        self.webui_process.start()
        await asyncio.sleep(3)

        if self.webui_process.is_alive():
            logger.info(f"WebUI 子进程已启动, PID: {self.webui_process.pid}")
            return f"✨ 管理后台已启动！\n请访问: http://<你的服务器IP>:{self.webui_port}"
        else:
            logger.error("WebUI 子进程启动失败！请检查日志。")
            return "❌ 后台启动失败，请检查控制台日志。"

    async def stop_webui_process(self):
        if not self.webui_process or not self.webui_process.is_alive():
            return "管理后台未在运行。"
        
        logger.info(f"正在终止 WebUI 子进程 (PID: {self.webui_process.pid})...")
        self.webui_process.terminate()
        self.webui_process.join(timeout=5)
        if self.webui_process.is_alive():
            self.webui_process.kill()
        self.webui_process = None
        logger.info("WebUI 子进程已终止。")
        return "✅ 管理后台已关闭。"

    # --- 数据同步核心方法 ---
    async def sync_all_users_data(self):
        """（V3.2 - 逻辑修正版）同步所有用户的CF和洛谷数据到数据库"""
        logger.info("[数据同步] 开始执行15分钟一次的数据同步任务...")
        async with self.db.execute("SELECT * FROM users WHERE cf_handle IS NOT NULL OR luogu_id IS NOT NULL") as cursor:
            users_to_sync = await cursor.fetchall()
        
        if not users_to_sync: return
        total_new_solves = 0
        async with aiohttp.ClientSession() as session:
            for user in users_to_sync:
                user_new_count = 0
                if user['cf_handle']:
                    # --- 修正点 ---
                    # 直接获取返回的数字，并累加
                    cf_added = await self.fetch_cf_submissions(session, user)
                    user_new_count += cf_added
                if user['luogu_id']:
                    # --- 修正点 ---
                    lg_added = await self.fetch_luogu_submissions(session, user)
                    user_new_count += lg_added
                
                if user_new_count > 0:
                    logger.info(f"为用户 {user['name']} 同步了 {user_new_count} 条新记录。")
                    total_new_solves += user_new_count
        logger.info(f"[数据同步] 任务完成，共新增 {total_new_solves} 条记录。")

    async def fetch_cf_submissions(self, session: aiohttp.ClientSession, user_row: aiosqlite.Row) -> int:
        """【V3.1 - 语法修正版】获取单个CF用户的近期AC记录并入库"""
        handle, qq_id = user_row['cf_handle'], user_row['qq_id']
        added_count = 0
        cutoff_timestamp = int(time.time()) - (7 * 24 * 60 * 60)
        
        url = f"https://codeforces.com/api/user.status?handle={handle}&from=1&count=100"
        
        try:
            async with session.get(url, timeout=15) as response:
                response.raise_for_status()
                data = await response.json()
            if data.get('status') != 'OK':
                logger.error(f"请求 CF API 失败 (用户: {handle}): {data.get('comment')}")
                return 0
            submissions = data.get('result', [])
            insert_tasks = []
            for sub in submissions:
                if sub.get('verdict') == 'OK' and sub['creationTimeSeconds'] > cutoff_timestamp:
                    prob = sub['problem']
                    pid = f"{prob.get('contestId')}{prob.get('index')}"
                    async with self.db.execute("SELECT 1 FROM submissions WHERE user_qq_id = ? AND platform = 'codeforces' AND problem_id = ?", (qq_id, pid)) as c:
                        if not await c.fetchone():
                            url_part = f"gym/{prob['contestId']}/problem/{prob['index']}" if prob.get('contestId', 0) >= 100000 else f"problemset/problem/{prob['contestId']}/{prob['index']}"
                            problem_url = f"https://codeforces.com/{url_part}"
                            insert_tasks.append((qq_id, 'codeforces', pid, prob.get('name'), str(prob.get('rating', -1)), problem_url, sub['creationTimeSeconds']))
                elif sub['creationTimeSeconds'] <= cutoff_timestamp:
                    break
            
            if insert_tasks:
                # --- 语法修正点 & 补全SQL ---
                await self.db.executemany(
                    "INSERT INTO submissions (user_qq_id, platform, problem_id, problem_name, problem_rating, problem_url, submit_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    insert_tasks
                )
                await self.db.commit()
                added_count += len(insert_tasks)
        
        except Exception as e:
            logger.error(f"处理 CF 用户 {handle} 时出错: {e}")
        return added_count
    async def fetch_luogu_submissions(self, session: aiohttp.ClientSession, user_row: aiosqlite.Row) -> int:
        """【V3.1 - 语法修正版】获取单个洛谷用户的近期AC记录并入库"""
        luogu_uid, qq_id = user_row['luogu_id'], user_row['qq_id']
        added_count = 0
        if not self.luogu_cookie or not self.luogu_csrf_token:
            if not hasattr(self, '_luogu_auth_warned'):
                logger.warning("洛谷 Cookie 或 CSRF-Token 未配置，已跳过洛谷同步。")
                self._luogu_auth_warned = True
            return 0
        
        headers = { 'User-Agent': 'Mozilla/5.0 ...', 'Cookie': self.luogu_cookie, 'x-csrf-token': self.luogu_csrf_token } # User-Agent省略
        page = 1
        cutoff_timestamp = int(time.time()) - (7 * 24 * 60 * 60)
        stop_fetching = False
        while not stop_fetching:
            url = f"https://www.luogu.com.cn/record/list?user={luogu_uid}&page={page}&status=12&_contentOnly=1"
            try:
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 403:
                        logger.error(f"洛谷API拒绝访问(403)，请检查 Cookie 和 CSRF-Token 是否正确或已过期。")
                        return 0
                    response.raise_for_status()
                    data = await response.json()
                
                records_on_page = data.get('currentData', {}).get('records', {}).get('result', [])
                if not records_on_page: break
                insert_tasks = []
                for record in records_on_page:
                    if record['submitTime'] > cutoff_timestamp:
                        pid = record['problem']['pid']
                        async with self.db.execute("SELECT 1 FROM submissions WHERE user_qq_id = ? AND platform = 'luogu' AND problem_id = ?", (qq_id, pid)) as c:
                            if not await c.fetchone():
                                difficulty = luogu_difficulty_map.get(record['problem'].get('difficulty', 0), "未知")
                                insert_tasks.append((qq_id, 'luogu', pid, record['problem']['title'], difficulty, f"https://www.luogu.com.cn/problem/{pid}", record['submitTime']))
                    else:
                        stop_fetching = True
                        break
                
                if insert_tasks:
                    # --- 语法修正点 & 补全SQL ---
                    await self.db.executemany(
                        "INSERT INTO submissions (user_qq_id, platform, problem_id, problem_name, problem_rating, problem_url, submit_time) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        insert_tasks
                    )
                    await self.db.commit()
                    added_count += len(insert_tasks)
                page += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"处理洛谷用户 {luogu_uid} 第 {page} 页时出错: {e}")
                break
        
        return added_count
    
    # --- 小时榜播报 ---
    async def report_hourly_solves(self):
        time_since = int(time.time()) - 3600
        async with self.db.execute(
            "SELECT s.problem_name, s.platform, s.problem_rating, s.problem_url, s.submit_time, u.name as user_name FROM submissions s JOIN users u ON s.user_qq_id = u.qq_id WHERE s.submit_time >= ? ORDER BY s.submit_time DESC LIMIT 10",
            (time_since,)
        ) as cursor:
            recent_solves = await cursor.fetchall()
        
        if not recent_solves: return

        parts = [f"📖 过去一小时内过题速报 (Top {len(recent_solves)}):"]
        for solve in recent_solves:
            time_str = time.strftime('%H:%M', time.localtime(solve['submit_time']))
            parts.append(f"\n👤 {solve['user_name']} 在 {time_str} 通过了\n💻 {solve['platform']} - {solve['problem_name']}\n📈 难度: {solve['problem_rating']}\n🔗 {solve['problem_url']}")
        
        try:
            await self.context.send_message(MessageChain([Plain("\n".join(parts))]), self.notification_group_id, "qq_group")
            logger.info(f"成功发送 {len(recent_solves)} 条小时榜过题通知到群 {self.notification_group_id}")
        except Exception as e:
            logger.error(f"发送小时榜通知失败: {e}")

    # --- QQ 命令组 ---
    @filter.command_group("acm")
    def acm_manager(self):
        """ACM 助手命令组"""
        pass

    @acm_manager.command("后台启动")
    async def cmd_start_webui(self, event: AstrMessageEvent):
        msg = await self.start_webui_process()
        yield event.plain_result(msg)

    @acm_manager.command("后台关闭")
    async def cmd_stop_webui(self, event: AstrMessageEvent):
        msg = await self.stop_webui_process()
        yield event.plain_result(msg)

    @acm_manager.command("rank", "显示排行榜")
    async def cmd_show_rank(self, event: AstrMessageEvent):
        """在群聊中显示当前排行榜Top10 (去重版)"""
        seven_days_ago = int(time.time()) - (7 * 24 * 60 * 60)
        async with self.db.execute(
            """
            SELECT
                u.name,
                -- 【核心去重优化】使用 COUNT(DISTINCT ...)
                COUNT(DISTINCT CASE WHEN s.submit_time >= ? THEN s.problem_id ELSE NULL END) as total_count
            FROM users u
            LEFT JOIN submissions s ON u.qq_id = s.user_qq_id
            GROUP BY u.qq_id
            ORDER BY total_count DESC, u.name ASC
            LIMIT 10
            """, (seven_days_ago,)
        ) as cursor:
            top_ten = await cursor.fetchall()
        if not top_ten:
            yield event.plain_result("排行榜暂无数据。")
            return
        
        parts = ["🏆 近 7 日刷题排行榜 Top 10 🏆"]
        emojis = ["🥇", "🥈", "🥉", "4.", "5.", "6.", "7.", "8.", "9.", "10."]
        for i, user in enumerate(top_ten):
            parts.append(f"{emojis[i]} {user['name']}: {user['total_count']} 题")
        yield event.plain_result("\n".join(parts))