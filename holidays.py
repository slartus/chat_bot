import logging
from datetime import date

import aiohttp

logger = logging.getLogger(__name__)

_API_URL = "http://htmlweb.ru/service/api.php"
_TYPE_ORDER = [4, 3, 2, 1]


def _extract_names(data) -> list[str]:
    """Вытаскивает названия праздников из ответа API."""
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        # API может вернуть {"data": [...]} или {"holiday": [...]} или сам быть словарём id→obj
        for key in ("data", "holiday", "holidays"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
        else:
            # словарь вида {id: {name: ...}}
            items = list(data.values())
    else:
        return []

    names = []
    for item in items:
        if isinstance(item, dict):
            name = item.get("name") or item.get("title") or item.get("holiday")
            if name:
                names.append(str(name))
    return names


async def get_holidays(d: date) -> list[str]:
    """Возвращает список праздников на дату. Перебирает типы 4→3→2→1,
    возвращает первый непустой результат."""
    date_str = d.strftime("%d.%m.%Y")
    params_base = {
        "holiday": "",
        "d_from": date_str,
        "d_to": date_str,
        "perpage": "50",
    }

    async with aiohttp.ClientSession() as session:
        for htype in _TYPE_ORDER:
            params = {**params_base, "type": htype}
            try:
                async with session.get(_API_URL, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json(content_type=None)
                    names = _extract_names(data)
                    if names:
                        return names
            except Exception:
                logger.exception("Ошибка при запросе праздников (тип %s)", htype)
                return []

    return []
