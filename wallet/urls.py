from django.urls import path

from .views import (
    DepositView,
    WalletView,
    WithdrawView,
)

urlpatterns = [
    path("me/", WalletView.as_view(), name="wallet-me"),
    path("deposit/", DepositView.as_view(), name="deposit"),
    path("withdraw/", WithdrawView.as_view(), name="withdraw"),
]
