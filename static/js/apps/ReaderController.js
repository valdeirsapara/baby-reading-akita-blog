registerController('ReaderController', (Vue) => {
    const { ref, onMounted, onUnmounted } = Vue;

    const postId = ref(null);
    const status = ref('unread');
    const scrollPercentage = ref(0.0);
    const showHeader = ref(true);
    
    let saveTimeout = null;
    let lastScrollTop = 0;
    let scrollDirection = null;
    let directionalDistance = 0;
    let isInitialMount = true;

    const HEADER_SHOW_DISTANCE = 8;
    const HEADER_HIDE_DISTANCE = 16;

    // Direct, immediate progress save
    const saveProgress = async (currentStatus, currentScroll) => {
        try {
            await api('/update-progress/', {
                method: 'POST',
                body: {
                    post_id: postId.value,
                    status: currentStatus,
                    scroll_position: currentScroll
                }
            });
        } catch (e) {
            console.error('Erro ao salvar progresso:', e);
        }
    };

    // Debounced version of saveProgress to avoid server spam
    const debouncedSaveProgress = (currentStatus, currentScroll) => {
        if (saveTimeout) clearTimeout(saveTimeout);
        saveTimeout = setTimeout(() => {
            saveProgress(currentStatus, currentScroll);
        }, 1500); // 1.5 second debounce
    };

    // Scroll listener callback
    const handleScroll = () => {
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        
        if (docHeight <= 0) return;
        
        let pct = (scrollTop / docHeight) * 100;
        pct = Math.max(0, Math.min(100, pct));
        scrollPercentage.value = pct;

        // Accumulate small mobile scroll events in the current direction. A single
        // touch gesture often emits deltas smaller than 5px, so checking only one
        // event can leave the header hidden until the reader reaches the top.
        const scrollDelta = scrollTop - lastScrollTop;
        const currentDirection = scrollDelta > 0 ? 'down' : scrollDelta < 0 ? 'up' : null;

        if (currentDirection) {
            if (currentDirection !== scrollDirection) {
                scrollDirection = currentDirection;
                directionalDistance = 0;
            }
            directionalDistance += Math.abs(scrollDelta);
        }

        if (!isInitialMount) {
            if (scrollTop <= 24) {
                showHeader.value = true;
                directionalDistance = 0;
            } else if (scrollDirection === 'up' && directionalDistance >= HEADER_SHOW_DISTANCE) {
                showHeader.value = true;
            } else if (
                scrollDirection === 'down' &&
                directionalDistance >= HEADER_HIDE_DISTANCE &&
                scrollTop > 72
            ) {
                showHeader.value = false;
            }
        }
        lastScrollTop = scrollTop;

        // Auto transition states:
        // 1. If scroll > 95%, auto-mark as read
        if (pct > 95 && status.value !== 'read') {
            status.value = 'read';
            saveProgress('read', pct);
        } 
        // 2. If scroll started (> 5%) and state is unread, transition to reading
        else if (pct > 5 && status.value === 'unread') {
            status.value = 'reading';
            saveProgress('reading', pct);
        } 
        // 3. Otherwise, if currently reading, debounce save scroll percentage
        else if (status.value === 'reading') {
            debouncedSaveProgress('reading', pct);
        }
    };

    // Force post as read
    const markAsRead = () => {
        status.value = 'read';
        scrollPercentage.value = 100;
        saveProgress('read', 100);
    };

    // Toggle between read / unread status
    const toggleReadStatus = () => {
        if (status.value === 'read') {
            status.value = 'unread';
            scrollPercentage.value = 0;
            // Scroll to top
            window.scrollTo({ top: 0, behavior: 'smooth' });
            saveProgress('unread', 0);
        } else {
            status.value = 'read';
            scrollPercentage.value = 100;
            saveProgress('read', 100);
        }
    };

    onMounted(() => {
        // Retrieve context data from hidden element
        const metaEl = document.getElementById('meta-context');
        if (metaEl) {
            postId.value = parseInt(metaEl.getAttribute('data-post-id'));
            status.value = metaEl.getAttribute('data-initial-status') || 'unread';
            const initialScroll = parseFloat(metaEl.getAttribute('data-initial-scroll') || '0.0');
            
            scrollPercentage.value = initialScroll;

            // Wait for rendering to settle before scrolling
            setTimeout(() => {
                const docHeight = document.documentElement.scrollHeight - window.innerHeight;
                if (docHeight > 0 && initialScroll > 0 && initialScroll < 95) {
                    const scrollTarget = (initialScroll / 100) * docHeight;
                    window.scrollTo({
                        top: scrollTarget,
                        behavior: 'instant'
                    });
                    lastScrollTop = scrollTarget;
                }
                
                // Allow scroll triggers after layout is settled
                setTimeout(() => {
                    isInitialMount = false;
                }, 100);
            }, 200);
        } else {
            isInitialMount = false;
        }

        // Attach scroll listener
        window.addEventListener('scroll', handleScroll);
    });

    onUnmounted(() => {
        // Clean up events and timeouts
        window.removeEventListener('scroll', handleScroll);
        if (saveTimeout) clearTimeout(saveTimeout);
    });

    return {
        status,
        scrollPercentage,
        showHeader,
        markAsRead,
        toggleReadStatus
    };
});
