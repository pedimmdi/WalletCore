import hashlib
import json
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Case, DecimalField, F, Sum, When
from .models import (
    Account,
    IdempotencyKey,
    LedgerEntry,
    Transaction,
    Wallet,
)
from .exceptions import (
    InsufficientBalance,
    InactiveWallet,
    InvalidAmount,
    InvalidIdempotencyKey,
)


def get_or_create_user_wallet(user):
    wallet = (
        Wallet.objects.select_related('account').filter(user=user).first()
    )
    if wallet:
        return wallet

    try:
        with transaction.atomic():
            account = Account.objects.create(
                name=f'Wallet Account - {user.pk}',
                account_type=Account.AccountType.USER,
            )
            wallet = Wallet.objects.create(
                user=user,
                account=account,
            )

    except IntegrityError:
        wallet = (
            Wallet.objects.select_related('account').get(user=user)
        )

    return wallet


def get_system_account():
    account, _ = Account.objects.get_or_create(
        account_type=Account.AccountType.SYSTEM,
        defaults={
            "name": "System Account",
        },
    )

    if not account.is_active:
        raise InactiveWallet(
            "System account is inactive."
        )

    return account


def get_account_balance(account):
    result = account.ledger_entries.aggregate(
        balance=Sum(
            Case(
                When(
                    entry_type=LedgerEntry.EntryType.CREDIT,
                    then=F("amount"),
                ),
                When(
                    entry_type=LedgerEntry.EntryType.DEBIT,
                    then=-F("amount"),
                ),
                default=Decimal("0.00"),
                output_field=DecimalField(
                    max_digits=14,
                    decimal_places=2,
                ),
            )
        )
    )

    return result["balance"] or Decimal("0.00")


def generate_request_hash(data):
    """
    Create a deterministic SHA-256 hash from request data.
    """

    normalized_data = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        normalized_data.encode("utf-8")
    ).hexdigest()


def get_or_create_idempotency_key(key, request_hash):
    """
    Get an existing idempotency key or create a new one.

    If the same key is reused with different request data,
    raise a validation error.
    """

    try:
        with transaction.atomic():
            idempotency_key = (
                IdempotencyKey.objects
                .select_for_update()
                .get(key=key)
            )

            if idempotency_key.request_hash != request_hash:
                raise InvalidIdempotencyKey(
                    "Idempotency-Key was already used with different request data."
                )

            return idempotency_key, False

    except IdempotencyKey.DoesNotExist:
        try:
            with transaction.atomic():
                idempotency_key = IdempotencyKey.objects.create(
                    key=key,
                    request_hash=request_hash,
                )

                return idempotency_key, True

        except IntegrityError:
            # Another concurrent request created the same key.
            idempotency_key = (
                IdempotencyKey.objects
                .select_for_update()
                .get(key=key)
            )

            if idempotency_key.request_hash != request_hash:
                raise InvalidIdempotencyKey(
                    "Idempotency-Key was already used with different request data."
                )

            return idempotency_key, False


def serialize_transaction(transaction):
    """
    Return the response data that is stored for idempotency.
    """

    return {
        "id": str(transaction.id),
        "type": transaction.type,
        "status": transaction.status,
        "amount": str(transaction.amount),
    }


@transaction.atomic
def deposit(user, amount):
    amount = Decimal(amount)

    if amount <= 0:
        raise InvalidAmount(
            "Amount must be positive."
        )

    user_wallet = (
        Wallet.objects
        .select_related("account")
        .select_for_update()
        .get(user=user)
    )

    if not user_wallet.is_active:
        raise InactiveWallet(
            "Wallet is inactive."
        )


    user_account = (
        Account.objects
        .select_for_update()
        .get(pk=user_wallet.account_id)
    )


    system_account = get_system_account()

    system_account = (
        Account.objects
        .select_for_update()
        .get(pk=system_account.pk)
    )


    user_balance = get_account_balance(
        user_account
    )

    system_balance = get_account_balance(
        system_account
    )


    tx = Transaction.objects.create(
        type=Transaction.TransactionType.DEPOSIT,
        status=Transaction.TransactionStatus.COMPLETED,
        amount=amount,
        initiated_by=user,
    )


    LedgerEntry.objects.create(
        account=system_account,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.DEBIT,
        amount=amount,
        balance_after=(
            system_balance - amount
        ),
    )


    LedgerEntry.objects.create(
        account=user_account,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=amount,
        balance_after=(
            user_balance + amount
        ),
    )


    Wallet.objects.filter(
        pk=user_wallet.pk
    ).update(
        balance=user_balance + amount
    )


    return tx


@transaction.atomic
def deposit_idempotent(
    user,
    amount,
    idempotency_key
):

    request_hash = generate_request_hash(
        {
            "operation": "deposit",
            "user_id": user.pk,
            "amount": str(
                Decimal(amount)
            ),
        }
    )


    key, created = (
        get_or_create_idempotency_key(
            idempotency_key,
            request_hash,
        )
    )


    if not created:

        if key.response_body:
            return (
                key.response_body,
                key.status_code,
            )


    tx = deposit(
        user,
        amount,
    )


    response_body = serialize_transaction(
        tx
    )


    key.response_body = response_body
    key.status_code = 201

    key.save(
        update_fields=[
            "response_body",
            "status_code",
        ]
    )


    return (
        response_body,
        201,
    )


@transaction.atomic
def withdraw(user, amount):
    amount = Decimal(amount)

    if amount <= 0:
        raise InvalidAmount("Amount must be positive.")

    user_wallet = (
        Wallet.objects
        .select_related("account")
        .select_for_update()
        .get(user=user)
    )

    if not user_wallet.is_active:
        raise InactiveWallet("Wallet is inactive.")

    user_account = (
        Account.objects
        .select_for_update()
        .get(pk=user_wallet.account_id)
    )

    system_account = (
        Account.objects
        .select_for_update()
        .get(
            account_type=Account.AccountType.SYSTEM,
            is_active=True,
        )
    )

    user_balance = get_account_balance(user_account)

    if user_balance < amount:
        raise InsufficientBalance("Insufficient balance.")

    system_balance = get_account_balance(system_account)

    tx = Transaction.objects.create(
        type=Transaction.TransactionType.WITHDRAW,
        status=Transaction.TransactionStatus.COMPLETED,
        amount=amount,
        initiated_by=user,
    )

    LedgerEntry.objects.create(
        account=user_account,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.DEBIT,
        amount=amount,
        balance_after=user_balance - amount,
    )

    LedgerEntry.objects.create(
        account=system_account,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=amount,
        balance_after=system_balance + amount,
    )

    Wallet.objects.filter(
        pk=user_wallet.pk
    ).update(
        balance=user_balance - amount
    )

    return tx


@transaction.atomic
def transfer(from_user, to_user, amount):
    amount = Decimal(amount)

    if amount <= 0:
        raise InvalidAmount("Amount must be positive.")

    if from_user == to_user:
        raise ValidationError(
            "You can't transfer money to yourself."
        )

    wallets = list(
        Wallet.objects
        .select_related("account")
        .filter(user__in=[from_user, to_user])
        .order_by("pk")
        .select_for_update()
    )

    if len(wallets) != 2:
        raise ValidationError(
            "One or both wallets do not exist."
        )

    wallet_map = {
        wallet.user_id: wallet
        for wallet in wallets
    }

    from_wallet = wallet_map.get(from_user.pk)
    to_wallet = wallet_map.get(to_user.pk)

    if from_wallet is None or to_wallet is None:
        raise ValidationError(
            "One or both wallets do not exist."
        )

    if not from_wallet.is_active:
        raise InactiveWallet(
            "Sender wallet is inactive."
        )

    if not to_wallet.is_active:
        raise InactiveWallet(
            "Receiver wallet is inactive."
        )

    account_ids = sorted(
        [
            from_wallet.account_id,
            to_wallet.account_id,
        ]
    )

    locked_accounts = {
        account.pk: account
        for account in (
            Account.objects
            .select_for_update()
            .filter(pk__in=account_ids)
        )
    }

    from_account = locked_accounts[from_wallet.account_id]
    to_account = locked_accounts[to_wallet.account_id]

    from_balance = get_account_balance(from_account)

    if from_balance < amount:
        raise InsufficientBalance("Insufficient balance.")

    to_balance = get_account_balance(to_account)

    tx = Transaction.objects.create(
        type=Transaction.TransactionType.TRANSFER,
        status=Transaction.TransactionStatus.COMPLETED,
        amount=amount,
        initiated_by=from_user,
    )

    LedgerEntry.objects.create(
        account=from_account,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.DEBIT,
        amount=amount,
        balance_after=from_balance - amount,
    )

    LedgerEntry.objects.create(
        account=to_account,
        transaction=tx,
        entry_type=LedgerEntry.EntryType.CREDIT,
        amount=amount,
        balance_after=to_balance + amount,
    )

    Wallet.objects.filter(
        pk=from_wallet.pk
    ).update(
        balance=from_balance - amount
    )

    Wallet.objects.filter(
        pk=to_wallet.pk
    ).update(
        balance=to_balance + amount
    )

    return tx
