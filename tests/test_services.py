from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.db import close_old_connections
from rest_framework.test import APIClient

from tests.factories import SystemAccountFactory, WalletFactory
from wallet.exceptions import InsufficientFunds, InvalidIdempotencyKey
from wallet.models import IdempotencyKey, LedgerEntry, Transaction
from wallet.services import (
    deposit,
    deposit_idempotent,
    withdraw,
    withdraw_idempotent,
    transfer,
)


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


# ------------------------------------------------------------------
# Withdraw tests
# ------------------------------------------------------------------


@pytest.mark.django_db
def test_successful_withdraw():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(wallet.user, Decimal("100.00"))

    amount = Decimal("40.00")

    tx = withdraw(wallet.user, amount)

    assert tx.type == Transaction.TransactionType.WITHDRAW
    assert tx.status == Transaction.TransactionStatus.COMPLETED
    assert tx.amount == amount

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("60.00")

    assert LedgerEntry.objects.filter(
        transaction=tx
    ).count() == 2


@pytest.mark.django_db
def test_withdraw_updates_user_and_system_ledger_balances():
    wallet = WalletFactory(balance=Decimal("0.00"))
    system_account = SystemAccountFactory()

    deposit(wallet.user, Decimal("100.00"))

    amount = Decimal("40.00")

    tx = withdraw(wallet.user, amount)

    user_entry = LedgerEntry.objects.get(
        transaction=tx,
        account=wallet.account,
    )

    system_entry = LedgerEntry.objects.get(
        transaction=tx,
        account=system_account,
    )

    assert user_entry.entry_type == LedgerEntry.EntryType.DEBIT
    assert system_entry.entry_type == LedgerEntry.EntryType.CREDIT

    assert user_entry.amount == amount
    assert system_entry.amount == amount

    assert user_entry.balance_after == Decimal("60.00")
    assert system_entry.balance_after == Decimal("-60.00")


@pytest.mark.django_db
def test_withdraw_preserves_double_entry_invariant():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(wallet.user, Decimal("100.00"))

    amount = Decimal("40.00")

    tx = withdraw(wallet.user, amount)

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
def test_withdraw_rejects_insufficient_funds():
    wallet = WalletFactory(balance=Decimal("100.00"))
    SystemAccountFactory()

    with pytest.raises(InsufficientFunds):
        withdraw(
            wallet.user,
            Decimal("150.00"),
        )

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("100.00")

    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0


@pytest.mark.django_db
def test_withdraw_idempotent_returns_same_response_for_same_request():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(wallet.user, Decimal("100.00"))

    amount = Decimal("40.00")
    idem_key = "withdraw-idempotent-123"

    body1, status1 = withdraw_idempotent(
        wallet.user,
        amount,
        idem_key,
    )

    body2, status2 = withdraw_idempotent(
        wallet.user,
        amount,
        idem_key,
    )

    assert status1 == 201
    assert status2 == 201

    assert body1 == body2

    assert Transaction.objects.filter(
        type=Transaction.TransactionType.WITHDRAW
    ).count() == 1
    assert LedgerEntry.objects.filter(
        transaction__type=Transaction.TransactionType.WITHDRAW
    ).count() == 2

    assert IdempotencyKey.objects.filter(
        key=idem_key
    ).count() == 1

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("60.00")


@pytest.mark.django_db
def test_withdraw_idempotency_rejects_different_request():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(wallet.user, Decimal("100.00"))

    idem_key = "withdraw-same-key"

    body1, status1 = withdraw_idempotent(
        wallet.user,
        Decimal("40.00"),
        idem_key,
    )

    assert status1 == 201

    with pytest.raises(InvalidIdempotencyKey):
        withdraw_idempotent(
            wallet.user,
            Decimal("50.00"),
            idem_key,
        )

    assert body1["type"] == Transaction.TransactionType.WITHDRAW

    assert Transaction.objects.filter(
        type=Transaction.TransactionType.WITHDRAW
    ).count() == 1
    assert LedgerEntry.objects.filter(
        transaction__type=Transaction.TransactionType.WITHDRAW
    ).count() == 2

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("60.00")


@pytest.mark.django_db
def test_withdraw_api():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(wallet.user, Decimal("100.00"))

    client = APIClient()

    client.force_authenticate(user=wallet.user)

    response = client.post(
        "/api/wallet/withdraw/",
        {
            "amount": "40.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-withdraw-123",
    )

    assert response.status_code == 201

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("60.00")

    assert Transaction.objects.filter(
        type=Transaction.TransactionType.WITHDRAW
    ).count() == 1
    assert LedgerEntry.objects.filter(
        transaction__type=Transaction.TransactionType.WITHDRAW
    ).count() == 2

    tx = Transaction.objects.first()

    assert tx.type == Transaction.TransactionType.WITHDRAW
    assert tx.status == Transaction.TransactionStatus.COMPLETED
    assert tx.amount == Decimal("40.00")


@pytest.mark.django_db
def test_withdraw_api_rejects_insufficient_funds():
    wallet = WalletFactory(balance=Decimal("100.00"))
    SystemAccountFactory()

    client = APIClient()

    client.force_authenticate(user=wallet.user)

    response = client.post(
        "/api/wallet/withdraw/",
        {
            "amount": "150.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="api-withdraw-insufficient-123",
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Insufficient funds."

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("100.00")

    assert Transaction.objects.count() == 0
    assert LedgerEntry.objects.count() == 0


# ------------------------------------------------------------------
# Transfer tests
# ------------------------------------------------------------------


@pytest.mark.django_db
def test_successful_transfer():
    sender_wallet = WalletFactory(balance=Decimal("0.00"))
    receiver_wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(
        sender_wallet.user,
        Decimal("100.00"),
    )

    amount = Decimal("40.00")

    tx = transfer(
        sender_wallet.user,
        receiver_wallet.user,
        amount,
    )

    assert tx.type == Transaction.TransactionType.TRANSFER
    assert tx.status == Transaction.TransactionStatus.COMPLETED
    assert tx.amount == amount
    assert tx.initiated_by == sender_wallet.user

    sender_wallet.refresh_from_db()
    receiver_wallet.refresh_from_db()

    assert sender_wallet.balance == Decimal("60.00")
    assert receiver_wallet.balance == Decimal("40.00")

    assert LedgerEntry.objects.filter(
        transaction=tx
    ).count() == 2


@pytest.mark.django_db
def test_transfer_creates_debit_and_credit_entries():
    sender_wallet = WalletFactory(balance=Decimal("0.00"))
    receiver_wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(
        sender_wallet.user,
        Decimal("100.00"),
    )

    amount = Decimal("40.00")

    tx = transfer(
        sender_wallet.user,
        receiver_wallet.user,
        amount,
    )

    sender_entry = LedgerEntry.objects.get(
        transaction=tx,
        account=sender_wallet.account,
    )

    receiver_entry = LedgerEntry.objects.get(
        transaction=tx,
        account=receiver_wallet.account,
    )

    assert sender_entry.entry_type == LedgerEntry.EntryType.DEBIT
    assert receiver_entry.entry_type == LedgerEntry.EntryType.CREDIT

    assert sender_entry.amount == amount
    assert receiver_entry.amount == amount

    assert sender_entry.balance_after == Decimal("60.00")
    assert receiver_entry.balance_after == Decimal("40.00")


@pytest.mark.django_db
def test_transfer_preserves_double_entry_invariant():
    sender_wallet = WalletFactory(balance=Decimal("0.00"))
    receiver_wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(
        sender_wallet.user,
        Decimal("100.00"),
    )

    amount = Decimal("40.00")

    tx = transfer(
        sender_wallet.user,
        receiver_wallet.user,
        amount,
    )

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
def test_transfer_rejects_insufficient_funds():
    sender_wallet = WalletFactory(balance=Decimal("0.00"))
    receiver_wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(
        sender_wallet.user,
        Decimal("100.00"),
    )

    with pytest.raises(InsufficientFunds):
        transfer(
            sender_wallet.user,
            receiver_wallet.user,
            Decimal("150.00"),
        )

    sender_wallet.refresh_from_db()
    receiver_wallet.refresh_from_db()

    assert sender_wallet.balance == Decimal("100.00")
    assert receiver_wallet.balance == Decimal("0.00")

    assert Transaction.objects.filter(
        type=Transaction.TransactionType.TRANSFER
    ).count() == 0

    assert LedgerEntry.objects.filter(
        transaction__type=Transaction.TransactionType.TRANSFER
    ).count() == 0


@pytest.mark.django_db
def test_transfer_rejects_self_transfer():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(
        wallet.user,
        Decimal("100.00"),
    )

    with pytest.raises(ValidationError):
        transfer(
            wallet.user,
            wallet.user,
            Decimal("40.00"),
        )

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("100.00")

    assert Transaction.objects.filter(
        type=Transaction.TransactionType.TRANSFER
    ).count() == 0

    assert LedgerEntry.objects.filter(
        transaction__type=Transaction.TransactionType.TRANSFER
    ).count() == 0


@pytest.mark.django_db(transaction=True)
def test_concurrent_withdraw_allows_only_one_success():
    wallet = WalletFactory(balance=Decimal("0.00"))
    SystemAccountFactory()

    deposit(wallet.user, Decimal("100.00"))

    def perform_withdraw():
        close_old_connections()

        try:
            withdraw(wallet.user, Decimal("70.00"))
            return "success"
        except InsufficientFunds:
            return "insufficient_funds"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda _: perform_withdraw(),
                range(2),
            )
        )

    assert results.count("success") == 1
    assert results.count("insufficient_funds") == 1

    wallet.refresh_from_db()

    assert wallet.balance == Decimal("30.00")

    assert Transaction.objects.filter(
        type=Transaction.TransactionType.WITHDRAW,
        status=Transaction.TransactionStatus.COMPLETED,
    ).count() == 1

    assert LedgerEntry.objects.filter(
        transaction__type=Transaction.TransactionType.WITHDRAW,
    ).count() == 2