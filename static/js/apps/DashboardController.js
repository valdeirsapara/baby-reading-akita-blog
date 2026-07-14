registerController('DashboardController', (Vue) => {
    const { ref, computed, onMounted, watch } = Vue;

    const posts = ref([]);
    const loading = ref(false);
    const syncing = ref(false);
    const currentTab = ref('queue'); // 'queue' | 'read' | 'all'
    const searchQuery = ref('');
    const RECENT_MONTHS = 3; // a home mostra só os posts dos últimos meses; o resto vai pro /arquivo
    const showHighlights = ref(false); // seção "Destaques" começa recolhida, como no Akita

    // Data de corte: posts mais antigos que isso só aparecem na página de arquivo completo
    const recentCutoff = computed(() => {
        const d = new Date();
        d.setMonth(d.getMonth() - RECENT_MONTHS);
        return d;
    });

    // Fetch posts list from API
    const fetchPosts = async () => {
        loading.value = true;
        try {
            const data = await api('/posts/');
            posts.value = data;
            setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 50);
        } catch (e) {
            console.error('Erro ao buscar posts:', e);
        } finally {
            loading.value = false;
        }
    };

    // Trigger RSS feed synchronization silently in background
    const syncFeed = async () => {
        if (syncing.value) return;
        syncing.value = true;
        try {
            const res = await api('/sync-feed/', { method: 'POST' });
            if (res.success && res.new_posts_count > 0) {
                await fetchPosts();
            }
        } catch (e) {
            console.error('Erro na sincronização silenciosa em background:', e);
        } finally {
            syncing.value = false;
        }
    };


    // Toggle reading state between read / unread
    const toggleReadStatus = async (post) => {
        const nextStatus = post.status === 'read' ? 'unread' : 'read';
        const initialStatus = post.status;
        
        // Optimistic UI update
        post.status = nextStatus;
        if (nextStatus === 'read') {
            post.scroll_position = 100;
        } else {
            post.scroll_position = 0;
        }
        setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 50);

        try {
            const res = await api('/update-progress/', {
                method: 'POST',
                body: {
                    post_id: post.id,
                    status: nextStatus,
                    scroll_position: post.scroll_position
                }
            });
            if (!res.success) {
                // Revert on failure
                post.status = initialStatus;
                setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 50);
                alert('Falha ao atualizar o status no servidor.');
            }
        } catch (e) {
            console.error('Erro ao atualizar status:', e);
            post.status = initialStatus;
            setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 50);
        }
    };

    // Posts marcados como destaque (via admin)
    const highlightedPosts = computed(() =>
        posts.value.filter(p => p.featured)
    );

    const toggleHighlights = () => {
        showHighlights.value = !showHighlights.value;
        setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 50);
    };

    // Reactive stats computed from posts
    const stats = computed(() => {
        const counts = { reading: 0, read: 0, unread: 0 };
        posts.value.forEach(p => {
            if (p.status === 'reading') counts.reading++;
            else if (p.status === 'read') counts.read++;
            else counts.unread++;
        });
        return counts;
    });

    // Reactive filtered posts
    const filteredPosts = computed(() => {
        const searching = !!searchQuery.value;
        const query = searchQuery.value.toLowerCase();
        return posts.value.filter(post => {
            // Tab filter
            if (currentTab.value === 'queue') {
                if (post.status === 'read') return false;
            } else if (currentTab.value === 'read') {
                if (post.status !== 'read') return false;
            }

            // Search filter (a busca varre todos os posts, ignorando o corte de data)
            if (searching) {
                const titleMatch = post.title.toLowerCase().includes(query);
                const summaryMatch = post.summary && post.summary.toLowerCase().includes(query);
                return titleMatch || summaryMatch;
            }

            // Sem busca: a home mostra só os posts recentes
            if (post.published_at && new Date(post.published_at) < recentCutoff.value) {
                return false;
            }

            return true;
        });
    });

    // Existem posts antigos escondidos (fora do corte)? Então mostramos o link do arquivo.
    const hasArchive = computed(() =>
        !searchQuery.value && posts.value.some(
            p => p.published_at && new Date(p.published_at) < recentCutoff.value
        )
    );

    // Group posts by Year - Month
    const groupedPosts = computed(() => {
        const groups = {};
        filteredPosts.value.forEach(post => {
            if (!post.published_at) return;
            const date = new Date(post.published_at);
            const year = date.getFullYear();
            
            // Get capitalized month name in Portuguese
            const monthName = date.toLocaleDateString('pt-BR', { month: 'long' });
            const monthCapitalized = monthName.charAt(0).toUpperCase() + monthName.slice(1);
            
            const key = `${year} - ${monthCapitalized}`;
            
            if (!groups[key]) {
                groups[key] = {
                    key: key,
                    year: year,
                    posts: []
                };
            }
            groups[key].posts.push(post);
        });
        
        return Object.values(groups);
    });

    // Simple date formatter (pt-BR format)
    const formatDate = (dateStr) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return d.toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    };

    // Date formatter for specific days in the list
    const formatDateDay = (dateStr) => {
        if (!dateStr) return '';
        const d = new Date(dateStr);
        return `Dia ${d.getDate().toString().padStart(2, '0')}`;
    };

    // Watch tab change to update Lucide icons
    watch(currentTab, () => {
        setTimeout(() => { if (typeof lucide !== 'undefined') lucide.createIcons(); }, 50);
    });

    // Load initial data and trigger silent feed update on mount
    onMounted(async () => {
        await fetchPosts();
        syncFeed();
    });

    return {
        posts,
        loading,
        syncing,
        currentTab,
        searchQuery,
        stats,
        filteredPosts,
        groupedPosts,
        hasArchive,
        highlightedPosts,
        showHighlights,
        toggleHighlights,
        syncFeed,
        toggleReadStatus,
        formatDate,
        formatDateDay
    };
});
