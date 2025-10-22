# 文件路径: acm-helper-plugin/main.py (V18.1 最终稳定版)

import asyncio
import aiohttp
import time
from pathlib import Path
import aiosqlite
from multiprocessing import Process
import urllib.parse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.core.message.components import Plain, Image
from astrbot.core.message.message_event_result import MessageChain

try:
    from PIL import Image as PILImage, ImageDraw, ImageFont
except ImportError:
    logger.error("Pillow 库未安装！图片功能将不可用。")
    PILImage, ImageDraw, ImageFont = None, None, None

from .webui import run_server
from .core.crawler import Crawler

@register("acm_helper", "YourName", "一个强大的 ACM 训练助手", "18.1.0")
class AcmHelperPlugin(Star):
    db: aiosqlite.Connection
    db_path: Path
    webui_process: Process | None = None
    scheduler: AsyncIOScheduler
    
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.FONT_PATH = Path(__file__).parent / "resources" / "SourceHanSansSC-Bold.otf"

    async def initialize(self):
        logger.info("ACM 助手插件开始初始化 (V18.1)...")
        await self.connect_db()
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        settings = await self._get_all_settings()
        await self.reschedule_jobs(settings)
        self.scheduler.add_job(self.sync_all_users_data, 'cron', minute='*/15', id='sync_data_job')
        self.scheduler.start()
        logger.info("✅ ACM 助手插件初始化成功！")

    async def terminate(self):
        logger.info("正在关闭 ACM 助手插件...");
        if hasattr(self, 'scheduler') and self.scheduler.running: self.scheduler.shutdown()
        await self.stop_webui_process()
        if hasattr(self, 'db') and self.db: await self.db.close()
        logger.info("ACM 插件已安全关闭。")

    async def connect_db(self):
        self.db_path = Path(__file__).parent / "data" / "acm_helper.db"
        self.db_path.parent.mkdir(exist_ok=True)
        self.db = await aiosqlite.connect(self.db_path); self.db.row_factory = aiosqlite.Row
        await self.db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);")
        await self.db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('report_enabled', 'true');")
        await self.db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('report_cron_hour', '*');")
        await self.db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('report_cron_minute', '0');")
        await self.db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('hourly_report_limit', '10');")
        await self.db.execute("CREATE TABLE IF NOT EXISTS users (qq_id TEXT PRIMARY KEY, name TEXT NOT NULL, cf_handle TEXT, luogu_id TEXT, status TEXT, school TEXT, last_sync_timestamp INTEGER DEFAULT 0);")
        await self.db.execute("CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_qq_id TEXT NOT NULL, platform TEXT NOT NULL, problem_id TEXT NOT NULL, problem_name TEXT, problem_rating TEXT, problem_url TEXT, submit_time INTEGER NOT NULL, UNIQUE(user_qq_id, platform, problem_id));")
        await self.db.commit()

    async def get_setting(self, key, default=None):
        async with self.db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor: row = await cursor.fetchone(); return row['value'] if row else default

    async def set_setting(self, key, value):
        await self.db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value))); await self.db.commit()

    async def _get_all_settings(self) -> dict:
        settings = {}; 
        async with self.db.execute("SELECT key, value FROM settings") as cursor:
            async for row in cursor: settings[row['key']] = row['value']
        return settings
        
    async def reschedule_jobs(self, settings: dict):
        report_job_id = 'hourly_report_job'
        try: self.scheduler.remove_job(report_job_id)
        except JobLookupError: pass
        is_enabled = settings.get('report_enabled') == 'true'; group_id = settings.get('notification_group_id')
        cron_hour = settings.get('report_cron_hour', '*'); cron_minute = settings.get('report_cron_minute', '0')
        if is_enabled and group_id:
            try:
                trigger = CronTrigger(hour=cron_hour, minute=cron_minute, timezone="Asia/Shanghai")
                self.scheduler.add_job(self.report_hourly_solves, trigger, id=report_job_id, name="Hourly Report")
                logger.info(f"✅ 定时播报任务已更新。群号: {group_id}, CRON: [hour={cron_hour}, minute={cron_minute}]")
            except Exception as e: logger.error(f"❌ 设置定时播报失败: {e}")
        else: logger.info("ℹ️ 定时播报已禁用或未配置群号。")

    async def start_webui_process(self):
        if self.webui_process and self.webui_process.is_alive(): return f"管理后台已在运行！"
        port = self.config.get('webui_port', 8088); logger.info(f"正在端口 {port} 上启动 WebUI 子进程...")
        webui_config = {"luogu_cookie": self.config.get("luogu_cookie"),"luogu_csrf_token": self.config.get("luogu_csrf_token"), "cf_api_key": self.config.get("cf_api_key"), "cf_api_secret": self.config.get("cf_api_secret")}
        self.webui_process = Process(target=run_server, args=(str(self.db_path), port, webui_config)); self.webui_process.start(); await asyncio.sleep(2)
        if self.webui_process.is_alive(): logger.info(f"WebUI 子进程已启动, PID: {self.webui_process.pid}"); return f"✨ 管理后台已启动！\n请访问: http://<你的服务器IP>:{port}"
        else: logger.error("WebUI 子进程启动失败！"); return "❌ 后台启动失败"

    async def stop_webui_process(self):
        if not self.webui_process or not self.webui_process.is_alive(): return "管理后台未在运行。"
        logger.info(f"正在终止 WebUI 子进程 (PID: {self.webui_process.pid})..."); self.webui_process.terminate(); self.webui_process.join(timeout=5)
        if self.webui_process.is_alive(): self.webui_process.kill()
        self.webui_process = None; logger.info("WebUI 子进程已终止。"); return "✅ 管理后台已关闭。"

    async def _generate_hourly_report_message(self) -> str:
        limit = int(await self.get_setting('hourly_report_limit', 10))
        time_since = int(time.time()) - 3600
        query = "SELECT s.problem_name, s.platform, s.problem_rating, s.problem_url, s.submit_time, u.name as user_name FROM submissions s JOIN users u ON s.user_qq_id = u.qq_id WHERE s.submit_time >= ? ORDER BY s.submit_time DESC LIMIT ?"
        async with self.db.execute(query, (time_since, limit)) as cursor:
            recent_solves = await cursor.fetchall()
        if not recent_solves: return "过去一小时内没有新的过题记录哦～"
        parts = [f"📖 过去一小时内过题速报 (Top {len(recent_solves)}):"]
        for solve in recent_solves:
            time_str = time.strftime('%H:%M', time.localtime(solve['submit_time']))
            parts.append(f"\n👤 {solve['user_name']} 在 {time_str} 通过了\n💻 {solve['platform']} - {solve['problem_name']}\n📈 难度: {solve['problem_rating'] or 'N/A'}\n🔗 {solve['problem_url']}")
        return "\n".join(parts)

    async def sync_single_user(self, qq_id: str):
        async with self.db.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id,)) as cursor: user = await cursor.fetchone()
        if not user: return
        current_sync_time = int(time.time()); seven_days_ago = current_sync_time - (7 * 24 * 60 * 60)
        last_sync = user['last_sync_timestamp'] or 0; start_timestamp = seven_days_ago if last_sync == 0 else last_sync
        sync_type = "7日全量" if last_sync == 0 else "增量"; logger.info(f"  -> 为用户 {user['name']} 执行 [{sync_type}] 同步...")
        user_new_count = 0
        async with aiohttp.ClientSession() as session:
            if user['cf_handle']: user_new_count += await Crawler.fetch_cf_submissions(session, user, start_timestamp, self.db, self.config)
            if user['luogu_id']: user_new_count += await Crawler.fetch_luogu_submissions(session, user, start_timestamp, self.db, self.config)
        if user_new_count > 0: logger.info(f"    为用户 {user['name']} 同步了 {user_new_count} 条新记录。")
        await self.db.execute("UPDATE users SET last_sync_timestamp = ? WHERE qq_id = ?", (current_sync_time, user['qq_id'])); await self.db.commit()

    async def sync_all_users_data(self):
        logger.info(f"[智能同步] 开始执行 {time.strftime('%H:%M')} 周期的同步任务...")
        async with self.db.execute("SELECT qq_id FROM users WHERE cf_handle IS NOT NULL OR luogu_id IS NOT NULL") as cursor: user_rows = await cursor.fetchall()
        if not user_rows: return
        for user_row in user_rows: await self.sync_single_user(user_row['qq_id'])
        logger.info("[智能同步] 本次周期任务完成。")

    async def report_hourly_solves(self):
        message_to_send = await self._generate_hourly_report_message()
        if "没有新的过题记录" in message_to_send: logger.info("[小时榜] 无新记录。"); return
        group_id = await self.get_setting("notification_group_id")
        if not group_id: logger.warning("[小时榜] 无法发送，未配置群号。"); return
        try:
            qq_platform = self.context.get_platform("qq")
            if not qq_platform: logger.error("[小时榜] 无法获取 QQ 平台实例。"); return
            bot = qq_platform.bot
            onebot_message = [{"type": "text", "data": {"text": message_to_send}}]
            await bot.send_group_msg(group_id=int(group_id), message=onebot_message)
            logger.info(f"[小时榜] 已成功向群 {group_id} 发送播报。")
        except Exception as e: logger.error(f"发送小时榜通知失败: {e}", exc_info=True)

    async def sync_single_user_for_days(self, qq_id: str, days: int):
        async with self.db.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id,)) as cursor: user = await cursor.fetchone()
        if not user: return
        start_timestamp = int(time.time()) - (days * 24 * 60 * 60)
        logger.info(f"  -> 为用户 {user['name']} 执行 [{days}天深度] 同步...")
        user_new_count = 0
        async with aiohttp.ClientSession() as session:
            if user['cf_handle']: user_new_count += await Crawler.fetch_cf_submissions(session, user, start_timestamp, self.db, self.config)
            if user['luogu_id']: user_new_count += await Crawler.fetch_luogu_submissions(session, user, start_timestamp, self.db, self.config)
        if user_new_count > 0: logger.info(f"    为用户 {user['name']} 同步了 {user_new_count} 条新记录。")

    async def _generate_rank_image(self, title: str, users_data: list) -> bytes | str:
        if not all([PILImage, ImageDraw, ImageFont]): return "❌ 无法生成图片：Pillow 库未正确安装。"
        if not self.FONT_PATH.exists(): return f"❌ 无法生成图片：字体文件丢失 ({self.FONT_PATH})。"

        header_height = 80; row_height = 50; footer_height = 20
        width = 800
        height = header_height + row_height + len(users_data) * row_height + footer_height
        image = PILImage.new('RGB', (width, height), '#FFFFFF')
        draw = ImageDraw.Draw(image)

        try:
            font_title = ImageFont.truetype(str(self.FONT_PATH), 24)
            font_header = ImageFont.truetype(str(self.FONT_PATH), 16)
            font_body = ImageFont.truetype(str(self.FONT_PATH), 15)
        except IOError: return f"❌ 无法加载字体文件 {self.FONT_PATH}。"

        color_dark_bg = '#343a40'; color_blue_bg = '#007bff'; color_white = '#FFFFFF'
        color_light_gray_bg = '#f8f9fa'; color_text = '#212529'; color_red = '#dc3545'
        color_green = '#28a745'; color_purple = '#6f42c1'; 
        
        draw.rectangle([0, 0, width, header_height], fill=color_dark_bg)
        draw.text((width/2, header_height/2), title, font=font_title, fill=color_white, anchor='mm')
        
        table_header_y = header_height
        draw.rectangle([0, table_header_y, width, table_header_y + row_height], fill=color_blue_bg)
        
        columns = {'排名': 50, '用户名': 160, 'CF题数': 320, '洛谷题数': 460, '总题数': 600, '身份': 720}
        for text, x in columns.items():
            draw.text((x, table_header_y + row_height/2), text, font=font_header, fill=color_white, anchor='mm')

        for i, user in enumerate(users_data):
            y_start = table_header_y + row_height + i * row_height
            bg_color = color_light_gray_bg if i % 2 == 1 else '#FFFFFF'
            draw.rectangle([0, y_start, width, y_start + row_height], fill=bg_color)
            
            y_text = y_start + row_height / 2
            draw.text((columns['排名'], y_text), str(i + 1), font=font_body, fill=color_text, anchor='mm')
            
            display_name = user['user_name']
            if font_body.getlength(display_name) > 150:
                while font_body.getlength(display_name + '..') > 150: display_name = display_name[:-1]
                display_name += '..'
            draw.text((columns['用户名'], y_text), display_name, font=font_body, fill=color_text, anchor='mm')
            
            draw.text((columns['CF题数'], y_text), str(user['cf_count']), font=font_body, fill=color_red, anchor='mm')
            draw.text((columns['洛谷题数'], y_text), str(user['luogu_count']), font=font_body, fill=color_red, anchor='mm')
            draw.text((columns['总题数'], y_text), str(user['total_count']), font=font_body, fill=color_green, anchor='mm')
            draw.text((columns['身份'], y_text), user['user_status'] or 'N/A', font=font_body, fill=color_purple, anchor='mm')

        for x in list(columns.values())[1:]:
            draw.line([x - 50, table_header_y, x - 50, height - footer_height], fill='#dee2e6', width=1)

        from io import BytesIO
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()

    @staticmethod
    def _pd_cf_color(rating):
        if not isinstance(rating, int): rating = 0
        if rating < 1200: return "灰名"
        if rating < 1400: return '绿名 Pupil'
        if rating < 1600: return '青名 Specialist'
        if rating < 1900: return '蓝名 Expert'
        if rating < 2100: return '紫名 Candidate Master'
        if rating < 2300: return '橙名 Master'
        if rating < 2400: return '橙名 International Master'
        if rating < 2600: return '红名 Grandmaster'
        if rating < 3000: return '红名 International Grandmaster'
        return '黑红名 Legendary Grandmaster'

    @staticmethod
    def _format_cf_contest(contest):
        return "比赛名称：{}\n开始时间：{}\n持续时间：{}小时{:02d}分钟\n报名链接：{}".format(
            contest['name'], time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(contest['startTimeSeconds']))),
            contest['durationSeconds'] // 3600, contest['durationSeconds'] % 3600 // 60,
            f"https://codeforces.com/contestRegistration/{str(contest['id'])}"
        )

    @filter.command_group("acm")
    def acm_manager(self): pass

    @acm_manager.command("后台启动")
    async def cmd_start_webui(self, event: AstrMessageEvent): msg = await self.start_webui_process(); yield event.plain_result(msg)

    @acm_manager.command("后台关闭")
    async def cmd_stop_webui(self, event: AstrMessageEvent): msg = await self.stop_webui_process(); yield event.plain_result(msg)
    
    @acm_manager.command("hourly")
    async def cmd_report_hourly(self, event: AstrMessageEvent):
        yield event.plain_result("正在查询过去一小时的过题记录..."); report_message = await self._generate_hourly_report_message(); yield event.plain_result(report_message)
    
    @acm_manager.command("contest")
    async def cmd_get_contests(self, event: AstrMessageEvent):
        url = "https://codeforces.com/api/contest.list?gym=false"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response: response.raise_for_status(); data = await response.json()
            if data.get('status') != 'OK': yield event.plain_result("获取比赛列表失败。"); return
            upcoming_contests = [c for c in data.get('result', []) if c.get('phase') == 'BEFORE' and 'Kotlin' not in c['name'] and 'Unrated' not in c['name']]; upcoming_contests.reverse()
            if not upcoming_contests: yield event.plain_result("最近没有找到合适的 Codeforces 比赛～"); return
            res_parts = [f"找到最近的 {min(5, len(upcoming_contests))} 场 CF 比赛:"]
            for contest in upcoming_contests[:5]: res_parts.append("--------------------"); res_parts.append(self._format_cf_contest(contest))
            yield event.plain_result("\n".join(res_parts))
        except Exception as e: logger.error(f"查询 CF 比赛时出错: {e}", exc_info=True); yield event.plain_result("获取比赛列表时发生网络错误。")
    
    @acm_manager.command("status")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_status(self, event: AstrMessageEvent):
        is_enabled = await self.get_setting('report_enabled') == 'true'; group_id = await self.get_setting('notification_group_id', '未设置')
        cron_hour = await self.get_setting('report_cron_hour'); cron_minute = await self.get_setting('report_cron_minute')
        hourly_limit = await self.get_setting('hourly_report_limit', '10')
        status_text = (f"📊 ACM 助手插件当前状态:\n--------------------------\n"
                       f"  - 定时播报: {'✅ 开启' if is_enabled else '❌ 关闭'}\n"
                       f"  - 小时榜上限: {hourly_limit} 题\n"
                       f"  - 目标群聊: {group_id}\n"
                       f"  - CRON 表达式: 小时={cron_hour}, 分钟={cron_minute}")
        yield event.plain_result(status_text)
        
    @acm_manager.command("rating")
    async def cmd_get_rating(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 3: yield event.plain_result("⚠️ 参数错误，请输入CF handle。\n格式: /acm rating tourist"); return
        handle = cmd_parts[2].strip()
        api_key = self.config.get("cf_api_key"); api_secret = self.config.get("cf_api_secret")
        method_name = "user.rating"; params = {"handle": handle}
        if api_key and api_secret:
            params["apiKey"] = api_key; params["time"] = str(int(time.time()))
            params["apiSig"] = Crawler._generate_cf_api_sig(method_name, params, api_key, api_secret)
        url = f"https://codeforces.com/api/{method_name}?" + urllib.parse.urlencode(params)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response: response.raise_for_status(); data = await response.json()
            if data.get('status') != 'OK': yield event.plain_result(f"查询失败: {data.get('comment', '未知错误')}"); return
            result = data.get('result', [])
            if not result: yield event.plain_result(f"用户 '{handle}' 还未参加过任何比赛。"); return
            final_contest = result[-1]; current_rating = final_contest['newRating']; recent_contests = result[-3:]
            res_parts = [f"查询【{handle}】的 Rating 结果:", f"称号: {self._pd_cf_color(current_rating)}", f"当前 Rating: {current_rating}", "---------------------------", "最近表现:"]
            for record in recent_contests: diff = record['newRating'] - record['oldRating']; diff_str = f"+{diff}" if diff >= 0 else str(diff); res_parts.append(f"  - {record['contestName']}: {diff_str} ➠ {record['newRating']}")
            yield event.plain_result("\n".join(res_parts))
        except Exception as e: logger.error(f"查询 CF Rating ({handle}) 时发生错误: {e}"); yield event.plain_result(f"查询 '{handle}' 时发生错误。")

    @acm_manager.command("sync_user")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_sync_user(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 3: yield event.plain_result("⚠️ 参数错误，请输入QQ号。\n格式: /acm sync_user 12345"); return
        qq_id = cmd_parts[2].strip()
        yield event.plain_result(f"收到指令，正在为用户 {qq_id} 执行一次同步任务..."); await self.sync_single_user(qq_id); yield event.plain_result(f"用户 {qq_id} 的同步任务已在后台执行完成！")

    @acm_manager.command("del_user")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_delete_user(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 3: yield event.plain_result("⚠️ 参数错误，请输入QQ号。\n格式: /acm del_user 12345"); return
        qq_id = cmd_parts[2].strip()
        async with self.db.execute("SELECT name FROM users WHERE qq_id = ?", (qq_id,)) as cursor: user = await cursor.fetchone()
        if not user: yield event.plain_result(f"❌ 删除失败：找不到 QQ号为 {qq_id} 的用户。"); return
        await self.db.execute("DELETE FROM submissions WHERE user_qq_id = ?", (qq_id,)); await self.db.execute("DELETE FROM users WHERE qq_id = ?", (qq_id,)); await self.db.commit()
        logger.info(f"管理员 {event.get_sender_id()} 删除了用户 {user['name']} (QQ: {qq_id})。")
        yield event.plain_result(f"✅ 操作成功！\n已永久删除用户【{user['name']}】(QQ: {qq_id})。")

    @acm_manager.command("set group")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_set_group(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 4: yield event.plain_result("⚠️ 参数错误，请输入群号。"); return
        group_id = cmd_parts[3].strip()
        if not group_id.isdigit(): yield event.plain_result("⚠️ 参数错误，群号必须是数字。"); return
        await self.set_setting('notification_group_id', group_id); settings = await self._get_all_settings(); await self.reschedule_jobs(settings)
        yield event.plain_result(f"✅ 操作成功！\n定时播报群已设置为: {group_id}")

    @acm_manager.command("set cron")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_set_cron(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 5: yield event.plain_result("⚠️ 参数错误。\n格式: /acm set cron * 0"); return
        hour, minute = cmd_parts[3], cmd_parts[4]
        try: CronTrigger(hour=hour, minute=minute)
        except Exception as e: yield event.plain_result(f"❌ 表达式无效！\n错误: {str(e)}"); return
        await self.set_setting('report_cron_hour', hour); await self.set_setting('report_cron_minute', minute)
        settings = await self._get_all_settings(); await self.reschedule_jobs(settings)
        yield event.plain_result(f"✅ 操作成功！\n定时播报时间已设置为: hour='{hour}', minute='{minute}'")
    
    @acm_manager.command("report")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_toggle_report(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 3: yield event.plain_result("⚠️ 参数错误，请输入 on 或 off。"); return
        switch = cmd_parts[2].lower().strip()
        if switch in ['on', 'off']:
            await self.set_setting('report_enabled', 'true' if switch == 'on' else 'false')
            settings = await self._get_all_settings(); await self.reschedule_jobs(settings)
            yield event.plain_result(f"✅ 定时播报功能已【{'开启' if switch == 'on' else '关闭'}】。")
        else: yield event.plain_result("无效的开关。")

    @acm_manager.command("查询")
    async def cmd_query_user_submissions(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 3 or not cmd_parts[2].isdigit(): yield event.plain_result("⚠️ 格式错误。\n用法: /acm 查询 <QQ号>"); return
        qq_id = cmd_parts[2]
        async with self.db.execute("SELECT name FROM users WHERE qq_id = ?", (qq_id,)) as cursor: user = await cursor.fetchone()
        if not user: yield event.plain_result(f"❌ 找不到QQ号为 {qq_id} 的用户。"); return
        query = "SELECT platform, problem_name, problem_rating, submit_time FROM submissions WHERE user_qq_id = ? ORDER BY submit_time DESC LIMIT 20"
        async with self.db.execute(query, (qq_id,)) as cursor: submissions = await cursor.fetchall()
        if not submissions: yield event.plain_result(f"用户【{user['name']}】暂无过题记录。"); return
        lines = [f"🔍 用户【{user['name']}】最近的20条过题记录:"]
        for sub in submissions:
            time_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(sub['submit_time']))
            lines.append(f"[{time_str}] {sub['platform']} - {sub['problem_name']} (Rating: {sub['problem_rating'] or 'N/A'})")
        yield event.plain_result("\n".join(lines))
        
    @acm_manager.command("set hourly_limit")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_set_hourly_limit(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 4 or not cmd_parts[3].isdigit(): yield event.plain_result("⚠️ 格式错误。\n用法: /acm set hourly_limit <数量>"); return
        limit = int(cmd_parts[3])
        if not (1 <= limit <= 50): yield event.plain_result("❌ 数量必须在 1 到 50 之间。"); return
        await self.set_setting("hourly_report_limit", str(limit))
        yield event.plain_result(f"✅ 操作成功！小时榜速报上限已设置为 {limit} 题。")

    async def _query_rank_data(self, days: int = None, status: str = None, limit: int = None) -> list:
        params = []
        sql = "SELECT u.name AS user_name, u.status AS user_status, COUNT(s.id) AS total_count, COUNT(CASE WHEN s.platform = 'codeforces' THEN 1 END) AS cf_count, COUNT(CASE WHEN s.platform = 'luogu' THEN 1 END) AS luogu_count FROM users u LEFT JOIN submissions s ON u.qq_id = s.user_qq_id"
        where_clauses = []
        if days is not None: where_clauses.append("s.submit_time >= ?"); params.append(int(time.time()) - (days * 24 * 60 * 60))
        if status is not None: where_clauses.append("u.status = ?"); params.append(status)
        if where_clauses: sql += " WHERE " + " AND ".join(where_clauses)
        sql += " GROUP BY u.qq_id HAVING total_count > 0 ORDER BY total_count DESC, user_name ASC"
        if limit is not None: sql += f" LIMIT {limit}"
        
        async with self.db.execute(sql, tuple(params)) as cursor: return await cursor.fetchall()

    @acm_manager.command("过题")
    async def cmd_rank_by_status(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 3: yield event.plain_result("⚠️ 格式错误。\n用法: /acm 过题 <身份> [天数]"); return
        status = cmd_parts[2]; days = 7
        if len(cmd_parts) > 3 and cmd_parts[3].isdigit(): days = int(cmd_parts[3])
        title = f"近 {days} 天【{status}】过题排行榜"
        users_data = await self._query_rank_data(days=days, status=status, limit=50) 
        if not users_data: yield event.plain_result(f"📊 {title}\n\n该条件下暂无过题记录。"); return
        image_bytes = await self._generate_rank_image(title, users_data)
        if isinstance(image_bytes, str): yield event.plain_result(image_bytes)
        else: yield event.chain_result([Image.fromBytes(image_bytes)])

    @acm_manager.command("sql")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_sql_sync(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 3 or not cmd_parts[2].isdigit(): yield event.plain_result("⚠️ 格式错误。\n用法: /acm sql <天数>"); return
        days = min(int(cmd_parts[2]), 30)
        yield event.plain_result(f"收到指令！正在为所有用户执行【{days}天深度同步】，请耐心等待...")
        async with self.db.execute("SELECT qq_id FROM users") as cursor: all_users = await cursor.fetchall()
        for user_row in all_users: await self.sync_single_user_for_days(user_row['qq_id'], days)
        yield event.plain_result(f"✅ 同步完成！正在生成榜单...")
        title = f"深度同步 · 近 {days} 天过题排行榜"
        users_data = await self._query_rank_data(days=days, limit=50)
        if not users_data: yield event.plain_result(f"📊 {title}\n\n该条件下暂无过题记录。"); return
        image_bytes = await self._generate_rank_image(title, users_data)
        if isinstance(image_bytes, str): yield event.plain_result(image_bytes)
        else: yield event.chain_result([Image.fromBytes(image_bytes)])

    @acm_manager.command("past")
    async def cmd_past_rank(self, event: AstrMessageEvent):
        cmd_parts = event.message_str.strip().split()
        if len(cmd_parts) < 3 or not cmd_parts[2].isdigit(): yield event.plain_result("⚠️ 格式错误。\n用法: /acm past <天数>"); return
        days = int(cmd_parts[2])
        title = f"数据库 · 近 {days} 天过题排行榜"
        users_data = await self._query_rank_data(days=days, limit=50)
        if not users_data: yield event.plain_result(f"📊 {title}\n\n该条件下暂无过题记录。"); return
        image_bytes = await self._generate_rank_image(title, users_data)
        if isinstance(image_bytes, str): yield event.plain_result(image_bytes)
        else: yield event.chain_result([Image.fromBytes(image_bytes)])
        
    @acm_manager.command("总榜")
    async def cmd_total_rank(self, event: AstrMessageEvent):
        title = "生涯总过题排行榜"
        users_data = await self._query_rank_data(days=None, limit=None) 
        if not users_data: yield event.plain_result("📊 生涯总榜暂无数据。"); return
        image_bytes = await self._generate_rank_image(title, users_data)
        if isinstance(image_bytes, str): yield event.plain_result(image_bytes)
        else: yield event.chain_result([Image.fromBytes(image_bytes)])
