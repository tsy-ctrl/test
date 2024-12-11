import subprocess
import sys
import os
import base64
import json
import html
import threading
import asyncio
from io import BytesIO
import glob
import platform
import re
import time
import hmac
import hashlib
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from telethon import TelegramClient
from flask import Flask, render_template, url_for, request, jsonify
from telethon import events
from telethon.tl.types import InputPeerUser, DocumentAttributeVideo 
from telethon.tl.functions.contacts import AddContactRequest
from telethon.tl.functions.messages import CheckChatInviteRequest
from telethon.tl.types import ChatInviteAlready, ChatInvite
from dotenv import load_dotenv
from PIL import Image,  ExifTags
from send2trash import send2trash
import telethon
import pyperclip
import cryptg
import uuid

exe_path = os.path.abspath(sys.executable)
exe_dir = os.path.dirname(exe_path)
ffmpeg_path = os.path.join(exe_dir, "ffmpeg")

if platform.system() == "Darwin":
    print("FFMPEG path: ", ffmpeg_path)
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
    os.chmod(ffmpeg_path, 0o755)

from moviepy import VideoFileClip

sys.stdout.flush()
# Initialize the Flask application

templatesDir = os.getcwd() + '/templates'
staticDir = os.getcwd() + '/static'

app = Flask(__name__, template_folder=templatesDir, static_folder=staticDir)
last_author = None

with open('templates/output.html', 'w', encoding='utf-8') as f:
    f.write("""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @keyframes swing {
                0% { transform: rotate(30deg); }
                50% { transform: rotate(15deg); }
                100% { transform: rotate(30deg); }
            }
            body {
                background-color: black;
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                font-size: 2em;
                font-family: Arial, sans-serif;
                overflow-x: hidden;
                overflow-y: hidden;
            }
            .logo {
                background-color: white;
                width: 400px;
                height: 400px;
                background-image: url('https://i.imgur.com/5dQ4At1.jpg');
                background-size: 107%;
                background-position: center;
                border-radius: 50%;
                transform: rotate(30deg);
                animation: swing 2s infinite ease-in-out;
            }
        </style>
    </head>
    <body>
        <div class="logo"></div>
    </body>
    </html>
    """)

def get_client_id(client):
    global clients
    for client_id, client_instance in clients.items():
        if client_instance == client:
            return client_id
    return None


def test_hashtag(text):
    for i in range(len(text)):
        if text[i] == '#':
            if i + 1 < len(text) and text[i + 1] != '#' and text[i + 1] != ' ':
                return text
    text += '\n\n#ads'
    return text

def replace_text(text):
    text = re.sub(r'#ad(?!\w)', '#ads', text, flags=re.IGNORECASE)
    text = re.sub(r'@\s\(https://onlyfans.com/(\w+)\)\1', r'@$1', text, flags=re.IGNORECASE)
    text = re.sub(r'\(https://\S+\)', '', text)
    text = test_hashtag(text)
    return text

def delete_files_py():
    retry_attempts=5
    delay=1
    try:
        while True:
            files = glob.glob(os.path.join(folder, '*'))
            if not files:
                break
            for f in files:
                for attempt in range(retry_attempts):
                    try:
                        send2trash(f)
                        break
                    except Exception as e:
                        time.sleep(delay)  
        return
    except Exception as e:
        print(f"Произошла ошибка: {e}")
        return

@app.route('/open-folder', methods=['POST'])
def open_folder():
    try:
        if os.path.exists(folder):
            if os.name == 'nt':
                subprocess.Popen(f'explorer {folder}')
            elif os.name == 'posix': 
                subprocess.Popen(['open', folder] if sys.platform == 'darwin' else ['xdg-open', folder])
            return jsonify(message='Folder opened!')
        else:
            return jsonify(message='Folder not found!')
    except Exception as e:
        return jsonify(message=str(e))

def set_clipboard_files(file_paths):
    paths_str = '","'.join(file_paths)  # Формируем строку с путями через запятую
    command = f'powershell Set-Clipboard -LiteralPath "{paths_str}"'
    os.system(command)
    print(f"Files {file_paths} copied to clipboard!")


@app.route('/stop-processing', methods=['POST'])
def stop_processing():
    try:
        return jsonify(message='Processing stopped!')
    except Exception as e:
        return jsonify(message=str(e)), 500

@app.route('/copy-files', methods=['POST'])
def copy_files():
    try:
        if platform.system() != 'Windows':
            return jsonify(message='Windows only'), 400
        if not os.path.exists(folder):
            return jsonify(message='Folder not found!'), 404
        file_paths = []
        for filename in os.listdir(folder):
            src_file = os.path.join(folder, filename)
            if os.path.isfile(src_file):
                file_paths.append(src_file)
        if not file_paths:
            return jsonify(message='No files found in folder.'), 404
        set_clipboard_files(file_paths)
        return jsonify(message='Files copied to clipboard!')
    except Exception as e:
        return jsonify(message=str(e)), 500

@app.route('/sendFiles', methods=['POST'])
def write_files():
    try: 
        data = request.get_json()
        with open('files/sendInfo.json', 'w') as f:
            json.dump(data, f)
        return jsonify(message='Sending files...')
    except Exception as e:
         return jsonify(message=str(e))

@app.route('/delete-files', methods=['POST'])
def delete_files():
    try:
        while True:
            files = glob.glob(os.path.join(folder, '*'))
            if not files: 
                break
            for f in files:
                send2trash(f)
        return jsonify(message='All files deleted')
    except Exception:
        return jsonify()
    
switch = False

def update_html(switch):
    with open('templates/output.html', 'r', encoding='utf-8') as f:
        html = f.read()

    old_str = f'switchAutoDelete()" style="background-color: {"red" if switch else "#488b5b"}'
    new_str = f'switchAutoDelete()" style="background-color: {"#488b5b" if switch else "red"}'
    html = html.replace(old_str, new_str)

    with open('templates/output.html', 'w', encoding='utf-8') as f:
        f.write(html)

@app.route('/switch-auto-delete', methods=['POST'])
def switch_auto_delete():
     global switch
     switch = not switch
     update_html(switch)
     return jsonify(message=f'Autodelete is now {"on" if switch else "off"}')

@app.route('/delete-files-one', methods=['POST'])
def delete_files_one():
    try:
        files = glob.glob(os.path.join(folder, '*'))
        if not files:
            return jsonify(message='No files to delete')
        files.sort(key=os.path.getmtime)
        send2trash(files[-1])
        return jsonify(message='Deleted 1 file')
    except Exception:
          return jsonify()

@app.route('/check-files', methods=['GET'])
def check_files():
    files = len(glob.glob(os.path.join(folder, '*')))
    return {'files': files}

@app.route('/update_hints', methods=['POST'])
def update_hints():
   data = request.json
   hint_key = data.get('hint_key')
   action = data.get('action', 'update')
   hint_type = data.get('hint_type', 'personal')  # personal или general

   try:
       # Выбираем нужный путь в зависимости от типа подсказок
       hints_path = os.path.join('..', 'files', 'hints',
           'hints.json' if hint_type == 'personal' else 'allhints.json')
       
       # Для персональных подсказок нужен chat_id
       chat_id = data.get('chat_id') if hint_type == 'personal' else None
       
       # Загрузка данных
       with open(hints_path, 'r') as f:
           hints_data = json.load(f)
       
       # Для персональных подсказок
       if hint_type == 'personal':
           if str(chat_id) in hints_data:
               # Логика удаления
               if action == 'delete':
                   if hint_key in hints_data[str(chat_id)]:
                       del hints_data[str(chat_id)][hint_key]
                   
                   # Находим не служебные ключи
                   non_service_keys = [key for key in hints_data[str(chat_id)].keys() 
                                       if key not in ['checkbox', 'now']]
                   
                   # Если не осталось ключей, очищаем запись
                   if not non_service_keys:
                       hints_data[str(chat_id)] = {'now': hints_data[str(chat_id)].get('now', False)}
                   else:
                       # Если удален текущий checkbox, обновляем
                       if hints_data[str(chat_id)].get('checkbox') == hint_key:
                           hints_data[str(chat_id)]['checkbox'] = non_service_keys[0]

                   # Обновление checkbox
               elif action == 'update':
                    hints_data[str(chat_id)]['checkbox'] = hint_key
                    
                    # Очищаем checkbox в общих подсказках
                    allhints_path = os.path.join('..', 'files', 'hints', 'allhints.json')
                    with open(allhints_path, 'r') as f:
                        allhints_data = json.load(f)
                    
                    # Очищаем checkbox в общих подсказках
                    allhints_data['checkbox'] = ''
                    
                    # Сохраняем изменения в общих подсказках
                    with open(allhints_path, 'w') as f:
                        json.dump(allhints_data, f, indent=4, ensure_ascii=False)
       
       # Для общих подсказок
       else:
           # Логика удаления
           if action == 'delete':
               if hint_key in hints_data.get('hints', []):
                   hints_data['hints'].remove(hint_key)
                   
                   # Сброс checkbox если удален текущий
                   if hints_data.get('checkbox') == hint_key:
                       hints_data['checkbox'] = ''
           
           # Обновление checkbox
           elif action == 'update':
               hints_data['checkbox'] = hint_key
               
               # Если это общие подсказки, очищаем персональные checkbox
               hints_hints_path = os.path.join('..', 'files', 'hints', 'hints.json')
               with open(hints_hints_path, 'r') as f:
                   hints_hints_data = json.load(f)
               
               # Очищаем checkbox во всех персональных подсказках
               for chat_id in hints_hints_data:
                   if 'checkbox' in hints_hints_data[chat_id]:
                       hints_hints_data[chat_id]['checkbox'] = ''
               
               # Сохраняем изменения в персональных подсказках
               with open(hints_hints_path, 'w') as f:
                   json.dump(hints_hints_data, f, indent=4, ensure_ascii=False)
       
       # Сохраняем изменения
       with open(hints_path, 'w') as f:
           json.dump(hints_data, f, indent=4, ensure_ascii=False)
       
       # Проверка на пустоту (только для персональных подсказок)
       if hint_type == 'personal':
           if str(chat_id) in hints_data and len(hints_data[str(chat_id)]) <= 1:
               return jsonify({
                   "status": "empty", 
                   "hint_key": hint_key, 
                   "action": action
               })
       
       return jsonify({
           "status": "success", 
           "hint_key": hint_key, 
           "action": action
       })
   
   except Exception as e:
       return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/add-hint', methods=['POST'])
def add_hint():
    data = request.json
    new_hint_key = data.get('hint_key')
    hint_type = data.get('hint_type', 'personal')  # personal или general
    
    # Выбираем путь в зависимости от типа
    hints_path = os.path.join('..', 'files', 'hints',
        'hints.json' if hint_type == 'personal' else 'allhints.json')
    
    try:
        # Загрузка существующих подсказок
        with open(hints_path, 'r', encoding='utf-8') as hints_file:
            hints_data = json.load(hints_file)
        
        # Для персональных подсказок
        if hint_type == 'personal':
            chat_id = str(data.get('chat_id'))
            message_count = int(data.get('message_count', 0))
            
            if chat_id not in hints_data:
                hints_data[chat_id] = {'now': False}
            
            # Логика формирования ключа
            hint_parts = new_hint_key.split()
            new_message_count = (message_count * 2 
                if not hints_data[chat_id].get('now', False) 
                else message_count)
            
            new_hint_value = (f"{new_hint_key} {new_message_count}" 
                            if len(hint_parts) == 1 
                            else new_hint_key)
            
            hints_data[chat_id][new_hint_value] = 0
            
            # Обновление checkbox
            if 'checkbox' not in hints_data[chat_id] or not hints_data[chat_id].get('checkbox'):
                non_service_keys = [
                    key for key in hints_data[chat_id].keys() 
                    if key not in ['now', 'checkbox']
                ]
                if non_service_keys:
                    hints_data[chat_id]['checkbox'] = non_service_keys[0]
            
            result_key = new_hint_value
        
        # Для общих подсказок
        else:
            # Создаем список hints если его нет
            if 'hints' not in hints_data:
                hints_data['hints'] = []
            
            # Добавляем только уникальные подсказки
            if new_hint_key not in hints_data['hints']:
                hints_data['hints'].append(new_hint_key)
            
            # Обновляем checkbox
            if not hints_data.get('checkbox'):
                hints_data['checkbox'] = new_hint_key
            
            result_key = new_hint_key
        
        # Сохраняем изменения
        with open(hints_path, 'w', encoding='utf-8') as hints_file:
            json.dump(hints_data, hints_file, ensure_ascii=False, indent=4)
        
        return jsonify({
            "success": True, 
            "full_hint_key": result_key
        })
    
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": str(e)})
    

executor = ThreadPoolExecutor(max_workers=1)

@app.route('/')
def index():
    return render_template('output.html')

async def process_gif(clip):
    clip = clip.set_duration(min(clip.duration, 10)) 
    clip = clip.resize(0.75) 
    return clip

def correct_orientation(img):
    try:
        for orientation in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation] == 'Orientation':
                break
        exif = dict(img._getexif().items())

        if exif[orientation] == 3:
            img = img.rotate(180, expand=True)
        elif exif[orientation] == 6:
            img = img.rotate(270, expand=True)
        elif exif[orientation] == 8:
            img = img.rotate(90, expand=True)

    except (AttributeError, KeyError, IndexError):
        pass

    return img

async def process_message(message, message_index):

    def get_at_word(message):
        text = html.escape(message.text).replace('\n', '<br>').replace('`', "'")
        text = re.sub(r'\\[|\\]|\\(|\\)', ' ', text) 
        text = re.sub(r'\\([^)]*\\)', '', text)
        text = re.sub(r'https?\\S+', '', text)
        text = re.sub(r'@\\s+', '@', text)
        text = re.sub(r"^'''|'''$", "", text)
        text = re.sub(r'`', '', text)
        text = replace_text(text)
        at_word_match = re.search(r'@([a-zA-Z0-9-_.]+)', text)
        at_word2 = at_word_match.group(1) if at_word_match else ''
        at_word = at_word_match.group(1).replace('.', '-') if at_word_match else ''
        while at_word.endswith('-'):
            at_word = at_word[:-1]
        with open(os.path.join('..', 'files', 'tags.txt'), 'a', encoding='utf-8') as ff:
            ff.write(at_word2 + '\n')
        return at_word, text

    def write_to_output(message, output_file, output_main_file):
        with open(output_file, 'a', encoding='utf-8') as f:
            at_word, text = get_at_word(message)
            f.write(f'<span class="copy-button" onclick="copyToClipboard(`{text}`, event)">copy text @{at_word}</span>')
        with open(output_main_file, 'a', encoding='utf-8') as f:
            f.write("""
            <script>
            document.addEventListener('DOMContentLoaded', (event) => {
                const lenMessagesDiv = document.querySelector('.len-messages');
                if (lenMessagesDiv) {
                    const messageCount = parseInt(lenMessagesDiv.textContent.split('/')[0]);
                    const allMessageCount = lenMessagesDiv.textContent.split('/')[1];
                    lenMessagesDiv.textContent = `${messageCount + 1} / ${allMessageCount}`;
                    const imageNumbers = document.querySelectorAll('.image-number');
                    for (let i = 0; i < imageNumbers.length; i++) {
                        imageNumbers[i].textContent = i;
                    }
                }
            });
            </script>
            """)
            return at_word

    output_file = f'templates/output_{message_index}.html'
    output_main_file = f'templates/output.html'
    try:
        if message.media:
            if hasattr(message.media, 'document'):
                for attr in message.media.document.attributes:
                    if isinstance(attr, DocumentAttributeVideo):
                        media_data = await message.download_media(file=BytesIO())
                        temp_video_path = f'images/{uuid.uuid4()}_temp_video.mp4'
                        with open(temp_video_path, 'wb') as temp_video_file:
                            temp_video_file.write(media_data.getvalue())

                        clip = VideoFileClip(temp_video_path)

                        trimmed_clip = clip[0:clip.duration-1] if clip.duration > 1 else clip

                        at_word = ''
                        if message.text:
                            at_word, text = get_at_word(message)

                        file_name = at_word if at_word else 'output_video'
                        output_video_path = f"images/{file_name}.mp4"
                        trimmed_clip.write_videofile(output_video_path, codec='libx264')
                        trimmed_clip.close()
                        clip.close()

                        with open(output_video_path, 'rb') as video_file:
                            video_bytes = video_file.read()
                            video_base64 = base64.b64encode(video_bytes).decode()

                        with open(output_file, 'a', encoding='utf-8') as f:
                            f.write(f'<div style="position: relative; display: flex; flex-direction: column">')
                            f.write(f'<video controls src="data:video/mp4;base64,{video_base64}" width="310"></video>')
                            f.write(f'<div class="image-number"></div>') 
                            f.write(f'<span class="copy-button img" onclick="copyVideoToClipboard(`{output_video_path}`, event)">copy video</span>')
                            f.write('</div>')

                        if message.text:
                            write_to_output(message, output_file, output_main_file)

                        if os.path.exists(temp_video_path):
                            os.remove(temp_video_path)
                        return  # Остановка обработки для этого сообщения

                    elif message.media and hasattr(message.media, 'document') and message.media.document:
                        document = message.media.document
                        if document.mime_type == 'image/gif':
                            media_data = await message.download_media(file=BytesIO())
                            gif_path = f'images/{uuid.uuid4()}_temp_image.gif'
                            with open(gif_path, 'wb') as gif_file:
                                gif_file.write(media_data.getvalue())

                            # Обработка GIF с использованием moviepy
                            clip = VideoFileClip(gif_path)
                            trimmed_clip = clip[0:clip.duration-1] if clip.duration > 1 else clip
                            at_word = ''
                            if message.text:
                                at_word, text = get_at_word(message)

                            file_name = at_word if at_word else f'output_gif_{uuid.uuid4()}'
                            output_gif_path = f"images/{file_name}.gif"
                            trimmed_clip = await process_gif(trimmed_clip)
                            trimmed_clip.write_gif(output_gif_path, fps=25, program='ffmpeg')
                            trimmed_clip.close()
                            clip.close()
                            # Копирование GIF в буфер обмена
                            with open(output_gif_path, 'rb') as gif_file:
                                gif_bytes = gif_file.read()
                                gif_base64 = base64.b64encode(gif_bytes).decode()

                            with open(output_file, 'a', encoding='utf-8') as f:
                                f.write(f'<div style="position: relative; display: flex; flex-direction: column">')
                                f.write(f'<img src="data:image/gif;base64,{gif_base64}" width="310" />')
                                f.write(f'<div class="image-number"></div>') 
                                f.write(f'<span class="copy-button img" onclick="copyVideoToClipboard(`{output_gif_path}`, event)">copy GIF</span>')
                                f.write('</div>')

                            if message.text:
                                write_to_output(message, output_file, output_main_file)

                            if os.path.exists(gif_path):
                                os.remove(gif_path)

                            return  


            # Handle images
            media_data = await message.download_media(file=BytesIO())
            img = Image.open(media_data)
            img = correct_orientation(img)
            width, height = img.size

            cropped_img = img.crop((2, 2, width - 2, height - 2))

            max_size = (900, 900)
            cropped_img.thumbnail(max_size, Image.Resampling.LANCZOS)

            buffered = BytesIO()
            file_format = 'PNG' if img.mode in ('RGBA', 'LA') else 'JPEG'
            cropped_img.save(buffered, format=file_format)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write(f'<div style="position: relative; display: flex; flex-direction: column">')
                f.write(f'<img src="data:image/{file_format.lower()};base64,{img_str}" />')
                f.write(f'<div class="image-number"></div>') 
                f.write(f'<span class="copy-button img" onclick="copyImageToClipboard(`data:image/{file_format.lower()};base64,{img_str}`, event)">copy image</span>')
                f.write(f'</div>')

            if message.text:

                at_word = write_to_output(message, output_file, output_main_file) 
                if cropped_img:
                    file_name = at_word
                    cropped_img.save(f"images/{file_name}.png", format=file_format)

    except Exception as e:
        print(e)
        pass

load_dotenv()

api_id1 = os.getenv('API_ID')
api_hash1 = os.getenv('API_HASH')
phone1 = os.getenv('PHONE')

api_id2 = os.getenv('API_ID2')
api_hash2 = os.getenv('API_HASH2')
phone2 = os.getenv('PHONE2')

api_id3 = os.getenv('API_ID3')
api_hash3 = os.getenv('API_HASH3')
phone3 = os.getenv('PHONE3')

api_id4 = os.getenv('API_ID4')
api_hash4 = os.getenv('API_HASH4')
phone4 = os.getenv('PHONE4')

MESSAGE = os.getenv('MESSAGE')
PROMO = os.getenv('PROMO')
FIX = os.getenv('FIX')
LINK = os.getenv('LINK')
folder = os.getenv('FOLDER')

app.config['SERVER_NAME'] = 'localhost:8765'    
clients = {}

async def send_message(client_id, receiver_id, folder):
    try:
        global clients
        client = clients[client_id]
        receiver = await client.get_input_entity(InputPeerUser(int(receiver_id), 0))
        media_files = glob.glob(os.path.join(folder, '*'))
        media = []
        for file in media_files:
            media.append(await client.upload_file(file))
        await client.send_file(receiver, media, album=True)
        with open("files/sendInfo.json", "w") as f:
            f.write("")
    except Exception as e:
        print(e)
        with open("files/sendInfo.json", "w") as f:
            f.write("")
        pass

async def check_file_and_send_message():

    while True:
        try:
            with open("files/sendInfo.json", "r") as f:
                data = f.read()

            if data:
                data = json.loads(data)
                client_id = data["client_id"]
                receiver_id = data["receiver_id"]

                await send_message(client_id, receiver_id, folder)

            await asyncio.sleep(1)
        except Exception as e:
            print(e)
            break

def get_color(switch):
    return '#488b5b' if switch else 'red'

def write_to_posts(message):
        text = message.text
        text = re.sub(r'\\[|\\]|\\(|\\)', ' ', text)
        text = re.sub(r'\\([^)]*\\)', '', text)
        text = re.sub(r'https?\\S+', '', text)
        text = re.sub(r'@\\s+', '@', text)
        text = re.sub(r"^'''|'''$", "", text)
        text = re.sub(r'`', '', text)
        text = replace_text(text)
        with open(os.path.join('..', 'files', 'posts.txt'), 'r+', encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                f.write('\n=\n')
            f.write(text)


isProcessing = False

async def process_messages_for_author(
    message, 
    original_author, 
    start_id, 
    event=None, 
    client_to_use=None, 
    chat_id_to_use=None,
    chat_user=None,
    nickname=None
):
    
    with open('./id/id.txt', 'w') as id_file:
                id_file.write(str(event.chat_id))
    
    global last_author
    global isProcessing

    # Определение клиента и chat_id
    if client_to_use is None:
        if event is not None:
            client_to_use = event.client
        else:
            client_to_use = message.client
    
    if chat_id_to_use is None:
        if event is not None:
            chat_id_to_use = event.chat_id
        else:
            chat_id_to_use = message.chat_id


    if original_author != last_author:
        folder_path = "./images"
        for filename in os.listdir(folder_path):
            os.remove(os.path.join(folder_path, filename))
        if switch:
            delete_files_py()

    last_author = original_author
    chat_user = ""
    
    try:
        # Попытка получить сущность пользователя и добавить в контакты
        user = await client_to_use.get_entity(original_author)
        await client_to_use(AddContactRequest(
            id=user.id,
            first_name=user.first_name if hasattr(user, 'first_name') and user.first_name is not None else '',
            last_name=user.last_name if hasattr(user, 'last_name') and user.last_name is not None else '',
            phone=user.phone if hasattr(user, 'phone') and user.phone is not None else '',
            add_phone_privacy_exception=False
        ))
        
        # Получение информации о чате
        chat_user = await client_to_use.get_entity(chat_id_to_use)
    except: 
        pass

    if nickname is None:
        nickname = ' '.join(chat_user.first_name.split()[:2]) if hasattr(chat_user, 'first_name') else 'Unknown'

    # Reset files
    with open(os.path.join('..', 'files', 'posts.txt'), 'w', encoding='utf-8'):
        pass
    with open(os.path.join('..', 'files', 'tags.txt'), 'w', encoding='utf-8'):
        pass

    with app.app_context():
        with open('templates/output.html', 'w', encoding='utf-8') as f:
            f.write(f'''
            <html>
            <head>
                <link rel="icon" href="https://i.imgur.com/OlZfxre.png">
                <link rel="preconnect" href="https://fonts.googleapis.com">
                <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                <link href="https://fonts.googleapis.com/css2?family=Varela+Round&display=swap" rel="stylesheet">
                <title>of helper by @yen_ofsfs</title>
                <link rel="stylesheet" type="text/css" href="{url_for('static', filename='styles.css')}">
                <script src="{url_for('static', filename='script.js')}"></script>
            </head>
            <body onload="setInterval('checkFiles(`{nickname}`)', 1000)">
            <div class="header">
            <div class="button1" onclick="deleteOneFile()">1</div>
            <div class="button3" onclick="switchAutoDelete()" style="background-color: {get_color(switch)};"></div>
            <div class="button2" onclick="deleteFiles()">
            <div id="button-text">0</div>
            <div id="button-del">Del</div>
            </div>
            <button id="send-button" onclick="sendFiles(`{chat_id_to_use}`, `{get_client_id(client_to_use)}`, event)">Send Files</button>
            <div>
             <button id="open-folder-button" onclick="openFolder()">Open Folder</button>
             <button id="copy-files-button" onclick="copyFiles()">Copy Files</button>
            </div>
            </div>
            <div class="container">
            <div id="delete-status"></div>
            <div id="send-status"></div>
            ''')

        def check_same_group(message1, message2):
            if message1.grouped_id is None or message2.grouped_id is None:
                return False
            return message1.grouped_id == message2.grouped_id

        messages_to_process = []
        messageCount = 0
        async for msg in client_to_use.iter_messages(chat_id_to_use, min_id=start_id-1, reverse=True):
            if msg.sender_id != original_author or not msg.media:
                break
            if (msg.text and '@' in msg.text):
                messages_to_process.append(msg)
                messageCount = messageCount + 1

        for i in range(len(messages_to_process) - 1):
            if check_same_group(messages_to_process[i], messages_to_process[i + 1]):
                messages_to_process[i], messages_to_process[i + 1] = messages_to_process[i + 1], messages_to_process[i]

        with open('templates/output.html', 'a', encoding='utf-8') as f:
            f.write(f'<div class = "len-messages"> 0 / {messageCount} </div>')

        await asyncio.gather(*(process_message(msg, index) for index, msg in enumerate(messages_to_process)))

        for msg in messages_to_process:
            write_to_posts(msg)

        with open('templates/output.html', 'a', encoding='utf-8') as output_file:
            # Идем по номерам файлов в нужном порядке
            for i in range(len(messages_to_process)):
                temp_filename = f'templates/output_{i}.html'
                # Проверяем, существует ли временный файл
                if os.path.exists(temp_filename):
                    # Открываем временный файл и записываем его содержимое в основной файл
                    with open(temp_filename, 'r', encoding='utf-8') as temp_file:
                        output_file.write(temp_file.read())
                    # Удаляем временный файл после его использования
                    os.remove(temp_filename)
            
            hints_path = os.path.join('..', 'files', 'hints', 'hints.json')
            allhints_path = os.path.join('..', 'files', 'hints', 'allhints.json')

            try:
                with open(hints_path, 'r', encoding='utf-8') as hints_file:
                    hints_data = json.load(hints_file)
                
                # Загружаем общие подсказки
                try:
                    with open(allhints_path, 'r', encoding='utf-8') as allhints_file:
                        allhints_data = json.load(allhints_file)
                except FileNotFoundError:
                    allhints_data = {'hints': [], 'checkbox': ''}
                except json.JSONDecodeError:
                    allhints_data = {'hints': [], 'checkbox': ''}

                chat_hints = hints_data.get(str(chat_id_to_use), {})
                old_checkbox = chat_hints.get('checkbox', '')

                if 'now' in chat_hints:
                    new_chat_hints = {}
                    for key, value in chat_hints.items():
                        # Пропускаем служебные ключи
                        if key in ['now']:
                            new_chat_hints[key] = value
                            continue
                        
                        # Разделяем значения по пробелу
                        parts = str(key).split()
                        
                        if len(parts) >= 2:
                            if chat_hints['now'] == False:
                                parts[1] = str(messageCount * 2)
                            else:
                                parts[1] = str(messageCount)
                            new_key = ' '.join(parts)
                            new_chat_hints[new_key] = value
                    
                    if old_checkbox not in new_chat_hints or not new_chat_hints.get('checkbox'):
                        non_service_keys = [key for key in new_chat_hints.keys() if key not in ['now']]
                        if non_service_keys:
                            new_chat_hints['checkbox'] = non_service_keys[0]

                    # Заменяем chat_hints полностью
                    chat_hints = new_chat_hints

                # Обновляем данные для конкретного chat_id
                hints_data[str(chat_id_to_use)] = chat_hints
                
                # Сохраняем обновленные данные обратно в файл
                with open(hints_path, 'w', encoding='utf-8') as hints_file:
                    json.dump(hints_data, hints_file, ensure_ascii=False, indent=4)
                
                default_hint = chat_hints.get('checkbox', '')
                sorted_hints = sorted(
                    [key for key in chat_hints.keys() 
                    if key not in ['checkbox', 'now'] 
                    and isinstance(key, str) 
                    and key in hints_data[str(chat_id_to_use)]  
                    ], 
                    key=lambda x: x == default_hint, 
                    reverse=True
                )


                hints_html = f'''
                    <div id="additional-hint-buttons" class="additional-hint-buttons">
                        <button id="add-hint-btn" onclick="document.getElementById('hint-modal').classList.remove('hidden')">+</button>
                        <button id="add-general-hint-btn" onclick="document.getElementById('hint-modal-general').classList.remove('hidden')">+</button>
                    </div>
                    
                    <div id="hint-modal" class="modal hidden">
                        <div class="modal-content">
                            <input type="text" autocomplete="off" id="hint-input" placeholder="Input personal time: ">
                            <div class="btn-wrapper">
                            <button id="save-hint-btn" onclick="saveHint('{chat_id_to_use}', '{messageCount}', 'personal')">Save</button>
                            <button id="close-modal-btn" onclick="document.getElementById('hint-modal').classList.add('hidden')">Close</button>
                            </div>
                        </div>
                    </div>

                    <div id="hint-modal-general" class="modal hidden">
                        <div class="modal-content">
                            <input type="text" autocomplete="off" id="general-hint-input" placeholder="Input general time: ">
                            <div class="btn-wrapper">
                            <button id="save-general-hint-btn" onclick="saveHint('{chat_id_to_use}', '{messageCount}', 'general')">Save</button>
                            <button id="close-general-modal-btn" onclick="document.getElementById('hint-modal-general').classList.add('hidden')">Close</button>
                            </div>
                        </div>
                    </div>
                '''

                if sorted_hints or allhints_data.get('hints'):
                    hints_html += f'''
                    <div id="hints-container" class="hints-container">
                        <div class="info-tooltip-container">
                            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="info-icon">
                                <circle cx="12" cy="12" r="10"></circle>
                                <line x1="12" y1="16" x2="12" y2="12"></line>
                                <line x1="12" y1="8" x2="12.01" y2="8"></line>
                            </svg>
                            <div class="tooltip-text">Press enter in "main" script to make a post with chosen time. Press + to add new time</div>
                        </div>
                    '''

                    if sorted_hints:
                        for hint_key in sorted_hints:
                            is_checked = hint_key == (default_hint or (sorted_hints[0] if sorted_hints else ''))
                            checked_attr = 'checked' if is_checked else ''
                            active_class = 'active' if is_checked else ''
                            
                            hints_html += f'''
                            <div class="hint-item {active_class}">
                                <div class="hint-wrapper">
                                    <input type="checkbox" 
                                        id="checkbox-{hint_key}" 
                                        {checked_attr} 
                                        onchange="updateHintCheckbox('{chat_id_to_use}', '{hint_key}', 'update', 'personal')"
                                        class="hint-checkbox">
                                    <label for="checkbox-{hint_key}" class="hint-label">{hint_key}</label>
                                    <button 
                                        class="hint-delete-btn" 
                                        onclick="deleteHint('{chat_id_to_use}', '{hint_key}', 'personal')"
                                        aria-label="Delete hint">
                                        <svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="32" height="32" viewBox="0 0 64 64">
                                        <rect width="48" height="10" x="7" y="7" fill="#f9e3ae" rx="2" ry="2"></rect>
                                        <rect width="36" height="4" x="13" y="55" fill="#f9e3ae" rx="2" ry="2"></rect>
                                        <path fill="#c2cde7" d="M47 55L15 55 10 17 52 17 47 55z"></path>
                                        <path fill="#ced8ed" d="M25 55L15 55 10 17 24 17 25 55z"></path>
                                        <path fill="#b5c4e0" d="M11,17v2a3,3 0,0,0 3,3H38L37,55H47l5-38Z"></path>
                                        <path fill="#8d6c9f" d="M16 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 16 10zM11 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 11 10zM21 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 21 10zM26 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 26 10zM31 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 31 10zM36 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 36 10zM41 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 41 10zM46 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 46 10zM51 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 51 10z"></path>
                                        <path fill="#8d6c9f" d="M53,6H9A3,3 0 0 0 6 9v6a3,3 0 0 0 3 3c0,.27 4.89 36.22 4.89 36.22A3 3 0 0 0 15 60H47a3,3 0 0 0 1.11 -5.78l2.28 -17.3a1 1 0 0 0 .06 -.47L52.92 18H53a3,3 0 0 0 3 -3V9A3,3 0 0 0 53 6ZM24.59 18l5 5 -4.78 4.78a1 1 0 1 0 1.41 1.41L31 24.41 37.59 31 31 37.59l-7.29 -7.29h0l-5.82 -5.82a1 1 0 0 0 -1.41 1.41L21.59 31l-7.72 7.72L12.33 27.08 21.41 18Zm16 0 3.33 3.33a1 1 0 0 0 1.41 -1.41L43.41 18h7.17L39 29.59 32.41 23l5 -5Zm-11 21L23 45.59l-5.11 -5.11a1 1 0 0 0 -1.41 1.41L21.59 47l-5.86 5.86L14.2 41.22l8.8 -8.8Zm7.25 4.42L32.41 39 39 32.41l5.14 5.14a1 1 0 0 0 1.41 -1.41L40.41 31 47 24.41l2.67 2.67 -1.19 9L38.3 46.28h0L31 53.59 24.41 47 31 40.41l4.42 4.42a1 1 0 0 0 1.41 -1.41ZM23 48.41 28.59 54H17.41Zm16 0L44.59 54H33.41ZM40.41 47 48 39.37 46.27 52.86ZM50 24.58 48.41 23l2.06 -2.06Zm-19 -3L27.41 18h7.17Zm-19.47 -.64L13.59 23 12 24.58Zm3.47 .64L11.41 18h7.17ZM47 58H15a1,1 0 0 1 0 -2H47a1,1 0 0 1 0 2Zm7 -43a1,1 0 0 1 -1 1H9a1,1 0 0 1 -1 -1V9A1,1 0 0 1 9 8H53a1,1 0 0 1 1 1Z"></path>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                            '''
                    
                    if allhints_data.get('hints'):
                        default_general_hint = allhints_data.get('checkbox', '')
                        sorted_general_hints = sorted(
                            allhints_data['hints'], 
                            key=lambda x: x == default_general_hint, 
                            reverse=True
                        )

                        for general_hint in sorted_general_hints:
                            is_checked = (
                                (not sorted_hints and general_hint == (default_general_hint or sorted_general_hints[0])) 
                                if sorted_general_hints 
                                else False
                            )
                            checked_attr = 'checked' if is_checked else ''
                            active_class = 'active' if is_checked else ''
                                                        
                            hints_html += f'''
                            <div class="hint-item general-hint {active_class}">
                                <div class="hint-wrapper">
                                    <input type="checkbox" 
                                        id="checkbox-general-{general_hint}" 
                                        {checked_attr} 
                                        onchange="updateHintCheckbox('{chat_id_to_use}', '{general_hint}', 'update', 'general')"
                                        class="hint-checkbox">
                                    <label for="checkbox-general-{general_hint}" class="hint-label general">{general_hint}</label>
                                    <button 
                                        class="hint-delete-btn" 
                                        onclick="deleteHint('{chat_id_to_use}', '{general_hint}', 'general')"
                                        aria-label="Delete general hint">
                                        <svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" width="32" height="32" viewBox="0 0 64 64">
                                        <rect width="48" height="10" x="7" y="7" fill="#f9e3ae" rx="2" ry="2"></rect>
                                        <rect width="36" height="4" x="13" y="55" fill="#f9e3ae" rx="2" ry="2"></rect>
                                        <path fill="#c2cde7" d="M47 55L15 55 10 17 52 17 47 55z"></path>
                                        <path fill="#ced8ed" d="M25 55L15 55 10 17 24 17 25 55z"></path>
                                        <path fill="#b5c4e0" d="M11,17v2a3,3 0,0,0 3,3H38L37,55H47l5-38Z"></path>
                                        <path fill="#8d6c9f" d="M16 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 16 10zM11 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 11 10zM21 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 21 10zM26 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 26 10zM31 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 31 10zM36 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 36 10zM41 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 41 10zM46 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 46 10zM51 10a1 1 0 0 0-1 1v2a1 1 0 0 0 2 0V11A1 1 0 0 0 51 10z"></path>
                                        <path fill="#8d6c9f" d="M53,6H9A3,3 0 0 0 6 9v6a3,3 0 0 0 3 3c0,.27 4.89 36.22 4.89 36.22A3 3 0 0 0 15 60H47a3,3 0 0 0 1.11 -5.78l2.28 -17.3a1 1 0 0 0 .06 -.47L52.92 18H53a3,3 0 0 0 3 -3V9A3,3 0 0 0 53 6ZM24.59 18l5 5 -4.78 4.78a1 1 0 1 0 1.41 1.41L31 24.41 37.59 31 31 37.59l-7.29 -7.29h0l-5.82 -5.82a1 1 0 0 0 -1.41 1.41L21.59 31l-7.72 7.72L12.33 27.08 21.41 18Zm16 0 3.33 3.33a1 1 0 0 0 1.41 -1.41L43.41 18h7.17L39 29.59 32.41 23l5 -5Zm-11 21L23 45.59l-5.11 -5.11a1 1 0 0 0 -1.41 1.41L21.59 47l-5.86 5.86L14.2 41.22l8.8 -8.8Zm7.25 4.42L32.41 39 39 32.41l5.14 5.14a1 1 0 0 0 1.41 -1.41L40.41 31 47 24.41l2.67 2.67 -1.19 9L38.3 46.28h0L31 53.59 24.41 47 31 40.41l4.42 4.42a1 1 0 0 0 1.41 -1.41ZM23 48.41 28.59 54H17.41Zm16 0L44.59 54H33.41ZM40.41 47 48 39.37 46.27 52.86ZM50 24.58 48.41 23l2.06 -2.06Zm-19 -3L27.41 18h7.17Zm-19.47 -.64L13.59 23 12 24.58Zm3.47 .64L11.41 18h7.17ZM47 58H15a1,1 0 0 1 0 -2H47a1,1 0 0 1 0 2Zm7 -43a1,1 0 0 1 -1 1H9a1,1 0 0 1 -1 -1V9A1,1 0 0 1 9 8H53a1,1 0 0 1 1 1Z"></path>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                            '''

                hints_html += '</div>'
                output_file.write(hints_html)

            except Exception as e:
                output_file.write(f'<div class="error-message">Error loading hints: {str(e)}</div>')

            
async def process_event(event):
    try:
        global last_author
        global isProcessing
        if event.is_private and not isProcessing:
            me = await event.client.get_me()
            if event.message.is_reply and event.message.message == MESSAGE and event.message.sender_id == me.id:
                isProcessing = True
                replied_message = await event.message.get_reply_message()   
                message_text = replied_message.text 
                pyperclip.copy(message_text)
                start_id = replied_message.id
                original_author = replied_message.sender_id
                
                await process_messages_for_author(replied_message, original_author, start_id, event)
                
                isProcessing = False

            elif event.message.message == PROMO and event.message.sender_id == me.id and PROMO != "":
                saved_messages = await event.client.get_entity('me')
                last_message = await event.client.get_messages(saved_messages, limit=1)
                if last_message[0].text.isdigit():   
                    num_messages = int(last_message[0].text)
                    if num_messages <= 20:
                        messages_to_forward = await event.client.get_messages(saved_messages, limit=num_messages+1)
                        try:
                            user = await event.client.get_entity(event.chat_id)
                        except ValueError:
                            await event.client.get_dialogs()
                            user = await event.client.get_entity(event.chat_id)
                        try:
                            await event.client(AddContactRequest(
                                    id=user.id,
                                    first_name=user.first_name if hasattr(user, 'first_name') and user.first_name is not None else '',
                                    last_name=user.last_name if hasattr(user, 'last_name') and user.last_name is not None else '',
                                    phone=user.phone if hasattr(user, 'phone') and user.phone is not None else '',
                                    add_phone_privacy_exception=False
                            ))
                        except:
                            pass
                        for message in reversed(messages_to_forward[1:]):
                            await event.client.forward_messages(event.chat_id, message)

            elif event.message.is_reply and event.message.message == FIX and event.message.sender_id == me.id and FIX != "":
                replied_message = await event.message.get_reply_message()
                original_author = replied_message.sender_id

                # Удаляем старые файлы, если автор изменился
                if original_author != last_author:
                    folder_path = "./images"
                    for filename in os.listdir(folder_path):
                        os.remove(os.path.join(folder_path, filename))
                    if switch:
                        delete_files_py()
                last_author = original_author

                # Добавляем контакт, если нужно
                user = await event.client.get_entity(original_author)
                try:
                    await event.client(AddContactRequest(
                        id=user.id,
                        first_name=user.first_name if hasattr(user, 'first_name') and user.first_name is not None else '',
                        last_name=user.last_name if hasattr(user, 'last_name') and user.last_name is not None else '',
                        phone=user.phone if hasattr(user, 'phone') and user.phone is not None else '',
                        add_phone_privacy_exception=False
                    ))
                except:
                    pass

                # Находим сообщения с медиа и текстом
                start_id = replied_message.id
                messages_to_process = []

                # Сохраняем все сообщения, начиная с того, на которое был сделан ответ
                async for message in event.client.iter_messages(event.chat_id, min_id=start_id - 1, reverse=True):
                    if message.sender_id != original_author:
                        break
                    # Добавляем все медиа и текстовые сообщения
                    messages_to_process.append(message)

                # Обрабатываем сообщения по порядку
                i = 0
                while i < len(messages_to_process):
                    current_message = messages_to_process[i]

                    # Проверка на медиа (файл/фото)
                    if current_message.media:
                        # Проверка следующего сообщения на текст
                        caption = ""
                        if i + 1 < len(messages_to_process):
                            next_message = messages_to_process[i + 1]
                            if next_message.text:
                                caption = next_message.text
                                i += 1  # Пропускаем текстовое сообщение, так как он будет использован как подпись

                        # Отправляем файл с текстом (если он есть)
                        await event.client.send_file(
                            event.chat_id,
                            file=current_message.media,
                            caption=caption
                        )

                    # Обработка текстового сообщения
                    elif current_message.text:
                        # Проверка, если два текстовых сообщения идут подряд, прекращаем обработку
                        if i + 1 < len(messages_to_process) and messages_to_process[i + 1].text:
                            break
                        else:
                            # Отправляем текстовое сообщение
                            await event.client.send_message(
                                event.chat_id,
                                current_message.text
                            )

                    # Переходим к следующему сообщению
                    i += 1

            elif event.message.is_reply and event.message.message == LINK and event.message.sender_id == me.id and LINK != "":
                    replied_message = await event.message.get_reply_message()
                    message_text = replied_message.text
                    if 't.me/' in message_text or 'https://t.me/' in message_text or '@' in message_text:
                        try:
                            # Используем регулярное выражение для извлечения ссылки или упоминания канала
                            match = re.search(r't\.me/([+a-zA-Z0-9_-]+)|@([a-zA-Z0-9_]+)', message_text)
                            if match:
                                link_part = match.group(1) if match.group(1) else match.group(2)  # Ссылка без 'https://t.me/' или 't.me/' или '@'
                                channel_entity = None

                                # Проверяем, если это инвайт-ссылка
                                if link_part.startswith('+'):
                                    try:
                                        # Сначала пробуем получить сущность напрямую
                                        channel_entity = await event.client.get_entity(link_part[1:])
                                        print("Пользователь уже является участником канала, пропускаем попытку присоединения.")
                                    except ValueError:
                                        # Если не удалось, пробуем через CheckChatInviteRequest
                                        try:
                                            invite_info = await event.client(CheckChatInviteRequest(link_part[1:]))  # Убираем '+'
                                            if isinstance(invite_info, ChatInviteAlready):
                                                channel_entity = invite_info.chat
                                            elif isinstance(invite_info, ChatInvite):
                                                print(f"Вы не являетесь участником канала: {invite_info.title}")
                                                return
                                        except Exception as e:
                                            if "The chat the user tried to join has expired" in str(e):
                                                print("Инвайт-ссылка истекла. Попробуйте получить новую ссылку.")
                                            else:
                                                print(f"Ошибка при проверке инвайт-ссылки: {e}")
                                            return
                                else:
                                    try:
                                        channel_entity = await event.client.get_entity(link_part)
                                    except Exception as e:
                                        print(f"Ошибка при получении сущности канала: {e}")
                                        return

                                # Если channel_entity все еще None, значит ничего не получилось, выходим
                                if channel_entity is None:
                                    print("Не удалось получить информацию о канале")
                                    return

                                # Пересылаем сообщения из канала в текущий чат
                                messages_to_forward = []
                                try:
                                    async for message in event.client.iter_messages(channel_entity):
                                        if not isinstance(message, telethon.tl.patched.MessageService):
                                            messages_to_forward.append(message)
                                except Exception as e:
                                    print(f"Ошибка при получении сообщений из канала: {e}")
                                    return
                                
                                messages_to_forward = []
                                try:
                                    async for message in event.client.iter_messages(channel_entity):
                                        if not isinstance(message, telethon.tl.patched.MessageService):
                                            messages_to_forward.append(message)
                                except Exception as e:
                                    print(f"Ошибка при получении сообщений из канала: {e}")
                                    return
                                
                                # Пересылаем сообщения из канала в текущий чат
                                messages_to_forward = []
                                try:
                                    async for message in event.client.iter_messages(channel_entity):
                                        if not isinstance(message, telethon.tl.patched.MessageService):
                                            messages_to_forward.append(message)
                                except Exception as e:
                                    print(f"Ошибка при получении сообщений из канала: {e}")
                                    return

                                # Проверяем, что есть сообщения для пересылки
                                if messages_to_forward:
                                    # Пересылаем сообщения в хронологическом порядке
                                    reversed_messages = list(reversed(messages_to_forward))
                                    
                                    # Находим индекс первого сообщения с текстом, @, и медиа
                                    start_index = 0
                                    for i, message in enumerate(reversed_messages):
                                        if '@' in message.text and message.media:
                                            start_index = i
                                            break
                                    
                                    # Находим последний индекс сообщений с @ и медиа
                                    end_index = len(reversed_messages)
                                    for i in range(len(reversed_messages) - 1, start_index - 1, -1):
                                        if '@' in reversed_messages[i].text and reversed_messages[i].media:
                                            end_index = i + 1
                                            break
                                    
                                    # Пересылаем сообщения от первого подходящего до последнего
                                    forwarded_messages = await event.client.forward_messages(event.chat_id, reversed_messages[start_index:end_index])
                                    
                                    # Берем первое пересланное сообщение
                                    first_forwarded_msg = forwarded_messages[0]
                                    
                                    chat_user = await event.client.get_entity(event.chat_id)
                                    nickname = ' '.join(chat_user.first_name.split()[:2]) if hasattr(chat_user, 'first_name') else 'Unknown'
                                    
                                    await process_messages_for_author(
                                        message=first_forwarded_msg, 
                                        original_author=first_forwarded_msg.sender_id,  
                                        start_id=first_forwarded_msg.id,
                                        event=event,
                                        client_to_use=event.client,
                                        chat_id_to_use=event.chat_id,
                                        chat_user=chat_user,
                                        nickname=nickname     
                                    )

                        except Exception as e:
                            print(f"Ошибка при обработке ссылки: {e}")

            isProcessing = False
    except Exception as e: 
            isProcessing = False
            print(e)

def parse_proxy_url(proxy_url):
    if not proxy_url:
        return None

    try:
        parsed_proxy = urlparse(proxy_url)
        
        # Проверка обязательных параметров
        if not all([parsed_proxy.scheme, parsed_proxy.hostname, parsed_proxy.port]):
            print("Некорректный формат URL прокси")
            return None

        proxy = {
            'proxy_type': parsed_proxy.scheme,
            'addr': parsed_proxy.hostname,
            'port': int(parsed_proxy.port),
            'username': parsed_proxy.username or None,
            'password': parsed_proxy.password or None,
        }
        print(f"Proxy: {proxy}")
        return proxy
    except Exception as e:
        print(f"Ошибка при обработке прокси: {e}")
        return None

# Использование
proxy_url = os.getenv('PROXY')
proxy = parse_proxy_url(proxy_url)

async def create_client(phone, api_id, api_hash):
    client = TelegramClient(f'session_{phone}', api_id, api_hash, proxy=proxy)
    await client.start(phone)
    return client

async def create_clients():
    client1 = await create_client(phone1, api_id1, api_hash1)
    client1.id = '1'

    client2 = await create_client(phone2, api_id2, api_hash2) if api_id2 and api_hash2 and phone2 else None
    if client2:
        client2.id = '2'

    client3 = await create_client(phone3, api_id3, api_hash3) if api_id3 and api_hash3 and phone3 else None
    if client3:
        client3.id = '3'

    client4 = await create_client(phone4, api_id4, api_hash4) if api_id4 and api_hash4 and phone4 else None
    if client4:
        client4.id = '4'

    global clients
    clients = {
        '1': client1,
        '2': client2,
        '3': client3,
        '4': client4
    }
    return clients

async def setup_event_handlers(clients):
    for client_id, client in clients.items():
        if client:
            @client.on(events.NewMessage)
            async def my_event_handler(event, client=client):
                await process_event(event)


async def main():
    global clients
    clients = await create_clients()
    await setup_event_handlers(clients)

    try:
        await asyncio.gather(*(client.run_until_disconnected() for client in clients.values() if client), check_file_and_send_message())
    except KeyboardInterrupt:
        sys.exit(0)

def run_flask_app():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(debug=True, use_reloader=False)

def run_telegram_client():
    asyncio.run(main())

def run_batch_file():
    updDir = os.getcwd()

    # Оборачиваем путь в кавычки, чтобы избежать проблем с пробелами
    if platform.system() == 'Windows':
        command = f'"{updDir}\\update.bat"'
    elif platform.system() == 'Darwin':
        command = f'"{updDir}/update.sh"'
    else:
        print("Unsupported platform:", platform.system())

    process = subprocess.Popen(command, shell=True, cwd=os.path.dirname(os.path.realpath(__file__)))
    process.communicate()
    return

SECRET_KEY = 'shared_secret_key'
TIME_THRESHOLD = 30 

def validate_time_based_key(provided_key: str, timestamp: str) -> bool:
    try:
        # Convert timestamp to int and validate time threshold
        current_time = int(time.time())
        timestamp_int = int(timestamp)
        
        if abs(current_time - timestamp_int) > TIME_THRESHOLD:
            return False
        
        expected_key = hmac.new(
            SECRET_KEY.encode('utf-8'),
            str(timestamp_int).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare provided key with expected key
        return hmac.compare_digest(expected_key, provided_key)
        
    except Exception as e:
        print(f"...")
        return False

if __name__ == '__main__':
    try:
        if len(sys.argv) < 3:
            print("Запустите скрипт через main.")
            sys.exit(1)

        provided_key = sys.argv[1]
        timestamp = sys.argv[2]

        if not validate_time_based_key(provided_key, timestamp):
            print("...")
            sys.exit(1)

        flask_thread = threading.Thread(target=run_flask_app)
        flask_thread.daemon = True
        flask_thread.start()

        # Запускаем batch file после старта Flask
        batch_file_thread = threading.Thread(target=run_batch_file)
        batch_file_thread.daemon = True
        batch_file_thread.start()

        # Запускаем Telegram клиент
        run_telegram_client()

    except Exception as e:
        print(f"Ошибка запуска: {str(e)}")
        sys.exit(1)

    except KeyboardInterrupt:
        print("\nInterrupted by user. Quitting...")
