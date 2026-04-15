"""
Camoufox GeoIP 中间件
自动启动 Camoufox 浏览器并启用 GeoIP 功能（时区随 IP 变化）
支持系统代理自动检测和 camoufox.exe 路径自动查找
"""
import argparse
import os
import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Union
from playwright.async_api import Browser, Page
from camoufox.async_api import AsyncCamoufox
import asyncio

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CamoufoxGeoIP")


def detect_system_proxy() -> Optional[Dict[str, str]]:
    """
    自动检测系统代理配置

    Returns:
        代理配置字典，格式: {"server": "http://host:port"}
        如果未检测到代理则返回 None
    """
    try:
        # 尝试从环境变量获取代理
        proxy_env = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy') or \
                    os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')

        if proxy_env:
            logger.info(f"从环境变量检测到代理: {proxy_env}")
            return {"server": proxy_env}

        # Windows 系统代理检测
        if sys.platform == 'win32':
            try:
                import winreg
                # 读取 Windows 注册表中的代理设置
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                   r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                    proxy_enable = winreg.QueryValueEx(key, 'ProxyEnable')[0]
                    if proxy_enable:
                        proxy_server = winreg.QueryValueEx(key, 'ProxyServer')[0]
                        # 处理格式: "http=host:port;https=host:port" 或 "host:port"
                        if '=' in proxy_server:
                            proxy_items = {}
                            for item in proxy_server.split(';'):
                                if '=' in item:
                                    protocol, address = item.split('=', 1)
                                    proxy_items[protocol.lower()] = address

                            proxy_server = (
                                proxy_items.get('http')
                                or proxy_items.get('https')
                                or proxy_items.get('socks')
                                or next(iter(proxy_items.values()), proxy_server)
                            )

                        # 确保有协议前缀
                        if not proxy_server.startswith(('http://', 'https://', 'socks://', 'socks5://')):
                            proxy_server = f"http://{proxy_server}"

                        logger.info(f"从 Windows 注册表检测到代理: {proxy_server}")
                        return {"server": proxy_server}
            except Exception as e:
                logger.debug(f"Windows 代理检测失败: {e}")

        logger.info("未检测到系统代理")
        return None

    except Exception as e:
        logger.error(f"检测系统代理时出错: {e}")
        return None


def find_camoufox_executable() -> Optional[Path]:
    """
    自动查找 Camoufox 可执行文件路径

    查找顺序:
    1. 当前脚本所在目录
    2. 当前工作目录
    3. 环境变量 CAMOUFOX_PATH

    Returns:
        Camoufox 可执行文件的 Path 对象，未找到则返回 None
    """
    # Windows 下的可执行文件名
    exe_name = "camoufox.exe" if sys.platform == 'win32' else "camoufox"

    # 1. 检查当前脚本所在目录 / exe 所在目录
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).parent
    else:
        base_dir = Path(__file__).parent

    exe_path = base_dir / exe_name
    if exe_path.exists():
        logger.info(f"在程序目录找到 Camoufox: {exe_path}")
        return exe_path

    # 2. 检查当前工作目录
    cwd_path = Path.cwd() / exe_name
    if cwd_path.exists():
        logger.info(f"在工作目录找到 Camoufox: {cwd_path}")
        return cwd_path

    # 3. 检查环境变量
    env_path = os.environ.get('CAMOUFOX_PATH')
    if env_path:
        env_path = Path(env_path)
        if env_path.is_file() and env_path.exists():
            logger.info(f"从环境变量找到 Camoufox: {env_path}")
            return env_path
        elif env_path.is_dir():
            exe_path = env_path / exe_name
            if exe_path.exists():
                logger.info(f"从环境变量目录找到 Camoufox: {exe_path}")
                return exe_path

    logger.warning(f"未找到 Camoufox 可执行文件，请确保 {exe_name} 在脚本同级目录或设置 CAMOUFOX_PATH 环境变量")
    return None


class BrowserManager:
    """
    浏览器管理器
    负责 Camoufox 浏览器的启动、配置和生命周期管理
    """

    def __init__(self):
        """初始化浏览器管理器"""
        self.camoufox: Optional[AsyncCamoufox] = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

    async def launch_browser(
        self,
        proxy: Optional[Union[Dict[str, str], str]] = None,
        headless: bool = False,
        viewport: Optional[Dict[str, int]] = None,
        os: Optional[str] = "windows",
        block_images: bool = False,
        **kwargs
    ) -> Browser:
        """
        启动 Camoufox 浏览器

        Args:
            proxy: 代理配置，支持两种格式:
                   1. 字典格式: {"server": "http://host:port", "username": "user", "password": "pass"}
                   2. 字符串格式: "http://host:port" (会自动转换为字典格式)
            headless: 是否无头模式，默认为 False
            viewport: 视口大小，格式: {"width": 1920, "height": 1080}
            os: 操作系统类型，默认为 "windows"
            block_images: 是否禁用图片加载，默认为 False
            **kwargs: 其他 Camoufox 启动参数

        Returns:
            Browser: 浏览器实例
        """
        try:
            logger.info("正在启动 Camoufox 浏览器...")

            # 如果没有传入代理，自动检测系统代理
            if proxy is None:
                proxy = detect_system_proxy()
            # 如果传入的是字符串格式，自动转换为字典格式
            elif isinstance(proxy, str):
                proxy = {"server": proxy}

            # 记录代理信息
            if proxy:
                logger.info(f"使用代理: {proxy.get('server')}")
            else:
                logger.info("未使用代理")

            # 查找 Camoufox 可执行文件
            exec_path = find_camoufox_executable()
            if not exec_path:
                raise RuntimeError("无法找到 Camoufox 可执行文件")

            logger.info(f"使用 Camoufox 路径: {exec_path}")

            # 设置默认视口
            if viewport is None:
                viewport = {"width": 1920, "height": 1080}

            # 配置环境变量以抑制 Node.js 驱动进程的非致命错误
            # 这些设置可以防止 Firefox 网络管理器的竞态条件错误导致进程崩溃
            import os as os_module
            env = os_module.environ.copy()

            # 设置 Node.js 选项：
            # --unhandled-rejections=warn: 将未处理的 Promise 拒绝降级为警告而非崩溃
            # --trace-warnings: 显示警告的堆栈跟踪（可选，用于调试）
            node_options = env.get('NODE_OPTIONS', '')
            node_options += ' --unhandled-rejections=warn'
            env['NODE_OPTIONS'] = node_options.strip()

            # 设置 Node.js 不因未捕获异常而退出（仅对某些错误有效）
            env['NODE_NO_WARNINGS'] = '1'  # 抑制 Node.js 警告输出

            self.camoufox = AsyncCamoufox(
                executable_path=exec_path,
                headless=headless,
                humanize=True,
                geoip=True,
                proxy=proxy,
                locale="en-US",
                enable_cache=False,
                os=os,
                block_images=block_images,
                env=env,
                **kwargs
            )

            # 进入上下文管理器
            self.browser = await self.camoufox.__aenter__()
            logger.info("Camoufox 浏览器启动成功")

            return self.browser

        except Exception as e:
            logger.error(f"启动浏览器失败: {str(e)}")
            await self.cleanup()
            raise

    async def new_page(self) -> Page:
        """
        创建新页面

        Returns:
            Page: 页面实例
        """
        if not self.browser:
            raise RuntimeError("浏览器未初始化，请先调用 launch_browser()")

        try:
            self.page = await self.browser.new_page()
            logger.info("新页面创建成功")
            return self.page
        except Exception as e:
            logger.error(f"创建页面失败: {str(e)}")
            raise

    async def cleanup(self):
        """清理资源"""
        try:
            if self.page:
                await self.page.close()
                logger.debug("页面已关闭")

            if self.camoufox:
                await self.camoufox.__aexit__(None, None, None)
                logger.debug("Camoufox 浏览器已关闭")

        except Exception as e:
            logger.error(f"清理资源时出错: {str(e)}")

    async def __aenter__(self):
        """上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        await self.cleanup()


async def create_browser(
    proxy: Optional[Union[Dict[str, str], str]] = None,
    headless: bool = False,
    viewport: Optional[Dict[str, int]] = None,
    os: str = "windows",
    block_images: bool = False,
    **kwargs
) -> BrowserManager:
    """
    快捷函数：创建并启动浏览器

    Args:
        proxy: 代理配置，支持两种格式:
               1. 字典格式: {"server": "http://127.0.0.1:17890"}
               2. 字符串格式: "http://127.0.0.1:17890" (会自动转换)
        headless: 是否无头模式，默认为 False
        viewport: 视口大小
        os: 操作系统类型，默认为 "windows"
        block_images: 是否禁用图片加载，默认为 False
        **kwargs: 其他启动参数

    Returns:
        BrowserManager: 浏览器管理器实例
    """
    manager = BrowserManager()
    await manager.launch_browser(
        proxy=proxy,
        headless=headless,
        viewport=viewport,
        os=os,
        block_images=block_images,
        **kwargs
    )
    return manager

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="Camoufox GeoIP 中间件")
    parser.add_argument("-proxy", dest="proxy", help="代理地址，例如 http://127.0.0.1:7890")
    parser.add_argument("-os", dest="os", default="windows", help="操作系统类型，默认 windows")
    parser.add_argument("-headless", dest="headless", action="store_true", help="启用无头模式")
    parser.add_argument(
        "-block-images",
        dest="block_images",
        action="store_true",
        help="禁用图片加载",
    )
    # URL 作为位置参数（支持默认浏览器调用时传入）
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="要打开的 URL（支持默认浏览器调用）",
    )
    parser.add_argument(
        "-url",
        dest="flag_url",
        default=None,
        help="要打开的 URL（等价于位置参数）",
    )
    return parser.parse_args()


async def main():
    """
    主程序入口
    启动 Camoufox 浏览器并保持运行，直到用户手动关闭
    """
    args = parse_args()
    proxy = args.proxy or detect_system_proxy()
    target_url = args.flag_url or args.url

    manager = None
    try:
        logger.info("=" * 60)
        logger.info("Camoufox GeoIP 中间件")
        logger.info("=" * 60)
        logger.info(f"OS: {args.os}")
        logger.info(f"Proxy: {proxy['server'] if proxy else '未配置，将直连'}")

        manager = await create_browser(
            proxy=proxy,
            headless=args.headless,
            os=args.os,
            block_images=args.block_images,
        )

        page = await manager.new_page()
        logger.info("浏览器启动成功！")
        logger.info("功能说明:")
        logger.info("  - GeoIP 功能已启用（时区随 IP 变化）")
        logger.info("  - 代理优先使用命令行参数，未传时自动检测系统代理")
        logger.info("  - 浏览器指纹已随机化")
        logger.info("提示:")
        logger.info("  - 浏览器窗口将保持打开状态")
        logger.info("  - 按 Ctrl+C 或关闭此窗口可退出程序")
        logger.info("=" * 60)

        if target_url:
            logger.info(f"正在打开 URL: {target_url}")
            await page.goto(target_url)
        else:
            logger.info("未提供 URL，浏览器将保持空白页")

        # 主循环：保持程序运行，忽略浏览器驱动的非致命错误
        while True:
            try:
                # 检查浏览器是否仍然连接
                if manager.browser and manager.browser.is_connected():
                    await asyncio.sleep(1)
                else:
                    logger.warning("浏览器连接已断开，但窗口可能仍在运行")
                    logger.info("如果浏览器窗口仍然打开，可以继续使用")
                    logger.info("程序将继续运行，按 Ctrl+C 退出")
                    # 即使连接断开，也保持程序运行
                    await asyncio.sleep(1)
            except Exception as e:
                # 捕获并忽略所有非致命错误，保持程序运行
                error_msg = str(e)
                if "setTransferSize" in error_msg or "ffNetworkManager" in error_msg:
                    logger.debug(f"忽略 Firefox 网络管理器错误: {error_msg}")
                else:
                    logger.debug(f"忽略非致命错误: {error_msg}")
                await asyncio.sleep(1)

    except KeyboardInterrupt:
        logger.info("用户中断，正在关闭浏览器...")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")

    finally:
        if manager:
            try:
                await manager.cleanup()
                logger.info("浏览器已关闭")
            except Exception as e:
                logger.debug(f"清理时出现错误（可忽略）: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序已退出")
    except Exception as e:
        logger.error(f"程序异常退出: {e}")
