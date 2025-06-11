from backend.app.services.smw.smw_queue_handler import SMWQueueHandlerTask
from backend.app.tasks.base_wallet_finder_tasks import BaseWalletFinderTask
from backend.app.utils.log_utils import setup_logging


class SMWQueueDailyProcessTask:

    @staticmethod
    def process_daily_smw():
        new_wallets = BaseWalletFinderTask().run()
        SMWQueueHandlerTask.daily_queue_shuffle_and_supply(new_wallets)
        SMWQueueHandlerTask.cleanup()


if __name__ == '__main__':
    setup_logging()
    SMWQueueDailyProcessTask.process_daily_smw()
