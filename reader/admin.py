import threading

from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path

from .models import Post, ReadingProgress, YouTubeVideo
from .importer import import_archive

# Evita disparar duas importações simultâneas
_import_lock = threading.Lock()


def _run_import_in_background():
    if not _import_lock.acquire(blocking=False):
        return False

    def _worker():
        try:
            import_archive(logger=lambda msg: print(f"[import_archive] {msg}"))
        finally:
            _import_lock.release()

    threading.Thread(target=_worker, daemon=True).start()
    return True


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    change_list_template = "admin/reader/post/change_list.html"
    list_display = ('title', 'published_at', 'featured', 'slug')
    list_editable = ('featured',)
    list_filter = ('featured',)
    search_fields = ('title', 'summary')
    date_hierarchy = 'published_at'
    ordering = ('-published_at',)
    actions = ('marcar_destaque', 'remover_destaque')

    @admin.action(description="Marcar como destaque")
    def marcar_destaque(self, request, queryset):
        updated = queryset.update(featured=True)
        self.message_user(request, f"{updated} post(s) marcados como destaque.")

    @admin.action(description="Remover destaque")
    def remover_destaque(self, request, queryset):
        updated = queryset.update(featured=False)
        self.message_user(request, f"{updated} post(s) removidos dos destaques.")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('importar-arquivo/', self.admin_site.admin_view(self.import_archive_view),
                 name='reader_post_import_archive'),
        ]
        return custom + urls

    def import_archive_view(self, request):
        started = _run_import_in_background()
        if started:
            self.message_user(
                request,
                "Importação do arquivo completo do AkitaOnRails iniciada em segundo plano. "
                "Os posts aparecerão aqui conforme forem importados (atualize a página).",
                level=messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "Já existe uma importação em andamento. Aguarde a conclusão.",
                level=messages.WARNING,
            )
        return redirect('admin:reader_post_changelist')


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ('post', 'status', 'scroll_position', 'last_read_at')
    list_filter = ('status',)


@admin.register(YouTubeVideo)
class YouTubeVideoAdmin(admin.ModelAdmin):
    list_display = ('title', 'youtube_id', 'post', 'added_at')
    search_fields = ('title', 'youtube_id')
