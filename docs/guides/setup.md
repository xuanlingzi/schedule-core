# Schedule Core 安装指南

本文档介绍如何安装和配置 Schedule Core 包，使其可以被多个项目共用。

## 1. 准备工作

首先，确保你的系统已经安装了 Python 3.9 或更高版本。你可以通过以下命令检查：

```bash
python3 --version
```

## 2. 创建全局虚拟环境（推荐）

为了避免污染系统的 Python 环境，我们建议创建一个专门的虚拟环境：

```bash
# 创建一个名为 schedule_core_env 的虚拟环境
python3 -m venv ~/.virtualenvs/schedule_core_env

# 激活虚拟环境
source ~/.virtualenvs/schedule_core_env/bin/activate
```

## 3. 安装 Schedule Core

### 3.1 克隆代码仓库

首先，将 Schedule Core 代码克隆到一个固定的位置：

```bash
# 创建一个目录用于存放共享包
mkdir -p ~/Developer/shared_packages
cd ~/Developer/shared_packages

# 克隆 Schedule Core 仓库
git clone <schedule_core_repo_url> schedule-core
```

### 3.2 安装依赖

安装 Schedule Core 及其依赖：

```bash
# 进入 schedule-core 目录
cd schedule-core

# 安装包及其依赖
pip install -e .
```

## 4. 项目配置

### 4.1 在项目中使用

在你的项目中，有两种方式使用 Schedule Core：

1. **使用虚拟环境（推荐）**

```bash
# 在你的项目目录中
python3 -m venv venv
source venv/bin/activate

# 安装 schedule-core
pip install -e ~/Developer/shared_packages/schedule-core
```

2. **在 requirements.txt 中指定**

在你的项目的 `requirements.txt` 文件中添加：

```
-e ~/Developer/shared_packages/schedule-core
```

然后运行：

```bash
pip install -r requirements.txt
```

### 4.2 验证安装

你可以通过以下命令验证安装是否成功：

```bash
python3 -c "import schedule_core; print(schedule_core.__file__)"
```

如果显示了 schedule_core 的路径，说明安装成功。

## 5. 常见问题

### 5.1 依赖问题

如果遇到依赖相关的错误，可以尝试安装以下包：

```bash
pip install pika redis sqlalchemy pydantic pydantic-settings aio-pika
```

### 5.2 权限问题

如果遇到权限相关的错误，确保：

1. 虚拟环境已经正确激活
2. 安装目录具有正确的读写权限

### 5.3 导入错误

如果遇到导入错误，检查：

1. Python 路径是否正确
2. 虚拟环境是否激活
3. 包是否正确安装

## 6. 更新 Schedule Core

当需要更新 Schedule Core 时：

```bash
cd ~/Developer/shared_packages/schedule-core
git pull
pip install -e .
```

## 7. 卸载

如果需要卸载 Schedule Core：

```bash
pip uninstall schedule-core
```

## 8. 注意事项

1. 建议使用版本控制（如 git）来管理 Schedule Core 的版本
2. 在生产环境中，最好指定具体的版本号
3. 定期更新依赖以修复潜在的安全问题
4. 在团队中统一使用相同的安装路径，便于维护

## 9. 技术支持

如果遇到问题，可以：

1. 查看 Schedule Core 的文档
2. 检查错误日志
3. 联系技术支持团队

## 10. 参考资料

- [Python 虚拟环境文档](https://docs.python.org/zh-cn/3/tutorial/venv.html)
- [Pip 安装指南](https://pip.pypa.io/en/stable/installation/)
- [Schedule Core 文档]() 