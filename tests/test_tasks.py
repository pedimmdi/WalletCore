from decimal import Decimal

import pytest

from tests.factories import SystemAccountFactory, WalletFactory
from wallet.services import deposit
from wallet.tasks import daily_reconciliation, notify_transaction


@pytest.mark.django_db
def test_notify_transaction_task():
    result = notify_transaction.delay("test-transaction-id")

    assert result.id is not None


@pytest.mark.django_db
def test_daily_reconciliation_task():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(wallet.user, Decimal("100.00"))

    result = daily_reconciliation.apply()

    assert result.get() == {"mismatches": 0}
