# helloworld

AstrBot 插件模板
/`      ACM 训练助手 - 命令大全 (v18.0)      `\
----------------------------------------------
✨  本插件由 suzakudry & OpenAI 联手打造  ✨
----------------------------------------------

【🏆  查询与排行 (所有人可用)  🏆】

/acm rating <CF Handle>
  » 查询指定 Codeforces 用户的 Rating 和近期表现。
  » 示例: /acm rating tourist

/acm contest
  » 获取近期即将开始的 Codeforces 比赛列表。

/acm rank
  » 显示近7日内，本群成员的刷题量排行榜。

/acm rank all
  » 显示生涯总刷题量排行榜。

/acm hourly
  » 手动触发一次“小时榜”，播报过去一小时的过题记录。

----------------------------------------------
【⚙️  管理员后台与设置 (仅限管理员)  ⚙️】

/acm 后台启动
  » 启动插件专属的 WebUI 管理后台。

/acm 后台关闭
  » 关闭插件的 WebUI 管理后台。

/acm set group <群号>
  » 设置“小时榜”和“日报”等定时播报的目标QQ群。
  » 示例: /acm set group 123456789

/acm set cron <小时> <分钟>
  » 设置定时播s报的时间 (使用 CRON 表达式)。
  » 示例1 (每天上午9点): /acm set cron 9 0
  » 示例2 (8点到23点的整点): /acm set cron 8-23 0

/acm report <on|off>
  » 开启或关闭所有定时播报功能。
  » 示例: /acm report on

/acm status
  » 查看插件当前所有配置的状态 (播报开关/群号/时间)。

----------------------------------------------
【👤  用户数据管理 (仅限管理员)  👤】

/acm sync_user <QQ号>
  » 手动为指定QQ号的用户同步一次刷题数据。
  » 示例: /acm sync_user 987654321

/acm del_user <QQ号>
  » 从数据库中永久删除指定用户及其所有刷题记录。
  » 示例: /acm del_user 987654321

\______________________________________________/

A template plugin for AstrBot plugin feature

# 支持

[帮助文档](https://astrbot.app)
