import math
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont


def create_rounded_avatar(avatar_data: bytes, size: int = 200) -> Image.Image:
    """将头像图片裁剪为圆形"""
    img = Image.open(BytesIO(avatar_data)).convert("RGBA")
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    
    # 创建圆形遮罩
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size, size), fill=255)
    
    # 应用遮罩
    result = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    result.paste(img, mask=mask)
    
    return result


def get_font(size: int) -> ImageFont.FreeTypeFont:
    """获取支持中文的字体"""
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "msyh.ttc",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_wife_image(
    sender_avatar: bytes,
    wife_avatar: bytes,
    sender_name: str,
    wife_name: str,
    width: int = 900,
    height: int = 600,
    avatar_size: int = 200,
) -> bytes:
    """生成今日老婆图片"""
    # 创建背景
    img = Image.new("RGB", (width, height), (255, 240, 245))
    draw = ImageDraw.Draw(img)
    
    # 计算头像位置
    avatar_y = (height - avatar_size) // 2 - 30
    left_avatar_x = width // 4 - avatar_size // 2
    right_avatar_x = width * 3 // 4 - avatar_size // 2
    
    # 处理头像
    sender_img = create_rounded_avatar(sender_avatar, avatar_size)
    wife_img = create_rounded_avatar(wife_avatar, avatar_size)
    
    # 粘贴头像
    img.paste(sender_img, (left_avatar_x, avatar_y), sender_img)
    img.paste(wife_img, (right_avatar_x, avatar_y), wife_img)
    
    # 绘制中间的大爱心符号（居中）
    font_big_heart = get_font(50)
    heart_x = width // 2 - 25
    heart_y = height // 2 - 25
    draw.text((heart_x, heart_y), "♥", fill=(255, 20, 147), font=font_big_heart)
    
    # 绘制文字
    font_large = get_font(40)
    font_medium = get_font(28)
    
    # 标题文字
    title = "今日老婆"
    title_bbox = draw.textbbox((0, 0), title, font=font_large)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(
        ((width - title_width) // 2, 25),
        title,
        fill=(255, 20, 147),
        font=font_large,
    )
    
    # 昵称文字
    max_name_len = 8
    display_sender = sender_name[:max_name_len] + "..." if len(sender_name) > max_name_len else sender_name
    display_wife = wife_name[:max_name_len] + "..." if len(wife_name) > max_name_len else wife_name
    
    # 左侧昵称
    sender_bbox = draw.textbbox((0, 0), display_sender, font=font_medium)
    sender_text_width = sender_bbox[2] - sender_bbox[0]
    draw.text(
        (left_avatar_x + (avatar_size - sender_text_width) // 2, avatar_y + avatar_size + 10),
        display_sender,
        fill=(139, 69, 19),
        font=font_medium,
    )
    
    # 右侧昵称
    wife_bbox = draw.textbbox((0, 0), display_wife, font=font_medium)
    wife_text_width = wife_bbox[2] - wife_bbox[0]
    draw.text(
        (right_avatar_x + (avatar_size - wife_text_width) // 2, avatar_y + avatar_size + 10),
        display_wife,
        fill=(139, 69, 19),
        font=font_medium,
    )
    
    # 底部文字
    bottom_text = f"{display_sender} 的今日老婆是 {display_wife}"
    bottom_bbox = draw.textbbox((0, 0), bottom_text, font=font_medium)
    bottom_text_width = bottom_bbox[2] - bottom_bbox[0]
    draw.text(
        ((width - bottom_text_width) // 2, height - 50),
        bottom_text,
        fill=(255, 105, 180),
        font=font_medium,
    )
    
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def generate_baby_image(
    sender_avatar: bytes,
    wife_avatar: bytes,
    baby_avatars: list[bytes],
    sender_name: str,
    wife_name: str,
    baby_names: list[str],
    width: int = 900,
    height: int = 800,
    avatar_size: int = 150,
) -> bytes:
    """生成生小孩图片（家庭照，底部一排展示孩子）"""
    # 创建背景
    img = Image.new("RGB", (width, height), (255, 240, 245))
    draw = ImageDraw.Draw(img)
    
    # 处理头像
    sender_img = create_rounded_avatar(sender_avatar, avatar_size)
    wife_img = create_rounded_avatar(wife_avatar, avatar_size)
    baby_imgs = [create_rounded_avatar(avatar, avatar_size) for avatar in baby_avatars]
    
    # 布局：上方中间是父母，下方一排是孩子
    parent_y = 80
    sender_x = width // 4 - avatar_size // 2
    wife_x = width * 3 // 4 - avatar_size // 2
    
    # 粘贴父母头像
    img.paste(sender_img, (sender_x, parent_y), sender_img)
    img.paste(wife_img, (wife_x, parent_y), wife_img)
    
    # 绘制文字
    font_large = get_font(36)
    font_medium = get_font(24)
    font_small = get_font(20)
    
    # 标题
    title = "原神家庭"
    title_bbox = draw.textbbox((0, 0), title, font=font_large)
    title_width = title_bbox[2] - title_bbox[0]
    draw.text(
        ((width - title_width) // 2, 25),
        title,
        fill=(255, 105, 180),
        font=font_large,
    )
    
    # 昵称处理函数
    def truncate_name(name: str, max_len: int = 8) -> str:
        return name[:max_len] + "..." if len(name) > max_len else name
    
    display_sender = truncate_name(sender_name)
    display_wife = truncate_name(wife_name)
    
    # 父亲昵称（左上）
    sender_bbox = draw.textbbox((0, 0), display_sender, font=font_medium)
    sender_text_width = sender_bbox[2] - sender_bbox[0]
    draw.text(
        (sender_x + (avatar_size - sender_text_width) // 2, parent_y + avatar_size + 10),
        display_sender,
        fill=(65, 105, 225),
        font=font_medium,
    )
    
    # 母亲昵称（右上）
    wife_bbox = draw.textbbox((0, 0), display_wife, font=font_medium)
    wife_text_width = wife_bbox[2] - wife_bbox[0]
    draw.text(
        (wife_x + (avatar_size - wife_text_width) // 2, parent_y + avatar_size + 10),
        display_wife,
        fill=(255, 105, 180),
        font=font_medium,
    )
    
    # 绘制父母之间的爱心
    heart_font = get_font(30)
    heart_x = width // 2 - 15
    heart_y = parent_y + avatar_size // 2 - 15
    draw.text((heart_x, heart_y), "♥", fill=(255, 20, 147), font=heart_font)
    
    # 绘制孩子区域
    if baby_imgs:
        # 计算孩子头像的布局（一排居中）
        num_children = len(baby_imgs)
        child_spacing = 30  # 孩子之间的间距
        total_children_width = num_children * avatar_size + (num_children - 1) * child_spacing
        start_x = (width - total_children_width) // 2
        child_y = height - avatar_size - 80  # 底部留出空间给昵称
        
        # 绘制"孩子"标签
        child_label = "孩子"
        child_label_bbox = draw.textbbox((0, 0), child_label, font=font_medium)
        child_label_width = child_label_bbox[2] - child_label_bbox[0]
        draw.text(
            ((width - child_label_width) // 2, child_y - 40),
            child_label,
            fill=(139, 69, 19),
            font=font_medium,
        )
        
        # 绘制每个孩子
        for i, (baby_img, baby_name) in enumerate(zip(baby_imgs, baby_names)):
            child_x = start_x + i * (avatar_size + child_spacing)
            
            # 粘贴孩子头像
            img.paste(baby_img, (child_x, child_y), baby_img)
            
            # 绘制孩子昵称
            display_baby = truncate_name(baby_name)
            baby_bbox = draw.textbbox((0, 0), display_baby, font=font_small)
            baby_text_width = baby_bbox[2] - baby_bbox[0]
            draw.text(
                (child_x + (avatar_size - baby_text_width) // 2, child_y + avatar_size + 5),
                display_baby,
                fill=(34, 139, 34),
                font=font_small,
            )
    
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()
