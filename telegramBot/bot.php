<?php

include './sys/inc/cfg.php';
include WWW_DIR . 'vendor/autoload.php';
include WWW_DIR . 'sys/inc/libs/VPExchangeBot/autoload.php';

try
{
	#Инициализация бота
	$bot = new \VPExchangeBot\Bot(TELEGRAM_BOT_TOKEN, REDIS_HOST, REDIS_DB);

	#Обработка команды /start
    $bot->command('start', function ($message) use ($bot) {
        $messageText = 'Что будем делать?';
		$main_keyboard = TELEGRAM_BOT_KEYBOARDS['main'];
		for ($i = 0, $keys = array(); $i < sizeof($main_keyboard); $i++)
		{
			foreach ($main_keyboard[$i] as $button)
			{
				if ($button['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $button['text'];}
			}
		}
		$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
		$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
    });

	#Обработка кнопок из файла /sys/inc/cfg.php
	$bot->on(
		function ($update) use ($bot)
		{
			$message = $update->getMessage();
			$mtext = $message->getText();
			foreach (TELEGRAM_BOT_KEYBOARDS as $keyboard)
			{
				foreach ($keyboard as $line)
				{
					foreach ($line as $button)
					{
						if ($button['text'] == $mtext)
						{
							$bot->wait_answer = 0;
							if ($button['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS))
							{
								switch ($button['action'])
								{
									case 'back':
										$messageText = 'Что будем делать?';
										$main_keyboard = TELEGRAM_BOT_KEYBOARDS['main'];
										for ($i = 0, $keys = array(); $i < sizeof($main_keyboard); $i++)
										{
											foreach ($main_keyboard[$i] as $btn)
											{
												if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
											}
										}
										$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
										$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
									break;
									case 'change_float':
										$settings = json_decode(file_get_contents(VPEXCHANGE_SETTINGS_FILE), true);
										$messageText = 'Изменяемый параметр: ' . $button['text'] . "\nТекущее значение: " . $settings[$button['param']];
										$sett_keyboard = TELEGRAM_BOT_KEYBOARDS['settings_cancel'];
										for ($i = 0, $keys = array(); $i < sizeof($sett_keyboard); $i++)
										{
											foreach ($sett_keyboard[$i] as $btn)
											{
												if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
											}
										}
										$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
										$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
										$bot->start_wait_answer = true;
										$bot->redis->set('tg:' . $bot->from_id . ':change_param_name', $button['param']);
										$bot->redis->set('tg:' . $bot->from_id . ':wait_action', 'change_float');
									break;
									case 'change_int':
										$settings = json_decode(file_get_contents(VPEXCHANGE_SETTINGS_FILE), true);
										$messageText = 'Изменяемый параметр: ' . $button['text'] . "\nТекущее значение: " . $settings[$button['param']];
										$sett_keyboard = TELEGRAM_BOT_KEYBOARDS['settings_cancel'];
										for ($i = 0, $keys = array(); $i < sizeof($sett_keyboard); $i++)
										{
											foreach ($sett_keyboard[$i] as $btn)
											{
												if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
											}
										}
										$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
										$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
										$bot->start_wait_answer = true;
										$bot->redis->set('tg:' . $bot->from_id . ':change_param_name', $button['param']);
										$bot->redis->set('tg:' . $bot->from_id . ':wait_action', 'change_int');
									break;
									case 'chatId':
										$bot->sendMessage($message->getFrom()->getId(), $message->getFrom()->getId());
									break;
									case 'settings':
										$messageText = 'Какую настройку меняем?';
										$sett_keyboard = TELEGRAM_BOT_KEYBOARDS['settings'];
										for ($i = 0, $keys = array(); $i < sizeof($sett_keyboard); $i++)
										{
											foreach ($sett_keyboard[$i] as $btn)
											{
												if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
											}
										}
										$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
										$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
									break;
									case 'startExchange':
										$messageText = "Запрос на запуск отправлен. Ожидание не больше минуты.";
										$bot->redis->set('tgbot_command', 'start');
										$main_keyboard = TELEGRAM_BOT_KEYBOARDS['main'];
										for ($i = 0, $keys = array(); $i < sizeof($main_keyboard); $i++)
										{
											foreach ($main_keyboard[$i] as $btn)
											{
												if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
											}
										}
										$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
										$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
									break;
									case 'statusExchange':
										$messageText = shell_exec('systemctl status exchanger.service');
										$main_keyboard = TELEGRAM_BOT_KEYBOARDS['main'];
										for ($i = 0, $keys = array(); $i < sizeof($main_keyboard); $i++)
										{
											foreach ($main_keyboard[$i] as $btn)
											{
												if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
											}
										}
										$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
										$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
									break;
									case 'stopExchange':
										$messageText = "Запрос на остановку отправлен. Ожидание не больше минуты.";
										$bot->redis->set('tgbot_command', 'stop');
										$main_keyboard = TELEGRAM_BOT_KEYBOARDS['main'];
										for ($i = 0, $keys = array(); $i < sizeof($main_keyboard); $i++)
										{
											foreach ($main_keyboard[$i] as $btn)
											{
												if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
											}
										}
										$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
										$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
									break;
								}
							}
							else {$bot->sendMessage($message->getFrom()->getId(), 'У Вас недостаточно прав.');}
						}
					}
				}
			}
			#Обработка ручного ввода пользователя, например, при редактировании настроек
			if ($bot->wait_answer)
			{
				switch ($bot->wait_action)
				{
					case 'change_float':
						$new_val = floatval(str_replace(',', '.', $mtext));
						$settings = json_decode(file_get_contents(VPEXCHANGE_SETTINGS_FILE), true);
						$settings[$bot->change_param_name] = $new_val;
						$res = file_put_contents(VPEXCHANGE_SETTINGS_FILE, json_encode($settings));
						$messageText = 'Новое значение параметра ' . $bot->change_param_name . ': ' . $new_val;
						$sett_keyboard = TELEGRAM_BOT_KEYBOARDS['settings'];
						for ($i = 0, $keys = array(); $i < sizeof($sett_keyboard); $i++)
						{
							foreach ($sett_keyboard[$i] as $btn)
							{
								if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
							}
						}
						$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
						$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
					break;
					case 'change_int':
						$new_val = intval($mtext);
						$settings = json_decode(file_get_contents(VPEXCHANGE_SETTINGS_FILE), true);
						$settings[$bot->change_param_name] = $new_val;
						$res = file_put_contents(VPEXCHANGE_SETTINGS_FILE, json_encode($settings));
						$messageText = 'Новое значение параметра ' . $bot->change_param_name . ': ' . $new_val;
						$sett_keyboard = TELEGRAM_BOT_KEYBOARDS['settings'];
						for ($i = 0, $keys = array(); $i < sizeof($sett_keyboard); $i++)
						{
							foreach ($sett_keyboard[$i] as $btn)
							{
								if ($btn['admin'] == 0 || in_array($message->getFrom()->getId(), TELEGRAM_BOT_ADMINS)) {$keys[$i][] = $btn['text'];}
							}
						}
						$reply_keyboard = new \TelegramBot\Api\Types\ReplyKeyboardMarkup($keys, false, true);
						$bot->sendMessage($message->getFrom()->getId(), $messageText, null, false, null, $reply_keyboard);
					break;
				}
			}
		}, 
		function () {return true;}
	);
	
	$bot->run();
	if ($bot->start_wait_answer) {$bot->wait_answer = 1;}
	else {$bot->wait_answer = 0;}
	$bot->redis->set('tg:' . $bot->from_id . ':wait_answer', $bot->wait_answer);
}
catch (\TelegramBot\Api\Exception $e) {$e->getMessage();}

?>