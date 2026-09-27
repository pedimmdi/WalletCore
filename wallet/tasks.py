import logging

from celery import shared_task

from .reconciliation import reconcile_wallets

logger = logging.getLogger(__name__)


@shared_task
def notify_transaction(transaction_id):
    logger.info(
        "Transaction notification sent: transaction_id=%s",
        transaction_id,
    )


@shared_task
def daily_reconciliation():
    mismatches = reconcile_wallets()

    if mismatches:
        logger.error(
            "Daily reconciliation found %s wallet mismatch(es): %s",
            len(mismatches),
            mismatches,
        )
    else:
        logger.info(
            "Daily reconciliation completed successfully. "
            "No wallet mismatches found."
        )

    return {
        "mismatches": len(mismatches),
    }
