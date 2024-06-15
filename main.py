import asyncio
import colorama
import datetime
import json
import pytz
import random
import threading

from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

from extensions.cashapp import Time, __get_receipt__
from extensions.database import database
from extensions.errors import errors
from extensions.file import FileSystem

user_state = {}
user_depositing = {}

remaining = 0
active_drop = {}
claimed_drop = []

settings = json.load(open('./settings.json', 'r'))
token = settings['order_bot_token']
bot = AsyncTeleBot(token)

with open(settings['word_path'], 'r') as wordlist:
    words = wordlist.readlines()

async def __get_note__(length: int = 2) -> str:
    return ' '.join(random.choice(words).strip() for __length in range(length))

async def __always_delete__() -> None:
    async def delete(deposit_key: str):
        deposit = user_depositing[deposit_key]
        while user_depositing.get(deposit_key):
            timestamp = Time.generateTimestamp()
            if timestamp >= deposit['future_timestamp']:
                try:
                   await bot.delete_message(chat_id = user_depositing.get(deposit_key, {}).get('chat_id'), message_id = user_depositing.get(deposit_key, {}).get('deposit_message_id'))
                except Exception as E:
                   pass
                try:
                  del user_depositing[deposit_key]
                  del user_state[deposit['user_id']]
                except:
                  pass
            await asyncio.sleep(1)
        print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}EXPIRED{colorama.Style.RESET_ALL}')

    while True:
        deposit_keys = list(user_depositing.keys())
        tasks = [delete(key) for key in deposit_keys]
        await asyncio.gather(*tasks)
        await asyncio.sleep(1)

threading.Thread(target = asyncio.run, args = (__always_delete__(), )).start()

async def main():
   while True:
        try:
          await bot.polling()
        except:
          await asyncio.sleep(5)

@bot.message_handler(commands = ['start'])
async def start(message):
    try:
      blacklisted = await database.__is_blacklisted__(message.from_user.id)
      if blacklisted:
         return
      markup = InlineKeyboardMarkup()
      user = await database.__fetch_user__(message.from_user.id)
      text = 'Welcome Back, ID: *{}*'.format(message.from_user.id)
      if not user:
         text = r'''👵 account\.mom —— \#1 Account Shop

account\.mom is an independently ran log shop that focuses on user privacy, ratings, and quality accounts\. To get started, check out the menu by pressing the "Shop" button\.
'''
         await database.__add_user__(message.from_user.id)
         print(f'{colorama.Style.BRIGHT}{colorama.Fore.LIGHTBLUE_EX}SUCCESS{colorama.Style.RESET_ALL} (REGISTERED)', f'{message.from_user.id}')
      user = await database.__fetch_user__(message.from_user.id)
      cart = [item for item in user[1].split(',') if item]
      markup.add(InlineKeyboardButton(text = '🛍️  Shop', callback_data = 'SHOP'))
      markup.add(
          InlineKeyboardButton(text = '💰 ${} '.format(user[0]), callback_data = 'CHOOSE-PAYMENT'), 
          InlineKeyboardButton(text = '🛒 Cart ({})'.format(len(cart)), callback_data = 'CART'), 
      row_width = 2)
      if message.from_user.id in settings['owners']:
         text += ' —— Admin Portal'
         markup.add(
             InlineKeyboardButton(text = '🕵️‍♀️ Lookup User ID', callback_data = 'LOOKUP-USER-ID'), 
             InlineKeyboardButton(text = '📦 Lookup Order ID', callback_data = 'LOOKUP-ORDER-ID'), 
         row_width = 2)
         markup.add(
             InlineKeyboardButton(text = '💰 Set Credits', callback_data = 'SET-CREDITS'),
             InlineKeyboardButton(text = '💸 Add Credits', callback_data = 'ADD-CREDITS'),
             InlineKeyboardButton(text = '💰 Remove Credits', callback_data = 'REMOVE-CREDITS'),
         row_width = 3)
         markup.add(
             InlineKeyboardButton(text = '🚫 Blacklist', callback_data = 'BLACKLIST'),
             InlineKeyboardButton(text = '🔓 Revoke Blacklist', callback_data = 'REVOKE-BLACKLIST'),
         row_width = 2)
         markup.add(InlineKeyboardButton(text = '🎨 Create Product', callback_data = 'CREATE-PRODUCT'))
         markup.add(InlineKeyboardButton(text = '🎨 Create Drop', callback_data = 'CREATE-DROP'))
         markup.add(InlineKeyboardButton(text = '📨 DM All', callback_data = 'DM-ALL'))
      await bot.send_message(message.chat.id, text, reply_markup = markup, parse_mode = 'MarkdownV2')
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (MENU)', f'{type(E)}: {str(E)}')
           try:
             await bot.send_message(message.chat.id, errors['ERROR_OCCURED_SUPPORT'])
           except:
             pass
           
@bot.message_handler(commands = ['drop', 'claim'])
async def drop(message):           
    try:
      blacklisted = await database.__is_blacklisted__(message.from_user.id)
      if blacklisted:
         return
      
      global active_drop
      global remaining
      
      if not active_drop:
         await bot.send_message(message.chat.id, 'There is no active drop.')
         return

      if active_drop.get('remaining', 0) == 0:
         await bot.send_message(message.chat.id, 'There are no more remaining items in the active drop.')
         return
      
      if message.from_user.id in claimed_drop:
         await bot.send_message(message.chat.id, 'You\'ve already claimed your item from the active drop.')
         return
   
      product = await database.__fetch_product__(int(active_drop['item']))
      fs = FileSystem(product[1])
      ps = fs.read()
      if not len(ps):
         await bot.send_message(message.chat.id, 'There are no more remaining items in the active drop.')
         return
      
      claimed_drop.append(message.from_user.id)
      active_drop['remaining'] -= 1
      item = random.choice(ps).strip()
      fs.remove(item)

      print(f'SUCCESS ({colorama.Style.BRIGHT}{colorama.Fore.LIGHTBLUE_EX}CLAIM{colorama.Style.RESET_ALL})', f'{message.from_user.id}: {item}')
      await bot.send_message(message.chat.id, f'{product[0]}: {item}')
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (MENU)', f'{type(E)}: {str(E)}')
           try:
             await bot.send_message(message.chat.id, errors['ERROR_OCCURED_SUPPORT'])
           except:
             pass
           
# Cashapp Payment Gateway           
@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'CASHAPP-CREDITS-WANTED')
async def __credits_wanted__(message):
    try:
      blacklisted = await database.__is_blacklisted__(message.from_user.id)
      if blacklisted:
         return
         
      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except Exception as E:
             print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CASHAPP-CREDITS-WANTED, DELETE)', f'{type(E)}: {str(E)}')

      if user_depositing.get(str(message.from_user.id)):
         msg = await bot.send_message(message.chat.id, 'You have a pending purchase, please complete it before making another purchase.'); 
         await asyncio.sleep(7.5)
         await bot.delete_message(message.chat.id, msg.id)
         return
         
      amount = message.text.replace('.', '').replace('$', '')
      if not amount.isdigit():
         msg = await bot.send_message(message.chat.id, 'We\'re sorry, but the amount provided doesn\'t seem to be a valid number. Please double-check the value you entered and try again.')
         await asyncio.sleep(7.5)
         await bot.delete_message(message.chat.id, msg.id)
         return
      elif float(amount) < 1:
         msg = await bot.send_message(message.chat.id, 'We\'re sorry, but the amount provided has to be over a dollar. Please try again.')
         await asyncio.sleep(7.5)
         await bot.delete_message(message.chat.id, msg.id)
         return
    
      user_state[str(message.from_user.id)]['state'] = 'CASHAPP-AWAITING-PAYMENT'
      user_state[str(message.from_user.id)]['variables']['amount'] = float(amount)

      print(f'{colorama.Style.BRIGHT}{colorama.Fore.LIGHTGREEN_EX}PENDING{colorama.Style.RESET_ALL}', f'{message.from_user.id}: {float(amount)}')
      note = await __get_note__()
      parsed_amount = amount.replace('.', r'\.')
      parsed_first_name = message.from_user.first_name.replace('.', r'\.')
      timestamp = Time.generateTimestamp()
      future_timestamp = Time.getFutureTimestamp(timestamp, settings['order_duration_time'])
      future_timestamp_str = datetime.datetime.fromtimestamp(future_timestamp, pytz.timezone('America/Denver')).strftime('%b %d, %Y at %I:%M %p')

      markup = InlineKeyboardMarkup()
      markup.add(InlineKeyboardButton('Pay', url = f'https://cash.app/{settings["cashapp_tag"]}/{amount}'))
      msg = await bot.send_message(message.chat.id, rf'''Hello, {parsed_first_name}\. To purchase your credits, please send a payment to *{settings["cashapp_tag"]}* with the following information\:
       
*Payment Note*\: *{note}*
*Payment Amount*\: *${parsed_amount}*

You have until *{future_timestamp_str} MDT* to send the payment before the order expires\. Once you\'ve sent, reply to this message with the web receipt link\.''', reply_markup = markup, parse_mode = 'MarkdownV2')
      
      user_depositing[str(message.from_user.id)] = {}
      user_depositing[str(message.from_user.id)]['note'] = note
      user_depositing[str(message.from_user.id)]['message_id'] = message.id
      user_depositing[str(message.from_user.id)]['deposit_message_id'] = msg.id
      user_depositing[str(message.from_user.id)]['chat_id'] = message.chat.id
      user_depositing[str(message.from_user.id)]['user_id'] = message.from_user.id
      user_depositing[str(message.from_user.id)]['timestamp'] = timestamp
      user_depositing[str(message.from_user.id)]['future_timestamp'] = future_timestamp
      user_state[str(message.from_user.id)]['variables']['amount'] = float(amount)
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CREDITS-WANTED)', f'{type(E)}: {str(E)}')

@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'CASHAPP-AWAITING-PAYMENT')
async def __awaiting_cashapp_payment__(message):
    try:
      blacklisted = await database.__is_blacklisted__(message.from_user.id)
      if blacklisted:
         return
      
      deposit = user_depositing.get(str(message.from_user.id))
      if not deposit:
         msg = await bot.send_message(message.chat.id, 'We\'re sorry, but this order has expired. Please restart the process.')
         await asyncio.sleep(7.5)
         try:
            await bot.delete_message(message.chat.id, msg.id)
            await bot.delete_message(message.chat.id, message.id)
         except:
            pass
         return
      
      amount = user_state[str(message.from_user.id)]['variables']['amount']
      parsed_amount = str(amount).replace('.', r'\.')

      payment = await __get_receipt__(message.text)
      if not payment:
         msg = await bot.reply_to(message, 'You must send a valid web receipt in order for your credits to be added.')
         await asyncio.sleep(7.5)
         await bot.delete_message(message.chat.id, msg.id)
         return     

      receipt = await database.__fetch_receipt__(payment[6])

      if receipt:
         msg = await bot.reply_to(message, 'This receipt has already been used, please try again with a valid web receipt.')
         await asyncio.sleep(7.5)
         await bot.delete_message(message.chat.id, msg.id)
         return
      
      if (
         payment[1].lower() != settings['cashapp_tag'].lower() and 
         float(payment[2]) != amount
      ):
          msg = await bot.reply_to(message, 'It seems like the provided web receipt isn\'t valid, please retry.')
          await asyncio.sleep(7.5)
          await bot.delete_message(message.chat.id, msg.id)
          await bot.delete_message(message.chat.id, message.id)
          return
      elif (
         payment[1].lower() != settings['cashapp_tag'].lower() and
         float(payment[2]) == amount
      ):
          msg = await bot.reply_to(message, 'It seems like you\'ve sent money to the wrong Cash App, please contact support to handle this situation.  (@{})'.format(settings['support_handle']))
          await asyncio.sleep(10)
          await bot.delete_message(message.chat.id, msg.id)
          return
      
      if not payment[1].lower() == settings['cashapp_tag'].lower():
         msg = await bot.reply_to(message, 'It seems like you\'ve sent money to the wrong Cash App, please contact support to handle this situation. (@{})'.format(settings['support_handle']))
         await asyncio.sleep(10)
         await bot.delete_message(message.chat.id, msg.id)
         return
      elif payment[3].lower() != deposit['note'].lower():
         msg = await bot.reply_to(message, 'It seems like you\'ve added the wrong note to the payment, please contact support to handle this situation. (@{})'.format(settings['support_handle']))
         await asyncio.sleep(10)
         await bot.delete_message(message.chat.id, msg.id)
         return
      elif not Time.withinTimeLimit(deposit['timestamp'], payment[4], deposit['future_timestamp']):
         msg = await bot.reply_to(message, 'This order has expired, you\'ve ran out of time. Please contact support to handle this situation. (@{})'.format(settings['support_handle']))
         await asyncio.sleep(10)
         await bot.delete_message(message.chat.id, msg.id) 
         return
      
      user = await database.__fetch_user__(message.from_user.id)
      await database.__update_user__(message.from_user.id, new_balance = user[0] + amount)
      await database.__add_receipt__(payment[6])
      try:
        msg_id =  user_depositing[str(message.from_user.id)]['deposit_message_id']
        del user_depositing[str(message.from_user.id)]
        del user_state[str(message.from_user.id)]

        print(f'SUCCESS ({colorama.Style.BRIGHT}{colorama.Fore.LIGHTBLUE_EX}PURCHASED{colorama.Style.RESET_ALL})', f'{message.from_user.id}: {float(user[0] + amount)} (${float(amount)})')
        msg = await bot.send_message(message.chat.id, rf'💰 You\'ve successfully bought *{parsed_amount}* credit\(s\)\.', parse_mode = 'MarkdownV2')
        await asyncio.sleep(10)
        await bot.delete_message(message.chat.id, msg.id)
        await bot.delete_message(message.chat.id, msg_id)
        await bot.delete_message(message.chat.id, message.id)
      except:
        pass
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CASHAPP-AWAITING-PAYMENT)', f'{type(E)}: {str(E)}')

# Adminstrator States
@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'DM-ALL')
async def __lookup_user_id__(message):
      if message.from_user.id not in settings['owners']:
         return
      
      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except:
        pass
      
      del user_state[str(message.from_user.id)]

      markup = InlineKeyboardMarkup()
      markup.add(InlineKeyboardButton('🗑️ Dispose', callback_data = 'DELETE-MESSAGE'))
      sent = 0
      try:
        users = await database.__fetch_all_users__()
        for user in users:
            try:
              await bot.send_message(user[0], message.text, parse_mode = 'MarkdownV2')
              print(f'SUCCESS ({colorama.Style.BRIGHT}{colorama.Fore.LIGHTBLUE_EX}DM{colorama.Style.RESET_ALL})', f'{user[0]}')
              sent += 1
            except:
              print(f'FAILURE ({colorama.Style.BRIGHT}{colorama.Fore.RED}DM{colorama.Style.RESET_ALL})', f'{user[0]}')
            await asyncio.sleep(0.5)
        await bot.send_message(message.chat.id, 'Sent {}/{}'.format(sent, len(users)), reply_markup = markup)
      except Exception as E:
         await bot.send_message(message.chat.id, '{}: {}'.format(type(E), str(E)))      

@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'LOOKUP-USER-ID')
async def __lookup_user_id__(message):
      if message.from_user.id not in settings['owners']:
         return
      
      if not message.text.isdigit():
         try:
           await bot.delete_message(message.chat.id, message.id)
         except:
           pass
         return
      
      user = await database.__fetch_user__(int(message.text))

      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except:
        pass

      del user_state[str(message.from_user.id)]
      
      if not user:
         msg = await bot.send_message(message.chat.id, 'Invalid User ID')
         await asyncio.sleep(10)
         await bot.delete_message(message.chat.id, msg.id) 
         return
      
      markup = InlineKeyboardMarkup()
      markup.add(InlineKeyboardButton('🗑️ Dispose Lookup', callback_data = 'DELETE-MESSAGE'))
      await bot.send_message(message.chat.id, '🕵️‍♀️ User ID: {}\n💰 Credits: {}'.format(message.text, float(user[0])), reply_markup = markup)

@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'BLACKLIST-USER-ID')
async def __blacklist_user_id__(message):
      if message.from_user.id not in settings['owners']:
         return
      
      if not message.text.isdigit():
         try:
           await bot.delete_message(message.chat.id, message.id)
         except:
           pass
         return
      
      user = await database.__fetch_user__(int(message.text))

      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except:
        pass

      del user_state[str(message.from_user.id)]
      
      if not user:
         msg = await bot.send_message(message.chat.id, 'Invalid User ID')
         await asyncio.sleep(10)
         await bot.delete_message(message.chat.id, msg.id) 
         return
      
      await database.__add_blacklist__(int(message.text))
      
      markup = InlineKeyboardMarkup()
      markup.add(InlineKeyboardButton('🗑️ Dispose', callback_data = 'DELETE-MESSAGE'))
      await bot.send_message(message.chat.id, '🚫 Blacklisted User'.format(message.text, float(user[0])), reply_markup = markup)

@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'REMOVE-BLACKLIST-USER-ID')
async def __remove_blacklist__(message):
      if message.from_user.id not in settings['owners']:
         return
      
      if not message.text.isdigit():
         try:
           await bot.delete_message(message.chat.id, message.id)
         except:
           pass
         return
      
      user = await database.__fetch_user__(int(message.text))

      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except:
        pass

      del user_state[str(message.from_user.id)]
      
      if not user:
         msg = await bot.send_message(message.chat.id, 'Invalid User ID')
         await asyncio.sleep(10)
         await bot.delete_message(message.chat.id, msg.id) 
         return
      
      await database.__remove_blacklist__(int(message.text))
      
      markup = InlineKeyboardMarkup()
      markup.add(InlineKeyboardButton('🗑️ Dispose', callback_data = 'DELETE-MESSAGE'))
      await bot.send_message(message.chat.id, '🔓 Revoked User Blacklist'.format(message.text, float(user[0])), reply_markup = markup)

@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'SET-USER-CREDITS')
async def __set_user_credits__(message):
      if message.from_user.id not in settings['owners']:
         return

      if not message.text.isdigit():
         try:
           await bot.delete_message(message.chat.id, message.id)
         except:
           pass
         return
      
      user = await database.__fetch_user__(int(message.text))
      if not user:
         await bot.delete_message(message.chat.id, message.id) 
         msg = await bot.send_message(message, 'Invalid User ID')
         await asyncio.sleep(10)
         await bot.delete_message(message.chat.id, msg.id) 
         return
      
      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except:
        pass

      msg = await bot.send_message(message.chat.id, '💰 Credits?')
      user_state[str(message.from_user.id)]['state'] = 'AWAITING-CREDITS'
      user_state[str(message.from_user.id)]['state_message_id'] = msg.id
      user_state[str(message.from_user.id)]['variables']['user_id'] = message.text

@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'AWAITING-PRODUCT-ID')
async def __create_drop__(message):
      if message.from_user.id not in settings['owners']:
         return

      if not message.text.isdigit():
         try:
           await bot.delete_message(message.chat.id, message.id)
         except:
           pass
         return
      
      product = await database.__fetch_product__(int(message.text))
      if not product:
         await bot.delete_message(message.chat.id, message.id) 
         msg = await bot.send_message(message, 'Invalid Product ID')
         await asyncio.sleep(10)
         await bot.delete_message(message.chat.id, msg.id) 
         return
      
      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except:
        pass

      msg = await bot.send_message(message.chat.id, '🎨 Amount of Items?')
      user_state[str(message.from_user.id)]['state'] = 'AWAITING-PRODUCT-AMOUNT'
      user_state[str(message.from_user.id)]['state_message_id'] = msg.id
      user_state[str(message.from_user.id)]['variables'] = {}
      user_state[str(message.from_user.id)]['variables']['product_id'] = message.text

@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'AWAITING-PRODUCT-AMOUNT')
async def __awaiting_product_amount__(message):
      if message.from_user.id not in settings['owners']:
         return
      
      global active_drop

      if not message.text.isdigit():
         try:
           await bot.delete_message(message.chat.id, message.id)
         except:
           pass
         return
      
      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except:
        pass

      active_drop = {
         'item': int(user_state[str(message.from_user.id)]['variables']['product_id']),
         'remaining': int(message.text)
      }

      msg = await bot.send_message(message.chat.id, '🎨 Created Drop (Remaining: {}/{})'.format(message.text, message.text))
      active_drop['message'] = msg

@bot.message_handler(func = lambda message: user_state.get(str(message.from_user.id), {}).get('state') == 'AWAITING-CREDITS')
async def __awaiting_credits__(message):
      if message.from_user.id not in settings['owners']:
         return

      if not message.text.replace('$', '').replace('.', '').isdigit():
         try:
           await bot.delete_message(message.chat.id, message.id)
         except:
           pass
         return

      try:
        await bot.delete_message(message.chat.id, message.id)
        await bot.delete_message(message.chat.id, user_state[str(message.from_user.id)]['state_message_id'])
      except:
        pass

      user_id = user_state[str(message.from_user.id)]['variables']['user_id']
      user = await database.__fetch_user__(user_id)
      if not user_id:
         await database.__add_user__(user_id, float(message.text))
      balance = user[0]
      if user_state[str(message.from_user.id)]['variables']['type'] == 'ADD': balance = user[0] + float(message.text)
      elif user_state[str(message.from_user.id)]['variables']['type'] == 'DEL': balance = user[0] - float(message.text)
      else: balance = float(message.text)
      await database.__update_user__(user_id, new_balance = balance)

      del user_state[str(message.from_user.id)]
      markup = InlineKeyboardMarkup()
      markup.add(InlineKeyboardButton('🗑️ Dispose', callback_data = 'DELETE-MESSAGE'))
      await bot.send_message(message.chat.id, '💰 Credits Configured.', reply_markup = markup)
      
# Functions
def __buttons__(current_page, total_pages):
    buttons = []
    if current_page > 1:
       buttons.append(InlineKeyboardButton('← Previous', callback_data = 'PREVIOUS-PAGE'))
    if current_page < total_pages:
       buttons.append(InlineKeyboardButton('Next →', callback_data = 'NEXT-PAGE'))
    return buttons

async def __products__(bot, call, products, current_page):
    start_index = (current_page - 1) * settings['max_products_per_page']
    end_index = min(start_index + settings['max_products_per_page'], len(products))
    page_products = products[start_index:end_index]
    max_products = (len(products) + settings['max_products_per_page'] - 1) // settings['max_products_per_page']

    if current_page > max_products:
       return
    
    text = ''

    if not page_products:
       text = '404 —— You\'ve reached a mystery product page.'

    for product in page_products:
        stock = open(product[2], 'r')
        text += f'''
{product[0]}. {product[1]}: ${product[3]} (x{len(stock.readlines())})'''
        
    text += f'''

pg. {current_page}/{max_products}
'''
    
    markup = InlineKeyboardMarkup()
    buttons = __buttons__(current_page, (len(products) + settings['max_products_per_page'] - 1) // settings['max_products_per_page'])
    markup.row(*buttons)
    markup.add(InlineKeyboardButton('🛒 Add to Cart', callback_data = 'ADD-TO-CART'), InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'START'), row_width = 2)
    
    return text, markup, page_products

async def __purchase__(call):
    markup = InlineKeyboardMarkup()
    user = await database.__fetch_user__(call.from_user.id)
    cart = [item.replace(' ', '') for item in user[1].split(',') if item]
    
    if not cart:
       markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'CART'))
       return [], 'Your cart contains no products.', markup
    
    products_ = {}
    
    for product_id in cart:
        try:
          product_details = await database.__fetch_product__(int(product_id)) + (product_id,)
          if product_details[0]:
             with open(product_details[1], 'r') as stock_file:
                  stock = stock_file.readlines()
                  if not stock:
                     continue
                  if not products_.get(str(product_details[0])):
                     products_[str(product_details[0])] = product_details + (0,)
                  products_[str(product_details[0])] = product_details + (products_[str(product_details[0])][4] + 1,)
        except:
            pass
    
    total = 0.00
    products__ = {}
    
    for product_key, product_value in list(products_.items()):
        with open(product_value[1], 'r') as stock_file:
             stock = stock_file.readlines()
             if len(stock) > product_value[4]:
                total += float(product_value[4] * product_value[2])
                products__[product_key] = product_value
             else:
                del products_[product_key]
    
    if float(total) == 0.00:
       markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'CART'))
       return [], 'The product(s) you\'re trying to purchase contain an empty stock.', markup
    
    if user[0] < total:
       markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'CART'))
       return [], 'You have an insufficient amount of credits. Please clear your cart and add affordable items.', markup

    await database.__update_user__(call.from_user.id, new_balance = user[0] - total)
    user = await database.__fetch_user__(call.from_user.id)
    cart = [item.replace(' ', '') for item in user[1].split(',')]
    bought = []
    
    for product_key, product_value in products__.items():
        with open(product_value[1], 'r') as stock_file:
            sk = stock_file.readlines()
            fs = FileSystem(product_value[1])
            for products in range(product_value[4]):
                gd = random.choice(sk)
                sk.remove(gd)
                fs.remove(gd)
                cart.remove(product_value[3])
                bought.append((product_value[3], product_key, gd.strip()))
    
    await database.__update_user__(call.from_user.id, new_cart = ', '.join(item for item in cart))
    markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'START'))
    return bought, None, markup

# Administrator Calls
@bot.callback_query_handler(func = lambda call: call.data == 'CREATE-DROP')
async def __calls_create_drop__(call):
    try:
      await bot.answer_callback_query(call.id)

      if call.from_user.id not in settings['owners']:
         return
      
      msg = await bot.send_message(call.message.chat.id, '🎨 Product ID?')
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'AWAITING-PRODUCT-ID'
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, CREATE-DROP)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'LOOKUP-USER-ID')
async def __calls_lookup_user_id__(call):
    try:
      await bot.answer_callback_query(call.id)

      if call.from_user.id not in settings['owners']:
         return
      
      msg = await bot.send_message(call.message.chat.id, '🕵️‍♀️ User ID?')
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'LOOKUP-USER-ID'
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, LOOKUP-USER-ID)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'DM-ALL')
async def __calls_lookup_user_id__(call):
    try:
      await bot.answer_callback_query(call.id)

      if call.from_user.id not in settings['owners']:
         return
      
      msg = await bot.send_message(call.message.chat.id, '🕵️‍♀️ Message?')
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'DM-ALL'
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, DM-ALL)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'BLACKIST')
async def __calls_blacklist__(call):
    try:
      await bot.answer_callback_query(call.id)

      if call.from_user.id not in settings['owners']:
         return
      
      msg = await bot.send_message(call.message.chat.id, '🕵️‍♀️ User ID?')
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'BLACKLIST-USER-ID'
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, BLACKLIST)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'REVOKE-BLACKLIST')
async def __calls_revoke_blacklist__(call):
    try:
      await bot.answer_callback_query(call.id)

      if call.from_user.id not in settings['owners']:
         return
      
      msg = await bot.send_message(call.message.chat.id, '🕵️‍♀️ User ID?')
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'REMOVE-BLACKLIST-USER-ID'
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, REVOKE-BLACKLIST)', f'{type(E)}: {str(E)}')
           
@bot.callback_query_handler(func = lambda call: call.data == 'SET-CREDITS')
async def __calls_set_credits__(call):
    try:
      await bot.answer_callback_query(call.id)

      if call.from_user.id not in settings['owners']:
         return
      
      msg = await bot.send_message(call.message.chat.id, '🕵️‍♀️ User ID?')
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'SET-USER-CREDITS'
      user_state[str(call.from_user.id)]['variables'] = {}
      user_state[str(call.from_user.id)]['variables']['type'] = ''
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, SET-USER-CREDITS)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'ADD-CREDITS')
async def __calls_add_credits__(call):
    try:
      await bot.answer_callback_query(call.id)

      if call.from_user.id not in settings['owners']:
         return
      
      msg = await bot.send_message(call.message.chat.id, '🕵️‍♀️ User ID?')
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'SET-USER-CREDITS'
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
      user_state[str(call.from_user.id)]['variables'] = {}
      user_state[str(call.from_user.id)]['variables']['type'] = 'ADD'
      print(user_state)
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, ADD-USER-CREDITS)', f'{type(E)}: {str(E)}')      


@bot.callback_query_handler(func = lambda call: call.data == 'REMOVE-CREDITS')
async def __calls_add_credits__(call):
    try:
      await bot.answer_callback_query(call.id)

      if call.from_user.id not in settings['owners']:
         return
      
      msg = await bot.send_message(call.message.chat.id, '🕵️‍♀️ User ID?')
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'SET-USER-CREDITS'
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
      user_state[str(call.from_user.id)]['variables'] = {}
      user_state[str(call.from_user.id)]['variables']['type'] = 'DEL'
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, ADD-USER-CREDITS)', f'{type(E)}: {str(E)}')                   
           
# Calls
@bot.callback_query_handler(func = lambda call: call.data == 'START')
async def __calls_start__(call):
    await bot.answer_callback_query(call.id)
    try:
      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
      
      markup = InlineKeyboardMarkup()
      user = await database.__fetch_user__(call.from_user.id)
      text = 'Welcome Back, ID: *{}*'.format(call.from_user.id)
      cart = [item for item in user[1].split(',') if item]
      markup.add(InlineKeyboardButton(text = '🛍️  Shop', callback_data = 'SHOP'))
      markup.add(
          InlineKeyboardButton(text = '💰 ${} '.format(user[0]), callback_data = 'CHOOSE-PAYMENT'), 
          InlineKeyboardButton(text = '🛒 Cart ({})'.format(len(cart)), callback_data = 'CART'), 
      row_width = 2)
      if call.from_user.id in settings['owners']:
         text += ' —— Admin Portal'
         markup.add(
             InlineKeyboardButton(text = '🕵️‍♀️ Lookup User ID', callback_data = 'LOOKUP-USER-ID'), 
             InlineKeyboardButton(text = '📦 Lookup Order ID', callback_data = 'LOOKUP-ORDER-ID'), 
         row_width = 2)
         markup.add(
             InlineKeyboardButton(text = '💰 Set Credits', callback_data = 'SET-CREDITS'),
             InlineKeyboardButton(text = '💸 Add Credits', callback_data = 'ADD-CREDITS'),
             InlineKeyboardButton(text = '💰 Remove Credits', callback_data = 'REMOVE-CREDITS'),
         row_width = 3)
         markup.add(
             InlineKeyboardButton(text = '🚫 Blacklist', callback_data = 'BLACKLIST'),
             InlineKeyboardButton(text = '🔓 Revoke Blacklist', callback_data = 'REVOKE-BLACKLIST'),
         row_width = 2)
         markup.add(InlineKeyboardButton(text = '🎨 Create Product', callback_data = 'CREATE-PRODUCT'))
         markup.add(InlineKeyboardButton(text = '🎨 Create Drop', callback_data = 'CREATE-DROP'))
         markup.add(InlineKeyboardButton(text = '📨 DM All', callback_data = 'DM-ALL'))

      await bot.edit_message_text(text = text, chat_id = call.message.chat.id, message_id = call.message.id, reply_markup = markup, parse_mode = 'MarkdownV2')
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (MENU)', f'{type(E)}: {str(E)}')
           try:
             await bot.send_message(call.message.chat.id, errors['ERROR_OCCURED_SUPPORT'])
           except:
             pass

@bot.callback_query_handler(func = lambda call: call.data == 'DELETE-MESSAGE')
async def __calls_delete_message__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
      
      await bot.delete_message(call.message.chat.id, call.message.id)
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, DELETE-MESSAGE)', f'{type(E)}: {str(E)}')


@bot.callback_query_handler(func = lambda call: call.data == 'SHOP')
async def __calls_shop__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return

      user = await database.__fetch_user__(call.from_user.id)
      products = await database.__fetch_all_products__()
      products = await __products__(bot, call, products, user[2])

      await bot.edit_message_text(text = products[0], chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup = products[1])
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, SHOP)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'CART')
async def __calls_cart__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
      
      user = await database.__fetch_user__(call.from_user.id)
      cart = [item for item in user[1].split(',') if item]

      products = {}
      products_total = 0.00

      for product in cart:
          try:
            product = await database.__fetch_product__(int(product))
            if product:
               if not products.get(str(product[0])):
                  products[str(product[0])] = (product[0], 0)
               products[str(product[0])] = products[str(product[0])][0], products[str(product[0])][1] + 1
               products_total += float(product[2])
          except:
             pass
          
      text = 'You have no products in your cart.'
      markup = InlineKeyboardMarkup()

      if products:
         text = ''
         for product in products.items():
             text += f'{product[1][0]}: x{product[1][1]}'
             text += '\n'
         text += '\n'
         text += f'Total: ${products_total}'
         markup.add(InlineKeyboardButton(text = '🗑️ Clear Cart', callback_data = 'CLEAR-CART'), InlineKeyboardButton(text = '💰 Purchase', callback_data = 'PURCHASE'), row_width = 2)

      markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'START'))
      await bot.edit_message_text(text, chat_id = call.message.chat.id, message_id = call.message.id, reply_markup = markup)
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, CART)', f'{type(E)}: {str(E)}')
           
@bot.callback_query_handler(func = lambda call: call.data == 'CLEAR-CART')
async def __calls_clear_cart__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
      
      await database.__update_user__(call.from_user.id, new_cart = '')

      markup = InlineKeyboardMarkup()
      markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'START'))
      await bot.edit_message_text('Your cart has been cleared.', chat_id = call.message.chat.id, message_id = call.message.id, reply_markup = markup)
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, ADD-PRODUCT)', f'{type(E)}: {str(E)}')
           
@bot.callback_query_handler(func = lambda call: call.data == 'ADD-TO-CART')
async def __calls_add_to_cart__(call):
    try:
      await bot.answer_callback_query(call.id)
      
      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
      
      user = await database.__fetch_user__(call.from_user.id)
      products = await database.__fetch_all_products__()
      products = await __products__(bot, call, products, user[2])

      text = 'Choose which product you want to add to your cart.'
      markup = InlineKeyboardMarkup() 

      for product in products[2]:
          markup.add(InlineKeyboardButton(text = product[1], callback_data = f'PRODUCT-{product[0]}'))
      markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'SHOP'))

      await bot.edit_message_text(text = text, chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup = markup)
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, ADD-TO-CART)', f'{type(E)}: {str(E)}')
                     
@bot.callback_query_handler(func = lambda call: call.data.startswith('PRODUCT'))
async def __calls_add_product_to_cart__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
         
      user = await database.__fetch_user__(call.from_user.id)
      cart = [item for item in user[1].split(',') if item]

      product_id = call.data.split('-')[1]
      product = await database.__fetch_product__(product_id)

      text = 'The product chosen is no longer in the database.'
      markup = InlineKeyboardMarkup()

      if product:
         text = f'"{product[0]}" has been added to your cart.'
         await database.__update_user__(call.from_user.id, new_cart = user[1] + ', {}'.format(product_id) if len(cart) != 0 else product_id)

      markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'ADD-TO-CART'))
      await bot.edit_message_text(text, chat_id = call.message.chat.id, message_id = call.message.id, reply_markup = markup)
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, ADD-PRODUCT)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'CHOOSE-PAYMENT')
async def __calls_choose_payment__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
    
      text = 'Select a Payment Method'
      markup = InlineKeyboardMarkup()
      
      markup.add(InlineKeyboardButton(text = ' Cash App', callback_data = 'CHOSE-CASHAPP'), InlineKeyboardButton(text = 'Cryptocurrency', callback_data = 'CHOSE-CRYPTO'), row_width = 2)
      markup.add(InlineKeyboardButton(text = 'Cancel', callback_data = 'DELETE-MESSAGE'))
      
      await bot.send_message(call.message.chat.id, text, reply_markup = markup)
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, CHOOSE-PAYMENT)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'CHOSE-CASHAPP')
async def __calls_chose_cashapp__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
    
      msg = await bot.edit_message_text('💰 Please reply with the amount of credits you\'re want to purchase.', chat_id = call.message.chat.id, message_id = call.message.id)
      user_state[str(call.from_user.id)] = {}
      user_state[str(call.from_user.id)]['state'] = 'CASHAPP-CREDITS-WANTED'
      user_state[str(call.from_user.id)]['state_message_id'] = msg.id
      user_state[str(call.from_user.id)]['variables'] = {}
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, CHOOSE-PAYMENT)', f'{type(E)}: {str(E)}')
           
@bot.callback_query_handler(func = lambda call: call.data == 'PURCHASE')
async def __calls_purchase__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
      
      user = await database.__fetch_user__(call.from_user.id)
      cart = [item for item in user[1].split(',') if item]
      markup = InlineKeyboardMarkup()

      if not cart:
         markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'CART'))
         await bot.edit_message_text('Your cart is empty.', chat_id = call.message.chat.id, message_id = call.message.id, reply_markup = markup)
         return
   
      purchase = await __purchase__(call)
      if purchase[0]:
         user = await database.__fetch_user__(call.from_user.id)
         markup.add(InlineKeyboardButton(text = '🔙 Go Back', callback_data = 'START'))

         accounts = {}
         for account in purchase[0]:
             if not accounts.get(account[1]):
                accounts[account[1]] = []
             accounts[account[1]].append(account[2])

         print(f'SUCCESS ({colorama.Style.BRIGHT}{colorama.Fore.LIGHTBLUE_EX}PURCHASED{colorama.Style.RESET_ALL})', f'{call.from_user.id}: {purchase[0]}')
         await bot.edit_message_text(f'You\'ve successfully purchased {len(purchase[0])} product(s). You now have {user[0]} credits. The goods will be delivered shortly.', chat_id = call.message.chat.id, message_id = call.message.id, reply_markup = markup)

         goods_markup = InlineKeyboardMarkup()
         goods_markup.add(InlineKeyboardButton(text = '🗑️ Dispose Message', callback_data = 'DELETE-MESSAGE'))
         text = ''.join('{}:\n{}'.format(account[0], '\n'.join(account_ for account_ in account[1])) for account in accounts.items())

         await bot.send_message(call.message.chat.id, text, reply_markup = goods_markup)
      else:
         await bot.edit_message_text(purchase[1], chat_id = call.message.chat.id, message_id = call.message.id, reply_markup = purchase[2])
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, PURCHASE)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'NEXT-PAGE')
async def __calls_next_page__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
      
      user = await database.__fetch_user__(call.from_user.id)
      products = await __products__(bot, call, await database.__fetch_all_products__(), user[2] + 1)
      if not products:
         return
      
      await database.__update_user__(call.from_user.id, new_page = user[2] + 1) 
      
      await bot.edit_message_text(text = products[0], chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup = products[1])
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, NEXT-PAGE)', f'{type(E)}: {str(E)}')

@bot.callback_query_handler(func = lambda call: call.data == 'PREVIOUS-PAGE')
async def __calls_previous_page__(call):
    try:
      await bot.answer_callback_query(call.id)

      blacklisted = await database.__is_blacklisted__(call.from_user.id)
      if blacklisted:
         return
      
      user = await database.__fetch_user__(call.from_user.id)
      if user[2] <= 0:
         return
      await database.__update_user__(call.from_user.id, new_page = user[2] - 1) 
      products = await __products__(bot, call, await database.__fetch_all_products__(), user[2] - 1)
      await bot.edit_message_text(text = products[0], chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup = products[1])
    except Exception as E:
           print(f'{colorama.Style.BRIGHT}{colorama.Fore.RED}FAILURE{colorama.Style.RESET_ALL} (CALLS, PREVIOUS-PAGE)', f'{type(E)}: {str(E)}')
           
asyncio.run(main())
