import os
from aiogram import Bot, Router
from aiogram.types import CallbackQuery, InputFile
from aiogram.fsm.context import FSMContext
from PIL import Image, ImageDraw, ImageFont
from tempfile import NamedTemporaryFile
from asgiref.sync import sync_to_async
import os
from pathlib import Path

async def draw_image(data):
    print("Current working directory:", os.getcwd())
    current_dir = Path(__file__).parent
    file_path = current_dir / "asd.jpg"
    image = Image.open(file_path)
    # image = Image.open('asd.jpg')
    draw = ImageDraw.Draw(image)

    # font_path = current_dir / "Roboto/Roboto-Medium.ttf"
    font = ImageFont.truetype("/tg/handlers/Roboto/Roboto-Medium.ttf", size=40)
    color = (255, 255, 255)

    # Текст, который мы хотим нарисовать
    text = f"{data['amount']} {data['network']}"
    image_width, image_height = image.size
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]  # Ширина текста
    text_height = bbox[3] - bbox[1]  # Высота текста
    x = (image_width - text_width) // 2
    y = 140
    draw.text((x, y), text, font=font, fill=color)

    font = ImageFont.truetype('Roboto/Roboto-Regular.ttf', size=17)
    y = 517
    right_margin = 20
    x = image_width - text_width - right_margin
    if x < 0:
        x = 0

    date = data['applyTime']
    draw.text((x, y), text, font=font, fill=color)
    draw.text((316, 660), date, font=font, fill=color)

    address = data['address']
    padding = 20
    bbox = draw.textbbox((0, 0), address, font=font)
    text_width = bbox[2] - bbox[0]
    x_position = image.width - text_width - padding
    y_position = 445

    draw.text((x_position, y_position), address, font=font, fill=color)

    with NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
        image.save(temp_file, format="PNG")
        temp_file_path = temp_file.name
    return temp_file_path