# 文件路径: backend/api.py (V12.0 完整版)

import time
import aiosqlite
from pathlib import Path
from quart import Blueprint, request, jsonify, current_app
from ..core.crawler import Crawler
import aiohttp
from astrbot.api import logger

api = Blueprint('api', __name__)

async def get_db():
    db_path = current_app.config.get('DB_PATH')
    if not db_path: raise ConnectionError("DB path not configured.")
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    return db

@api.route('/register', methods=['POST'])
async def api_register_user():
    db = await get_db()
    try:
        data = await request.get_json()
        if not data or not data.get('qq_id') or not data.get('name'):
            return jsonify({"success": False, "message": "QQ号和用户名是必填项！"}), 400
        
        qq_id_str = str(data['qq_id']).strip()
        
        async with db.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id_str,)) as cursor:
            existing_user = await cursor.fetchone()

        await db.execute(
            "INSERT OR REPLACE INTO users (qq_id, name, cf_handle, luogu_id, status, school, last_sync_timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (qq_id_str, str(data['name']).strip(), data.get('cf_handle','').strip() or None,
             data.get('luogu_id','').strip() or None, data.get('status','').strip() or None,
             data.get('school','').strip() or None, existing_user['last_sync_timestamp'] if existing_user else 0)
        )
        await db.commit()
        
        message = "注册/更新成功！"
        
        if not existing_user:
            try:
                async with db.execute("SELECT * FROM users WHERE qq_id = ?", (qq_id_str,)) as cursor:
                    new_user_row = await cursor.fetchone()
                
                plugin_config = current_app.config.get('PLUGIN_CONFIG', {})
                start_timestamp = int(time.time()) - (7 * 24 * 60 * 60)
                
                logger.info(f"[API实时同步] 正在为新用户 {qq_id_str} 执行首次同步...")
                async with aiohttp.ClientSession() as session:
                    if new_user_row['cf_handle']:
                        await Crawler.fetch_cf_submissions(session, new_user_row, start_timestamp, db, plugin_config)
                    if new_user_row['luogu_id']:
                        await Crawler.fetch_luogu_submissions(session, new_user_row, start_timestamp, db, plugin_config)
                
                await db.execute("UPDATE users SET last_sync_timestamp = ? WHERE qq_id = ?", (int(time.time()), qq_id_str))
                await db.commit()
                message += " 首次数据已实时同步完成！"
                logger.info(f"[API实时同步] 新用户 {qq_id_str} 同步完成。")
            except Exception as e:
                logger.error(f"[API实时同步] 失败: {e}", exc_info=True)
                message += " 但实时同步失败，数据将在15分钟内更新。"
        
        return jsonify({"success": True, "message": message})
    except Exception as e:
        logger.error(f"[API Error] /register: {e}", exc_info=True)
        return jsonify({"success": False, "message": "服务器内部错误"}), 500
    finally:
        if db: await db.close()

@api.route('/leaderboard', methods=['GET'])
async def api_get_leaderboard():
    db = await get_db()
    try:
        seven_days_ago = int(time.time()) - (7 * 24 * 60 * 60)
        cursor = await db.execute(
            """
            SELECT u.name, u.status, u.school,
                   COUNT(DISTINCT CASE WHEN s.platform = 'codeforces' AND s.submit_time >= ? THEN s.problem_id ELSE NULL END) as cf_count,
                   COUNT(DISTINCT CASE WHEN s.platform = 'luogu' AND s.submit_time >= ? THEN s.problem_id ELSE NULL END) as luogu_count,
                   COUNT(DISTINCT CASE WHEN s.submit_time >= ? THEN s.problem_id ELSE NULL END) as total_count
            FROM users u LEFT JOIN submissions s ON u.qq_id = s.user_qq_id
            GROUP BY u.qq_id, u.name, u.status, u.school
            ORDER BY total_count DESC, u.name ASC
            """, (seven_days_ago, seven_days_ago, seven_days_ago)
        )
        rows = await cursor.fetchall()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        logger.error(f"[API Error] /leaderboard: {e}", exc_info=True)
        return jsonify([]), 500
    finally:
        if db: await db.close()

