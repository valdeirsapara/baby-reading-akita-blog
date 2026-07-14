#!/bin/sh
set -e

# Aguarda o banco e aplica as migrações (resiliente a DB ainda subindo)
echo "==> Aplicando migrações do banco de dados..."
until python manage.py migrate --noinput; do
    echo "    Banco indisponível ou falhou; tentando novamente em 2s..."
    sleep 2
done

# Coleta os arquivos estáticos (servidos pelo WhiteNoise)
echo "==> Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "==> Iniciando processo: $*"
exec "$@"
