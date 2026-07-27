from .converter_page import ConverterPage
from .cover_page import CoverPage
from .home_page import HomePage
from .publisher_change import install_publisher_change_prompt

install_publisher_change_prompt(CoverPage)

__all__ = ["CoverPage", "ConverterPage", "HomePage"]
