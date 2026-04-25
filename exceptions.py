class ApiRequestError(Exception):
    """Ошибка запроса к API Практикума."""


class ApiResponseError(Exception):
    """Некорректный формат ответа API."""


class HomeworkStatusError(Exception):
    """Неожиданный статус домашней работы."""
