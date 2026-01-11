"""Base service class."""

import logging
from abc import ABC

logger = logging.getLogger(__name__)


class BaseService(ABC):
    """Abstract base service class."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
