import pytest
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APIClient
from django.core.cache import cache
from tests.factories import UserFactory, WalletFactory, SystemAccountFactory
from wallet.models import LedgerEntry, Transaction
from wallet.services import deposit, transfer


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def wallet(user):
    return WalletFactory(user=user)


@pytest.fixture
def system_account():
    return SystemAccountFactory()


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
def test_transaction_history_returns_user_transactions(
    authenticated_client,
    wallet,
    system_account,
):
    deposit(wallet.user, Decimal("100.00"))

    response = authenticated_client.get(
        reverse("transaction-list")
    )

    assert response.status_code == 200
    assert response.data["count"] == 1

    transaction = response.data["results"][0]

    assert transaction["type"] == "deposit"
    assert transaction["status"] == "completed"
    assert transaction["amount"] == "100.00"


@pytest.mark.django_db
def test_transaction_history_does_not_return_other_users_transactions(
    api_client,
    wallet,
    system_account,
):
    other_wallet = WalletFactory()

    deposit(wallet.user, Decimal("100.00"))
    deposit(other_wallet.user, Decimal("200.00"))

    api_client.force_authenticate(user=wallet.user)

    response = api_client.get(
        reverse("transaction-list")
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["amount"] == "100.00"


@pytest.mark.django_db
def test_transaction_history_filters_by_type(
    authenticated_client,
    wallet,
    system_account,
):
    deposit(wallet.user, Decimal("100.00"))

    from wallet.services import withdraw

    withdraw(wallet.user, Decimal("40.00"))

    response = authenticated_client.get(
        reverse("transaction-list"),
        {"type": "deposit"},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1

    assert response.data["results"][0]["type"] == "deposit"


@pytest.mark.django_db
def test_transaction_history_filters_by_status(
    authenticated_client,
    wallet,
    system_account,
):
    deposit(wallet.user, Decimal("100.00"))

    response = authenticated_client.get(
        reverse("transaction-list"),
        {"status": "completed"},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1

    assert response.data["results"][0]["status"] == "completed"


@pytest.mark.django_db
def test_transaction_history_filters_by_type_and_status(
    authenticated_client,
    wallet,
    system_account,
):
    deposit(wallet.user, Decimal("100.00"))

    response = authenticated_client.get(
        reverse("transaction-list"),
        {
            "type": "deposit",
            "status": "completed",
        },
    )

    assert response.status_code == 200
    assert response.data["count"] == 1

    transaction = response.data["results"][0]

    assert transaction["type"] == "deposit"
    assert transaction["status"] == "completed"


@pytest.mark.django_db
def test_transaction_history_is_paginated(
    authenticated_client,
    wallet,
    system_account,
):
    for _ in range(11):
        deposit(wallet.user, Decimal("10.00"))

    response = authenticated_client.get(
        reverse("transaction-list")
    )

    assert response.status_code == 200
    assert response.data["count"] == 11
    assert len(response.data["results"]) == 10
    assert response.data["next"] is not None

    response = authenticated_client.get(
        reverse("transaction-list"),
        {"page": 2},
    )

    assert response.status_code == 200
    assert len(response.data["results"]) == 1
    assert response.data["previous"] is not None


@pytest.mark.django_db
def test_transaction_history_is_ordered_newest_first(
    authenticated_client,
    wallet,
    system_account,
):
    first_transaction = deposit(
        wallet.user,
        Decimal("100.00"),
    )

    second_transaction = deposit(
        wallet.user,
        Decimal("50.00"),
    )

    response = authenticated_client.get(
        reverse("transaction-list")
    )

    assert response.status_code == 200
    assert response.data["count"] == 2

    results = response.data["results"]

    assert results[0]["id"] == str(second_transaction.id)
    assert results[1]["id"] == str(first_transaction.id)


@pytest.mark.django_db
def test_transaction_history_requires_authentication(api_client):
    response = api_client.get(
        reverse("transaction-list")
    )

    assert response.status_code == 401


@pytest.mark.django_db
def test_transaction_history_includes_transfer(
    authenticated_client,
    wallet,
    system_account,
):
    receiver_wallet = WalletFactory()

    deposit(wallet.user, Decimal("100.00"))

    transfer(
        wallet.user,
        receiver_wallet.user,
        Decimal("40.00"),
    )

    response = authenticated_client.get(
        reverse("transaction-list"),
        {"type": "transfer"},
    )

    assert response.status_code == 200
    assert response.data["count"] == 1

    transaction = response.data["results"][0]

    assert transaction["type"] == "transfer"
    assert transaction["status"] == "completed"
    assert transaction["amount"] == "40.00"


@pytest.mark.django_db
def test_admin_wallet_list_requires_staff(api_client):
    user = UserFactory(is_staff=False)
    api_client.force_authenticate(user=user)

    response = api_client.get(reverse("admin-wallet-list"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_wallet_list_for_staff(api_client):
    staff = UserFactory(is_staff=True)
    WalletFactory()

    api_client.force_authenticate(user=staff)

    response = api_client.get(reverse("admin-wallet-list"))

    assert response.status_code == 200
    assert len(response.data) == 1


@pytest.mark.django_db
def test_admin_wallet_freeze_requires_staff(api_client):
    user = UserFactory(is_staff=False)
    wallet = WalletFactory()

    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("admin-wallet-freeze", kwargs={"pk": wallet.pk})
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_wallet_freeze_for_staff(api_client):
    staff = UserFactory(is_staff=True)
    wallet = WalletFactory(is_active=True)

    api_client.force_authenticate(user=staff)

    response = api_client.post(
        reverse("admin-wallet-freeze", kwargs={"pk": wallet.pk})
    )

    assert response.status_code == 200

    wallet.refresh_from_db()

    assert wallet.is_active is False
    assert response.data["is_active"] is False


@pytest.mark.django_db
def test_wallet_me_uses_cache():
    client = APIClient()
    user = UserFactory()

    client.force_authenticate(user=user)

    response = client.get(reverse("wallet-me"))

    assert response.status_code == 200

    cached_data = cache.get(f"wallet:me:{user.pk}")

    assert cached_data == response.data


@pytest.mark.django_db(transaction=True)
def test_wallet_cache_is_invalidated_after_deposit():
    client = APIClient()
    user = UserFactory()

    client.force_authenticate(user=user)

    response = client.get(reverse("wallet-me"))

    assert response.status_code == 200
    assert cache.get(f"wallet:me:{user.pk}") is not None

    response = client.post(
        reverse("deposit"),
        {"amount": "100.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="stage18-test-deposit-001",
    )

    assert response.status_code == 201

    assert cache.get(f"wallet:me:{user.pk}") is None


@pytest.mark.django_db(transaction=True)
def test_wallet_cache_is_invalidated_after_withdraw():
    client = APIClient()
    wallet = WalletFactory()
    user = wallet.user

    client.force_authenticate(user=user)

    client.post(
        reverse("deposit"),
        {"amount": "100.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="stage18-withdraw-deposit-001",
    )

    response = client.get(reverse("wallet-me"))

    assert response.status_code == 200
    assert cache.get(f"wallet:me:{user.pk}") is not None

    response = client.post(
        reverse("withdraw"),
        {"amount": "30.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="stage18-withdraw-001",
    )

    assert response.status_code == 201

    assert cache.get(f"wallet:me:{user.pk}") is None


@pytest.mark.django_db(transaction=True)
def test_wallet_cache_is_invalidated_after_transfer():
    client = APIClient()

    sender_wallet = WalletFactory()
    receiver_wallet = WalletFactory()

    sender = sender_wallet.user
    receiver = receiver_wallet.user

    client.force_authenticate(user=sender)

    client.post(
        reverse("deposit"),
        {"amount": "100.00"},
        format="json",
        HTTP_IDEMPOTENCY_KEY="stage18-transfer-deposit-001",
    )

    client.get(reverse("wallet-me"))

    client.force_authenticate(user=receiver)
    client.get(reverse("wallet-me"))

    assert cache.get(f"wallet:me:{sender.pk}") is not None
    assert cache.get(f"wallet:me:{receiver.pk}") is not None

    client.force_authenticate(user=sender)

    response = client.post(
        reverse("transfer"),
        {
            "to_user_id": receiver.pk,
            "amount": "20.00",
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY="stage18-transfer-001",
    )

    assert response.status_code == 201

    assert cache.get(f"wallet:me:{sender.pk}") is None
    assert cache.get(f"wallet:me:{receiver.pk}") is None