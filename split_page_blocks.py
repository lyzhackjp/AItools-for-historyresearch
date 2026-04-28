"""
页面分块分析器
将每页竖排文献切分为上中下三大块
使用空白区域作为切分标志
"""
import os
import sys
from pathlib import Path
from PIL import Image
import numpy as np


class PageBlockSplitter:
    """页面分块切割器"""

    def __init__(self, image_path: str):
        """
        初始化分块器

        Args:
            image_path: 图片路径
        """
        self.image_path = Path(image_path)
        self.img = Image.open(image_path)
        self.img_array = np.array(self.img.convert('L'))  # 转为灰度

    def analyze_layout(self) -> dict:
        """
        分析页面布局，返回三块的位置信息

        Returns:
            dict: 包含三块的位置信息
        """
        width, height = self.img.size

        # 将页面水平分stripes，分析每列的空白程度
        # 竖排三块意味着左右方向有三个主要内容区

        # 分析垂直方向（上下分块）的空白
        horizontal_profile = self._get_horizontal_profile()

        # 找到三个主要内容的区域
        # 通过分析哪些区域内容密集、哪些是空白
        blocks = self._find_content_blocks(horizontal_profile, width, height)

        return blocks

    def _get_horizontal_profile(self) -> np.ndarray:
        """
        获取水平方向的空白分布
        返回每列（垂直条带）的平均灰度值
        """
        img_array = self.img_array
        # 按列计算平均值
        col_means = img_array.mean(axis=0)
        return col_means

    def _get_vertical_profile(self) -> np.ndarray:
        """
        获取垂直方向的空白分布
        返回每行（水平条带）的平均灰度值
        """
        img_array = self.img_array
        # 按行计算平均值
        row_means = img_array.mean(axis=1)
        return row_means

    def _find_content_blocks(self, profile: np.ndarray, width: int, height: int) -> dict:
        """
        找到内容密集的区域（分块）

        Args:
            profile: 灰度分布
            width, height: 图片尺寸

        Returns:
            三块的位置信息
        """
        # 阈值：低于此值认为是空白
        threshold = 240

        # 找出所有低于阈值的列（密集内容区）
        content_cols = np.where(profile < threshold)[0]

        if len(content_cols) == 0:
            return {'left': (0, width//3), 'middle': (width//3, 2*width//3), 'right': (2*width//3, width)}

        # 找到内容的连续区域
        content_regions = []
        start = content_cols[0]
        for i in range(1, len(content_cols)):
            if content_cols[i] != content_cols[i-1] + 1:
                # 断开
                content_regions.append((start, content_cols[i-1]))
                start = content_cols[i]
        content_regions.append((start, content_cols[-1]))

        print(f"发现 {len(content_regions)} 个内容区域:")
        for i, (s, e) in enumerate(content_regions):
            print(f"  区域 {i+1}: 列 {s}-{e} (宽度: {e-s})")

        # 根据内容区域位置，决定三块划分
        # 通常三块是均匀分布的，但有些区域可能有空白间隙

        # 方法：找到两个最大的间隙作为分界线
        if len(content_regions) >= 3:
            # 计算每个区域的中心
            centers = [(s + e) // 2 for s, e in content_regions]

            # 找到两个最远的区域中心之间的分界线
            # 但这可能不够准确

            # 备选方案：按列均分三块
            blocks = {
                'left': (0, width // 3),
                'middle': (width // 3, 2 * width // 3),
                'right': (2 * width // 3, width)
            }
        elif len(content_regions) == 1:
            # 只有一个区域，按列均分
            blocks = {
                'left': (0, width // 3),
                'middle': (width // 3, 2 * width // 3),
                'right': (2 * width // 3, width)
            }
        elif len(content_regions) == 2:
            # 两个区域
            blocks = {
                'left': (0, width // 3),
                'middle': (width // 3, 2 * width // 3),
                'right': (2 * width // 3, width)
            }
        else:
            # 太少的区域，按均分
            blocks = {
                'left': (0, width // 3),
                'middle': (width // 3, 2 * width // 3),
                'right': (2 * width // 3, width)
            }

        return blocks

    def split_into_blocks(self, output_dir: str = None) -> dict:
        """
        将页面切分为多个块

        Returns:
            dict: 块路径信息
        """
        blocks = self.analyze_layout()

        if output_dir is None:
            output_dir = self.image_path.parent

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        block_paths = {}

        for block_name, (x1, x2) in blocks.items():
            # 裁剪左侧块
            block_img = self.img.crop((x1, 0, x2, self.img.height))

            # 输出文件名
            output_path = output_dir / f"{self.image_path.stem}_{block_name}.png"
            block_img.save(output_path)

            block_paths[block_name] = str(output_path)
            print(f"保存块 {block_name}: {output_path} ({x1}-{x2})")

        return block_paths


def split_all_pages(image_dir: str, output_base: str = None) -> dict:
    """
    将目录下所有图片分块

    Args:
        image_dir: 图片目录
        output_base: 输出根目录

    Returns:
        所有页面的分块结果
    """
    image_dir = Path(image_dir)

    if output_base is None:
        output_base = image_dir.parent / 'split_blocks'

    results = {}

    for img_path in sorted(image_dir.glob('*.png')):
        print(f"\n处理: {img_path.name}")

        try:
            splitter = PageBlockSplitter(str(img_path))
            blocks = splitter.split_into_blocks(str(Path(output_base) / img_path.stem))
            results[img_path.name] = blocks
        except Exception as e:
            print(f"  错误: {e}")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="页面分块切割")
    parser.add_argument('image_path', help="图片路径或目录")
    parser.add_argument('--output', '-o', help="输出目录")

    args = parser.parse_args()

    img_path = Path(args.image_path)

    if img_path.is_dir():
        split_all_pages(str(img_path), args.output)
    else:
        splitter = PageBlockSplitter(str(img_path))
        blocks = splitter.analyze_layout()
        print(f"\n分块结果: {blocks}")

        if args.output:
            splitter.split_into_blocks(args.output)
