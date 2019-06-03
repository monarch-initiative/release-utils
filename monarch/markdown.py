import logging
from typing import List, Tuple, Iterable


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def add_md_header(header: str, size: int=1) -> str:
    """
    :param header: str
    :param size: int
    :return: str
    """
    if size not in range(7)[1:7]:
        logger.error("Invalid header size: {}".format(size))
    return "{} {}".format(('#'*size), header)


def add_italics(text: str) -> str:
    return "_{}_".format(text)


def add_bold(text: str) -> str:
    return "__{}__".format(text)


def add_href(link: str, display_name: str) -> str:
    return "[{}]({})".format(display_name, link)


def add_md_table(data: Iterable[Tuple], headers: List[str]=None) -> str:
    """
    Convert tuple to markdown table
    :param data: Tuple[Tuple]
    :param headers: List[str]
    :return: str
    """
    table = '| {} |\n'.format(' | '.join(str(header) for header in headers))
    table += '|-'*(len(headers)) + '|\n'
    for row in data:
        table += '| {} |\n'.format(' | '.join(str(cell) for cell in row))

    return table
