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
        with open('sendInfo.json', 'w') as f:
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
        with open("sendInfo.json", "w") as f:
            f.write("")
    except Exception as e:
        print(e)
        with open("sendInfo.json", "w") as f:
            f.write("")
        pass

async def check_file_and_send_message():

    while True:
        try:
            with open("sendInfo.json", "r") as f:
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

async def process_messages_for_author(message, original_author, start_id):
    global last_author
    global isProcessing

    # Reset folder if author changed
    if original_author != last_author:
        folder_path = "./images"
        for filename in os.listdir(folder_path):
            os.remove(os.path.join(folder_path, filename))
        if switch:
            delete_files_py()

    last_author = original_author
    user = await message.client.get_entity(original_author)
    try:
        await message.client(AddContactRequest(
            id=user.id,
            first_name=user.first_name if hasattr(user, 'first_name') and user.first_name is not None else '',
            last_name=user.last_name if hasattr(user, 'last_name') and user.last_name is not None else '',
            phone=user.phone if hasattr(user, 'phone') and user.phone is not None else '',
            add_phone_privacy_exception=False
        ))
    except: 
        pass

    chat_user = await message.client.get_entity(message.chat_id)
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
            <button id="send-button" onclick="sendFiles(`{message.chat_id}`, `{get_client_id(message.client)}`, event)">Send Files</button>
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
        async for msg in message.client.iter_messages(message.chat_id, min_id=start_id-1, reverse=True):
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

        with open('templates/output.html', 'a', encoding='utf-8') as f:
            f.write(f'</div> </div> </body></html>')

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
                
                await process_messages_for_author(replied_message, original_author, start_id)
                
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
                                        # Проверяем, что сообщение не является служебным
                                        if not isinstance(message, telethon.tl.patched.MessageService):
                                            messages_to_forward.append(message)
                                except Exception as e:
                                    print(f"Ошибка при получении сообщений из канала: {e}")
                                    return

                                # Проверяем, что есть сообщения для пересылки
                                if messages_to_forward:
                                    # Пересылаем сообщения в хронологическом порядке
                                    reversed_messages = list(reversed(messages_to_forward))
                                    first_msg = reversed_messages[0]  # Берем первое сообщение
                                    for msg in reversed_messages:
                                        await event.client.forward_messages(event.chat_id, msg)
                                    
                                    # Используем только первое сообщение для обработки
                                    await process_messages_for_author(
                                    message=first_msg,  # Передаем первое пересланное сообщение вместо event
                                    original_author=first_msg.sender_id, 
                                    start_id=first_msg.id
                                    )

                        except Exception as e:
                            print(f"Ошибка при обработке ссылки: {e}")

            isProcessing = False
    except Exception as e: 
            isProcessing = False
            print(e)

proxy_url = os.getenv('PROXY')
proxy = None

if proxy_url:
    parsed_proxy = urlparse(proxy_url)
    proxy = {
        'proxy_type': parsed_proxy.scheme,
        'addr': parsed_proxy.hostname,
        'port': int(parsed_proxy.port) if parsed_proxy.port else None,
        'username': parsed_proxy.username,
        'password': parsed_proxy.password,
    }

print(f"Proxy: {proxy}")

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
        # Проверяем количество аргументов
        if len(sys.argv) < 3:
            print("Запустите скрипт через main.")
            sys.exit(1)

        # Получаем ключ и временную метку из аргументов
        provided_key = sys.argv[1]
        timestamp = sys.argv[2]

        # Проверяем валидность ключа
        if not validate_time_based_key(provided_key, timestamp):
            print("...")
            sys.exit(1)

        # Запускаем Flask в отдельном потоке
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
