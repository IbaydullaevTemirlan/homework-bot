import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv

from exceptions import ApiRequestError, ApiResponseError, HomeworkStatusError


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {
    'Authorization': f'OAuth {PRACTICUM_TOKEN}',
}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}

logger = logging.getLogger(__name__)


def check_tokens():
    """Check that all required environment variables exist."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }

    ok = True
    for name, value in tokens.items():
        if not value:
            logger.critical(
                'Отсутствует обязательная переменная окружения: %s',
                name,
            )
            ok = False
    return ok


def send_message(bot, message):
    """Send message to Telegram chat."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Бот отправил сообщение "%s"', message)
    except Exception as error:
        logger.error('Сбой при отправке сообщения в Telegram: %s', error)
        raise


def get_api_answer(timestamp):
    """Make request to Practicum API and return response as Python dict."""
    params = {'from_date': timestamp}

    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=10,
        )
    except requests.RequestException as error:
        raise ApiRequestError(f'Ошибка запроса к API: {error}') from error

    if response.status_code != HTTPStatus.OK:
        raise ApiRequestError(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )

    try:
        return response.json()
    except ValueError as error:
        raise ApiResponseError(f'Ответ API не JSON: {error}') from error


def check_response(response):
    """Validate API response structure and return list of homeworks."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API должен быть словарём (dict).')

    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа "homeworks".')
    if 'current_date' not in response:
        raise KeyError('В ответе API нет ключа "current_date".')

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError('Значение ключа "homeworks" должно быть списком.')

    return homeworks


def parse_status(homework):
    """Parse homework status and return message for Telegram."""
    if not isinstance(homework, dict):
        raise TypeError('Элемент списка homeworks должен быть словарём.')

    if 'homework_name' not in homework:
        raise KeyError('В homework нет ключа "homework_name".')
    if 'status' not in homework:
        raise KeyError('В homework нет ключа "status".')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusError(
            f'Неожиданный статус домашней работы: {status}'
        )

    verdict = HOMEWORK_VERDICTS[status]
    return (
        f'Изменился статус проверки работы "{homework_name}". '
        f'{verdict}'
    )


def main():
    """Main bot loop."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    if not check_tokens():
        logger.critical('Программа принудительно остановлена.')
        sys.exit(1)

    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if not homeworks:
                logger.debug('Отсутствие в ответе новых статусов.')
            else:
                message = parse_status(homeworks[0])
                send_message(bot, message)

            timestamp = response.get('current_date', timestamp)
            last_error_message = ''

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)

            if message != last_error_message:
                try:
                    send_message(bot, message)
                except Exception:
                    pass
                last_error_message = message

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
