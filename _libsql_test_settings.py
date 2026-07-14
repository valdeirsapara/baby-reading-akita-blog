from config.settings import *  # noqa

# Exercita o backend libSQL com um arquivo local (sem precisar de Turso remoto)
DATABASES = {
    'default': {
        'ENGINE': 'libsql.db.backends.sqlite3',
        'NAME': 'file:' + str(BASE_DIR / 'scratch' / 'libsql_test.db'),  # noqa: F405
    }
}
