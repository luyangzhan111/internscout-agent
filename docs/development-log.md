# InternScout Agent 开发日志

## 2026-07-23：阶段1项目初始化

### 今天完成

- 创建正式项目目录
- 创建Python 3.12虚拟环境
- 初始化Git仓库
- 安装FastAPI、Uvicorn、Pytest和HTTPX
- 完成根路径和健康检查接口
- 编写并运行两个接口自动化测试

### 学到的知识

- 虚拟环境可以隔离不同项目的Python依赖
- FastAPI通过路由装饰器定义接口
- Uvicorn负责启动FastAPI应用
- Pytest使用assert检查程序实际结果
- Uvicorn启动后一直等待请求，不是程序卡住

### 遇到的问题

- PowerShell最初禁止运行虚拟环境的激活脚本
- 浏览器请求favicon.ico时返回404
- Pytest出现一个第三方库的弃用警告

### 解决方法

- 将CurrentUser执行策略设置为RemoteSigned
- favicon.ico不是业务接口，可以暂时忽略
- Pytest警告不影响当前两个测试通过，后续统一检查依赖兼容性

### 仍然不理解

- FastAPI和Uvicorn之间更具体的关系
- Git add和Git commit分别做什么