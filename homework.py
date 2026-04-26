"""Бот Telegram: проверка статуса домашней работы в Практикуме."""

import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telebot
from dotenv import load_dotenv
from telebot.apihelper import ApiException

from exceptions import ApiRequestError, HomeworkStatusError


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens():
    """Проверить обязательные переменные окружения."""
    required = (
        'PRACTICUM_TOKEN',
        'TELEGRAM_TOKEN',
        'TELEGRAM_CHAT_ID',
    )
    missing = [name for name in required if not globals().get(name)]
    if missing:
        logging.critical(
            'Отсутствуют обязательные переменные окружения: %s',
            ', '.join(missing),
        )
        return False
    return True


def send_message(bot, message):
    """Отправить сообщение в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Бот отправил сообщение "%s"', message)
    except (ApiException, requests.RequestException) as error:
        logging.error('Сбой при отправке сообщения в Telegram: %s', error)


def get_api_answer(timestamp):
    """Запросить API Практикума и вернуть JSON."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params,
            timeout=10,
        )
    except requests.RequestException as error:
        raise ConnectionError(
            'Ошибка запроса к API. '
            f'Эндпоинт: {ENDPOINT}. '
            f'Параметры: {params}. '
            f'Ошибка: {error}'
        ) from error

    if response.status_code != HTTPStatus.OK:
        raise ApiRequestError(
            f'Эндпоинт {ENDPOINT} недоступен. '
            f'Код ответа API: {response.status_code}'
        )

    return response.json()


def check_response(response):
    """Проверить структуру ответа API."""
    if not isinstance(response, dict):
        raise TypeError(
            'Ответ API должен быть dict. '
            f'Получен тип: {type(response)}'
        )

    if 'homeworks' not in response:
        raise KeyError('В ответе API нет ключа "homeworks".')

    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(
            'Значение ключа "homeworks" должно быть list. '
            f'Получен тип: {type(homeworks)}'
        )
    return homeworks


def parse_status(homework):
    """Собрать сообщение о статусе."""
    if not isinstance(homework, dict):
        raise TypeError(
            'Элемент "homeworks" должен быть dict. '
            f'Получен тип: {type(homework)}'
        )

    if 'homework_name' not in homework:
        raise KeyError('В homework нет ключа "homework_name".')
    if 'status' not in homework:
        raise KeyError('В homework нет ключа "status".')

    homework_name = homework['homework_name']
    status = homework['status']

    if status not in HOMEWORK_VERDICTS:
        raise HomeworkStatusError(f'Неожиданный статус: {status}')

    verdict = HOMEWORK_VERDICTS[status]
    return (
        f'Изменился статус проверки работы "{homework_name}". '
        f'{verdict}'
    )


def main():
    """Запустить основной цикл."""
    if not check_tokens():
        sys.exit(1)

    bot = telebot.TeleBot(TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)

            if not homeworks:
                logging.debug('Отсутствие в ответе новых статусов.')
            else:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                last_error_message = ''

            timestamp = response.get('current_date', int(time.time()))

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)

            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message

        finally:
            time.sleep(RETRY_PERIOD)


def setup_logging():
    """Настроить логирование."""
    logging.basicConfig(
        level=logging.DEBUG,
        format=(
            '%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d '
            '%(message)s'
        ),
        handlers=[logging.StreamHandler(sys.stdout)],
    )


if __name__ == '__main__':
    setup_logging()
    main()
