from decimal import Decimal

import pytest
from django.db.models import Sum
from rest_framework.test import APIClient

from tests.factories import SystemAccountFactory, WalletFactory
from wallet.models import IdempotencyKey, LedgerEntry, Transaction
from wallet.services import deposit, deposit_idempotent
from wallet.exceptions import InvalidIdempotencyKey


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

    debit_total = (
        LedgerEntry.objects
        .filter(
            transaction=tx,
            entry_type=LedgerEntry.EntryType.DEBIT,
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    credit_total = (
        LedgerEntry.objects
        .filter(
            transaction=tx,
            entry_type=LedgerEntry.EntryType.CREDIT,
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    assert debit_total == credit_total == amount


@pytest.mark.django_db
def test_deposit_updates_user_and_system_ledger_balances():
    wallet = WalletFactory(balance=Decimal("0.00"))
    system_account = SystemAccountFactory()

    amount = Decimal("100.00")

    tx = deposit(wallet.user, amount)

    user_entry = LedgerEntry.objects.get(
        transaction=tx,
        account=wallet.account,
    )

    system_entry = LedgerEntry.objects.get(
        transaction=tx,
        account=system_account,
    )

    assert user_entry.entry_type == LedgerEntry.EntryType.CREDIT
    assert system_entry.entry_type == LedgerEntry.EntryType.DEBIT

    assert user_entry.amount == amount
    assert system_entry.amount == amount

    assert user_entry.balance_after == Decimal("100.00")
    assert system_entry.balance_after == Decimal("-100.00")


@pytest.mark.django_db
def test_deposit_idempotent_returns_same_response_for_same_request():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    amount = Decimal("100.00")
    idem_key = "unique-key-123"

    body1, status1 = deposit_idempotent(
        wallet.user,
        amount,
        idem_key,
    )

    body2, status2 = deposit_idempotent(
        wallet.user,
        amount,
        idem_key,
    )

    assert status1 == 201
    assert status2 == 201

    assert body1 == body2

    assert Transaction.objects.count() == 1

    assert IdempotencyKey.objects.filter(
        key=idem_key
    ).count() == 1

    assert LedgerEntry.objects.count() == 2

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("100.00")


@pytest.mark.django_db
def test_deposit_idempotency_rejects_different_request():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    idem_key = "same-key"

    body1, status1 = deposit_idempotent(
        wallet.user,
        Decimal("100.00"),
        idem_key,
    )

    assert status1 == 201

    with pytest.raises(InvalidIdempotencyKey):
        deposit_idempotent(
            wallet.user,
            Decimal("200.00"),
            idem_key,
        )

    assert Transaction.objects.count() == 1

    assert IdempotencyKey.objects.filter(
        key=idem_key
    ).count() == 1

    assert LedgerEntry.objects.count() == 2

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("100.00")


@pytest.mark.django_db
def test_deposit_api():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    client = APIClient()

    client.force_authenticate(user=wallet.user)

    response = client.post(
        "/api/wallet/deposit/",
        {
            "amount": "100.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-deposit-123",
    )

    assert response.status_code == 201

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("100.00")

    assert Transaction.objects.count() == 1
    assert LedgerEntry.objects.count() == 2

    tx = Transaction.objects.first()

    assert tx.type == Transaction.TransactionType.DEPOSIT
    assert tx.status == Transaction.TransactionStatus.COMPLETED
    assert tx.amount == Decimal("100.00")


@pytest.mark.django_db
def test_deposit_api_is_idempotent():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    client = APIClient()

    client.force_authenticate(user=wallet.user)

    response1 = client.post(
        "/api/wallet/deposit/",
        {
            "amount": "100.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-idempotent-123",
    )

    response2 = client.post(
        "/api/wallet/deposit/",
        {
            "amount": "100.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-idempotent-123",
    )

    assert response1.status_code == 201
    assert response2.status_code == 201

    assert response1.data == response2.data

    assert Transaction.objects.count() == 1
    assert LedgerEntry.objects.count() == 2

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("100.00")
