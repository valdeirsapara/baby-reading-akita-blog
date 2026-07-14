# Leitor AkitaOnRails

Um leitor pessoal e rastreador de leitura para o blog [AkitaOnRails.com](https://www.akitaonrails.com).
Ele importa os posts do blog e permite ler tudo em uma interface própria,
acompanhando o que você já leu, está lendo ou ainda vai ler.

## O que o projeto faz

- **Importa os posts do Akita** — sincroniza automaticamente os posts recentes pelo feed RSS e permite
  importar o **arquivo completo** (todos os posts históricos) com um clique no admin.
- **Rastreia sua leitura** — cada post tem um status (*não lido / lendo / lido*) e guarda a posição de
  rolagem, tudo **separado por usuário** (cada conta tem seu próprio histórico).
- **Home enxuta + arquivo completo** — a página inicial mostra só os posts recentes; uma página de
  arquivo lista todos os posts agrupados por ano/mês, com navegação lateral.
- **Destaques** — você marca posts como destaque no admin e eles aparecem em uma seção especial.
- **Vídeos no contexto** — quando o Akita linka vídeos do YouTube, eles são embutidos dentro do post.
- **Autenticação** — todo o leitor exige login; os usuários são criados por você.
- **PWA** — pode ser instalado como aplicativo (service worker + manifest).

Stack: **Django 6 + Vue 3 + Tailwind**, banco via `DATABASE_URL` (SQLite por padrão, PostgreSQL no Docker).

---

## Como rodar

Antes de tudo, copie o arquivo de exemplo de variáveis de ambiente:

```bash
cp .env.example .env
```

Edite o `.env` e defina ao menos uma `SECRET_KEY`. Para gerar uma:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

### Opção A — Docker (recomendado)

Sobe o app + PostgreSQL, roda as migrações automaticamente e coleta os arquivos estáticos.

```bash
docker compose up --build
```

Depois, em outro terminal, crie seu usuário de acesso:

```bash
docker compose exec web python manage.py createsuperuser
```

Acesse **http://localhost:8000** e faça login.

> Para parar: `docker compose down` (os dados do banco ficam salvos no volume `pgdata`).

### Opção B — Local com uv

Requer [uv](https://docs.astral.sh/uv/) instalado. Usa SQLite por padrão (não precisa de `DATABASE_URL`).

```bash
# Instala as dependências
uv sync

# Prepara o banco
uv run python manage.py migrate

# Cria seu usuário de acesso
uv run python manage.py createsuperuser

# Sobe o servidor de desenvolvimento
uv run python manage.py runserver
```

Acesse **http://127.0.0.1:8000** e faça login.

---

## Primeiro uso

1. Faça login com o usuário criado.
2. Os posts recentes são sincronizados sozinhos ao abrir a home.
3. Para trazer **todos** os posts antigos: entre no admin (`/admin/`), vá em **Posts** e clique em
   **"Importar arquivo completo (AkitaOnRails)"**. A importação roda em segundo plano.
4. Para destacar posts, marque o campo **destaque** deles no admin.

---

## Variáveis de ambiente

Todas ficam no `.env` (veja `.env.example`):

| Variável | Descrição | Padrão |
|---|---|---|
| `SECRET_KEY` | Chave secreta do Django | *(defina a sua)* |
| `DEBUG` | Modo debug | `False` |
| `ALLOWED_HOSTS` | Hosts permitidos (separados por vírgula) | `localhost,127.0.0.1` |
| `DATABASE_URL` | Banco via URL (`postgres://…` ou `sqlite:///…`) | SQLite local |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Credenciais do Postgres no Docker | `akita` |
