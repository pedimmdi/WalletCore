from .models import Wallet
from .services import get_account_balance


def reconcile_wallets():
    wallets = Wallet.objects.select_related("account").all()

    mismatches = []

    for wallet in wallets:
        ledger_balance = get_account_balance(wallet.account)

        if wallet.balance != ledger_balance:
            mismatches.append(
                {
                    "wallet_id": wallet.pk,
                    "user_id": wallet.user_id,
                    "wallet_balance": wallet.balance,
                    "ledger_balance": ledger_balance,
                    "difference": wallet.balance - ledger_balance,
                }
            )

    return mismatches