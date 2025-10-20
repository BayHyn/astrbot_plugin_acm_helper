# 文件路径: acm-helper-plugin/backend/api.py

import time
import aiosqlite
from pathlib import Path
from quart import Blueprint, request, jsonify

api = Blueprint('api', __name__)
DB_PATH = Path(__file__).parent.parent / "data" / "acm_helper.db"

async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db

@api.route('/register', methods=['POST'])
async def api_register_user():
    db = await get_db()
    try:
        data = await request.get_json()
        if not data: return jsonify({"success": False, "message": "请求体为空！"}), 400
        qq_id, name = data.get('qq_id'), data.get('name')
        if not qq_id or not name: return jsonify({"success": False, "message": "QQ号和用户名是必填项！"}), 400
        
        await db.execute(
            "INSERT OR REPLACE INTO users (qq_id, name, cf_handle, luogu_id, status, school) VALUES (?, ?, ?, ?, ?, ?)",
            (str(qq_id).strip(), str(name).strip(), data.get('cf_handle','').strip() or None,
             data.get('luogu_id','').strip() or None, data.get('status','').strip() or None,
             data.get('school','').strip() or None)
        )
        await db.commit()
        return jsonify({"success": True, "message": "注册/更新成功！"})
    except Exception as e:
        print(f"[ACM API Error] /register: {e}")
        return jsonify({"success": False, "message": "服务器内部错误"}), 500
    finally:
        if db: await db.close()
        
@api.route('/leaderboard', methods=['GET'])
async def api_get_leaderboard():
    """提供排行榜数据的 API (V2.0 - 题目去重版)"""
    db = await get_db()
    try:
        seven_days_ago = int(time.time()) - (7 * 24 * 60 * 60)
        cursor = await db.execute(
            """
            SELECT
                u.name, u.status, u.school,
                -- 【核心去重优化】使用 COUNT(DISTINCT ...)
                COUNT(DISTINCT CASE WHEN s.platform = 'codeforces' AND s.submit_time >= ? THEN s.problem_id ELSE NULL END) as cf_count,
                COUNT(DISTINCT CASE WHEN s.platform = 'luogu' AND s.submit_time >= ? THEN s.problem_id ELSE NULL END) as luogu_count,
                COUNT(DISTINCT CASE WHEN s.submit_time >= ? THEN s.problem_id ELSE NULL END) as total_count
            FROM users u
            LEFT JOIN submissions s ON u.qq_id = s.user_qq_id
            GROUP BY u.qq_id, u.name, u.status, u.school
            ORDER BY total_count DESC, u.name ASC
            """, (seven_days_ago, seven_days_ago, seven_days_ago)
        )
        rows = await cursor.fetchall()
        leaderboard_data = [dict(row) for row in rows]
        return jsonify(leaderboard_data)
    except Exception as e:
        print(f"[ACM API Error] /leaderboard: {e}")
        return jsonify([]), 500
    finally:
        if db: await db.close()