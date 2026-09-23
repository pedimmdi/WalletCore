from django.urls import path

from .views import (
    DepositView,
    WalletView,
    WithdrawView,
    TransferView,
    TransactionListView,
)

urlpatterns = [
    path("me/", WalletView.as_view(), name="wallet-me"),
    path("deposit/", DepositView.as_view(), name="deposit"),
    path("withdraw/", WithdrawView.as_view(), name="withdraw"),
    path("transfer/", TransferView.as_view(), name="transfer"),
    path("transactions/", TransactionListView.as_view(), name="transaction-list"),
]
