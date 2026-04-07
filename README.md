# Camoufox GeoIP 中间件

这是一个用于启动 Camoufox 浏览器并启用 GeoIP 功能的中间件，解决了 Camoufox 只能通过代码方式开启 GeoIP 的问题。

## 功能特性

- 自动启用 GeoIP（时区随 IP 变化）
- 未传代理时自动检测系统代理
- 自动查找 `camoufox.exe`
- 浏览器指纹随机化
- 支持打包为 Windows exe
- 所有命令行参数均为可选参数

## 安装依赖

本项目依赖 Camoufox 的 GeoIP 能力，不能只安装基础版 `camoufox`，需要安装带 `geoip` extra 的版本：

```bash
pip install "camoufox[geoip]" playwright
```

## 使用方法

### 方式 1：直接运行 Python 脚本

直接启动浏览器（不传任何参数）：

```bash
python browser.py
```

启动后自动打开 URL：

```bash
python browser.py https://example.com
```

或使用 `-url` 参数：

```bash
python browser.py -url https://example.com
```

指定代理与其他参数：

```bash
python browser.py -proxy http://127.0.0.1:7890 -os windows -headless -block-images
```

### 命令行参数

支持的参数：

- `-proxy`：代理地址，例如 `http://127.0.0.1:7890`
- `-os`：浏览器操作系统指纹，默认 `windows`
- `-headless`：启用无头模式
- `-block-images`：禁用图片加载
- `-url`：启动后自动打开的页面
- `url`：位置参数形式的 URL，效果与 `-url` 等价

说明：

- 所有参数都不是必填项
- `-url` 优先级高于位置参数 `url`
- 未传 URL 时，程序只启动浏览器并保持空白页
- 未传 `-proxy` 时，程序会自动尝试检测系统代理

## 打包为 exe

### 安装 PyInstaller

建议先进入项目虚拟环境，再在该虚拟环境里安装并调用 PyInstaller：

```bash
pip install pyinstaller
python -m PyInstaller --version
```

注意：不要直接使用系统里的全局 `pyinstaller` 命令来打包，否则很可能会误用其他 Python 解释器，导致日志里出现类似下面的信息：

```text
Python: 3.13.5
Python environment: D:\project\python\python313
```

一旦 PyInstaller 实际运行在错误的 Python 环境下，即使你已经在项目 `.venv` 里安装了 `camoufox[geoip]`，打包产物里也还是会缺少 `camoufox`，最终运行时报错：

```text
ModuleNotFoundError: No module named 'camoufox'
```

### 推荐打包命令（onefile）

请在已经安装好项目依赖的虚拟环境中执行：

```bash
python -m PyInstaller --noconfirm --clean --name camoufox-geoip --onefile --collect-all camoufox --collect-all playwright --collect-all browserforge --collect-all apify_fingerprint_datapoints --collect-all language_tags browser.py
```

之所以需要这些 `--collect-all`，是因为依赖里包含运行时读取的 zip/json 数据文件，默认打包经常漏掉。

### 生成后的目录摆放

打包完成后，需要把 `camoufox.exe` 放到 `camoufox-geoip.exe` 同级目录：

```text
your-folder/
├── camoufox-geoip.exe
└── camoufox.exe
```

这是因为程序会优先在 exe 所在目录查找 `camoufox.exe`。

### exe 运行示例

直接启动浏览器：

```bash
camoufox-geoip.exe
```

启动后打开目标页面：

```bash
camoufox-geoip.exe https://example.com
```

或：

```bash
camoufox-geoip.exe -url https://example.com
```

指定代理：

```bash
camoufox-geoip.exe -proxy http://127.0.0.1:7890 https://example.com
```

### 备选：使用 onedir

如果你更关注打包稳定性，也可以使用 `--onedir`：

```bash
python -m PyInstaller --noconfirm --clean --name camoufox-geoip --onedir --collect-all camoufox --collect-all playwright --collect-all browserforge --collect-all apify_fingerprint_datapoints --collect-all language_tags browser.py
```

注意：`onedir` 模式下不要只拷出 exe，必须保留整个输出目录。

## 代理配置

### 自动检测系统代理

程序会按以下顺序尝试检测代理：

1. 环境变量：`HTTP_PROXY`、`http_proxy`、`HTTPS_PROXY`、`https_proxy`
2. Windows 注册表代理设置

### 手动指定代理

```bash
camoufox-geoip.exe -proxy http://127.0.0.1:7890
```

## 环境变量

- `CAMOUFOX_PATH`：指定 `camoufox.exe` 的路径
- `HTTP_PROXY` / `HTTPS_PROXY`：代理配置

## 作为库使用

```python
import asyncio
from browser import create_browser

async def main():
    manager = await create_browser(proxy="http://127.0.0.1:7890", os="windows")
    page = await manager.new_page()
    await page.goto("https://example.com")
    await manager.cleanup()

asyncio.run(main())
```

## 高级配置

```python
manager = await create_browser(
    proxy="http://127.0.0.1:7890",
    headless=False,
    viewport={"width": 1920, "height": 1080},
    os="windows",
    block_images=False,
)
```

## 故障排查

### 1. 找不到 `camoufox.exe`

确保 `camoufox.exe` 位于以下位置之一：

- 与 `camoufox-geoip.exe` 同级目录
- 当前工作目录
- 环境变量 `CAMOUFOX_PATH` 指定的路径

另外，如果你要使用 GeoIP 功能，必须先安装带 extra 的依赖：

```bash
pip install -U "camoufox[geoip]"
```

### 2. 打包后运行提示 `ModuleNotFoundError: No module named 'camoufox'`

如果打包产物启动时看到类似：

```text
ModuleNotFoundError: No module named 'camoufox'
```

通常不是因为你没装依赖，而是因为 **打包时实际使用的不是项目虚拟环境里的 Python**。

例如你虽然已经激活了 `.venv`，但执行的 `pyinstaller` 仍然可能来自全局 Python；这时构建日志里会出现错误的解释器路径，例如：

```text
Python environment: D:\project\python\python313
```

解决方法：

1. 确保项目虚拟环境里已经安装依赖：

```bash
pip install -U "camoufox[geoip]" playwright pyinstaller
```

2. 不要直接调用全局 `pyinstaller`，改为在虚拟环境里执行：

```bash
python -m PyInstaller --noconfirm --clean --name camoufox-geoip --onedir --collect-all camoufox --collect-all playwright --collect-all browserforge --collect-all apify_fingerprint_datapoints --collect-all language_tags browser.py
```

3. 打包后先检查日志中的 `Python environment` 是否指向你的项目虚拟环境。

### 3. 打包后运行提示缺少 zip/json 数据文件

如果看到类似下面的报错：

- `apify_fingerprint_datapoints/.../*.zip` 不存在
- `language_tags/data/json/index.json` 不存在

说明打包时没有把依赖的数据文件收进去。请使用 README 中的推荐打包命令重新打包。

### 4. `onedir` 模式提示缺少 `python312.dll`

如果出现类似：

```text
Failed to load Python DLL '...\\_internal\\python312.dll'
```

通常是因为只复制了 exe，没有保留整个 `onedir` 输出目录。

### 5. 代理连接失败

请检查：

- 代理地址格式是否正确，例如 `http://host:port`
- 代理服务是否正在运行
- 本机防火墙或安全软件是否拦截

### 6. 关闭浏览器时出现 cleanup 日志错误

如果在你手动关闭浏览器窗口后看到类似连接关闭的 cleanup 日志，通常只是收尾阶段的日志噪音，不影响主流程是否启动成功。

## 许可证

MIT License
