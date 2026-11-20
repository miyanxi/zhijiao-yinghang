# 智教英航

面向高中英语教师的学习画像与教学工作台，连接教学目标、教案、班级统一作业和学习记录。

**项目角色：独立开发与交付。** 负责客户需求沟通、方案设计与调整、前后端开发、模型服务接入、部署交付、使用指导及后续微调；第三方框架和模型能力按各自来源使用。

本目录为独立整理的公开源码候选版，使用源码内的虚构种子数据，不包含原客户数据、已有发布包、真实凭据或旧 Git 历史。当前没有可承诺长期可用的在线体验地址；截图、视频和静态展示将在后续阶段补齐。

- [数据与凭据边界](docs/privacy.md)
- [演示数据与体验范围](docs/demo.md)
- [安装手册](docs/安装手册.md)
- [配套资料清单](docs/资料清单.md)

下方部署说明来自既有项目，供后续部署时参考；本次整理不创建托管服务、不产生费用，也不代表现有代码已经具备公网访问控制。

## 公开演示部署

此版本只允许使用虚构学生数据。所有访问者共享同一演示库，没有账号隔离，不要录入真实姓名、作业或其他个人信息。公开后 DeepSeek 调用会消耗项目持有人的额度。

推荐：后端通过仓库根目录的 `render.yaml` 部署到 Render Starter（带 1 GB 持久磁盘），前端把 `frontend` 设为 Vercel 项目的 Root Directory。Render 后台设置 `DEEPSEEK_API_KEY`；首次部署时先将 `FRONTEND_ORIGIN` 设为 Vercel 分配的正式域名（含 `https://`，不带末尾 `/`）。Vercel 后台设置 `VITE_API_BASE_URL` 为 Render 后端的 `https://...onrender.com` 地址，然后重新部署前端。两个变量都必须指向正式域名，不能使用 `localhost`。后端健康检查为 `<后端域名>/api/v1/health`。

`render.yaml` 的 Starter 持久磁盘是付费资源。数据库保存在 `/var/data/zhijiao_yinghang.db`；首次启动自动创建并写入虚构演示数据，后续重启保留教师在演示环境的修改。不要把本地 `backend/data/` 或 `.env` 上传到云端。公开演示并非多用户系统，任何访问者都能修改共享内容；正式教学使用前必须增加身份认证与数据隔离。

基于学习画像的高中英语教学智能体。当前工作台聚焦教学目标、智能教案、班级统一作业和学习画像；智能阅卷、专项训练与 AI 总管家不再出现在导航中。

## 启动后端

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --port 8001
```

后端启动时会自动初始化 SQLite，并幂等写入高一（3）班、6 名学生和 4 次历史班级统一作业的演示数据。画像由逐题学习记录计算。

教学目标解析、智能教案生成/分段重新生成、智能作业生成和题目 AI 检查均要求真实 DeepSeek；未配置 `DEEPSEEK_API_KEY` 或模型调用失败时会明确报错，不会返回预设内容。必须在启动后端的同一 PowerShell 会话中设置 `$env:DEEPSEEK_API_KEY = "实际密钥"`，然后重启后端。不要把密钥写入仓库。可调用 `POST /api/v1/teaching-goals/parse` 并检查返回的 `source`：`deepseek` 表示真实模型。教案和作业均先保存为草稿，由教师审核；只有审核通过的统一作业能由教师显式发布。离线回归测试会显式设置 `ENABLE_TEST_DEMO_GENERATION=1`，该开关不用于正常运行。

智能作业支持单选、多选和填空题。文件阅卷先由教师上传试卷、参考答案和学生作业，教师核对系统提取的题目及逐题答案后，程序按标准答案计算得分并更新画像。没有学生登录端，也没有开放式作文自动评分；这两项不可当作已完成能力。

智能作业支持单选、多选和填空题，新生成的作业至少包含一道填空题，教师可核对中文题干、答案和解析。教案和统一作业均可直接下载 PDF；作业 PDF 不含答案，未审核稿带草稿标记。PDF 生成依赖 ReportLab 和本机中文字体。智能阅卷已从教师工作台移除，历史数据库记录及后端接口暂留，以免破坏已有数据。

教学目标页支持教师新增课程知识点并删除尚未生成教案/作业的草稿目标。解析目标时会结合班级已有学习记录生成相关学情和本课上课建议。教案审核通过后，教师可以在同一教案下填写课后评价与教学反思，保存内容会同步到班级学情分析。

专项训练和 AI 总管家同样已从教师工作台导航移除；历史数据库表及旧接口暂时保留。可通过 `DEEPSEEK_MODEL` 设置模型，默认 `deepseek-flash`。

## 启动前端

需要 Node.js 和包管理器。进入 `frontend` 后执行：

```powershell
pnpm install
pnpm run dev
```

前端地址：`http://localhost:5173`

前端默认连接 `http://localhost:8001`。若后端改用其他端口，请在启动前端的同一 PowerShell 会话中设置 `$env:VITE_API_BASE_URL = "http://localhost:实际端口"`。前端 5173 被占用时 Vite 会显示实际使用的端口。若同时运行了旧版服务，务必确认前端连接的是包含 `/api/v1/teaching-goals/parse` 和 `/api/v1/assessment-imports` 的完整后端；仅 `/api/v1/health` 返回正常不足以说明后端版本正确。

请通过上述地址访问页面，不要直接打开 `frontend/index.html` 文件。

也可以使用 `npm install` 和 `npm run dev`。

## 基础测试

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -v
```

产品修订回归测试为 `backend/tests/test_product_revision.py`。它使用临时 SQLite，覆盖教学目标、教案课后复盘、班级统一作业、文件导入阅卷和学习画像更新，不会修改 `backend/data/zhijiao_yinghang.db`。

数据库检查可使用：

```powershell
python -c "import sqlite3; c=sqlite3.connect('backend/data/zhijiao_yinghang.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(c.execute('PRAGMA foreign_key_check').fetchall())"
```

比赛演示建议使用隔离数据库运行测试链路；真实页面默认连接现有演示库，启动地址为前端 `http://localhost:5173`（若端口被占用，以 Vite 输出为准），后端健康检查为 `http://localhost:8001/api/v1/health`。

## 核心 API

```text
GET /api/v1/health
GET /api/v1/classes
GET /api/v1/classes/{class_id}
GET /api/v1/classes/{class_id}/students
GET /api/v1/students/{student_id}
GET /api/v1/classes/{class_id}/learning-overview
GET /api/v1/students/{student_id}/learning-overview
GET /api/v1/assignments?class_id={class_id}
GET /api/v1/assignments/{assignment_id}
```

历史作业和画像接口只读。Phase 3 提供班级/学生维护、教学目标解析与确认、教案草稿生成与分模块编辑、统一作业草稿生成与逐题检查及教师审核。Phase 4 新增 `POST /api/v1/assignments/publish/{draft_id}` 和 `POST /api/v1/assignments/{assignment_id}/submissions`；班级/学生学情接口新增近期成绩趋势。
文件阅卷接口包括 `POST /api/v1/assessment-imports`（上传试卷和参考答案）、`PATCH /api/v1/assessment-imports/{id}/questions/{question_id}`（教师修订题目）、`POST /api/v1/assessment-imports/{id}/approve`（确认试卷）以及学生作业上传、识别结果修订和确认评分接口。专项训练和 AI 总管家不属于当前工作台流程；为兼容历史数据，旧数据库表和后端路由仍保留，但当前前端不提供入口。
