from django.contrib.auth import get_user_model
from .models import Wallet, Transaction, LedgerEntry
from django.db import transaction
from decimal import Decimal
from django.core.exceptions import ValidationError


def get_system_wallet():
    User = get_user_model()
    user = User.objects.get(username="__system__")
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


@transaction.atomic
def deposit(user, amount):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError('The amount must be positive')

    # Locking both wallets
    system_wallet = Wallet.objects.select_for_update().get(
        pk=get_system_wallet().pk
    )
    user_wallet = Wallet.objects.select_for_update().get(
        pk=Wallet.objects.get(user=user).pk
    )

    # Transaction creation
    tx = Transaction.objects.create(
        user=user,
        type=Transaction.TransactionType.DEPOSIT,
        status=Transaction.TransactionStatus.COMPLETED,
        amount=amount,
    )

    # System side: debit
    system_wallet.balance -= amount
    system_wallet.save()
    LedgerEntry.objects.create(
        wallet=system_wallet,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.DEBIT,
        amount=amount,
        balance_after=system_wallet.balance,
    )

    # User side: credit
    user_wallet.balance += amount
    user_wallet.save()
    LedgerEntry.objects.create(
        wallet=user_wallet,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=amount,
        balance_after=user_wallet.balance,
    )

    return tx


@transaction.atomic
def withdraw(user, amount):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError('The amount must be positive')

    # Locking both wallets
    system_wallet = Wallet.objects.select_for_update().get(
        pk=get_system_wallet().pk
    )
    user_wallet = Wallet.objects.select_for_update().get(
        pk=Wallet.objects.get(user=user).pk
    )
    # Check the balance inside the lock
    if user_wallet.balance < amount:
        raise ValidationError('Insufficient balance')

    # Transaction creation
    tx = Transaction.objects.create(
        user=user,
        type=Transaction.TransactionType.WITHDRAW,
        status=Transaction.TransactionStatus.COMPLETED,
        amount=amount,
    )

    # User side: debit
    user_wallet.balance -= amount
    user_wallet.save()
    LedgerEntry.objects.create(
        wallet=user_wallet,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.DEBIT,
        amount=amount,
        balance_after=user_wallet.balance,
    )

    # System side: credit
    system_wallet.balance += amount
    system_wallet.save()
    LedgerEntry.objects.create(
        wallet=system_wallet,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=amount,
        balance_after=system_wallet.balance,
    )

    return tx


@transaction.atomic
def transfer(from_user, to_user, amount):
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError('The amount must be positive')
    if from_user == to_user:
        raise ValidationError("You can't transfer it to yourself")

    from_wallet = Wallet.objects.get(user=from_user)
    to_wallet = Wallet.objects.get(user=to_user)

    # Locking both wallets(By id order to prevent deadlocks)
    if from_wallet.pk < to_wallet.pk:
        first = Wallet.objects.select_for_update().get(pk=from_wallet.pk)
        second = Wallet.objects.select_for_update().get(pk=to_wallet.pk)
        from_wallet, to_wallet = first, second
    else:
        first = Wallet.objects.select_for_update().get(pk=to_wallet.pk)
        second = Wallet.objects.select_for_update().get(pk=from_wallet.pk)
        to_wallet, from_wallet = first, second

    # Check the balance inside the lock
    if from_wallet.balance < amount:
        raise ValidationError('Insufficient balance')

    # Transaction creation
    tx = Transaction.objects.create(
        user=from_user,
        type=Transaction.TransactionType.TRANSFER,
        status=Transaction.TransactionStatus.COMPLETED,
        amount=amount,
    )

    # from_wallet: debit
    from_wallet.balance -= amount
    from_wallet.save()
    LedgerEntry.objects.create(
        wallet=from_wallet,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.DEBIT,
        amount=amount,
        balance_after=from_wallet.balance,
    )

    # to_wallet: credit
    to_wallet.balance += amount
    to_wallet.save()
    LedgerEntry.objects.create(
        wallet=to_wallet,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=amount,
        balance_after=to_wallet.balance,
    )

    return tx
