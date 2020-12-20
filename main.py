import os
import random
from io import BytesIO

from token import TOKEN
import requests
import telebot
from PIL import Image

bot = telebot.TeleBot(TOKEN, parse_mode=None)
state = dict()
im_list = dict()


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Run /new to create a new document. Follow the instructions and DON'T PANIC!")


@bot.message_handler(commands=['new'])
def send_welcome(message):
    global state
    if check_idle(chat_id=message.chat.id):
        if message.chat.id in im_list:
            del im_list[message.chat.id][:]
        else:
            im_list[message.chat.id] = []
            state[message.chat.id] = []
        bot.reply_to(message, "Creating a new document. Send me some photos and run /end when you are done.")
        state[message.chat.id] = "working"
    else:
        bot.reply_to(message, "Already working! Send /end to stop")


@bot.message_handler(content_types=['photo'])
def respond_photo(message):
    global state
    if check_idle(chat_id=message.chat.id):
        bot.reply_to(message, "You haven't started working yet! Send /new first.")
        return
    photo = message.photo[-1]
    info = bot.get_file(photo.file_id)
    img_url = "https://api.telegram.org/file/bot{0}/{1}".format(TOKEN, info.file_path)
    response = requests.get(img_url)
    im_list[message.chat.id].append(Image.open(BytesIO(response.content)))


@bot.message_handler(commands=['end'])
def end(message):
    global state
    if check_idle(chat_id=message.chat.id):
        bot.reply_to(message, "You haven't started working yet! Send /new first.")
        return
    if not im_list:
        bot.reply_to(message, "You haven't sent any photos, but ok, ending now.")
    random.seed()
    bot.send_message(message.chat.id, "Sending a document with {0} photos.".format(len(im_list[message.chat.id])))
    docname = "res " + str(message.chat.id) + str(random.randint(a=0, b=1000)) + ".pdf"
    im_list[message.chat.id][0].save(docname, "PDF", resolution=100.0, save_all=True,
                                     append_images=im_list[message.chat.id][1:])
    send_doc(message.chat.id, docname)
    bot.send_message(message.chat.id, "Done!")
    state[message.chat.id] = "idle"
    del im_list[message.chat.id][:]
    os.remove(docname)


def check_idle(chat_id):
    return chat_id not in state or state[chat_id] == "idle"


def send_doc(chat_id, doc_path):
    doc = open(doc_path, 'rb')
    bot.send_document(chat_id, doc)


bot.polling()
