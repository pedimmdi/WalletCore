from django.core.cache import cache


WALLET_CACHE_TTL = 60


def get_wallet_cache_key(user_id):
    return f"wallet:me:{user_id}"


def get_wallet_cache(user_id):
    return cache.get(get_wallet_cache_key(user_id))


def set_wallet_cache(user_id, data):
    cache.set(
        get_wallet_cache_key(user_id),
        data,
        timeout=WALLET_CACHE_TTL,
    )


def delete_wallet_cache(user_id):
    cache.delete(get_wallet_cache_key(user_id))