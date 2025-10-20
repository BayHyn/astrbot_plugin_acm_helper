# ACM Helper - ACM 训练助手

[

![Stars](https://img.shields.io/github/stars/Suzakudry/astrbot-plugin-acm-helper?style=flat-square&label=Stars)

](https://github.com/Suzakudry/astrbot-plugin-acm-helper)
[

![Version](https://img.shields.io/badge/Version-1.0.0-blue.svg?style=flat-square)

](https://github.com/Suzakudry/astrbot-plugin-acm-helper)
[

![License](https://img.shields.io/github/license/Suzakudry/astrbot-plugin-acm-helper?style=flat-square)

](https://github.com/Suzakudry/astrbot-plugin-acm-helper/blob/main/LICENSE)

一款为 [AstrBot](https://github.com/soulter/AstrBot) 设计的、功能强大的 ACM 训练辅助插件。它能够自动追踪成员在 Codeforces 和洛谷的刷题动态，提供实时排名，并通过一个直观的 WebUI 后台进行管理。让每一次提交，都留下印记。



---

## 🚀 主要功能

*   **📈 自动刷题记录**: 自动同步并持久化存储成员在 **Codeforces** 和 **洛谷** 的 AC 记录。
*   **📊 多维度排行榜**:
    *   `/acm rank`: 显示近7日刷题量的**周榜**，激励短期冲刺。
    *   `/acm rank all`: 显示生涯总刷题量的**总榜**，见证长期积累。
*   **📢 实时播报**:
    *   **小时榜**: 每小时自动播报上一小时内的新增过题记录，营造你追我赶的训练氛围。
    *   **日报** (未来计划): 每日总结，回顾一天的收获。
*   **⚙️ 直观的 Web 管理后台**:
    *   提供基于 Web 的图形化界面，方便管理员添加、删除、修改成员信息。
    *   无需记忆复杂命令，点点鼠标即可完成成员管理。
*   **🤖 丰富的群聊命令**:
    *   查询个人 CF Rating: `/acm rating <handle>`
    *   查询近期 CF 比赛: `/acm contest`
*   **🔧 高度可配置**: 管理员可通过命令轻松设置播报开关、目标群聊和播报时间。

## 📸 效果演示



**排行榜示例:**




**WebUI 管理后台:**




---

## 🛠️ 配置指南

### 1. 安装

请通过 AstrBot 的插件商店安装本插件，或将本项目手动放置于 `data/plugins` 目录下。

### 2. 获取 API 密钥 (可选但强烈推荐)

为了获得更稳定、更强大的功能，建议配置以下平台的 API 密钥：

*   **Codeforces API**:
    1.  访问 [Codeforces API Settings](https://codeforces.com/settings/api)。
    2.  点击 "Add API key"，生成你的 `key` 和 `secret`。
*   **洛谷 Cookie**:
    1.  登录洛谷。
    2.  打开浏览器开发者工具 (F12)。
    3.  切换到 "网络 (Network)" 标签页。
    4.  刷新页面，找到任意一个对 `luogu.com.cn` 的请求。
    5.  在请求头 (Request Headers) 中找到 `Cookie`，复制其完整值。
    6.  同样在请求头中找到 `x-csrf-token`，复制其值。

### 3. 在 AstrBot 中配置

进入 AstrBot 主后台 -> 设置 -> 插件设置 -> `acm_helper`，填写以下配置项：

*   `luogu_cookie` (推荐): 填入上一步获取的洛谷 Cookie。
*   `luogu_csrf_token` (推荐): 填入上一步获取的洛谷 CSRF Token。
*   `cf_api_key` (可选): 填入你的 Codeforces API Key。
*   `cf_api_secret` (可选): 填入你的 Codeforces API Secret。
*   `webui_port` (必须): 为插件的 WebUI 后台指定一个端口，例如 `11451`。**请确保此端口未被占用，并在服务器防火墙中放行。**

### 4. 启动 WebUI 并注册成员

1.  在群聊中发送 `/acm 后台启动` 来启动 Web 管理界面。
2.  机器人会返回后台地址。访问该地址，开始添加和管理你的团队成员。

---

## 📖 使用说明 (命令大全)

### 🏆 查询与排行 (所有人可用)

| 命令                          | 功能说明                             | 示例                      |
| :---------------------------- | :----------------------------------- | :------------------------ |
| `/acm rating <CF Handle>`     | 查询指定 Codeforces 用户的 Rating。  | `/acm rating tourist`     |
| `/acm contest`                | 获取近期 Codeforces 比赛列表。       | `/acm contest`            |
| `/acm rank`                   | 显示近7日刷题量**周榜**。            | `/acm rank`               |
| `/acm rank all`               | 显示生涯总刷题量**总榜**。           | `/acm rank all`           |
| `/acm hourly`                 | 手动触发一次**小时榜**播报。         | `/acm hourly`             |

### ⚙️ 管理员后台与设置 (仅限管理员)

| 命令                          | 功能说明                             | 示例                      |
| :---------------------------- | :----------------------------------- | :------------------------ |
| `/acm 后台启动`               | 启动 WebUI 管理后台。                | `/acm 后台启动`           |
| `/acm 后台关闭`               | 关闭 WebUI 管理后台。                | `/acm 后台关闭`           |
| `/acm set group <群号>`       | 设置定时播报的目标QQ群。             | `/acm set group 123456789` |
| `/acm set cron <小时> <分钟>` | 设置定时播报时间 (CRON格式)。        | `/acm set cron 8-23 0`    |
| `/acm report <on/off>`        | 开启或关闭所有定时播报。             | `/acm report on`          |
| `/acm status`                 | 查看插件当前所有配置状态。           | `/acm status`             |

### 👤 用户数据管理 (仅限管理员)

| 命令                          | 功能说明                             | 示例                      |
| :---------------------------- | :----------------------------------- | :------------------------ |
| `/acm sync_user <QQ号>`       | 手动同步指定用户的刷题数据。         | `/acm sync_user 987654321` |
| `/acm del_user <QQ号>`        | **永久删除**指定用户及所有数据。     | `/acm del_user 987654321` |

---

## 📝 未来计划 (TODO)

*   [ ] 每日总结播报功能。
*   [ ] 支持更多 OJ 平台 (如 AtCoder, VJudge)。
*   [ ] WebUI 增加数据统计图表。
*   [ ] 比赛提醒功能。

## 🤝 贡献

欢迎通过 Pull Request 或 Issue 为本项目做出贡献。如果你有任何好的想法或建议，请随时提出！

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源。
