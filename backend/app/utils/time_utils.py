from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo


class TimeUtils:

    @staticmethod
    def get_utc_0_hour_ts() -> int:
       return int(datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp())

    @staticmethod
    def get_bg_0_hour_ts() -> int:
       return int(datetime.now(ZoneInfo("Asia/Shanghai")).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp())

    @staticmethod
    def get_current_ts() -> int:
        return int(datetime.now(timezone.utc).timestamp())
    
    @staticmethod
    def get_cur_bg_date() -> str:
        now_shanghai = datetime.now(ZoneInfo("Asia/Shanghai"))
        formatted_date_shanghai = now_shanghai.strftime('%Y-%m-%d')
        return formatted_date_shanghai
    
    @staticmethod
    def get_prev_bg_date() -> str:
        yesterday_shanghai = datetime.now(ZoneInfo("Asia/Shanghai")) - timedelta(days=1)
        return yesterday_shanghai.strftime('%Y-%m-%d')


    @staticmethod
    def get_prev_utc_0_hour_ts() -> int:
       return int(datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).timestamp()) - 86400
    
    @staticmethod
    def get_prev_utc_day_time_range() -> tuple[int, int]:
        yesterday_utc = datetime.now(timezone.utc) - timedelta(days=1)
        start_of_day = yesterday_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = yesterday_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        return int(start_of_day.timestamp()), int(end_of_day.timestamp())