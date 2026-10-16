from __future__ import annotations

import asyncio
import math
from io import BytesIO
from pathlib import Path
from typing import Any


class LotteryGifRenderer:
    """使用 Playwright 加载 lottery.html，逐帧截图并输出 500x180 GIF。"""

    OUTPUT_WIDTH = 500
    OUTPUT_HEIGHT = 300

    def __init__(
        self,
        *,
        html_path: Path,
        gif_duration_ms: int,
        fps: int,
        max_width: int,
        timeout_ms: int,
        browser_channel: str = "",
        max_concurrent_renders: int = 2,
    ):
        self.html_path = html_path
        self.gif_duration_ms = max(1200, gif_duration_ms)
        self.fps = max(4, min(20, fps))
        self.max_width = max_width
        self.timeout_ms = max(5000, timeout_ms)
        self.browser_channel = browser_channel or ""
        self._playwright: Any = None
        self._browser: Any = None
        self._start_lock = asyncio.Lock()
        self._render_semaphore = asyncio.Semaphore(max_concurrent_renders)

    async def start(self) -> None:
        if self._browser is not None:
            return
        async with self._start_lock:
            if self._browser is not None:
                return

            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            launch_options: dict[str, Any] = {
                "headless": True,
                "args": ["--no-sandbox", "--disable-dev-shm-usage"],
            }
            if self.browser_channel:
                launch_options["channel"] = self.browser_channel
            try:
                self._browser = await self._playwright.chromium.launch(**launch_options)
            except Exception:
                await self._playwright.stop()
                self._playwright = None
                raise

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def render(self, item_name: str, output_path: Path) -> None:
        if not self.html_path.exists():
            raise FileNotFoundError(f"抽奖页面不存在：{self.html_path}")
        if self._browser is None:
            await self.start()

        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._render_semaphore:
            page = await self._browser.new_page(
                viewport={
                    "width": self.OUTPUT_WIDTH,
                    "height": self.OUTPUT_HEIGHT,
                },
                device_scale_factor=2,
            )
            try:
                page.set_default_timeout(self.timeout_ms)
                await page.goto(self.html_path.resolve().as_uri(), wait_until="load")
                await page.wait_for_function(
                    """
                    () => Boolean(window.__lotteryBridge) &&
                      Array.from(document.images).every(image => image.complete)
                    """
                )
                await page.evaluate("() => document.fonts.ready")
                await page.add_style_tag(
                    content=".result-card, .draw-btn, .toast { display: none !important; }"
                )

                frame_delay = 1.0 / self.fps
                frame_count = max(
                    8, math.ceil(self.gif_duration_ms / 1000 * self.fps) + 1
                )
                await page.evaluate(
                    """
                    ([itemName, durationMs]) => {
                      window.__lotteryBridge.configure(itemName, durationMs);
                      window.__lotteryBridge.start();
                    }
                    """,
                    [item_name, self.gif_duration_ms],
                )

                clip = {
                    "x": 0,
                    "y": 0,
                    "width": self.OUTPUT_WIDTH,
                    "height": self.OUTPUT_HEIGHT,
                }
                frames: list[bytes] = []
                loop = asyncio.get_running_loop()
                started_at = loop.time()
                for frame_index in range(frame_count):
                    due = started_at + frame_index * frame_delay
                    wait_seconds = due - loop.time()
                    if wait_seconds > 0:
                        await asyncio.sleep(wait_seconds)
                    frames.append(await page.screenshot(type="png", clip=clip))

                await page.wait_for_function(
                    "() => !window.__lotteryBridge.isRolling()",
                    timeout=self.gif_duration_ms + 5000,
                )
                frames.append(await page.screenshot(type="png", clip=clip))
                await asyncio.to_thread(self._save_gif, frames, output_path)
            finally:
                await page.close()

    def _save_gif(self, frame_data: list[bytes], output_path: Path) -> None:
        from PIL import Image

        output_size = (self.OUTPUT_WIDTH, self.OUTPUT_HEIGHT)
        images: list[Image.Image] = []
        for data in frame_data:
            image = Image.open(BytesIO(data)).convert("RGB")
            if image.size != output_size:
                image = image.resize(output_size, Image.Resampling.LANCZOS)
            images.append(
                image.quantize(
                    colors=256,
                    method=Image.Quantize.MEDIANCUT,
                    dither=Image.Dither.NONE,
                )
            )

        frame_duration = max(40, round(1000 / self.fps))
        durations = [frame_duration] * max(0, len(images) - 1) + [1200]
        images[0].save(
            output_path,
            format="GIF",
            save_all=True,
            append_images=images[1:],
            duration=durations,
            loop=0,
            optimize=True,
            disposal=2,
        )
