from backend.app.services.smw.smw_queue_handler import SMWQueueHandlerTask
from backend.app.tasks.base_wallet_finder_tasks import BaseWalletFinderTask


class SMWQueueDailyProcessTask:

    @staticmethod
    def process_daily_smw():
        BaseWalletFinderTask().run()
        SMWQueueHandlerTask.daily_queue_shuffle_and_supply()