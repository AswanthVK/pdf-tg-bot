import os
import random
import ssl
from io import BytesIO

# from my_token import TOKEN
import requests
import telebot
from PIL import Image
from aiohttp import web

TOKEN = os.environ["TOKEN"]

WEBHOOK_HOST = 'https://pdf-tg-bot.herokuapp.com/'
WEBHOOK_PORT = 8443  # 443, 80, 88 or 8443 (port need to be 'open')
WEBHOOK_LISTEN = '0.0.0.0'  # In some VPS you may need to put here the IP addr

WEBHOOK_SSL_CERT = './webhook_cert.pem'  # Path to the ssl certificate
WEBHOOK_SSL_PRIV = './webhook_pkey.pem'  # Path to the ssl private key

WEBHOOK_URL_BASE = "https://{}:{}".format(WEBHOOK_HOST, WEBHOOK_PORT)
WEBHOOK_URL_PATH = "/{}/".format(TOKEN)

app = web.Application()
bot = telebot.TeleBot(TOKEN, parse_mode=None)
user_states = dict()
user_photos = dict()


async def handle(request):
    if request.match_info.get('token') == bot.token:
        request_body_dict = await request.json()
        update = telebot.types.Update.de_json(request_body_dict)
        bot.process_new_updates([update])
        return web.Response()
    else:
        return web.Response(status=403)


app.router.add_post('/{token}/', handle)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Run /new to create a new document. Follow the instructions and DON'T PANIC!")


@bot.message_handler(commands=['new'])
def send_welcome(message):
    global user_states
    if check_idle(chat_id=message.chat.id):
        if message.chat.id in user_photos:
            del user_photos[message.chat.id][:]
        else:
            user_photos[message.chat.id] = []
            user_states[message.chat.id] = []
        bot.reply_to(message, "Creating a new document. Send me some photos and run /end when you are done.")
        user_states[message.chat.id] = "working"
    else:
        bot.reply_to(message, "Already working! Send /end to stop")


@bot.message_handler(content_types=['photo'])
def photo_response(message):
    if check_idle(chat_id=message.chat.id):
        bot.reply_to(message, "You haven't started working yet! Send /new first.")
        return
    photo = message.photo[-1]
    info = bot.get_file(photo.file_id)
    img_url = "https://api.telegram.org/file/bot{0}/{1}".format(TOKEN, info.file_path)
    response = requests.get(img_url)
    user_photos[message.chat.id].append(Image.open(BytesIO(response.content)))


@bot.message_handler(commands=['end'])
def end(message):
    global user_states
    if check_idle(chat_id=message.chat.id):
        bot.reply_to(message, "You haven't started working yet! Send /new first.")
        return
    if not user_photos[message.chat.id]:
        bot.reply_to(message, "You haven't sent any photos, but ok, ending now. Run /new to make another doc.")
        user_states[message.chat.id] = "idle"
        return
    bot.send_message(message.chat.id, "Sending a document with {0} photos.".format(len(user_photos[message.chat.id])))
    random.seed()
    docname = "res" + str(message.chat.id) + "r" + str(random.randint(a=0, b=1000)) + ".pdf"
    # create and send pdf
    user_photos[message.chat.id][0].save(docname, "PDF", resolution=100.0, save_all=True,
                                         append_images=user_photos[message.chat.id][1:])
    send_doc(message.chat.id, docname)
    bot.send_message(message.chat.id, "Done! Run /new to make another doc, or just leave.")
    # cleanup
    user_states[message.chat.id] = "idle"
    for img in user_photos[message.chat.id]:
        img.close()
    del user_photos[message.chat.id][:]
    os.remove(docname)


def check_idle(chat_id):
    return chat_id not in user_states or user_states[chat_id] == "idle"


def send_doc(chat_id, doc_path):
    with open(doc_path, 'rb') as doc:
        bot.send_document(chat_id, doc)


# Remove webhook, it fails sometimes the set if there is a previous webhook
bot.remove_webhook()

# Set webhook
bot.set_webhook(url=WEBHOOK_URL_BASE + WEBHOOK_URL_PATH,
                certificate=open(WEBHOOK_SSL_CERT, 'r'))

# Build ssl context
context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
context.load_cert_chain(WEBHOOK_SSL_CERT, WEBHOOK_SSL_PRIV)

# Start aiohttp server
web.run_app(
    app,
    host=WEBHOOK_LISTEN,
    port=WEBHOOK_PORT,
    ssl_context=context,
)
