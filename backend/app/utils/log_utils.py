import logging
import os
from logging.handlers import RotatingFileHandler


class LoggingService:
    @staticmethod
    def setup():
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(project_root, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        if root_logger.handlers:
            for handler in root_logger.handlers:
                root_logger.removeHandler(handler)

        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        main_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'app.log'),
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setFormatter(formatter)
        root_logger.addHandler(main_handler)

        error_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'error.log'),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)

        api_handler = RotatingFileHandler(
            os.path.join(logs_dir, 'api.log'),
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        api_handler.setFormatter(formatter)
        api_logger = logging.getLogger("api")
        api_logger.setLevel(logging.INFO)
        api_logger.addHandler(api_handler)

        for logger_name in ["uvicorn", "uvicorn.access", "fastapi"]:
            logger = logging.getLogger(logger_name)
            logger.handlers = []
            logger.propagate = True
        
        logging.info("日志系统初始化完成")
        return root_logger


def setup_logging():
    return LoggingService.setup()