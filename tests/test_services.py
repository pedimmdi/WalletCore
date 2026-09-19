import pytest
from decimal import Decimal
from wallet.services import deposit, deposit_idempotent
from wallet.models import Transaction, LedgerEntry, IdempotencyKey
from tests.factories import WalletFactory, SystemAccountFactory


@pytest.mark.django_db
def test_successful_deposit():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()
    amount = Decimal("100.00")

    tx = deposit(wallet.user, amount)

    assert tx.type == Transaction.TransactionType.DEPOSIT
    assert tx.status == Transaction.TransactionStatus.COMPLETED
    assert tx.amount == amount

    wallet.refresh_from_db()
    assert wallet.balance == Decimal("100.00")
    assert LedgerEntry.objects.filter(transaction=tx).count() == 2


@pytest.mark.django_db
def test_deposit_idempotent_only_one_transaction():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()
    amount = Decimal("100.00")
    idem_key = "unique-key-123"

    body1, status1 = deposit_idempotent(wallet.user, amount, idem_key)
    body2, status2 = deposit_idempotent(wallet.user, amount, idem_key)

    assert status1 == 201
    assert status2 == 201
    assert body1 == body2

    assert Transaction.objects.count() == 1
    assert IdempotencyKey.objects.filter(key=idem_key).count() == 1

    wallet.refresh_from_db()
    assert wallet.balance == Decimal("100.00")
