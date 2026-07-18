from django.core.management.base import BaseCommand, CommandError

from reader.importer import import_archive


class Command(BaseCommand):
    help = (
        "Importa todos os posts do arquivo do AkitaOnRails. "
        "O comando pode ser executado novamente: posts já existentes são ignorados."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Quantidade máxima de novos posts a importar (0 = todos).",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Intervalo, em segundos, entre requisições (padrão: 0.5).",
        )
        parser.add_argument(
            "--skip-content",
            action="store_true",
            help="Importa somente metadados, sem baixar o conteúdo dos posts.",
        )
        parser.add_argument(
            "--skip-videos",
            action="store_true",
            help="Não procura vídeos do YouTube depois da importação.",
        )

    def handle(self, *args, **options):
        if options["limit"] < 0:
            raise CommandError("--limit não pode ser negativo.")
        if options["delay"] < 0:
            raise CommandError("--delay não pode ser negativo.")

        self.stdout.write("Iniciando importação completa do AkitaOnRails...")
        try:
            created = import_archive(
                limit=options["limit"],
                delay=options["delay"],
                skip_content=options["skip_content"],
                extract_videos=not options["skip_videos"],
                logger=self.stdout.write,
            )
        except Exception as exc:
            raise CommandError(f"A importação falhou: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Importação concluída: {created} novo(s) post(s) importado(s)."
            )
        )
